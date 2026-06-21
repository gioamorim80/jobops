"""Shared helper for running a JSON-returning Anthropic agent.

Prompt-based JSON (no structured-output coupling). Prompt caching is
intentionally NOT used yet — there is no repeated context at this stage
(deferred per the roadmap).
"""

import json
from typing import Any

import anthropic
from fastapi import HTTPException

from app.config import settings


def extract_json_object(text: str) -> dict:
    """Pull the first JSON object out of a model reply, tolerating prose/fences."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise HTTPException(status_code=502, detail="Agent returned no JSON.")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Agent returned malformed JSON.") from exc


def _run_raw(
    system: str,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float | None,
    model: str | None,
) -> tuple[str, Any]:
    """Call the model and return the RAW reply text + usage. JSON parsing (if any)
    is left to the caller, so a non-JSON reply never crashes inside the helper."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured.")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    params: dict = {
        "model": model or settings.anthropic_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if temperature is not None:
        params["temperature"] = temperature
    try:
        message = client.messages.create(**params)
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc

    reply = "".join(block.text for block in message.content if block.type == "text")
    return reply, message.usage


def run_json_agent(
    system: str,
    user: str,
    *,
    max_tokens: int = 2000,
    model: str | None = None,
    temperature: float | None = None,
) -> tuple[dict, Any]:
    """Run one single-turn agent and return (parsed_json, usage).

    Pass `temperature` (e.g. 0 for the scorer) when you want deterministic output;
    omit it to use the model's default sampling (natural writing for the tailor).
    """
    text, usage = _run_raw(
        system,
        [{"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=temperature,
        model=model,
    )
    return extract_json_object(text), usage


def run_chat_text(
    system: str,
    messages: list[dict],
    *,
    max_tokens: int = 800,
    model: str | None = None,
    temperature: float | None = None,
) -> tuple[str, Any]:
    """Run a multi-turn chat (history must end with a user turn) and return the
    RAW reply text + usage. The caller parses leniently so a prose reply (common
    as a conversation grows) is handled gracefully instead of raising a 502."""
    return _run_raw(
        system,
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        model=model,
    )
