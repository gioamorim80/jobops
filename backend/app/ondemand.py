"""On-demand "paste a link → score, then tailor on demand" endpoints (M2).

POST /ondemand/score    accept a job URL or pasted text; fetch+extract if a URL;
                        run ONLY the scorer (the cheap step) against the user's
                        stored profile; save to `tailorings` not-yet-tailored
                        (empty bullets, approved=false).
POST /ondemand/tailor   run the tailor (the expensive Sonnet step) ON DEMAND for
                        one already-scored tailoring; save the suggested bullets.
                        Only ever runs when the user explicitly asks for it.
POST /ondemand/approve  save the user-edited bullets and mark approved=true.
POST /ondemand/applied  toggle the "applied" marker (applied_at) on one tailoring.

Cost principle: scoring is cheap and automatic; tailoring is expensive and gated
behind explicit user intent. usage_log records "score" and "tailor" as distinct
actions, so tailoring spend is visibly only on /tailor clicks.

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

from app.applog import get_logger
from app.auth import CurrentUserId
from app.config import settings
from app.jobfetch import MAX_JOB_CHARS, UnreadableLink, fetch_job_text
from app.llm import run_json_agent
from app.supabase_client import get_service_client
from app.usage import count_calls_today, log_call

router = APIRouter(prefix="/ondemand", tags=["ondemand"])
logger = get_logger("jobops.ondemand")

# Model per step, declared explicitly (mirrors matcher.MATCH_MODEL) so the model
# we CALL is the model we LOG — not whatever the global default happens to be.
# Sonnet for the on-demand scorer and tailor today.
SCORE_MODEL = "claude-sonnet-4-6"
TAILOR_MODEL = "claude-sonnet-4-6"


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


class TailorRequest(BaseModel):
    id: str  # an existing (already-scored) tailoring to tailor on demand


class ApproveRequest(BaseModel):
    id: str
    tailored_bullets: list[TailoredBullet] = Field(default_factory=list)
    analysis: str | None = None


# --------------------------------- helpers ------------------------------------
def _strlist(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _clean_label(value: object, max_len: int = 140) -> str:
    """Tidy an extracted role/company string: collapse whitespace, trim, cap
    length. Empty string when the scorer found nothing (no fabrication)."""
    return " ".join(str(value or "").split()).strip()[:max_len]


def _normalize_score(data: dict) -> dict:
    try:
        fit = int(data.get("fit", 0))
    except (TypeError, ValueError):
        fit = 0
    fit = max(0, min(100, fit))
    raw_decision = str(data.get("decision", "")).strip().upper()
    decision = raw_decision
    if decision not in {"APPLY", "STRETCH", "SKIP"}:
        # The scorer should always emit a valid decision; if it doesn't, fall back
        # to STRETCH (don't crash) but surface it — a silent default would mask a
        # malformed reply and make two equal scores diverge for a non-substantive
        # reason. Note: not raw text/PII, just the offending label.
        logger.warning(
            "scorer returned missing/invalid decision %r (fit=%s); defaulting to STRETCH",
            raw_decision,
            fit,
        )
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


def _tailor_from_row(row: dict) -> dict | None:
    """The saved tailoring for a row, or None if it was scored but not yet
    tailored. `flags` are not persisted, so a saved result has an empty flags
    list."""
    if not row.get("tailored_bullets"):
        return None
    return _normalize_tailor(
        {
            "tailored_bullets": row.get("tailored_bullets") or [],
            "analysis": row.get("analysis") or "",
            "flags": [],
        }
    )


def _score_payload(
    *, tailoring_id: str, cached: bool, approved: bool, score: dict, tailor: dict | None
) -> dict:
    """Shape returned by /score. `tailored` tells the UI whether to show the saved
    bullets or the on-demand "Tailor my resume for this" button."""
    return {
        "status": "ok",
        "id": tailoring_id,
        "cached": cached,
        "approved": approved,
        "score": score,
        "tailored": tailor is not None,
        "tailor": tailor,
    }


def _cached_score_response(row: dict) -> dict:
    """Build the /score response from a saved row — no LLM call. Includes the
    saved tailoring if the job was already tailored, else tailor=None."""
    return _score_payload(
        tailoring_id=row["id"],
        cached=True,
        approved=bool(row.get("approved")),
        score=_normalize_score(row.get("score") or {}),
        tailor=_tailor_from_row(row),
    )


# --------------------------------- endpoints ----------------------------------
@router.post("/score")
def score_job(user_id: CurrentUserId, body: ScoreRequest) -> dict:
    client = get_service_client()

    # 1) Need a completed profile to score against. (The resume text isn't needed
    #    here — only tailoring uses it — so we don't load it on the cheap path.)
    profile_rows = (
        client.table("profiles")
        .select("parsed, onboarding_complete")
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
        return _cached_score_response(existing)

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

    # 6) Score ONLY — the cheap step. Tailoring is a separate, on-demand call
    #    (POST /ondemand/tailor) so we never spend the expensive tailor on a job
    #    the user won't pursue. temperature=0 keeps scoring stable.
    score_raw, score_usage = run_json_agent(
        SCORER_SYSTEM_PROMPT_V1,
        f"USER PROFILE (JSON):\n{json.dumps(parsed)}\n\nJOB POSTING:\n{job_text}",
        max_tokens=1200,
        temperature=0,
        model=SCORE_MODEL,
        label="scorer",
        log_output_on_error=True,  # scorer output is a fit verdict (no user PII)
    )
    log_call(client, user_id, "score", score_usage, model=SCORE_MODEL)
    score = _normalize_score(score_raw)
    # Role/company are extracted from the posting (never invented); stored in
    # their own columns so the history list can show "Role — Company".
    role = _clean_label(score_raw.get("role"))
    company = _clean_label(score_raw.get("company"))

    # 7) Persist as scored-but-not-tailored (empty bullets/analysis, approved=false).
    #    Re-scoring an existing job overwrites that one row (and resets any prior
    #    tailoring/approval, since the score is fresh) rather than piling up dupes.
    record = {
        "user_id": user_id,
        "source_url": source_url,
        "job_text": job_text,
        "role": role,
        "company": company,
        "score": score,
        "tailored_bullets": [],
        "analysis": "",
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

    return _score_payload(
        tailoring_id=tailoring_id, cached=False, approved=False, score=score, tailor=None
    )


@router.post("/tailor")
def tailor_resume(user_id: CurrentUserId, body: TailorRequest) -> dict:
    """Run the tailor (the expensive Sonnet step) ON DEMAND for one already-scored
    tailoring of the caller's own. Saves the suggested bullets + analysis. If the
    row was already tailored, returns the saved bullets with no model call."""
    client = get_service_client()

    rows = (
        client.table("tailorings")
        .select("id, job_text, score, tailored_bullets, analysis, approved")
        .eq("id", body.id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Tailoring not found.")
    row = rows[0]

    # Already tailored — return what's saved, no LLM call (and no cap consumed).
    existing_tailor = _tailor_from_row(row)
    if existing_tailor is not None:
        return {
            "status": "ok",
            "id": row["id"],
            "approved": bool(row.get("approved")),
            "tailor": existing_tailor,
        }

    job_text = (row.get("job_text") or "")[:MAX_JOB_CHARS]
    if not job_text:
        raise HTTPException(status_code=422, detail="No saved job text to tailor against.")

    # Need the resume/profile to tailor against.
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
            "message": "Finish setting up your profile first, then tailor for this job.",
        }
    parsed = profile_rows[0].get("parsed") or {}
    raw_resume = profile_rows[0].get("raw_resume_text") or ""
    score = _normalize_score(row.get("score") or {})

    # Cost guardrail: per-user daily LLM-call cap (shared with scoring/coach).
    if count_calls_today(client, user_id) >= settings.per_user_daily_llm_cap:
        return {
            "status": "limit_reached",
            "message": (
                f"You've reached today's limit of {settings.per_user_daily_llm_cap} "
                "agent calls. It resets at midnight UTC — see you then."
            ),
        }

    tailor_raw, tailor_usage = run_json_agent(
        TAILOR_SYSTEM_PROMPT_V1,
        (
            f"USER PROFILE (JSON):\n{json.dumps(parsed)}\n\n"
            f"ATTRIBUTION NOTES:\n{json.dumps(parsed.get('attribution_notes', []))}\n\n"
            f"RESUME TEXT:\n{raw_resume}\n\n"
            f"JOB POSTING:\n{job_text}\n\n"
            f"SCORER RESULT (JSON):\n{json.dumps(score)}"
        ),
        max_tokens=2500,
        model=TAILOR_MODEL,
        label="tailor",  # output is rephrased resume content — never snippet-logged
    )
    log_call(client, user_id, "tailor", tailor_usage, model=TAILOR_MODEL)
    tailor = _normalize_tailor(tailor_raw)

    # Save the suggestions; leave approved=false until the user reviews + approves.
    client.table("tailorings").update(
        {"tailored_bullets": tailor["tailored_bullets"], "analysis": tailor["analysis"]}
    ).eq("id", row["id"]).eq("user_id", user_id).execute()

    return {
        "status": "ok",
        "id": row["id"],
        "approved": bool(row.get("approved")),
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
