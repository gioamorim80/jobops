"""Admin trigger tests — auth gate + the admin allowlist (no network)."""

import app.admin as admin_mod
import pytest
from app.admin import is_admin
from app.auth import get_current_user_id
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


def test_test_email_requires_auth() -> None:
    response = client.post("/admin/test-email", json={"to": "x@example.com"})
    assert response.status_code == 401


def test_test_email_rejects_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    # Authenticated but NOT on the allowlist -> 403, and the send helper is never
    # reached (no spam vector). Sending must be admin-only, not merely authenticated.
    monkeypatch.setattr(settings, "admin_user_ids", "admin-1")

    def _boom(*a, **k):  # send_email must not be called for a denied caller
        raise AssertionError("send_email reached despite non-admin caller")

    monkeypatch.setattr(admin_mod, "send_email", _boom)
    app.dependency_overrides[get_current_user_id] = lambda: "not-an-admin"
    try:
        response = client.post("/admin/test-email", json={"to": "x@example.com"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 403


def test_test_email_allows_admin_and_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    # An allowlisted caller passes the gate and the endpoint returns the helper's
    # structured result. send_email is faked so no network is touched.
    monkeypatch.setattr(settings, "admin_user_ids", "admin-1")
    calls: dict = {}

    def fake_send(to, subject, html, text=None):
        calls["to"] = to
        return {"status": "ok", "id": "msg_1"}

    monkeypatch.setattr(admin_mod, "send_email", fake_send)
    app.dependency_overrides[get_current_user_id] = lambda: "admin-1"
    try:
        response = client.post("/admin/test-email", json={"to": "ops@example.com"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "id": "msg_1"}
    assert calls["to"] == "ops@example.com"  # the gate passed the request through


def test_is_admin_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", "uid-1, uid-2")
    assert is_admin("uid-1") is True
    assert is_admin("uid-2") is True
    assert is_admin("someone-else") is False


def test_is_admin_empty_allowlist_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", "")
    assert is_admin("uid-1") is False
