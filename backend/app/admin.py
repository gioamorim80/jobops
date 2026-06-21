"""Manual job-fetch trigger (M3) — no scheduler, runs for one user on demand.

POST /admin/fetch-jobs fetches per-user from each enabled source (built from that
user's profile keywords), dedupes into the shared `jobs` pool, and returns a
generous no-LLM prefilter shortlist. There are NO LLM calls in this milestone.

SECURITY: triggering external API calls and writing the shared pool must not be
open to any authenticated user. The caller's verified-JWT user_id is checked
against the ADMIN_USER_IDS allowlist; an empty allowlist means no one is allowed
(fail closed). Admins may run a fetch for themselves or, for the per-user pattern,
for a given user_id.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.applog import get_logger
from app.auth import CurrentUserId
from app.config import settings
from app.dedupe import upsert_jobs
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
        remote=(parsed.get("remote_pref") or "").lower() == "remote",
        max_days_old=body.max_days_old,
        max_pages=body.max_pages,
    )
    logger.info(
        "fetch-jobs: admin=%s target=%s roles=%s location=%r remote=%s",
        caller_id[:8],
        target_user_id[:8],
        target_roles[:3],
        criteria.location,
        criteria.remote,
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
