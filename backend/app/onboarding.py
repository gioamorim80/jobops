"""Onboarding endpoints.

Flow:
  POST /onboarding/parse     → download the user's uploaded resume (service
                               role), extract text, run the onboarding agent,
                               persist the resume text under RLS, return a
                               draft profile (no raw PII returned to the browser).
  POST /onboarding/complete  → save the user-confirmed profile + preferences.
                               This is the human-approval gate: nothing is
                               marked complete until the user submits here.

The user_id always comes from the verified JWT (CurrentUserId), never request
input, so a caller can only ever write their own rows.
"""

import json
from typing import Literal

import anthropic
from agents.onboarding import ONBOARDING_SYSTEM_PROMPT_V1
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUserId
from app.config import settings
from app.resume import extract_resume_text
from app.supabase_client import get_service_client

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# --------------------------- request/response models ---------------------------
class ParseRequest(BaseModel):
    resume_path: str


class Draft(BaseModel):
    full_name: str = ""
    email: str = ""
    skills: list[str] = Field(default_factory=list)
    roles_held: list[str] = Field(default_factory=list)
    seniority: str = ""
    domains: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    summary: str = ""


class ParsedProfile(BaseModel):
    skills: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    seniority: str = ""
    domains: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_pref: str = ""
    comp_floor: str = ""
    attribution_notes: list[str] = Field(default_factory=list)


class PreferencesIn(BaseModel):
    alert_frequency: Literal["off", "daily", "weekly"] = "weekly"
    score_threshold: int = Field(default=60, ge=0, le=100)


class CompleteRequest(BaseModel):
    full_name: str = ""
    email: str = ""
    parsed: ParsedProfile
    preferences: PreferencesIn


class ProfileUpdateRequest(BaseModel):
    full_name: str = ""
    email: str = ""
    parsed: ParsedProfile
    preferences: PreferencesIn


