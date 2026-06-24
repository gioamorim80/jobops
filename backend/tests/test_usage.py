"""Counting guardrail tests for the daily + monthly caps and the (inert) budget.

These prove the caps count exactly the right rows: scoped to one user, to the right
window (today / this calendar month), and (when an action is given) to only that
action — so a Coach turn is counted once and is never inflated by the conversation
history or by other features' calls. The query is recorded via a fake client so no
network/DB is needed.
"""

import inspect
from datetime import datetime

import app.matcher as matcher
import app.ondemand as ondemand
import app.usage as usage
from app.usage import (
    _month_start_iso,
    count_calls_this_month,
    count_calls_today,
    is_over_monthly_budget,
    total_cost_this_month,
)


class _FakeResult:
    def __init__(self, count: int) -> None:
        self.count = count


class _FakeQuery:
    def __init__(self, calls: dict) -> None:
        self.calls = calls

    def select(self, *args: object, **kwargs: object) -> "_FakeQuery":
        self.calls["select"] = {"args": args, "kwargs": kwargs}
        return self

    def eq(self, column: str, value: object) -> "_FakeQuery":
        self.calls["eq"].append((column, value))
        return self

    def gte(self, column: str, value: object) -> "_FakeQuery":
        self.calls["gte"] = (column, value)
        return self

    def execute(self) -> _FakeResult:
        return _FakeResult(self.calls["count"])


class _FakeClient:
    def __init__(self, calls: dict) -> None:
        self.calls = calls

    def table(self, name: str) -> _FakeQuery:
        self.calls["table"] = name
        return _FakeQuery(self.calls)


def test_count_filters_by_user_today_and_action() -> None:
    calls: dict = {"eq": [], "count": 5}
    result = count_calls_today(_FakeClient(calls), "user-123", action="enrich")

    assert result == 5  # returns the exact count, not a per-message tally
    assert calls["table"] == "usage_log"
    assert calls["select"]["kwargs"].get("count") == "exact"
    assert ("user_id", "user-123") in calls["eq"]  # per-user isolation
    assert ("action", "enrich") in calls["eq"]  # only enrich turns counted
    assert calls["gte"][0] == "created_at"  # since 00:00 UTC today (daily reset)


def test_count_without_action_has_no_action_filter() -> None:
    calls: dict = {"eq": [], "count": 0}
    count_calls_today(_FakeClient(calls), "user-123")
    assert all(column != "action" for column, _ in calls["eq"])


# ============================ per-user monthly cap ============================
def test_count_this_month_filters_user_action_and_month_window() -> None:
    calls: dict = {"eq": [], "count": 7}
    result = count_calls_this_month(_FakeClient(calls), "user-123", "score")

    assert result == 7
    assert calls["table"] == "usage_log"
    assert ("user_id", "user-123") in calls["eq"]  # per-user isolation
    assert ("action", "score") in calls["eq"]  # per-action: score and tailor separate
    assert calls["gte"][0] == "created_at"  # windowed by created_at


def test_count_this_month_window_is_first_of_month_midnight_utc() -> None:
    # Month boundary: the window starts at the 1st at 00:00 UTC, so a usage_log row
    # dated last month falls before it and never counts toward this month's cap.
    calls: dict = {"eq": [], "count": 0}
    count_calls_this_month(_FakeClient(calls), "user-123", "tailor")
    boundary = calls["gte"][1]
    assert boundary == _month_start_iso()
    parsed = datetime.fromisoformat(boundary)
    assert (parsed.day, parsed.hour, parsed.minute, parsed.second) == (1, 0, 0, 0)


# ===================== global monthly budget (built, inert) ===================
class _SumResult:
    def __init__(self, data: list) -> None:
        self.data = data


class _SumQuery:
    def __init__(self, rows: list, calls: dict) -> None:
        self.rows = rows
        self.calls = calls

    def select(self, *args: object, **kwargs: object) -> "_SumQuery":
        self.calls["select"] = args
        return self

    def gte(self, column: str, value: object) -> "_SumQuery":
        self.calls["gte"] = (column, value)
        return self

    def execute(self) -> _SumResult:
        return _SumResult(self.rows)


class _SumClient:
    def __init__(self, rows: list, calls: dict) -> None:
        self.rows = rows
        self.calls = calls

    def table(self, name: str) -> _SumQuery:
        self.calls["table"] = name
        return _SumQuery(self.rows, self.calls)


def test_total_cost_sums_all_users_for_the_month() -> None:
    rows = [{"cost_estimate": 1.5}, {"cost_estimate": 2.25}, {"cost_estimate": None}]
    calls: dict = {}
    total = total_cost_this_month(_SumClient(rows, calls))

    assert total == 3.75  # None is treated as 0, not an error
    assert calls["table"] == "usage_log"
    assert calls["gte"][0] == "created_at"  # same calendar-month window as the caps


def test_is_over_monthly_budget_true_when_over(monkeypatch) -> None:
    monkeypatch.setattr(usage.settings, "monthly_budget_ceiling_usd", 10.0)
    rows = [{"cost_estimate": 6.0}, {"cost_estimate": 6.0}]  # sum 12 > 10
    assert is_over_monthly_budget(_SumClient(rows, {})) is True


def test_is_over_monthly_budget_false_when_under(monkeypatch) -> None:
    monkeypatch.setattr(usage.settings, "monthly_budget_ceiling_usd", 10.0)
    rows = [{"cost_estimate": 4.0}, {"cost_estimate": 4.0}]  # sum 8 <= 10
    assert is_over_monthly_budget(_SumClient(rows, {})) is False


def test_budget_ceiling_is_built_but_not_wired_to_block() -> None:
    # Inert by design: no request path references it yet. It is the kill-switch for
    # the future digest scanner, to be wired in a later M5 step.
    assert "is_over_monthly_budget" not in inspect.getsource(ondemand)
    assert "is_over_monthly_budget" not in inspect.getsource(matcher)
