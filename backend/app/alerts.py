"""M5 step 4 — sent-state helpers over `alerts_log`, so the digest never emails the
same match to the same user twice.

Two helpers, both per-user scoped:
- unsent_matches_for_user: the digest's "what to send" query — the user's matches
  that clear the SAME threshold gate `/matches` uses (score >= the user's
  score_threshold, inclusive, default 60) AND have no alerts_log row yet.
- mark_matches_sent: service-role insert of one alerts_log row per (user, match),
  idempotent against the UNIQUE(user_id, match_id) constraint (ON CONFLICT DO
  NOTHING), so a race or double-call is a safe no-op.

These take the Supabase client as their first arg (like matcher.score_shortlist):
the digest passes a service-role client. Writes are service-role only by design
(alerts_log grants no write policy to authenticated — see migration 0011). Every
query is scoped to the passed user_id, which callers derive from a verified JWT —
never request input — so there is no cross-user leakage of matches or send history.
"""

from app.applog import get_logger

logger = get_logger("jobops.alerts")

# The default surfacing threshold when a user has no preferences row. Mirrors
# preferences.score_threshold's default (migration 0001 / onboarding.PreferencesIn)
# and the /matches gate. The RULE itself (score >= the user's threshold, inclusive)
# lives once here in unsent_matches_for_user, which the digest reuses rather than
# re-deriving — so the two surfaces can never disagree.
DEFAULT_SCORE_THRESHOLD = 60


def _effective_threshold(client, user_id: str) -> int:
    """The user's score_threshold from preferences, or the default if unset."""
    rows = (
        client.table("preferences")
        .select("score_threshold")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if rows and rows[0].get("score_threshold") is not None:
        return int(rows[0]["score_threshold"])
    return DEFAULT_SCORE_THRESHOLD


def unsent_matches_for_user(client, user_id: str) -> list[dict]:
    """The matches to email this user now: above their score_threshold (the same
    inclusive gate `/matches` applies) and not already in alerts_log. Highest fit
    first. Scoped to user_id — never another user's matches or send history."""
    threshold = _effective_threshold(client, user_id)
    # Embed the job's role/company/link so a consumer (the digest) can label each
    # match without a second query — same `jobs(...)` embed `/matches` uses.
    matches = (
        client.table("matches")
        .select(
            "id, job_id, score, band, decision, analysis, posted_at, "
            "jobs ( title, company, source_url )"
        )
        .eq("user_id", user_id)
        .gte("score", threshold)
        .order("score", desc=True)
        .execute()
        .data
        or []
    )
    if not matches:
        return []

    sent_rows = (
        client.table("alerts_log").select("match_id").eq("user_id", user_id).execute().data or []
    )
    already_sent = {row["match_id"] for row in sent_rows}
    unsent = [m for m in matches if m["id"] not in already_sent]
    logger.info(
        "unsent_matches: user=%s threshold=%s above=%s already_sent=%s unsent=%s",
        user_id[:8],
        threshold,
        len(matches),
        len(already_sent),
        len(unsent),
    )
    return unsent


def mark_matches_sent(client, user_id: str, match_ids: list[str], channel: str = "email") -> int:
    """Record (user, match) as sent — one alerts_log row each. Idempotent: uses
    upsert ON CONFLICT DO NOTHING against UNIQUE(user_id, match_id), so re-marking an
    already-sent match (race / double-call) is a no-op, never a crash. Returns the
    number of rows newly inserted (0 if all were already present)."""
    if not match_ids:
        return 0
    rows = [
        {"user_id": user_id, "match_id": match_id, "channel": channel} for match_id in match_ids
    ]
    inserted = (
        client.table("alerts_log")
        .upsert(rows, on_conflict="user_id,match_id", ignore_duplicates=True)
        .execute()
        .data
        or []
    )
    logger.info(
        "mark_matches_sent: user=%s requested=%s inserted=%s",
        user_id[:8],
        len(rows),
        len(inserted),
    )
    return len(inserted)