# --------------------------------- helpers ------------------------------------
def _extract_json_object(text: str) -> dict:
    """Pull the first JSON object out of the model's reply, tolerating fences."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise HTTPException(status_code=502, detail="Onboarding agent returned no JSON.")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502, detail="Onboarding agent returned malformed JSON."
        ) from exc


def _run_onboarding_agent(resume_text: str) -> Draft:
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured.")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1500,
            system=ONBOARDING_SYSTEM_PROMPT_V1,
            messages=[
                {
                    "role": "user",
                    "content": f"Resume text to extract from:\n\n{resume_text}",
                }
            ],
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Onboarding agent error: {exc}") from exc

    reply = "".join(block.text for block in message.content if block.type == "text")
    return Draft(**_extract_json_object(reply))


# --------------------------------- endpoints ----------------------------------
@router.post("/parse")
def parse_resume(user_id: CurrentUserId, body: ParseRequest) -> dict:
    # Defense in depth: storage RLS already scopes the bucket, but never read a
    # path outside the caller's own folder even with the service role.
    if not body.resume_path.startswith(f"{user_id}/"):
        raise HTTPException(status_code=403, detail="Resume path does not belong to you.")

    client = get_service_client()
    try:
        file_bytes = client.storage.from_(settings.resume_bucket).download(body.resume_path)
    except Exception as exc:  # missing object / storage error
        raise HTTPException(status_code=404, detail="Could not read the uploaded resume.") from exc

    try:
        resume_text = extract_resume_text(file_bytes, body.resume_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not resume_text:
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted from that file. Try a text-based PDF or DOCX.",
        )

    draft = _run_onboarding_agent(resume_text)

    # Persist the resume text under RLS now (service role). The final, confirmed
    # profile is written by /complete. raw_resume_text is never returned to the
    # browser and never logged.
    client.table("profiles").upsert(
        {
            "user_id": user_id,
            "raw_resume_text": resume_text,
            "resume_file_path": body.resume_path,
            "onboarding_complete": False,
        },
        on_conflict="user_id",
    ).execute()

    return {"draft": draft.model_dump()}


@router.post("/complete")
def complete_onboarding(user_id: CurrentUserId, body: CompleteRequest) -> dict:
    """Human-approval gate: save the user-confirmed profile and preferences."""
    client = get_service_client()

    client.table("profiles").upsert(
        {
            "user_id": user_id,
            "full_name": body.full_name or None,
            "email": body.email or None,
            "parsed": body.parsed.model_dump(),
            "onboarding_complete": True,
        },
        on_conflict="user_id",
    ).execute()

    client.table("preferences").upsert(
        {
            "user_id": user_id,
            "alert_frequency": body.preferences.alert_frequency,
            "score_threshold": body.preferences.score_threshold,
        },
        on_conflict="user_id",
    ).execute()

    return {"ok": True}


# Fields the settings form owns: the user edits the full visible set, so these are
# REPLACED wholesale (including deletions). This is the OPPOSITE of enrich.py's
# merge_changes, which APPENDS.
_PROFILE_FORM_FIELDS = (
    "skills",
    "target_roles",
    "domains",
    "locations",
    "seniority",
    "remote_pref",
)
# Fields this endpoint must NEVER let the client set: preserved from the live DB
# row. attribution_notes is coach-written; comp_floor is set elsewhere. (Any other
# parsed field not in the form set is also preserved, via the merge below.)
_PROFILE_PRESERVED_FIELDS = ("comp_floor", "attribution_notes")


def merge_profile_edit(current: dict, submitted: dict) -> dict:
    """Field-scoped merge for a settings save. Start from the current DB `parsed`,
    REPLACE the form-owned fields with the submitted values (wholesale, so removals
    stick), and preserve everything else — including the client-immutable
    comp_floor / attribution_notes — from the current row. The submitted values for
    preserved fields are ignored on purpose."""
    merged = dict(current or {})
    for field in _PROFILE_FORM_FIELDS:
        merged[field] = submitted.get(field)
    # Preserved fields are pinned to the live DB value, never the request body.
    for field in _PROFILE_PRESERVED_FIELDS:
        if current and field in current:
            merged[field] = current[field]
    return merged


@router.post("/profile")
def update_profile(user_id: CurrentUserId, body: ProfileUpdateRequest) -> dict:
    """Edit individual profile fields + preferences — WITHOUT re-uploading a resume.

    Updates only parsed / full_name / email and the preferences row. It never
    touches raw_resume_text, resume_file_path, or onboarding_complete.

    `parsed` is a FIELD-SCOPED MERGE, not a full overwrite: the form-owned fields
    (skills, target_roles, domains, locations, seniority, remote_pref) are replaced
    wholesale, while comp_floor and attribution_notes are preserved from the live DB
    row so a stale client can't wipe coach-written attribution_notes. user_id comes
    only from the verified JWT, so a caller can only ever read/write their own rows.

    Concurrency: this is a read-modify-write on the same `parsed` JSONB that
    enrich.py's /apply also merges into. Fine today (single-user, sequential). If
    profile-save and enrich-apply ever run concurrently, serialize the write here
    (e.g. a row lock or an atomic jsonb update) — not built now.
    """
    client = get_service_client()

    # Read THIS user's current parsed (JWT-derived id only; RLS is the backstop).
    rows = (
        client.table("profiles").select("parsed").eq("user_id", user_id).limit(1).execute().data
        or []
    )
    current_parsed = (rows[0].get("parsed") if rows else None) or {}
    merged_parsed = merge_profile_edit(current_parsed, body.parsed.model_dump())

    client.table("profiles").upsert(
        {
            "user_id": user_id,
            "full_name": body.full_name or None,
            "email": body.email or None,
            "parsed": merged_parsed,
        },
        on_conflict="user_id",
    ).execute()

    client.table("preferences").upsert(
        {
            "user_id": user_id,
            "alert_frequency": body.preferences.alert_frequency,
            "score_threshold": body.preferences.score_threshold,
        },
        on_conflict="user_id",
    ).execute()

    return {"ok": True}
