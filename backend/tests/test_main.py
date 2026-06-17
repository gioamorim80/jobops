"""M0 endpoint tests. The /agent/ping test stubs the Anthropic client so CI
runs without a real API key or network call."""

import pytest
from app.config import settings
from app.main import app, get_anthropic_client
from fastapi.testclient import TestClient


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class _FakeTextBlock:
    type = "text"
    text = "JobOps agent brain online and ready."


class _FakeMessage:
    model = "claude-sonnet-4-6"
    content = [_FakeTextBlock()]


class _FakeMessages:
    def create(self, **_kwargs: object) -> _FakeMessage:
        return _FakeMessage()


class _FakeClient:
    messages = _FakeMessages()


def test_agent_ping_returns_model_text() -> None:
    app.dependency_overrides[get_anthropic_client] = lambda: _FakeClient()
    try:
        client = TestClient(app)
        response = client.get("/agent/ping")
        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "claude-sonnet-4-6"
        assert body["text"] == "JobOps agent brain online and ready."
    finally:
        app.dependency_overrides.clear()


def test_agent_ping_returns_503_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the key off so the endpoint takes the graceful-503 path even if a
    # developer has ANTHROPIC_API_KEY exported in their shell.
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    client = TestClient(app)
    response = client.get("/agent/ping")
    assert response.status_code == 503
