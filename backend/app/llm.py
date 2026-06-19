"""Shared helper for running a JSON-returning Anthropic agent.

Prompt-based JSON (no structured-output coupling). Prompt caching is
intentionally NOT used in M2 — there is no repeated context yet (deferred per
the roadmap).
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


def run_json_agent(
    system: str,
    user: str,
    *,
    max_tokens: int = 2000,
    model: str | None = None,
) -> tuple[dict, Any]:
    """Run one agent turn and return (parsed_json, usage). Raises HTTPException
    on misconfiguration (503) or API/parse errors (502)."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured.")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        message = client.messages.create(
            model=model or settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc

    reply = "".join(block.text for block in message.content if block.type == "text")
    return extract_json_object(reply), message.usage
