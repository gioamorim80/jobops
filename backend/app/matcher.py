"""M4 — automated LLM scoring of a user's prefilter shortlist into `matches`.

Stage 2 of the funnel: the cheap no-LLM prefilter (M3) narrows the pool to a
generous shortlist; this scores that shortlist with the EXISTING honest scorer so
automated scores use the same rubric/logic as the on-demand flow. Differences by
design: it runs on Haiku 4.5 (cheap; Sonnet is reserved for on-demand tailoring)
and scores the ~500-char snippet rather than the full JD.

Cost architecture, all on from the start (first automated-LLM milestone):
- Haiku 4.5 for the scorer.
- Prompt caching: the rubric + profile prefix is identical for every job in a
  run, so it's marked with cache_control and only the per-job snippet is uncached.
- Each score logs to usage_log as action "match_score" (model-priced, cache-aware).
- The per-user daily LLM cap is respected: a run scores what fits and reports what
  it skipped, never failing hard.

The fit score stays PURE — recency/posted_at is never factored into it. posted_at
is carried onto the match row only so M5 can use recency as a separate signal.

Isolation: every write sets user_id explicitly (the service role bypasses RLS);
callers pass a user_id derived from a verified JWT, never request input.
"""

import json

from agents.scorer import SCORER_SYSTEM_PROMPT_V1
from fastapi import HTTPException

from app.applog import get_logger
from app.config import settings
from app.llm import run_cached_json_agent
from app.ondemand import _normalize_score  # reuse the EXACT on-demand scorer normalization
from app.usage import count_calls_today, log_call

logger = get_logger("jobops.matcher")

# Haiku for automated triage scoring. Sonnet stays reserved for on-demand tailoring.
MATCH_MODEL = "claude-haiku-4-5"
_SCORE_MAX_TOKENS = 1200


def score_band(fit: int) -> str:
    """Qualitative band for a 0–100 fit. Mirrors the frontend `fitBand` so an
    automated match reads with the same verdict as an on-demand score. The band
    describes fit quality only — it deliberately avoids the word "Stretch" so it
    never collides with the separate STRETCH decision label."""
    if fit >= 80:
        return "Strong fit"
    if fit >= 65:
        return "Solid fit"
    if fit >= 50:
        return "Moderate fit"
    return "Likely skip"


def score_shortlist(client, user_id: str, parsed: dict, shortlist: list[dict]) -> dict:
    """Score each shortlisted job not already scored for this user, writing one
    `matches` row each. Returns a summary (counts + cache token totals so caching
    is observable). `shortlist` items are `jobs`-pool rows (they carry `id` and
    `posted_at`)."""
    job_ids = [job["id"] for job in shortlist if job.get("id")]
    already: set[str] = set()
    if job_ids:
        rows = (
            client.table("matches")
            .select("job_id")
            .eq("user_id", user_id)
            .in_("job_id", job_ids)
            .execute()
            .data
            or []
        )
        already = {row["job_id"] for row in rows}

    to_score = [job for job in shortlist if job.get("id") and job["id"] not in already]

    # Cost guardrail: score only what fits under today's per-user cap; skip the
    # rest and report it, rather than failing the run.
    used = count_calls_today(client, user_id)
    remaining = max(0, settings.per_user_daily_llm_cap - used)
    will_score = to_score[:remaining]
    skipped_cap = len(to_score) - len(will_score)

    # The rubric + profile prefix is constant across every job in this run, so it
    # is cached; only the per-job snippet (the user turn) is uncached.
    profile_block = f"USER PROFILE (JSON):\n{json.dumps(parsed)}"
    system_blocks = [
        {"type": "text", "text": SCORER_SYSTEM_PROMPT_V1},
        {"type": "text", "text": profile_block, "cache_control": {"type": "ephemeral"}},
    ]

    scored = 0
    failed = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    for job in will_score:
        snippet = (job.get("description") or "").strip()
        try:
            raw, usage = run_cached_json_agent(
                system_blocks,
                f"JOB POSTING:\n{snippet}",
                max_tokens=_SCORE_MAX_TOKENS,
                model=MATCH_MODEL,
                temperature=0,  # deterministic, same as the on-demand scorer
            )
        except HTTPException as exc:
            failed += 1
            logger.warning("match score failed for job=%s: %s", job["id"], exc.detail)
            continue

        log_call(client, user_id, "match_score", usage, model=MATCH_MODEL)
        cache_read_tokens += int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_write_tokens += int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

        score = _normalize_score(raw)
        client.table("matches").upsert(
            {
                "user_id": user_id,
                "job_id": job["id"],
                "score": score["fit"],
                "band": score_band(score["fit"]),
                "decision": score[
                    "decision"
                ],  # the scorer's holistic call (not derived from score)
                "cleared": score["cleared"],
                "gaps": score["gaps"],
                "analysis": score["pitch"],  # one honest line; recency NOT in the score
                "posted_at": job.get("posted_at"),
                "model": MATCH_MODEL,
            },
            on_conflict="user_id,job_id",
        ).execute()
        scored += 1

    logger.info(
        "score_shortlist: user=%s shortlist=%s already=%s scored=%s failed=%s skipped_cap=%s "
        "cache_read=%s cache_write=%s",
        user_id[:8],
        len(shortlist),
        len(already),
        scored,
        failed,
        skipped_cap,
        cache_read_tokens,
        cache_write_tokens,
    )
    return {
        "shortlist_count": len(shortlist),
        "already_scored": len(already),
        "scored": scored,
        "failed": failed,
        "skipped_for_cap": skipped_cap,
        "model": MATCH_MODEL,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
    }
