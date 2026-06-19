"""Onboarding endpoint auth tests — no real network/Supabase calls.

The full happy path needs Supabase + Anthropic and is covered by the manual
two-account isolation test in the M1 docs. Here we assert the auth gate.
"""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


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
