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


def test_send_digests_requires_auth() -> None:
    response = client.post("/admin/send-digests", json={})
    assert response.status_code == 401


def test_send_digests_rejects_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    # Non-admin -> 403; the per-user digest worker is never reached.
    monkeypatch.setattr(settings, "admin_user_ids", "admin-1")

    def _boom(*a, **k):
        raise AssertionError("send_user_digest reached despite non-admin caller")

    monkeypatch.setattr(admin_mod, "send_user_digest", _boom)
    app.dependency_overrides[get_current_user_id] = lambda: "not-an-admin"
    try:
        response = client.post("/admin/send-digests", json={"user_id": "u1"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 403


def test_send_digests_admin_targeted_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # Admin + explicit user_id (test mode) -> only that user is processed, and the
    # endpoint returns the aggregated summary. send_user_digest is faked (no network).
    monkeypatch.setattr(settings, "admin_user_ids", "admin-1")
    seen: list = []

    def fake_digest(client_, user_id):
        seen.append(user_id)
        return {"user": user_id[:8], "status": "sent", "sent": 3}

    monkeypatch.setattr(admin_mod, "send_user_digest", fake_digest)
    # The endpoint builds a service client before delegating; stub it so the test
    # needs no Supabase env (CI has none). In targeted mode the client is only passed
    # to send_user_digest, which is faked above.
    monkeypatch.setattr(admin_mod, "get_service_client", lambda: object())
    app.dependency_overrides[get_current_user_id] = lambda: "admin-1"
    try:
        response = client.post("/admin/send-digests", json={"user_id": "target-user"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 200
    body = response.json()
    assert body["targeted"] == 1 and body["sent"] == 1
    assert seen == ["target-user"]  # only the targeted user, no fan-out


def test_scan_all_requires_auth() -> None:
    response = client.post("/admin/scan-all", json={})
    assert response.status_code == 401


def test_scan_all_rejects_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    # Non-admin -> 403; the scan loop is never reached (it spends LLM).
    monkeypatch.setattr(settings, "admin_user_ids", "admin-1")

    def _boom(*a, **k):
        raise AssertionError("scan_all_opted_in reached despite non-admin caller")

    monkeypatch.setattr(admin_mod, "scan_all_opted_in", _boom)
    app.dependency_overrides[get_current_user_id] = lambda: "not-an-admin"
    try:
        response = client.post("/admin/scan-all", json={})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 403


def test_scan_all_admin_runs_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    # Admin passes the gate; the endpoint aggregates the loop's per-user results.
    monkeypatch.setattr(settings, "admin_user_ids", "admin-1")
    monkeypatch.setattr(admin_mod, "get_service_client", lambda: object())
    monkeypatch.setattr(
        admin_mod,
        "scan_all_opted_in",
        lambda _client: [
            {"user": "a", "status": "ok", "scored": 2},
            {"user": "b", "status": "skipped_no_roles"},
        ],
    )
    app.dependency_overrides[get_current_user_id] = lambda: "admin-1"
    try:
        response = client.post("/admin/scan-all", json={})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 200
    body = response.json()
    assert body["users"] == 2 and body["scanned"] == 1 and body["scored"] == 2


def test_is_admin_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", "uid-1, uid-2")
    assert is_admin("uid-1") is True
    assert is_admin("uid-2") is True
    assert is_admin("someone-else") is False


def test_is_admin_empty_allowlist_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", "")
    assert is_admin("uid-1") is False
