"""Manual, admin-gated triggers (no scheduler yet) — the scanner/digest building
blocks, runnable on demand for one user or all opted-in users.

POST /admin/fetch-jobs   (M3) fetches per-user from each enabled source, dedupes
                         into the shared `jobs` pool, returns a no-LLM prefilter
                         shortlist. No LLM calls.
POST /admin/score-matches (M4) prefilters the user's candidates from the pool and
                         LLM-scores that shortlist into the per-user `matches`
                         table (Haiku + prompt caching; logged as "match_score").
POST /admin/scan-all     (M5 step 6) runs the per-user fetch+score for EVERY opted-in
                         user (scanner.scan_all_opted_in). The manual stand-in for
                         the scheduler; no budget gate / inactivity pause yet.

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
from app.digest import send_user_digest
from app.mailer import send_email
from app.prefilter import DEFAULT_CAP, prefilter
from app.scanner import (
    fetch_into_pool,
    load_parsed,
    scan_all_opted_in,
    score_from_pool,
    target_roles_of,
)
from app.supabase_client import get_service_client

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger("jobops.admin")


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


@router.post("/fetch-jobs")
def fetch_jobs(caller_id: CurrentUserId, body: FetchRequest) -> dict:
    if not is_admin(caller_id):
        logger.warning("fetch-jobs denied: caller=%s not in admin allowlist", caller_id[:8])
        raise HTTPException(status_code=403, detail="Not authorized to trigger job fetches.")

    target_user_id = (body.user_id or caller_id).strip()
    client = get_service_client()
    parsed = load_parsed(client, target_user_id)
    if not target_roles_of(parsed):
        return {
            "status": "no_keywords",
            "message": "That user has no target roles set, so there is nothing to search for yet.",
        }

    logger.info("fetch-jobs: admin=%s target=%s", caller_id[:8], target_user_id[:8])
    fetch = fetch_into_pool(client, parsed, body.max_days_old, body.max_pages)
    shortlist = prefilter(parsed, fetch["all_jobs"], cap=DEFAULT_CAP)
    logger.info(
        "fetch-jobs done: target=%s sources_run=%s failed=%s raw=%s stored=%s shortlist=%s",
        target_user_id[:8],
        fetch["sources_run"],
        len(fetch["sources_failed"]),
        fetch["raw_count"],
        fetch["stored"],
        len(shortlist),
    )

    return {
        "status": "ok",
        "target_user": target_user_id[:8],
        "sources_run": fetch["sources_run"],
        "sources_failed": fetch["sources_failed"],
        "fetched_raw": fetch["raw_count"],
        "parse_failures": fetch["parse_failures"],
        "unique_stored": fetch["stored"],
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
    parsed = load_parsed(client, target_user_id)
    if not target_roles_of(parsed):
        return {
            "status": "no_keywords",
            "message": "That user has no target roles set, so there is nothing to score against yet.",
        }

    score = score_from_pool(client, target_user_id, parsed, body.candidate_limit)
    if score["candidates"] == 0:
        return {
            "status": "no_jobs",
            "message": "The jobs pool is empty for now — run /admin/fetch-jobs first.",
        }

    candidates = score["candidates"]
    summary = {k: v for k, v in score.items() if k != "candidates"}
    logger.info(
        "score-matches done: admin=%s target=%s candidates=%s %s",
        caller_id[:8],
        target_user_id[:8],
        candidates,
        summary,
    )
    return {
        "status": "ok",
        "target_user": target_user_id[:8],
        "candidates": candidates,
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


@router.post("/scan-all")
def scan_all(caller_id: CurrentUserId) -> dict:
    """M5 step 6 (commit 1): run the per-user fetch+score for EVERY opted-in user —
    the manual trigger for what the scheduler will later run on a timer. NO scheduler,
    NO budget gate, NO inactivity pause yet. ADMIN-GATED with the same fail-closed
    ADMIN_USER_IDS allowlist. One user's failure is isolated and never aborts the run
    (see scan_all_opted_in). The scanner's existing per-user cost controls (no-LLM
    prefilter + the daily LLM cap in score_shortlist) still apply."""
    if not is_admin(caller_id):
        logger.warning("scan-all denied: caller=%s not in admin allowlist", caller_id[:8])
        raise HTTPException(status_code=403, detail="Not authorized to trigger scanning.")

    client = get_service_client()
    summary = scan_all_opted_in(client)
    results = summary["results"]
    scanned_ok = sum(1 for r in results if r.get("status") == "ok")
    total_scored = sum(r.get("scored", 0) for r in results)
    logger.info(
        "scan-all done: admin=%s status=%s users=%s scanned_ok=%s scored=%s stopped_on_budget=%s",
        caller_id[:8],
        summary["status"],
        len(results),
        scanned_ok,
        total_scored,
        summary["stopped_on_budget"],
    )
    return {
        "status": summary["status"],  # "ok" | "budget_exceeded"
        "users": len(results),
        "scanned": scanned_ok,
        "scored": total_scored,
        "paused_now": summary.get("paused_now", 0),
        "skipped_paused": summary.get("skipped_paused", 0),
        "unpaused": summary.get("unpaused", 0),
        "stopped_on_budget": summary["stopped_on_budget"],
        "results": results,
    }
