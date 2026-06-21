"""Counting guardrail tests for the daily cap.

These prove the cap counts exactly the right rows: scoped to one user, to today,
and (when an action is given) to only that action — so a Coach turn is counted
once and is never inflated by the conversation history or by other features'
calls. The query is recorded via a fake client so no network/DB is needed.
"""

from app.usage import count_calls_today


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
