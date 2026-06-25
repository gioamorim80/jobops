"""Manual, admin-gated triggers (no scheduler) — run for one user on demand.

POST /admin/fetch-jobs   (M3) fetches per-user from each enabled source, dedupes
                         into the shared `jobs` pool, returns a no-LLM prefilter
                         shortlist. No LLM calls.
POST /admin/score-matches (M4) prefilters the user's candidates from the pool and
                         LLM-scores that shortlist into the per-user `matches`
                         table (Haiku + prompt caching; logged as "match_score").

SECURITY: triggering external API calls / LLM spend / pool writes must not be open
to any authenticated user. The caller's verified-JWT user_id is checked against
the ADMIN_USER_IDS allowlist; an empty allowlist means no one is allowed (fail
closed). Admins may run for themselves or, for the per-user pattern, a given
user_id.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.applog import get_logger
from app.auth import CurrentUserId
from app.config import settings
from app.dedupe import upsert_jobs
from app.digest import send_user_digest
from app.mailer import send_email
from app.matcher import score_shortlist
from app.prefilter import DEFAULT_CAP, prefilter
from app.sources.adzuna import AdzunaSource
from app.sources.base import FetchResult, JobSource, JobSourceError, SearchCriteria
from app.supabase_client import get_service_client

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger("jobops.admin")

# Source registry: enabling/disabling a source is a one-line change here, not a
# change scattered through the codebase.
SOURCES: list[JobSource] = [AdzunaSource()]


class FetchRequest(BaseModel):
    user_id: str | None = None  # admin may target another user; defaults to the caller
    max_days_old: int = 30
    max_pages: int = 2


class ScoreMatchesRequest(BaseModel):
    user_id: str | None = None  # admin may target another user; defaults to the caller
    candidate_limit: int = 500  # cap on pool rows to prefilter (cost/perf bound)


class TestEmailRequest(BaseModel):
    to: str  # recipient for the one-off test send


class SendDigestsRequest(BaseModel):
    # Test mode: digest ONLY this user (still opt-in gated). Omitted = real mode:
    # every user with email_opt_in = true. user_id is never trusted for auth.
    user_id: str | None = None


def is_admin(user_id: str) -> bool:
    """Allowlist gate. Empty allowlist = locked (no one), so it fails closed."""
    return user_id in settings.admin_user_id_list


def _load_parsed(client, user_id: str) -> dict:
    rows = (
        client.table("profiles").select("parsed").eq("user_id", user_id).limit(1).execute().data
        or []
    )
    return (rows[0].get("parsed") if rows else None) or {}


@router.post("/fetch-jobs")
def fetch_jobs(caller_id: CurrentUserId, body: FetchRequest) -> dict:
    if not is_admin(caller_id):
        logger.warning("fetch-jobs denied: caller=%s not in admin allowlist", caller_id[:8])
        raise HTTPException(status_code=403, detail="Not authorized to trigger job fetches.")

    target_user_id = (body.user_id or caller_id).strip()
    client = get_service_client()
    parsed = _load_parsed(client, target_user_id)
    target_roles = [r for r in (parsed.get("target_roles") or []) if r.strip()]
    if not target_roles:
        return {
            "status": "no_keywords",
            "message": "That user has no target roles set, so there is nothing to search for yet.",
        }

    locations = [loc for loc in (parsed.get("locations") or []) if loc]
    criteria = SearchCriteria(
        keywords=target_roles,
        location=locations[0] if locations else None,
        remote_pref=parsed.get("remote_pref") or "",
        max_days_old=body.max_days_old,
        max_pages=body.max_pages,
    )
    logger.info(
        "fetch-jobs: admin=%s target=%s roles=%s location=%r remote_pref=%r",
        caller_id[:8],
        target_user_id[:8],
        target_roles[:3],
        criteria.location,
        criteria.remote_pref,
    )

    all_jobs: list[dict] = []
    sources_run: list[str] = []
    sources_failed: list[dict] = []
    raw_count = 0
    parse_failures = 0

    for source in SOURCES:
        try:
            result: FetchResult = source.fetch(criteria)
        except JobSourceError as exc:
            logger.error("source %s failed: %s", source.name, exc)
            sources_failed.append({"source": source.name, "error": str(exc)})
            continue
        except Exception as exc:  # never let one source 500 the whole fetch
            logger.exception("source %s crashed unexpectedly", source.name)
            sources_failed.append({"source": source.name, "error": f"unexpected: {exc}"})
            continue
        sources_run.append(source.name)
        raw_count += result.raw_count
        parse_failures += result.parse_failures
        all_jobs.extend(job.model_dump() for job in result.jobs)

    stored = upsert_jobs(client, all_jobs)
    shortlist = prefilter(parsed, all_jobs, cap=DEFAULT_CAP)
    logger.info(
        "fetch-jobs done: target=%s sources_run=%s failed=%s raw=%s parse_failures=%s stored=%s shortlist=%s",
        target_user_id[:8],
        sources_run,
        len(sources_failed),
        raw_count,
        parse_failures,
        stored,
        len(shortlist),
    )

    return {
        "status": "ok",
        "target_user": target_user_id[:8],
        "sources_run": sources_run,
        "sources_failed": sources_failed,
        "fetched_raw": raw_count,
        "parse_failures": parse_failures,
        "unique_stored": stored,
        "shortlist_count": len(shortlist),
        "shortlist": [
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location_display"),
                "remote": job.get("remote"),
                "source_url": job.get("source_url"),
                "posted_at": job.get("posted_at"),
                "prefilter_score": job.get("prefilter_score"),
            }
            for job in shortlist
        ],
    }


@router.post("/score-matches")
def score_matches(caller_id: CurrentUserId, body: ScoreMatchesRequest) -> dict:
    """M4: prefilter the target user's candidates from the shared pool, then
    LLM-score that shortlist into the per-user `matches` table. Does NOT re-fetch
    from sources (run /admin/fetch-jobs first to populate the pool). Same
    fail-closed admin gate as /admin/fetch-jobs."""
    if not is_admin(caller_id):
        logger.warning("score-matches denied: caller=%s not in admin allowlist", caller_id[:8])
        raise HTTPException(status_code=403, detail="Not authorized to trigger scoring.")

    target_user_id = (body.user_id or caller_id).strip()
    client = get_service_client()
    parsed = _load_parsed(client, target_user_id)
    target_roles = [r for r in (parsed.get("target_roles") or []) if r.strip()]
    if not target_roles:
        return {
            "status": "no_keywords",
            "message": "That user has no target roles set, so there is nothing to score against yet.",
        }

    # Candidate jobs from the shared pool (most recently fetched first), bounded.
    candidates = (
        client.table("jobs")
        .select(
            "id, source_url, title, company, location_display, location_area, "
            "remote, description, category, posted_at"
        )
        .order("fetched_at", desc=True)
        .limit(body.candidate_limit)
        .execute()
        .data
        or []
    )
    if not candidates:
        return {
            "status": "no_jobs",
            "message": "The jobs pool is empty for now — run /admin/fetch-jobs first.",
        }

    # Stage 1: cheap no-LLM prefilter → generous shortlist. Stage 2: LLM-score it.
    shortlist = prefilter(parsed, candidates, cap=DEFAULT_CAP)
    summary = score_shortlist(client, target_user_id, parsed, shortlist)
    logger.info(
        "score-matches done: admin=%s target=%s candidates=%s %s",
        caller_id[:8],
        target_user_id[:8],
        len(candidates),
        summary,
    )
    return {
        "status": "ok",
        "target_user": target_user_id[:8],
        "candidates": len(candidates),
        **summary,
    }


@router.post("/test-email")
def test_email(caller_id: CurrentUserId, body: TestEmailRequest) -> dict:
    """Send ONE test email via Resend to confirm backend email delivery works (M5
    step 3) — NOT the digest, just a fixed subject/body. ADMIN-GATED with the same
    fail-closed ADMIN_USER_IDS allowlist as fetch-jobs/score-matches: sending from
    our verified domain to an arbitrary address must not be open to any authenticated
    user (it would be a spam vector). Returns the helper's structured result
    (message id or error) so the operator can confirm or diagnose."""
    if not is_admin(caller_id):
        logger.warning("test-email denied: caller=%s not in admin allowlist", caller_id[:8])
        raise HTTPException(status_code=403, detail="Not authorized to send test email.")

    result = send_email(
        to=body.to,
        subject="JobOps test email",
        html=(
            "<p>This is a test email from JobOps. If it reached your inbox, "
            "backend email sending is working.</p>"
        ),
        text=(
            "This is a test email from JobOps. If it reached your inbox, "
            "backend email sending is working."
        ),
    )
    # result carries only status/id/error — no PII — so it is safe to log and return.
    logger.info("test-email: admin=%s status=%s", caller_id[:8], result.get("status"))
    return result


@router.post("/send-digests")
def send_digests(caller_id: CurrentUserId, body: SendDigestsRequest) -> dict:
    """M5 step 5: email each target user their unsent qualifying matches (score-only),
    then mark those sent. NO scheduler — this is the manual trigger. ADMIN-GATED with
    the same fail-closed ADMIN_USER_IDS allowlist as fetch-jobs/score-matches.

    Targets: a given `user_id` (test mode), else ALL users with email_opt_in = true.
    Each user is still double-gated inside send_user_digest (opt-in + score_threshold),
    so a targeted opted-out user is skipped, not emailed. LLM-free: surfaces
    already-scored matches, no Anthropic call."""
    if not is_admin(caller_id):
        logger.warning("send-digests denied: caller=%s not in admin allowlist", caller_id[:8])
        raise HTTPException(status_code=403, detail="Not authorized to send digests.")

    client = get_service_client()
    if body.user_id:
        targets = [body.user_id.strip()]
    else:
        rows = (
            client.table("preferences").select("user_id").eq("email_opt_in", True).execute().data
            or []
        )
        targets = [r["user_id"] for r in rows]

    results = [send_user_digest(client, uid) for uid in targets]
    sent = sum(1 for r in results if r.get("status") == "sent")
    logger.info(
        "send-digests done: admin=%s targeted=%s sent=%s", caller_id[:8], len(targets), sent
    )
    return {"status": "ok", "targeted": len(targets), "sent": sent, "results": results}
