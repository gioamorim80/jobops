"""On-demand score/tailor tests — auth gate + the pure readability extractor.

The full score→tailor happy path needs Supabase + Anthropic and is covered by
the manual end-to-end test in the M2 docs.
"""

import app.ondemand as ondemand
import pytest
from app.auth import get_current_user_id
from app.config import settings
from app.jobfetch import extract_main_text
from app.main import app
from app.ondemand import _applied_at_iso, _clean_label, _normalize_score
from fastapi import HTTPException
from fastapi.testclient import TestClient

client = TestClient(app)


def test_score_requires_auth() -> None:
    response = client.post("/ondemand/score", json={"text": "Some job posting"})
    assert response.status_code == 401


def test_tailor_requires_auth() -> None:
    response = client.post(
        "/ondemand/tailor",
        json={"id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


def test_approve_requires_auth() -> None:
    response = client.post(
        "/ondemand/approve",
        json={"id": "00000000-0000-0000-0000-000000000000", "tailored_bullets": []},
    )
    assert response.status_code == 401


def test_applied_requires_auth() -> None:
    response = client.post(
        "/ondemand/applied",
        json={"id": "00000000-0000-0000-0000-000000000000", "applied": True},
    )
    assert response.status_code == 401


def test_applied_at_iso_uses_chosen_day_at_noon_utc() -> None:
    # A user-chosen day is stored at noon UTC so it reads as the same calendar
    # date in any timezone.
    assert _applied_at_iso(True, "2026-06-20") == "2026-06-20T12:00:00+00:00"


def test_applied_at_iso_defaults_to_today_when_no_date() -> None:
    iso = _applied_at_iso(True, None)
    assert iso is not None and iso.endswith("T12:00:00+00:00")


def test_applied_at_iso_unmark_is_none() -> None:
    assert _applied_at_iso(False, "2026-06-20") is None


def test_applied_at_iso_rejects_bad_date() -> None:
    with pytest.raises(HTTPException) as exc:
        _applied_at_iso(True, "not-a-date")
    assert exc.value.status_code == 422


def test_clean_label_trims_collapses_and_caps() -> None:
    assert _clean_label("  Senior  Data\nScientist ") == "Senior Data Scientist"
    assert _clean_label(None) == ""  # nothing extracted -> empty, never fabricated
    assert _clean_label("") == ""
    assert len(_clean_label("x" * 500)) == 140  # capped


def test_normalize_score_preserves_valid_decision() -> None:
    # decision is the model's holistic call, carried through verbatim (not derived
    # from the fit number).
    assert _normalize_score({"fit": 72, "decision": "apply"})["decision"] == "APPLY"
    assert _normalize_score({"fit": 72, "decision": "STRETCH"})["decision"] == "STRETCH"


def test_normalize_score_invalid_decision_defaults_and_logs(caplog) -> None:
    # A missing/garbled decision falls back to STRETCH but is surfaced (logged),
    # never silently swallowed.
    with caplog.at_level("WARNING"):
        result = _normalize_score({"fit": 72, "decision": "MAYBE"})
    assert result["decision"] == "STRETCH"
    assert any("invalid decision" in r.message for r in caplog.records)


def test_extract_main_text_pulls_article_body() -> None:
    html = """
    <html><head><title>Senior Engineer</title></head>
    <body>
      <nav>home about careers</nav>
      <article>
        <h1>Senior Backend Engineer</h1>
        <p>We are hiring a senior backend engineer to build scalable payment
        systems in Python and FastAPI. You will own services end to end and
        mentor other engineers across the platform team.</p>
      </article>
      <footer>copyright</footer>
    </body></html>
    """
    text = extract_main_text(html)
    assert "senior backend engineer" in text.lower()
    assert "FastAPI" in text


def test_extract_main_text_handles_empty_html() -> None:
    assert extract_main_text("") == ""


# ===================== scorer-v2: scorable + seniority cap =====================
def test_normalize_score_scorable_defaults_true_when_absent() -> None:
    # MISSING scorable must default True — never silently reject a real posting.
    assert _normalize_score({"fit": 70, "decision": "APPLY"})["scorable"] is True


def test_normalize_score_scorable_false_passthrough() -> None:
    out = _normalize_score({"fit": 0, "decision": "SKIP", "scorable": False})
    assert out["scorable"] is False


def test_normalize_score_posting_seniority_normalized() -> None:
    assert (
        _normalize_score({"fit": 1, "decision": "SKIP", "posting_seniority": "VP"})[
            "posting_seniority"
        ]
        == "vp"
    )
    assert _normalize_score({"fit": 1, "decision": "SKIP"})["posting_seniority"] == ""


def test_cap_fires_on_clear_mismatch() -> None:
    # >=2 levels above target -> APPLY capped to STRETCH.
    assert (
        _normalize_score({"fit": 80, "decision": "APPLY", "posting_seniority": "vp"}, "senior")[
            "decision"
        ]
        == "STRETCH"
    )
    # director (5) vs senior (3) = exactly 2 levels -> fires.
    assert (
        _normalize_score({"fit": 80, "decision": "APPLY", "posting_seniority": "director"}, "mid")[
            "decision"
        ]
        == "STRETCH"
    )


def test_cap_does_not_fire_at_one_level_gap() -> None:
    # principal (4) vs senior (3) = 1 level -> decision left as the model emitted.
    assert (
        _normalize_score(
            {"fit": 80, "decision": "APPLY", "posting_seniority": "principal"}, "senior"
        )["decision"]
        == "APPLY"
    )


def test_cap_no_op_when_unmappable_or_unparseable() -> None:
    # posting_seniority empty -> no cap
    assert (
        _normalize_score({"fit": 80, "decision": "APPLY", "posting_seniority": ""}, "senior")[
            "decision"
        ]
        == "APPLY"
    )
    # posting_seniority not in the map -> no cap
    assert (
        _normalize_score({"fit": 80, "decision": "APPLY", "posting_seniority": "wizard"}, "senior")[
            "decision"
        ]
        == "APPLY"
    )
    # target free text has no recognizable level -> no cap
    assert (
        _normalize_score({"fit": 80, "decision": "APPLY", "posting_seniority": "vp"}, "rockstar")[
            "decision"
        ]
        == "APPLY"
    )


def test_cap_does_not_touch_non_apply_or_matching_level() -> None:
    # senior posting for a senior target is APPLY-eligible (not capped).
    assert (
        _normalize_score({"fit": 85, "decision": "APPLY", "posting_seniority": "senior"}, "senior")[
            "decision"
        ]
        == "APPLY"
    )
    # only APPLY is capped; STRETCH stays STRETCH even on a big mismatch.
    assert (
        _normalize_score({"fit": 40, "decision": "STRETCH", "posting_seniority": "vp"}, "senior")[
            "decision"
        ]
        == "STRETCH"
    )


def test_target_seniority_takes_highest_level() -> None:
    # "senior, mid-level" -> highest is senior (3); vp (6) gap 3 -> caps.
    assert (
        _normalize_score(
            {"fit": 80, "decision": "APPLY", "posting_seniority": "vp"}, "senior, mid-level"
        )["decision"]
        == "STRETCH"
    )


# ----- score_job endpoint: non-posting is not saved (Bug 1) -----
class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Records writes; returns a completed profile and an empty cache lookup."""

    def __init__(self, store: dict):
        self.store = store
        self.table_name = ""
        self.op = "select"

    def table(self, name: str):
        self.table_name = name
        self.op = "select"
        return self

    def select(self, *a, **k):
        self.op = "select"
        return self

    def insert(self, row, **k):
        self.op = "insert"
        self.store["writes"].append((self.table_name, "insert", row))
        return self

    def update(self, row, **k):
        self.op = "update"
        self.store["writes"].append((self.table_name, "update", row))
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        if self.op == "select" and self.table_name == "profiles":
            return _Resp([{"parsed": self.store["parsed"], "onboarding_complete": True}])
        if self.op == "select" and self.table_name == "tailorings":
            return _Resp([])  # no cache hit
        if self.op == "insert":
            return _Resp([{"id": "new-id"}])
        return _Resp([])


def _wire_score_job(monkeypatch, store, raw):
    monkeypatch.setattr(ondemand, "get_service_client", lambda: _FakeQuery(store))
    monkeypatch.setattr(ondemand, "run_json_agent", lambda *a, **k: (raw, object()))
    monkeypatch.setattr(ondemand, "log_call", lambda *a, **k: None)
    monkeypatch.setattr(ondemand, "count_calls_today", lambda *a, **k: 0)
    monkeypatch.setattr(ondemand, "count_calls_this_month", lambda *a, **k: 0)
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"


def test_score_job_non_posting_not_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    raw = {"fit": 0, "decision": "SKIP", "scorable": False, "cleared": [], "gaps": []}
    _wire_score_job(monkeypatch, store, raw)
    try:
        resp = client.post(
            "/ondemand/score", json={"text": "Cookie consent. Privacy policy. Menu."}
        )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert resp.status_code == 200
    assert resp.json()["status"] == "unreadable"  # reuses the fetch-failure notice shape
    assert not any(t == "tailorings" for (t, _op, _r) in store["writes"])  # nothing saved


def test_score_job_real_posting_is_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    raw = {
        "fit": 78,
        "decision": "APPLY",
        "scorable": True,
        "role": "Data Scientist",
        "company": "Acme",
        "posting_seniority": "senior",
        "cleared": ["Python"],
        "gaps": [],
        "referral_angle": "",
        "pitch": "p",
    }
    _wire_score_job(monkeypatch, store, raw)
    try:
        resp = client.post("/ondemand/score", json={"text": "Real posting with requirements."})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert resp.json()["status"] == "ok"
    assert any(t == "tailorings" and op == "insert" for (t, op, _r) in store["writes"])


# ===================== per-user monthly caps (score path) =====================
_REAL_POSTING_RAW = {
    "fit": 78,
    "decision": "APPLY",
    "scorable": True,
    "role": "Data Scientist",
    "company": "Acme",
    "posting_seniority": "senior",
    "cleared": ["Python"],
    "gaps": [],
    "referral_angle": "",
    "pitch": "p",
}


def test_score_blocked_at_monthly_score_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    # At/over the monthly SCORE cap: no LLM call, no save, a score-specific message
    # that names the limit and the reset.
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_score_job(monkeypatch, store, _REAL_POSTING_RAW)
    monkeypatch.setattr(
        ondemand, "count_calls_this_month", lambda c, u, action: 999 if action == "score" else 0
    )
    try:
        resp = client.post("/ondemand/score", json={"text": "Real posting with requirements."})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    body = resp.json()
    assert body["status"] == "limit_reached"
    assert "scored jobs" in body["message"] and "month" in body["message"]
    assert not any(t == "tailorings" for (t, _op, _r) in store["writes"])  # nothing scored/saved


def test_score_proceeds_under_monthly_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    # Under the cap (count returns 0 via the wire helper) the score runs and saves.
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_score_job(monkeypatch, store, _REAL_POSTING_RAW)
    try:
        resp = client.post("/ondemand/score", json={"text": "Real posting with requirements."})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert resp.json()["status"] == "ok"
    assert any(t == "tailorings" and op == "insert" for (t, op, _r) in store["writes"])


def test_score_blocked_by_daily_cap_regardless_of_monthly(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both checks are present. The daily brake is checked first, so a daily-capped
    # user is blocked with the DAILY message even when the monthly count is free.
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_score_job(monkeypatch, store, _REAL_POSTING_RAW)
    monkeypatch.setattr(ondemand, "count_calls_today", lambda *a, **k: 999)  # daily maxed
    monkeypatch.setattr(ondemand, "count_calls_this_month", lambda *a, **k: 0)  # monthly free
    try:
        resp = client.post("/ondemand/score", json={"text": "Real posting with requirements."})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    body = resp.json()
    assert body["status"] == "limit_reached"
    assert "today's limit" in body["message"]  # daily message, not the monthly one
    assert not any(t == "tailorings" for (t, _op, _r) in store["writes"])


# ===================== per-user monthly caps (tailor path) ====================
class _TailorQuery:
    """Returns a not-yet-tailored row for the tailorings select and a completed
    profile for the profiles select; records writes (the final tailor update)."""

    def __init__(self, store: dict):
        self.store = store
        self.table_name = ""
        self.op = "select"

    def table(self, name: str):
        self.table_name = name
        self.op = "select"
        return self

    def select(self, *a, **k):
        self.op = "select"
        return self

    def update(self, row, **k):
        self.op = "update"
        self.store["writes"].append((self.table_name, "update", row))
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        if self.op == "select" and self.table_name == "tailorings":
            return _Resp(
                [
                    {
                        "id": "t1",
                        "job_text": "Real job posting text.",
                        "score": {"fit": 70, "decision": "APPLY"},
                        "tailored_bullets": [],  # not yet tailored -> proceeds to LLM
                        "analysis": "",
                        "approved": False,
                    }
                ]
            )
        if self.op == "select" and self.table_name == "profiles":
            return _Resp(
                [
                    {
                        "parsed": self.store["parsed"],
                        "raw_resume_text": "resume text",
                        "onboarding_complete": True,
                    }
                ]
            )
        return _Resp([])


def _wire_tailor(monkeypatch, store):
    monkeypatch.setattr(ondemand, "get_service_client", lambda: _TailorQuery(store))
    monkeypatch.setattr(
        ondemand,
        "run_json_agent",
        lambda *a, **k: (
            {
                "tailored_bullets": [{"original": "a", "tailored": "b", "why": "c", "where": "d"}],
                "analysis": "x",
                "flags": [],
            },
            object(),
        ),
    )
    monkeypatch.setattr(ondemand, "log_call", lambda *a, **k: None)
    monkeypatch.setattr(ondemand, "count_calls_today", lambda *a, **k: 0)
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"


def test_tailor_blocked_at_monthly_tailor_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_tailor(monkeypatch, store)
    monkeypatch.setattr(
        ondemand, "count_calls_this_month", lambda c, u, action: 999 if action == "tailor" else 0
    )
    try:
        resp = client.post("/ondemand/tailor", json={"id": "t1"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    body = resp.json()
    assert body["status"] == "limit_reached"
    assert "resume tailors" in body["message"] and "month" in body["message"]
    assert not any(op == "update" for (_t, op, _r) in store["writes"])  # no LLM call, no save


def test_tailor_works_when_score_cap_is_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    # Separate caps: a user who has exhausted the SCORE cap can still tailor.
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_tailor(monkeypatch, store)
    monkeypatch.setattr(
        ondemand, "count_calls_this_month", lambda c, u, action: 999 if action == "score" else 0
    )
    try:
        resp = client.post("/ondemand/tailor", json={"id": "t1"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert resp.json()["status"] == "ok"
    assert any(t == "tailorings" and op == "update" for (t, op, _r) in store["writes"])


# ===================== cap-exemption (per-user bypass, budget still applies) ====
def test_exempt_user_bypasses_score_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    # Over BOTH per-user caps, but exempt + under global budget -> scores anyway.
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_score_job(monkeypatch, store, _REAL_POSTING_RAW)
    monkeypatch.setattr(ondemand, "count_calls_today", lambda *a, **k: 999)
    monkeypatch.setattr(ondemand, "count_calls_this_month", lambda *a, **k: 999)
    monkeypatch.setattr(settings, "cap_exempt_user_ids", "user-1")
    monkeypatch.setattr(ondemand, "is_over_monthly_budget", lambda c: False)
    try:
        resp = client.post("/ondemand/score", json={"text": "Real posting with requirements."})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert resp.json()["status"] == "ok"
    assert any(t == "tailorings" and op == "insert" for (t, op, _r) in store["writes"])


def test_exempt_user_still_blocked_by_global_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    # THE critical one: exempt bypasses per-user caps but NOT the global ceiling.
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_score_job(monkeypatch, store, _REAL_POSTING_RAW)
    monkeypatch.setattr(ondemand, "count_calls_today", lambda *a, **k: 0)  # under per-user
    monkeypatch.setattr(ondemand, "count_calls_this_month", lambda *a, **k: 0)
    monkeypatch.setattr(settings, "cap_exempt_user_ids", "user-1")
    monkeypatch.setattr(ondemand, "is_over_monthly_budget", lambda c: True)  # over budget
    try:
        resp = client.post("/ondemand/score", json={"text": "Real posting with requirements."})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    body = resp.json()
    assert body["status"] == "limit_reached"
    assert "budget" in body["message"].lower()  # the global-budget message, not a per-user cap
    assert not any(t == "tailorings" for (t, _op, _r) in store["writes"])  # nothing scored/saved


def test_empty_exemption_means_caps_still_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default-safe: empty allowlist -> the caller is not exempt -> per-user cap blocks.
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_score_job(monkeypatch, store, _REAL_POSTING_RAW)
    monkeypatch.setattr(settings, "cap_exempt_user_ids", "")
    monkeypatch.setattr(
        ondemand, "count_calls_this_month", lambda c, u, action: 999 if action == "score" else 0
    )
    try:
        resp = client.post("/ondemand/score", json={"text": "Real posting."})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    body = resp.json()
    assert body["status"] == "limit_reached"
    assert "scored jobs" in body["message"]  # per-user cap message (not the budget one)


def test_usage_logged_for_exempt_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # Exemption skips the cap BLOCK, not the logging — exempt spend still counts.
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_score_job(monkeypatch, store, _REAL_POSTING_RAW)
    monkeypatch.setattr(settings, "cap_exempt_user_ids", "user-1")
    monkeypatch.setattr(ondemand, "is_over_monthly_budget", lambda c: False)
    logged: list[str] = []
    monkeypatch.setattr(
        ondemand, "log_call", lambda client_, uid, action, usage, **k: logged.append(action)
    )
    try:
        resp = client.post("/ondemand/score", json={"text": "Real posting."})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert resp.json()["status"] == "ok"
    assert "score" in logged  # the exempt call was still logged


def test_exempt_user_bypasses_tailor_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_tailor(monkeypatch, store)
    monkeypatch.setattr(ondemand, "count_calls_today", lambda *a, **k: 999)
    monkeypatch.setattr(ondemand, "count_calls_this_month", lambda *a, **k: 999)
    monkeypatch.setattr(settings, "cap_exempt_user_ids", "user-1")
    monkeypatch.setattr(ondemand, "is_over_monthly_budget", lambda c: False)
    try:
        resp = client.post("/ondemand/tailor", json={"id": "t1"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert resp.json()["status"] == "ok"
    assert any(t == "tailorings" and op == "update" for (t, op, _r) in store["writes"])


def test_exempt_tailor_still_blocked_by_global_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {"parsed": {"seniority": "senior"}, "writes": []}
    _wire_tailor(monkeypatch, store)
    monkeypatch.setattr(settings, "cap_exempt_user_ids", "user-1")
    monkeypatch.setattr(ondemand, "is_over_monthly_budget", lambda c: True)
    try:
        resp = client.post("/ondemand/tailor", json={"id": "t1"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    body = resp.json()
    assert body["status"] == "limit_reached"
    assert "budget" in body["message"].lower()
    assert not any(op == "update" for (_t, op, _r) in store["writes"])  # no tailor/save
