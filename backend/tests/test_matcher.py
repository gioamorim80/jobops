"""Matcher tests — band thresholds + Haiku model choice + scorable skip (no net)."""

import app.matcher as matcher
import pytest
from app.matcher import MATCH_MODEL, score_band, score_shortlist


def test_score_band_thresholds_match_frontend() -> None:
    # Mirrors lib/ui.ts fitBand so automated matches read like on-demand scores.
    assert score_band(80) == "Strong fit"
    assert score_band(90) == "Strong fit"
    assert score_band(65) == "Solid fit"
    assert score_band(79) == "Solid fit"
    # 50–64 band is "Moderate fit", NOT "Stretch" — that word is reserved for the
    # separate STRETCH decision label (avoids the vocabulary collision).
    assert score_band(50) == "Moderate fit"
    assert score_band(64) == "Moderate fit"
    assert "Stretch" not in {score_band(s) for s in range(0, 101)}
    assert score_band(49) == "Likely skip"
    assert score_band(0) == "Likely skip"


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
