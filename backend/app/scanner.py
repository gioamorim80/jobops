"""M5 — the per-user scanner: fetch fresh jobs for a user, then score them into the
user's `matches`. The per-user fetch+score that M3/M4 exposed as admin endpoints
lives here as reusable cores so it runs for ONE user (the admin endpoints) or for ALL
opted-in users (scan_all_opted_in — the building block the scheduler will call).

Cost controls the scanner already respects are preserved: the no-LLM prefilter funnel
and the per-user daily LLM cap enforced inside score_shortlist. NOT YET here (later
commits in M5 step 6): the global budget ceiling kill-switch and the 15-day
inactivity pause.
"""

from app.applog import get_logger
from app.dedupe import upsert_jobs
from app.matcher import score_shortlist
from app.prefilter import DEFAULT_CAP, prefilter
from app.sources.adzuna import AdzunaSource
from app.sources.base import FetchResult, JobSource, JobSourceError, SearchCriteria
from app.usage import is_over_monthly_budget

logger = get_logger("jobops.scanner")

# Source registry: enabling/disabling a source is a one-line change here, not a change
# scattered through the codebase.
SOURCES: list[JobSource] = [AdzunaSource()]

# Pool columns the scorer needs (the score-from-pool candidate select).
_CANDIDATE_COLUMNS = (
    "id, source_url, title, company, location_display, location_area, "
    "remote, description, category, posted_at"
)


def load_parsed(client, user_id: str) -> dict:
    """The user's parsed profile (skills/roles/locations/remote_pref), or {}."""
    rows = (
        client.table("profiles").select("parsed").eq("user_id", user_id).limit(1).execute().data
        or []
    )
    return (rows[0].get("parsed") if rows else None) or {}


def target_roles_of(parsed: dict) -> list[str]:
    """Non-empty target roles — the precondition for scanning (no roles => nothing
    to search/score for)."""
    return [r for r in (parsed.get("target_roles") or []) if r.strip()]


def _build_criteria(parsed: dict, max_days_old: int, max_pages: int) -> SearchCriteria:
    locations = [loc for loc in (parsed.get("locations") or []) if loc]
    return SearchCriteria(
        keywords=target_roles_of(parsed),
        location=locations[0] if locations else None,
        remote_pref=parsed.get("remote_pref") or "",
        max_days_old=max_days_old,
        max_pages=max_pages,
    )


def fetch_into_pool(client, parsed: dict, max_days_old: int, max_pages: int) -> dict:
    """Fetch per-user from each enabled source and dedupe into the shared `jobs` pool.
    One source failing is logged and skipped — never aborts the others or the run.
    No LLM here. Returns the fetched jobs + counts."""
    criteria = _build_criteria(parsed, max_days_old, max_pages)
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
    return {
        "all_jobs": all_jobs,
        "sources_run": sources_run,
        "sources_failed": sources_failed,
        "raw_count": raw_count,
        "parse_failures": parse_failures,
        "stored": stored,
    }


def score_from_pool(client, user_id: str, parsed: dict, candidate_limit: int) -> dict:
    """Prefilter the user's candidates from the shared pool (no LLM) → LLM-score the
    shortlist into the per-user `matches`. score_shortlist enforces the per-user daily
    LLM cap and skips jobs already scored for this user. Returns the candidate count
    plus the score summary; candidates=0 when the pool is empty."""
    candidates = (
        client.table("jobs")
        .select(_CANDIDATE_COLUMNS)
        .order("fetched_at", desc=True)
        .limit(candidate_limit)
        .execute()
        .data
        or []
    )
    shortlist = prefilter(parsed, candidates, cap=DEFAULT_CAP)
    summary = score_shortlist(client, user_id, parsed, shortlist)
    return {"candidates": len(candidates), **summary}


def scan_user(
    client,
    user_id: str,
    *,
    max_days_old: int = 30,
    max_pages: int = 2,
    candidate_limit: int = 500,
) -> dict:
    """Fetch fresh jobs for ONE user, then score them into that user's matches — the
    automated equivalent of /admin/fetch-jobs then /admin/score-matches for that user.
    Per-user cost controls (prefilter + daily cap) are preserved. Returns a per-user
    result dict; the no-roles case is a skip, not an error."""
    parsed = load_parsed(client, user_id)
    if not target_roles_of(parsed):
        return {"user": user_id[:8], "status": "skipped_no_roles"}

    fetch = fetch_into_pool(client, parsed, max_days_old, max_pages)
    score = score_from_pool(client, user_id, parsed, candidate_limit)
    result = {
        "user": user_id[:8],
        "status": "ok",
        "stored": fetch["stored"],
        "sources_failed": len(fetch["sources_failed"]),
        "candidates": score["candidates"],
        "scored": score.get("scored", 0),
        "already_scored": score.get("already_scored", 0),
        "skipped_for_cap": score.get("skipped_for_cap", 0),
        "failed": score.get("failed", 0),
    }
    logger.info("scan_user done: user=%s %s", user_id[:8], result)
    return result


def scan_all_opted_in(client) -> dict:
    """Run scan_user for every user with email_opt_in = true.

    BUDGET KILL-SWITCH: the scanner is the only LLM-spending path, so it honors the
    global month-to-date ceiling (is_over_monthly_budget / MONTHLY_BUDGET_CEILING_USD).
    Checked at the top (skip the whole run when already over) AND before each user (a
    long multi-user run can cross the ceiling mid-way — stop scoring the rest rather
    than blow well past it). The ceiling value already carries headroom for
    cost_estimate under-counting, so we just honor the boolean — no extra math. This
    gates ONLY scoring; the LLM-free digest is never gated by the budget.

    One user's failure is captured and the loop continues — a single bad profile/source
    must not abort the run. Returns a summary: {status, scanned, stopped_on_budget,
    results}."""
    if is_over_monthly_budget(client):
        logger.warning(
            "scan-all SKIPPED: monthly budget ceiling reached — no scoring this run "
            "(digest still runs on existing matches)"
        )
        return {"status": "budget_exceeded", "scanned": 0, "stopped_on_budget": True, "results": []}

    rows = (
        client.table("preferences").select("user_id").eq("email_opt_in", True).execute().data or []
    )
    user_ids = [r["user_id"] for r in rows]

    results: list[dict] = []
    stopped_on_budget = False
    for uid in user_ids:
        # Re-check before each user's scoring: stop the moment the ceiling is crossed.
        if is_over_monthly_budget(client):
            logger.warning(
                "scan-all STOPPED mid-run: budget ceiling reached after %s user(s) — "
                "remaining users skipped this run",
                len(results),
            )
            stopped_on_budget = True
            break
        try:
            results.append(scan_user(client, uid))
        except Exception as exc:  # isolate per-user failures; keep scanning the rest
            logger.exception("scan_user crashed for user=%s", uid[:8])
            results.append({"user": uid[:8], "status": "error", "error": str(exc)})

    logger.info(
        "scan_all_opted_in done: scanned=%s stopped_on_budget=%s", len(results), stopped_on_budget
    )
    return {
        "status": "budget_exceeded" if stopped_on_budget else "ok",
        "scanned": len(results),
        "stopped_on_budget": stopped_on_budget,
        "results": results,
    }
