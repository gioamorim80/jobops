"""On-demand "paste a link → score + tailor" endpoints (M2).

POST /ondemand/score    accept a job URL or pasted text; fetch+extract if a URL;
                        run the scorer then the tailor against the user's stored
                        profile; save the result to `tailorings` (approved=false).
POST /ondemand/approve  save the user-edited bullets and mark approved=true.
POST /ondemand/applied  toggle the "applied" marker (applied_at) on one tailoring.

Security: user_id always comes from the verified JWT (CurrentUserId), never
request input. Every read/write is scoped to that user's own rows. Per-user
daily LLM-call cap is enforced before any model call; every call is logged.
Resume/profile/job text is sent only to the agent calls and never logged.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    force: bool = False  # bypass the exact-match cache and force a fresh run


class TailoredBullet(BaseModel):
    original: str = ""
    tailored: str = ""
    why: str = ""
    where: str = ""  # which real role/section of the resume this edit applies to


class AppliedRequest(BaseModel):
    id: str
    applied: bool
    applied_on: str | None = None  # "YYYY-MM-DD"; when marking applied, the date
    # the user actually applied (defaults to today). Ignored when un-marking.


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
                    "where": str(item.get("where") or ""),
                }
            )
    return {
        "tailored_bullets": bullets,
        "analysis": str(data.get("analysis") or ""),
        "flags": _strlist(data.get("flags")),
    }


# ------------------------- exact-match cache helpers --------------------------
_TRACKING_KEYS = {"fbclid", "gclid", "mc_eid", "msclkid"}


def _normalize_url(raw: str) -> str:
    """Normalize for cache matching: lowercase scheme/host, drop fragment and
    common tracking params, strip trailing slash. Best-effort; falls back to
    the trimmed input."""
    raw = raw.strip()
    try:
        parts = urlsplit(raw)
        scheme = (parts.scheme or "https").lower()
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/") or "/"
        query = [
            (k, v)
            for k, v in parse_qsl(parts.query)
            if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_KEYS
        ]
        return urlunsplit((scheme, netloc, path, urlencode(sorted(query)), ""))
    except Exception:
        return raw


def _text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).lower().encode("utf-8")).hexdigest()


def _find_existing(client, user_id: str, source_url: str | None, pasted_text: str) -> dict | None:
    """Find this user's prior tailoring for the same job. Matches on normalized
    URL when a URL was given, else on a hash of the pasted text. Scoped to the
    caller's own rows."""
    if source_url:
        rows = (
            client.table("tailorings")
            .select("id, score, tailored_bullets, analysis, approved")
            .eq("user_id", user_id)
            .eq("source_url", source_url)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    if pasted_text:
        target = _text_hash(pasted_text)
        rows = (
            client.table("tailorings")
            .select("id, job_text, score, tailored_bullets, analysis, approved")
            .eq("user_id", user_id)
            .is_("source_url", "null")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
            or []
        )
        for row in rows:
            if row.get("job_text") and _text_hash(row["job_text"]) == target:
                return row
    return None


def _cached_response(row: dict) -> dict:
    """Build the score response from a saved row — no LLM call. Note: tailor
    `flags` are not persisted, so a saved result returns an empty flags list."""
    return {
        "status": "ok",
        "id": row["id"],
        "cached": True,
        "approved": bool(row.get("approved")),
        "score": _normalize_score(row.get("score") or {}),
        "tailor": _normalize_tailor(
            {
                "tailored_bullets": row.get("tailored_bullets") or [],
                "analysis": row.get("analysis") or "",
                "flags": [],
            }
        ),
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

    # 2) Resolve inputs. A URL (if given) is normalized and used as the cache key;
    #    otherwise the pasted text is. Pasted text wins as the posting body.
    pasted = (body.text or "").strip()
    source_url = _normalize_url(body.url) if (body.url or "").strip() else None
    if not pasted and not source_url:
        raise HTTPException(status_code=422, detail="Paste a job link or the posting text.")

    # 3) Exact-match cache: if this user already scored this exact job, return the
    #    saved result with NO LLM call (and so no cap consumed, no usage logged),
    #    unless they explicitly asked to re-score.
    existing = _find_existing(client, user_id, source_url, pasted)
    if existing and not body.force:
        return _cached_response(existing)

    # 4) Cost guardrail (only on a fresh run): per-user daily LLM-call cap.
    if count_calls_today(client, user_id) >= settings.per_user_daily_llm_cap:
        return {
            "status": "limit_reached",
            "message": (
                f"You've reached today's limit of {settings.per_user_daily_llm_cap} "
                "agent calls. It resets at midnight UTC — see you then."
            ),
        }

    # 5) Resolve the posting text: pasted text wins; otherwise fetch the URL once.
    job_text = pasted
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

    # 6) Score, then tailor — both on the backend; log every call.
    # temperature=0 keeps scoring stable: the same job + profile scores the same.
    score_raw, score_usage = run_json_agent(
        SCORER_SYSTEM_PROMPT_V1,
        f"USER PROFILE (JSON):\n{json.dumps(parsed)}\n\nJOB POSTING:\n{job_text}",
        max_tokens=1200,
        temperature=0,
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

    # 7) Persist for the user (unapproved until they explicitly approve). Re-scoring
    #    an existing job overwrites that one row rather than piling up duplicates.
    record = {
        "user_id": user_id,
        "source_url": source_url,
        "job_text": job_text,
        "score": score,
        "tailored_bullets": tailor["tailored_bullets"],
        "analysis": tailor["analysis"],
        "approved": False,
    }
    if existing:
        client.table("tailorings").update(record).eq("id", existing["id"]).eq(
            "user_id", user_id
        ).execute()
        tailoring_id = existing["id"]
    else:
        inserted = client.table("tailorings").insert(record).execute().data
        tailoring_id = inserted[0]["id"] if inserted else None

    return {
        "status": "ok",
        "id": tailoring_id,
        "cached": False,
        "approved": False,
        "score": score,
        "tailor": tailor,
    }


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


def _applied_at_iso(applied: bool, applied_on: str | None) -> str | None:
    """Resolve the stored `applied_at` value. None when un-marking. Otherwise the
    chosen day (`applied_on`, defaulting to today) at noon UTC — noon so the date
    shows as the same calendar day regardless of the viewer's timezone. Raises a
    422 if `applied_on` isn't a YYYY-MM-DD date."""
    if not applied:
        return None
    if applied_on:
        try:
            day = date.fromisoformat(applied_on)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="applied_on must be a date (YYYY-MM-DD)."
            ) from exc
    else:
        day = datetime.now(UTC).date()
    return datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC).isoformat()


@router.post("/applied")
def set_applied(user_id: CurrentUserId, body: AppliedRequest) -> dict:
    """Set the applied marker on one of the user's own tailorings. When marking
    applied, store the date the user actually applied (`applied_on`, defaulting to
    today) — users often apply on a different day than they click the button. When
    un-marking, clear it."""
    client = get_service_client()
    applied_at = _applied_at_iso(body.applied, body.applied_on)

    # Scope to the caller's own row (service role bypasses RLS).
    result = (
        client.table("tailorings")
        .update({"applied_at": applied_at})
        .eq("id", body.id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Tailoring not found.")
    return {"ok": True, "applied_at": applied_at}
