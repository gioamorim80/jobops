"""Shared helper for running a JSON-returning Anthropic agent.

Prompt-based JSON (no structured-output coupling). Prompt caching is used by the
M4 matcher (`run_cached_json_agent`): the rubric + profile prefix is identical
across every job in a scoring run, so it's marked with `cache_control` and the
per-job snippet is the only uncached part (cache reads bill at ~0.1x input).
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
    system: str | list[dict],
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


def run_cached_json_agent(
    system_blocks: list[dict],
    user: str,
    *,
    max_tokens: int = 1200,
    model: str | None = None,
    temperature: float | None = None,
) -> tuple[dict, Any]:
    """Like `run_json_agent`, but `system_blocks` is a list of system content
    blocks so the caller can mark a stable prefix with `cache_control`. Used by the
    matcher to cache the rubric+profile across every job in a run. The returned
    `usage` carries `cache_read_input_tokens` / `cache_creation_input_tokens` so
    the savings are observable. Returns (parsed_json, usage)."""
    text, usage = _run_raw(
        system_blocks,
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
