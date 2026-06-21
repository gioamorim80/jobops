"""Profile-enrichment coach endpoints (M2.5).

POST /enrich/chat   one chat turn: the coach (with the user's profile as context)
                    replies in-voice and may return a structured `proposal`.
POST /enrich/apply  write a user-confirmed proposal into profiles.parsed.

Isolation: user_id always comes from the verified JWT, never request input; every
read/write touches only that user's own profile. The chat transcript is NOT
persisted and raw message content is NEVER logged — only token counts go to
usage_log. The per-user daily LLM cap is shared with the rest of the app.
"""

import json
import logging
from typing import Literal

from agents.enrich import ENRICH_SYSTEM_PROMPT_V2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUserId
from app.config import settings
from app.llm import run_json_chat
from app.supabase_client import get_service_client
from app.usage import count_calls_today, log_call

router = APIRouter(prefix="/enrich", tags=["enrich"])

MAX_MESSAGES = 20  # cap conversation length sent to the model
MAX_CONTENT_CHARS = 2000  # cap per-message length

# Abuse-only floor for the chat cap. A Coach turn is ~0.6 cents, so even if the
# configured cap is somehow very low (e.g. a leftover test override on the
# server), never block real conversations below this many turns/day.
ENRICH_TURN_FLOOR = 40

logger = logging.getLogger("jobops.enrich")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


# --------------------------------- models -------------------------------------
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class ProposalChanges(BaseModel):
    add_skills: list[str] = Field(default_factory=list)
    add_domains: list[str] = Field(default_factory=list)
    add_target_roles: list[str] = Field(default_factory=list)
    add_attribution_notes: list[str] = Field(default_factory=list)
    set_seniority: str = ""
    set_remote_pref: str = ""


class ApplyRequest(BaseModel):
    changes: ProposalChanges


# --------------------------------- helpers ------------------------------------
def _strlist(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _load_parsed(client, user_id: str) -> dict:
    rows = (
        client.table("profiles").select("parsed").eq("user_id", user_id).limit(1).execute().data
        or []
    )
    return (rows[0].get("parsed") if rows else None) or {}


def _normalize_proposal(raw: object) -> dict | None:
    """Coerce the model's proposal into a clean shape, or None if it proposes
    nothing concrete."""
    if not isinstance(raw, dict):
        return None
    raw_changes = raw.get("changes") if isinstance(raw.get("changes"), dict) else {}
    changes = {
        "add_skills": _strlist(raw_changes.get("add_skills")),
        "add_domains": _strlist(raw_changes.get("add_domains")),
        "add_target_roles": _strlist(raw_changes.get("add_target_roles")),
        "add_attribution_notes": _strlist(raw_changes.get("add_attribution_notes")),
        "set_seniority": str(raw_changes.get("set_seniority") or "").strip(),
        "set_remote_pref": str(raw_changes.get("set_remote_pref") or "").strip(),
    }
    has_change = (
        changes["add_skills"]
        or changes["add_domains"]
        or changes["add_target_roles"]
        or changes["add_attribution_notes"]
        or changes["set_seniority"]
        or changes["set_remote_pref"]
    )
    if not has_change:
        return None
    return {"summary": str(raw.get("summary") or "").strip(), "changes": changes}


def _aslist(value: object) -> list[str]:
    return _strlist(value) if isinstance(value, list) else []


def _merge_list(existing: list[str], additions: list[str]) -> list[str]:
    seen = {item.lower() for item in existing}
    out = list(existing)
    for addition in additions:
        cleaned = addition.strip()
        if cleaned and cleaned.lower() not in seen:
            out.append(cleaned)
            seen.add(cleaned.lower())
    return out


def merge_changes(parsed: dict, changes: dict) -> dict:
    """Apply confirmed changes onto a parsed profile (pure). Appends to lists
    (case-insensitive dedupe) and sets scalars only when non-empty. Other parsed
    fields are preserved untouched."""
    updated = dict(parsed)
    updated["skills"] = _merge_list(_aslist(updated.get("skills")), changes.get("add_skills", []))
    updated["domains"] = _merge_list(
        _aslist(updated.get("domains")), changes.get("add_domains", [])
    )
    updated["target_roles"] = _merge_list(
        _aslist(updated.get("target_roles")), changes.get("add_target_roles", [])
    )
    updated["attribution_notes"] = _merge_list(
        _aslist(updated.get("attribution_notes")), changes.get("add_attribution_notes", [])
    )
    if str(changes.get("set_seniority") or "").strip():
        updated["seniority"] = changes["set_seniority"].strip()
    if str(changes.get("set_remote_pref") or "").strip():
        updated["remote_pref"] = changes["set_remote_pref"].strip()
    return updated


# --------------------------------- endpoints ----------------------------------
@router.post("/chat")
def chat(user_id: CurrentUserId, body: ChatRequest) -> dict:
    client = get_service_client()

    # Abuse guardrail only. The cap counts ONLY this user's own logged "enrich"
    # turns today (one user message = exactly one row via log_call below — never
    # the resent conversation history, never other features' calls), resets at
    # 00:00 UTC, and is floored generously so a stray low value can't cut off a
    # real conversation. The log line makes the count vs cap visible in prod.
    cap = max(settings.enrich_daily_turn_cap, ENRICH_TURN_FLOOR)
    turns_today = count_calls_today(client, user_id, action="enrich")
    logger.info(
        "enrich cap check user=%s turns_today=%s configured_cap=%s effective_cap=%s",
        user_id[:8],
        turns_today,
        settings.enrich_daily_turn_cap,
        cap,
    )
    if turns_today >= cap:
        logger.warning(
            "enrich cap reached user=%s turns_today=%s effective_cap=%s",
            user_id[:8],
            turns_today,
            cap,
        )
        return {
            "status": "limit_reached",
            "message": (
                "Let's pick this up tomorrow — we've covered a lot today, and your "
                "stories will keep. (Daily chat limit reached; it resets at "
                "midnight UTC.)"
            ),
        }

    # Bound the conversation: last N non-empty turns, each capped in length.
    turns = [m for m in body.messages if m.content.strip()][-MAX_MESSAGES:]
    if not turns or turns[-1].role != "user":
        raise HTTPException(status_code=422, detail="Send a message to the coach.")
    convo = [{"role": m.role, "content": m.content.strip()[:MAX_CONTENT_CHARS]} for m in turns]

    parsed = _load_parsed(client, user_id)
    system = f"{ENRICH_SYSTEM_PROMPT_V2}\n\nCURRENT PROFILE (JSON):\n{json.dumps(parsed)}"

    data, usage = run_json_chat(system, convo, max_tokens=800)
    log_call(client, user_id, "enrich", usage)

    reply = str(data.get("reply") or "").strip() or "Tell me a little more?"
    return {"status": "ok", "reply": reply, "proposal": _normalize_proposal(data.get("proposal"))}


@router.post("/apply")
def apply(user_id: CurrentUserId, body: ApplyRequest) -> dict:
    """Human-approval gate: write a confirmed proposal into the user's profile.
    No LLM call — so no cap consumed and no usage logged."""
    client = get_service_client()
    parsed = _load_parsed(client, user_id)
    updated = merge_changes(parsed, body.changes.model_dump())
    client.table("profiles").upsert(
        {"user_id": user_id, "parsed": updated},
        on_conflict="user_id",
    ).execute()
    return {"ok": True}
