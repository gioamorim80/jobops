"""Per-user usage logging + daily LLM-call cap (cost guardrail).

We never log raw resume/profile/job text — only token counts and a coarse cost
estimate, one row per agent call.
"""

from datetime import UTC, datetime
from typing import Any

from supabase import Client

# Coarse USD-per-token estimate for the cost log (defaults to Sonnet 4.6 pricing:
# $3 / 1M input, $15 / 1M output). This is a logging estimate, not billing.
_PRICE_IN = 3.0 / 1_000_000
_PRICE_OUT = 15.0 / 1_000_000


def _today_start_iso() -> str:
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat()


def count_calls_today(client: Client, user_id: str, action: str | None = None) -> int:
    """How many agent calls this user has logged since 00:00 UTC. Pass `action`
    to count only one kind of call (e.g. 'enrich'), so a per-feature cap isn't
    polluted by other features' calls."""
    query = (
        client.table("usage_log")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("created_at", _today_start_iso())
    )
    if action is not None:
        query = query.eq("action", action)
    return query.execute().count or 0


def log_call(client: Client, user_id: str, action: str, usage: Any) -> None:
    tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
    tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
    cost = tokens_in * _PRICE_IN + tokens_out * _PRICE_OUT
    client.table("usage_log").insert(
        {
            "user_id": user_id,
            "action": action,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_estimate": round(cost, 6),
        }
    ).execute()
