"""send_email tests — failure-without-crash, request shape, and PII-safe logging.

No network: httpx.post is monkeypatched. Log capture uses a handler attached
directly to the module logger (which has propagate=False), so these assertions hold
regardless of root-logger propagation.
"""

import logging

import app.mailer as mailer_mod
import pytest
from app.mailer import send_email


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def email_logs():
    """Capture everything the jobops.mailer logger emits during a test."""
    handler = _CaptureHandler()
    mailer_mod.logger.addHandler(handler)
    try:
        yield handler
    finally:
        mailer_mod.logger.removeHandler(handler)


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self) -> dict:
        return self._json


_FAKE_KEY = "re_test_key_DO_NOT_LOG"


def _configure(monkeypatch) -> None:
    monkeypatch.setattr(mailer_mod.settings, "resend_api_key", _FAKE_KEY)
    monkeypatch.setattr(mailer_mod.settings, "alert_from_email", "noreply@myjobops.app")


def test_returns_error_when_not_configured(monkeypatch, email_logs) -> None:
    # No API key -> structured error, never a crash, and no send attempted.
    monkeypatch.setattr(mailer_mod.settings, "resend_api_key", None)
    monkeypatch.setattr(mailer_mod.settings, "alert_from_email", "noreply@myjobops.app")

    def _boom(*a, **k):  # must never be reached
        raise AssertionError("httpx.post should not be called when unconfigured")

    monkeypatch.setattr(mailer_mod.httpx, "post", _boom)

    result = send_email("user@example.com", "Subj", "<p>Body</p>")
    assert result == {
        "status": "error",
        "error": "not_configured",
        "detail": "RESEND_API_KEY and ALERT_FROM_EMAIL must both be set.",
    }


def test_builds_correct_request_and_succeeds(monkeypatch, email_logs) -> None:
    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(200, {"id": "msg_abc123"})

    _configure(monkeypatch)
    monkeypatch.setattr(mailer_mod.httpx, "post", fake_post)

    result = send_email(
        "user@example.com", "Secret Subject", "<p>Secret Body</p>", text="Secret Body"
    )

    # Request shape: correct endpoint, from = alert_from_email, bearer auth present.
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == f"Bearer {_FAKE_KEY}"
    assert captured["json"]["from"] == "noreply@myjobops.app"
    assert captured["json"]["to"] == ["user@example.com"]
    assert captured["json"]["subject"] == "Secret Subject"
    assert captured["json"]["html"] == "<p>Secret Body</p>"
    assert captured["json"]["text"] == "Secret Body"

    assert result == {"status": "ok", "id": "msg_abc123"}

    # PII-safe logging on success: recipient + message id + status only; NEVER the
    # API key, the subject, or the body.
    logged = " ".join(email_logs.messages)
    assert _FAKE_KEY not in logged
    assert "Secret Subject" not in logged
    assert "Secret Body" not in logged
    assert "user@example.com" in logged and "msg_abc123" in logged


def test_resend_error_logs_status_not_body(monkeypatch, email_logs) -> None:
    def fake_post(url, headers=None, json=None, timeout=None):
        # A real Resend error body would echo request details — must not be logged.
        return _FakeResponse(422, {"name": "validation_error", "message": "domain not verified"})

    _configure(monkeypatch)
    monkeypatch.setattr(mailer_mod.httpx, "post", fake_post)

    result = send_email("user@example.com", "Subj", "<p>Body</p>")
    assert result == {"status": "error", "error": "resend_error", "status_code": 422}

    logged = " ".join(email_logs.messages)
    assert _FAKE_KEY not in logged  # API key never logged
    assert "domain not verified" not in logged  # response body never logged
    assert "422" in logged and "user@example.com" in logged  # status + recipient ok


def test_network_error_returns_failure_not_crash(monkeypatch, email_logs) -> None:
    def fake_post(url, headers=None, json=None, timeout=None):
        raise mailer_mod.httpx.ConnectError("connection refused")

    _configure(monkeypatch)
    monkeypatch.setattr(mailer_mod.httpx, "post", fake_post)

    result = send_email("user@example.com", "Subj", "<p>Body</p>")
    assert result == {"status": "error", "error": "request_failed"}

    logged = " ".join(email_logs.messages)
    assert _FAKE_KEY not in logged  # key not leaked via the error path
    assert "connection refused" not in logged  # exception detail not logged
    assert "user@example.com" in logged
