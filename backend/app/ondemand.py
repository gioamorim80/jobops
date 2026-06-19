"""On-demand "paste a link → score + tailor" endpoints (M2).

POST /ondemand/score    accept a job URL or pasted text; fetch+extract if a URL;
                        run the scorer then the tailor against the user's stored
                        profile; save the result to `tailorings` (approved=false).
POST /ondemand/approve  save the user-edited bullets and mark approved=true.

Security: user_id always comes from the verified JWT (CurrentUserId), never
request input. Every read/write is scoped to that user's own rows. Per-user
daily LLM-call cap is enforced before any model call; every call is logged.
Resume/profile/job text is sent only to the agent calls and never logged.
"""

import json

from agents.scorer import SCORER_SYSTEM_PROMPT_V1
from agents.tailor import TAILOR_SYSTEM_PROMPT_V1
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUserId
from app.config import settings
from app.jobfetch import MAX_JOB_CHARS, UnreadableLink, fetch_job_text
from app.llm import run_json_agent
from app.supabase_client import get_service_client
from app.usage import count_calls_today, log_call

router = APIRouter(prefix="/ondemand", tags=["ondemand"])


# --------------------------------- models -------------------------------------
class ScoreRequest(BaseModel):
    url: str | None = None
    text: str | None = None


class TailoredBullet(BaseModel):
    original: str = ""
    tailored: str = ""
    why: str = ""


class ApproveRequest(BaseModel):
    id: str
    tailored_bullets: list[TailoredBullet] = Field(default_factory=list)
    analysis: str | None = None


# --------------------------------- helpers ------------------------------------
def _strlist(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _normalize_score(data: dict) -> dict:
    try:
        fit = int(data.get("fit", 0))
    except (TypeError, ValueError):
        fit = 0
    fit = max(0, min(100, fit))
    decision = str(data.get("decision", "")).strip().upper()
    if decision not in {"APPLY", "STRETCH", "SKIP"}:
        decision = "STRETCH"
    return {
        "fit": fit,
        "decision": decision,
        "cleared": _strlist(data.get("cleared")),
        "gaps": _strlist(data.get("gaps")),
        "referral_angle": str(data.get("referral_angle") or ""),
        "pitch": str(data.get("pitch") or ""),
    }


def _normalize_tailor(data: dict) -> dict:
    bullets = []
    for item in data.get("tailored_bullets") or []:
        if isinstance(item, dict):
            bullets.append(
                {
                    "original": str(item.get("original") or ""),
                    "tailored": str(item.get("tailored") or ""),
                    "why": str(item.get("why") or ""),
                }
            )
    return {
        "tailored_bullets": bullets,
        "analysis": str(data.get("analysis") or ""),
        "flags": _strlist(data.get("flags")),
    }


# --------------------------------- endpoints ----------------------------------
@router.post("/score")
def score_and_tailor(user_id: CurrentUserId, body: ScoreRequest) -> dict:
    client = get_service_client()

    # 1) Need a completed profile to score against.
    profile_rows = (
        client.table("profiles")
        .select("parsed, raw_resume_text, onboarding_complete")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not profile_rows or not profile_rows[0].get("onboarding_complete"):
        return {
            "status": "no_profile",
            "message": "Finish setting up your profile first — then paste a job to score it.",
        }
    profile = profile_rows[0]
    parsed = profile.get("parsed") or {}
    raw_resume = profile.get("raw_resume_text") or ""

    # 2) Cost guardrail: per-user daily LLM-call cap (friendly, not a crash).
    if count_calls_today(client, user_id) >= settings.per_user_daily_llm_cap:
        return {
            "status": "limit_reached",
            "message": (
                f"You've reached today's limit of {settings.per_user_daily_llm_cap} "
                "agent calls. It resets at midnight UTC — see you then."
            ),
        }

    # 3) Resolve the posting text: pasted text wins; otherwise fetch the URL once.
    job_text = (body.text or "").strip()
    source_url = (body.url or "").strip() or None
    if not job_text and not source_url:
        raise HTTPException(status_code=422, detail="Paste a job link or the posting text.")
    if not job_text and source_url:
        try:
            job_text = fetch_job_text(source_url)
        except UnreadableLink:
            return {
                "status": "unreadable",
                "message": (
                    "We couldn't read that link — some sites block fetching or load "
                    "the posting with JavaScript. Paste the job description text instead "
                    "and we'll take it from there."
                ),
            }
    job_text = job_text[:MAX_JOB_CHARS]

    # 4) Score, then 5) tailor — both on the backend; log every call.
    score_raw, score_usage = run_json_agent(
        SCORER_SYSTEM_PROMPT_V1,
        f"USER PROFILE (JSON):\n{json.dumps(parsed)}\n\nJOB POSTING:\n{job_text}",
        max_tokens=1200,
    )
    log_call(client, user_id, "score", score_usage)
    score = _normalize_score(score_raw)

    tailor_raw, tailor_usage = run_json_agent(
        TAILOR_SYSTEM_PROMPT_V1,
        (
            f"USER PROFILE (JSON):\n{json.dumps(parsed)}\n\n"
            f"ATTRIBUTION NOTES:\n{json.dumps(parsed.get('attribution_notes', []))}\n\n"
            f"RÉSUMÉ TEXT:\n{raw_resume}\n\n"
            f"JOB POSTING:\n{job_text}\n\n"
            f"SCORER RESULT (JSON):\n{json.dumps(score)}"
        ),
        max_tokens=2500,
    )
    log_call(client, user_id, "tailor", tailor_usage)
    tailor = _normalize_tailor(tailor_raw)

    # 6) Persist for the user (unapproved until they explicitly approve).
    inserted = (
        client.table("tailorings")
        .insert(
            {
                "user_id": user_id,
                "source_url": source_url,
                "job_text": job_text,
                "score": score,
                "tailored_bullets": tailor["tailored_bullets"],
                "analysis": tailor["analysis"],
                "approved": False,
            }
        )
        .execute()
        .data
    )
    tailoring_id = inserted[0]["id"] if inserted else None

    return {"status": "ok", "id": tailoring_id, "score": score, "tailor": tailor}


@router.post("/approve")
def approve_tailoring(user_id: CurrentUserId, body: ApproveRequest) -> dict:
    """Human-approval gate: save the user's edited bullets and mark approved."""
    client = get_service_client()

    update: dict = {
        "tailored_bullets": [bullet.model_dump() for bullet in body.tailored_bullets],
        "approved": True,
    }
    if body.analysis is not None:
        update["analysis"] = body.analysis

    # Scope to the caller's own row (service role bypasses RLS).
    result = (
        client.table("tailorings").update(update).eq("id", body.id).eq("user_id", user_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Tailoring not found.")
    return {"ok": True}
