"""Per-user usage logging + daily LLM-call cap (cost guardrail).

We never log raw resume/profile/job text — only token counts and a coarse cost
estimate, one row per agent call.
"""

from datetime import UTC, datetime
from typing import Any

from supabase import Client

# Coarse USD-per-token estimates for the cost log (a logging estimate, not
# billing). Per-model (input, output) price per token; default = Sonnet 4.6.
_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0 / 1_000_000, 15.0 / 1_000_000),
    "claude-haiku-4-5": (1.0 / 1_000_000, 5.0 / 1_000_000),
}
_DEFAULT_PRICING = _PRICING["claude-sonnet-4-6"]
# Prompt-cache multipliers on the input price: reads ~0.1x, writes ~1.25x.
_CACHE_READ_MULT = 0.1
_CACHE_WRITE_MULT = 1.25


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


def log_call(
    client: Client, user_id: str, action: str, usage: Any, *, model: str | None = None
) -> None:
    """Log one agent call. `model` selects pricing (default Sonnet). Prompt-cache
    tokens are priced at their discounted multipliers, so a cached match_score row
    shows a much smaller cost_estimate than an uncached one — making the Haiku +
    caching savings visible. `tokens_in` records the full input the model saw
    (fresh input + cache reads + cache writes)."""
    price_in, price_out = _PRICING.get(model or "", _DEFAULT_PRICING)
    fresh_in = int(getattr(usage, "input_tokens", 0) or 0)
    tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cost = (
        fresh_in * price_in
        + cache_write * price_in * _CACHE_WRITE_MULT
        + cache_read * price_in * _CACHE_READ_MULT
        + tokens_out * price_out
    )
    client.table("usage_log").insert(
        {
            "user_id": user_id,
            "action": action,
            "tokens_in": fresh_in + cache_read + cache_write,
            "tokens_out": tokens_out,
            "cost_estimate": round(cost, 6),
        }
    ).execute()
