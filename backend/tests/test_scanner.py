"""Scanner tests — scan_user (skip/fetch-then-score) and scan_all_opted_in (loop +
per-user failure isolation). No network: the fetch/score cores are monkeypatched and
the fake clients answer only the queries each function makes.
"""

import app.scanner as scanner_mod
from app.scanner import scan_all_opted_in, scan_user


class _Resp:
    def __init__(self, data: list) -> None:
        self.data = data


# ------------------------------- scan_all_opted_in -----------------------------
class _OptedInClient:
    """Answers only preferences.select('user_id').eq('email_opt_in', True)."""

    def __init__(self, user_ids: list[str]) -> None:
        self._rows = [{"user_id": u} for u in user_ids]

    def table(self, name: str):
        assert name == "preferences"
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self) -> _Resp:
        return _Resp(self._rows)


def test_scan_all_runs_each_opted_in_user(monkeypatch) -> None:
    seen: list[str] = []

    def fake_scan_user(client, uid):
        seen.append(uid)
        return {"user": uid[:8], "status": "ok", "scored": 2}

    monkeypatch.setattr(scanner_mod, "scan_user", fake_scan_user)
    results = scan_all_opted_in(_OptedInClient(["u1", "u2", "u3"]))

    assert seen == ["u1", "u2", "u3"]  # one call per opted-in user
    assert len(results) == 3 and all(r["status"] == "ok" for r in results)


def test_scan_all_isolates_one_user_failure(monkeypatch) -> None:
    def fake_scan_user(client, uid):
        if uid == "bad":
            raise RuntimeError("boom")
        return {"user": uid[:8], "status": "ok", "scored": 1}

    monkeypatch.setattr(scanner_mod, "scan_user", fake_scan_user)
    results = scan_all_opted_in(_OptedInClient(["u1", "bad", "u2"]))

    # The failure is captured as an error entry; the other users still scan.
    assert [r["status"] for r in results] == ["ok", "error", "ok"]
    assert "boom" in results[1]["error"]
    assert sum(1 for r in results if r["status"] == "ok") == 2


def test_scan_all_empty_when_none_opted_in(monkeypatch) -> None:
    monkeypatch.setattr(scanner_mod, "scan_user", lambda *a, **k: {"status": "ok"})
    assert scan_all_opted_in(_OptedInClient([])) == []


# ----------------------------------- scan_user ---------------------------------
class _ProfileClient:
    """Answers only profiles.select('parsed').eq(...).limit(1) for load_parsed."""

    def __init__(self, parsed: dict | None) -> None:
        self._parsed = parsed

    def table(self, name: str):
        assert name == "profiles"
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self) -> _Resp:
        return _Resp([{"parsed": self._parsed}] if self._parsed is not None else [])


def test_scan_user_skips_when_no_target_roles(monkeypatch) -> None:
    def _boom(*a, **k):
        raise AssertionError("must not fetch/score a user with no target roles")

    monkeypatch.setattr(scanner_mod, "fetch_into_pool", _boom)
    monkeypatch.setattr(scanner_mod, "score_from_pool", _boom)

    result = scan_user(_ProfileClient({"target_roles": []}), "u1")
    assert result == {"user": "u1", "status": "skipped_no_roles"}


def test_scan_user_fetches_then_scores(monkeypatch) -> None:
    order: list[str] = []

    def fake_fetch(client, parsed, max_days_old, max_pages):
        order.append("fetch")
        return {
            "all_jobs": [],
            "sources_run": ["adzuna"],
            "sources_failed": [],
            "raw_count": 5,
            "parse_failures": 0,
            "stored": 3,
        }

    def fake_score(client, user_id, parsed, candidate_limit):
        order.append("score")
        return {
            "candidates": 10,
            "shortlist_count": 4,
            "already_scored": 1,
            "scored": 3,
            "failed": 0,
            "unscorable": 0,
            "skipped_for_cap": 0,
            "model": "claude-haiku-4-5",
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }

    monkeypatch.setattr(scanner_mod, "fetch_into_pool", fake_fetch)
    monkeypatch.setattr(scanner_mod, "score_from_pool", fake_score)

    result = scan_user(_ProfileClient({"target_roles": ["Engineer"]}), "user-1234")

    assert order == ["fetch", "score"]  # fetch BEFORE score (fresh jobs then scored)
    assert result["status"] == "ok"
    assert result["stored"] == 3
    assert result["candidates"] == 10
    assert result["scored"] == 3
    assert result["user"] == "user-123"  # user_id[:8]
