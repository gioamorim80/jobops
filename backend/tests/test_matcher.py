"""Matcher tests — band thresholds + Haiku model choice + scorable skip (no net)."""

import app.matcher as matcher
import pytest
from app.matcher import MATCH_MODEL, score_band, score_shortlist


def test_score_band_thresholds_match_frontend() -> None:
    # Mirrors lib/ui.ts fitBand so automated matches read like on-demand scores.
    # Calibrated cutoffs: Strong >=74, Solid 62-73, Moderate 48-61, Likely skip <48.
    # Boundary values (74/73, 62/61, 48/47) pin the exact cutoffs.
    assert score_band(78) == "Strong fit"  # the all-time max now reads "Strong fit"
    assert score_band(74) == "Strong fit"  # lower edge of Strong
    assert score_band(73) == "Solid fit"  # just below Strong
    assert score_band(72) == "Solid fit"  # the common cluster
    assert score_band(62) == "Solid fit"  # lower edge of Solid
    assert score_band(61) == "Moderate fit"  # just below Solid
    assert score_band(48) == "Moderate fit"  # lower edge of Moderate
    assert score_band(47) == "Likely skip"  # just below Moderate
    assert score_band(0) == "Likely skip"
    # The band never uses "Stretch" — that word is reserved for the separate
    # STRETCH decision label (avoids the vocabulary collision).
    assert "Stretch" not in {score_band(s) for s in range(0, 101)}


def test_matcher_uses_haiku_not_sonnet() -> None:
    # Automated scoring is the cheap step; Sonnet stays reserved for tailoring.
    assert MATCH_MODEL == "claude-haiku-4-5"


class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Records matches writes; reports no already-scored rows."""

    def __init__(self, store):
        self.store = store
        self.op = "select"

    def table(self, name):
        self.op = "select"
        return self

    def select(self, *a, **k):
        self.op = "select"
        return self

    def upsert(self, row, **k):
        self.store["upserts"].append(row)
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def execute(self):
        return _Resp([])  # nothing already scored


def test_score_shortlist_skips_non_posting(monkeypatch: pytest.MonkeyPatch) -> None:
    # A candidate that comes back scorable=False is NOT persisted (no 0 row).
    store = {"upserts": []}
    raw = {"fit": 0, "decision": "SKIP", "scorable": False, "cleared": [], "gaps": []}
    monkeypatch.setattr(matcher, "run_cached_json_agent", lambda *a, **k: (raw, object()))
    monkeypatch.setattr(matcher, "log_call", lambda *a, **k: None)
    monkeypatch.setattr(matcher, "count_calls_today", lambda *a, **k: 0)

    summary = score_shortlist(
        _FakeQuery(store),
        "user-1",
        {"seniority": "senior"},
        [{"id": "job-1", "description": "nav / cookie boilerplate", "posted_at": None}],
    )
    assert store["upserts"] == []  # nothing written
    assert summary["scored"] == 0
    assert summary["unscorable"] == 1


def _real(idx: int) -> dict:
    return {"id": f"job-{idx}", "description": f"Real posting {idx}", "posted_at": None}


def test_score_shortlist_exempt_user_bypasses_daily_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    # count_calls_today is way over the cap, which would leave a normal user 0 budget;
    # an exempt user scores the whole shortlist anyway. Global budget is enforced by
    # the scanner loop, not here.
    store = {"upserts": []}
    raw = {
        "fit": 80,
        "decision": "APPLY",
        "scorable": True,
        "cleared": [],
        "gaps": [],
        "pitch": "p",
    }
    monkeypatch.setattr(matcher, "run_cached_json_agent", lambda *a, **k: (raw, object()))
    monkeypatch.setattr(matcher, "log_call", lambda *a, **k: None)
    monkeypatch.setattr(matcher, "count_calls_today", lambda *a, **k: 999)
    monkeypatch.setattr(matcher, "is_cap_exempt", lambda uid: True)

    summary = score_shortlist(
        _FakeQuery(store), "user-1", {"seniority": "senior"}, [_real(1), _real(2)]
    )
    assert summary["scored"] == 2  # both scored despite the over-cap count
    assert summary["skipped_for_cap"] == 0
    assert len(store["upserts"]) == 2


def test_score_shortlist_non_exempt_respects_daily_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: a non-exempt user over the daily cap scores nothing (unchanged).
    store = {"upserts": []}
    raw = {
        "fit": 80,
        "decision": "APPLY",
        "scorable": True,
        "cleared": [],
        "gaps": [],
        "pitch": "p",
    }
    monkeypatch.setattr(matcher, "run_cached_json_agent", lambda *a, **k: (raw, object()))
    monkeypatch.setattr(matcher, "log_call", lambda *a, **k: None)
    monkeypatch.setattr(matcher, "count_calls_today", lambda *a, **k: 999)
    monkeypatch.setattr(matcher, "is_cap_exempt", lambda uid: False)

    summary = score_shortlist(
        _FakeQuery(store), "user-1", {"seniority": "senior"}, [_real(1), _real(2)]
    )
    assert summary["scored"] == 0
    assert summary["skipped_for_cap"] == 2
    assert store["upserts"] == []
