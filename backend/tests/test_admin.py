"""Admin fetch-jobs tests — auth gate + the admin allowlist (no network)."""

import pytest
from app.admin import is_admin
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_fetch_jobs_requires_auth() -> None:
    response = client.post("/admin/fetch-jobs", json={})
    assert response.status_code == 401


def test_score_matches_requires_auth() -> None:
    # M4 scoring trigger is gated the same way (LLM spend + pool reads).
    response = client.post("/admin/score-matches", json={})
    assert response.status_code == 401


def test_is_admin_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", "uid-1, uid-2")
    assert is_admin("uid-1") is True
    assert is_admin("uid-2") is True
    assert is_admin("someone-else") is False


def test_is_admin_empty_allowlist_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", "")
    assert is_admin("uid-1") is False
