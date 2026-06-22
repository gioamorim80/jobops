"""Proof that the model= kwarg actually reaches the Anthropic API call.

We patch the Anthropic client at the lowest layer (`llm._run_raw` builds the
request) and capture the params handed to `messages.create`. To prove the PASSED
model wins over the env default rather than being silently ignored, the fixture
sets `settings.anthropic_model` to a sentinel that must NEVER appear on the call.
No network, no real key.
"""

import pytest
from app import llm
from app.config import settings
from app.enrich import ENRICH_MODEL
from app.matcher import MATCH_MODEL
from app.ondemand import SCORE_MODEL, TAILOR_MODEL

_SENTINEL_DEFAULT = "sentinel-default-MUST-NOT-be-used"


class _Block:
    type = "text"
    text = '{"ok": true}'  # valid JSON so run_json_agent's parse succeeds


class _Usage:
    input_tokens = 1
    output_tokens = 1
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class _Message:
    content = [_Block()]
    usage = _Usage()


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Patch the Anthropic client; return the list of params seen by
    messages.create. Sets a sentinel default model so any fallback is visible."""
    calls: list[dict] = []

    class _Messages:
        def create(self, **params: object) -> _Message:
            calls.append(params)
            return _Message()

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.messages = _Messages()

    monkeypatch.setattr(llm.anthropic, "Anthropic", _Client)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(settings, "anthropic_model", _SENTINEL_DEFAULT)
    return calls


@pytest.mark.parametrize("model", [SCORE_MODEL, TAILOR_MODEL])
def test_run_json_agent_sends_passed_model_not_default(captured: list[dict], model: str) -> None:
    # score/tailor path: the Sonnet model id passed in must reach the API call.
    assert model == "claude-sonnet-4-6"
    llm.run_json_agent("system", "user", model=model)
    assert captured[-1]["model"] == model
    assert captured[-1]["model"] != _SENTINEL_DEFAULT  # passed wins over env default


def test_run_cached_json_agent_sends_match_model(captured: list[dict]) -> None:
    # match path: Haiku must reach the API call, not the env default.
    assert MATCH_MODEL == "claude-haiku-4-5"
    blocks = [{"type": "text", "text": "rubric"}, {"type": "text", "text": "profile"}]
    llm.run_cached_json_agent(blocks, "JOB POSTING: …", model=MATCH_MODEL)
    assert captured[-1]["model"] == "claude-haiku-4-5"
    assert captured[-1]["model"] != _SENTINEL_DEFAULT


def test_run_chat_text_sends_enrich_model(captured: list[dict]) -> None:
    # coach path: the enrich model id passed in must reach the API call.
    llm.run_chat_text("system", [{"role": "user", "content": "hi"}], model=ENRICH_MODEL)
    assert captured[-1]["model"] == ENRICH_MODEL == "claude-sonnet-4-6"
    assert captured[-1]["model"] != _SENTINEL_DEFAULT


def test_no_model_falls_back_to_env_default(captured: list[dict]) -> None:
    # Contrast: with NO model passed, the helper still falls back to the configured
    # default (proving the assertions above test the override, not a no-op).
    llm.run_json_agent("system", "user")
    assert captured[-1]["model"] == _SENTINEL_DEFAULT
