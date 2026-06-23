"""Onboarding endpoint auth tests + the profile-edit field-scoped merge.

The full happy path needs Supabase + Anthropic and is covered by the manual
two-account isolation test in the M1 docs. Here we assert the auth gate and the
merge contract that protects coach-written attribution_notes from being wiped.
"""

import app.onboarding as onboarding
from app.auth import get_current_user_id
from app.main import app
from app.onboarding import merge_profile_edit
from fastapi.testclient import TestClient

client = TestClient(app)


class _FakeTable:
    """Minimal Supabase query-builder stand-in. Records upserts; returns a preset
    `parsed` row on select so the endpoint's read-modify-write can be exercised."""

    def __init__(self, store: dict):
        self._store = store
        self._table = ""
        self._is_select = False

    def table(self, name: str):
        self._table = name
        return self

    def select(self, *_a, **_k):
        self._is_select = True
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def upsert(self, row: dict, **_k):
        self._store["upserts"].append({"table": self._table, "row": row})
        self._pending = None
        return self

    def execute(self):
        if self._is_select and self._table == "profiles":
            self._is_select = False
            return type("R", (), {"data": [{"parsed": self._store["current_parsed"]}]})()
        self._is_select = False
        return type("R", (), {"data": []})()


def test_parse_requires_auth() -> None:
    response = client.post("/onboarding/parse", json={"resume_path": "uid/resume.pdf"})
    assert response.status_code == 401


def test_complete_requires_auth() -> None:
    response = client.post(
        "/onboarding/complete",
        json={
            "full_name": "x",
            "email": "x@example.com",
            "parsed": {},
            "preferences": {"alert_frequency": "weekly", "score_threshold": 60},
        },
    )
    assert response.status_code == 401


def test_profile_update_requires_auth() -> None:
    response = client.post(
        "/onboarding/profile",
        json={
            "full_name": "x",
            "email": "x@example.com",
            "parsed": {},
            "preferences": {"alert_frequency": "weekly", "score_threshold": 60},
        },
    )
    assert response.status_code == 401


def test_parse_malformed_auth_header() -> None:
    response = client.post(
        "/onboarding/parse",
        json={"resume_path": "uid/resume.pdf"},
        headers={"Authorization": "Token abc"},
    )
    assert response.status_code == 401


# --------------------- field-scoped merge (pure contract) ---------------------
def test_merge_preserves_attribution_notes_and_replaces_form_fields() -> None:
    current = {
        "skills": ["Python"],
        "attribution_notes": ["Led rollout; architecture was a teammate's."],
        "comp_floor": "180k",
    }
    submitted = {"skills": ["Python", "SQL"], "attribution_notes": [], "comp_floor": ""}
    merged = merge_profile_edit(current, submitted)
    # form-owned field replaced wholesale...
    assert merged["skills"] == ["Python", "SQL"]
    # ...but coach-written / client-immutable fields preserved from the DB row,
    # NOT taken from the (here, emptied) request body.
    assert merged["attribution_notes"] == ["Led rollout; architecture was a teammate's."]
    assert merged["comp_floor"] == "180k"


def test_merge_replaces_with_deletion() -> None:
    current = {"skills": ["Python", "SQL", "Go"]}
    merged = merge_profile_edit(current, {"skills": ["Python", "SQL"]})
    assert merged["skills"] == ["Python", "SQL"]  # removed skill is gone (wholesale replace)


# --------------------- endpoint: read-modify-write wiring ---------------------
def test_profile_update_endpoint_preserves_attribution_notes(monkeypatch) -> None:
    """End-to-end through the endpoint: a save that edits skills and omits
    attribution_notes must NOT wipe the coach-written notes already on the row,
    and must not let the body set them."""
    store = {
        "current_parsed": {
            "skills": ["Python"],
            "attribution_notes": ["true note from the coach"],
            "comp_floor": "200k",
        },
        "upserts": [],
    }
    monkeypatch.setattr(onboarding, "get_service_client", lambda: _FakeTable(store))
    app.dependency_overrides[get_current_user_id] = lambda: "user-123"
    try:
        resp = client.post(
            "/onboarding/profile",
            json={
                "full_name": "Gio",
                "email": "gio@example.com",
                "parsed": {
                    "skills": ["Python", "SQL"],
                    # body tries to clear the protected fields — must be ignored:
                    "attribution_notes": [],
                    "comp_floor": "",
                },
                "preferences": {"alert_frequency": "weekly", "score_threshold": 60},
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert resp.status_code == 200
    profile_upsert = next(u["row"] for u in store["upserts"] if u["table"] == "profiles")
    written = profile_upsert["parsed"]
    assert written["skills"] == ["Python", "SQL"]  # edit applied
    assert written["attribution_notes"] == ["true note from the coach"]  # survived
    assert written["comp_floor"] == "200k"  # survived; body's "" ignored
    assert profile_upsert["user_id"] == "user-123"  # JWT-derived id, not request body
