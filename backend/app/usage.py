"""Per-user usage logging + daily LLM-call cap (cost guardrail).

We never log raw resume/profile/job text — only token counts and a coarse cost
estimate, one row per agent call.
"""

from datetime import UTC, datetime
from typing import Any

from app.config import settings
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


def _month_start_iso() -> str:
    """Start of the current calendar month at 00:00 UTC — the UTC equivalent of
    Postgres `date_trunc('month', now())`. Monthly caps and the budget query share
    this window, so they reset on the 1st (not a rolling 30 days)."""
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
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


def count_calls_this_month(client: Client, user_id: str, action: str) -> int:
    """How many calls of `action` this user has logged since the 1st of the current
    calendar month (UTC). Always per-action so the score and tailor monthly caps are
    independent: a user who has exhausted their score cap can still tailor, and vice
    versa. Rows from a previous month fall outside the `created_at >= month start`
    window, so they never consume this month's allowance."""
    return (
        client.table("usage_log")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("action", action)
        .gte("created_at", _month_start_iso())
        .execute()
        .count
        or 0
    )


def total_cost_this_month(client: Client) -> float:
    """Sum of `cost_estimate` across ALL users for the current calendar month (UTC).
    cost_estimate is a coarse logging estimate that UNDER-counts real spend
    (~15–18% low), so a ceiling compared against it should carry deliberate headroom."""
    rows = (
        client.table("usage_log")
        .select("cost_estimate")
        .gte("created_at", _month_start_iso())
        .execute()
        .data
        or []
    )
    return round(sum(float(row.get("cost_estimate") or 0) for row in rows), 6)


def is_over_monthly_budget(client: Client) -> bool:
    """Whether global month-to-date spend exceeds MONTHLY_BUDGET_CEILING_USD.

    BUILT BUT NOT YET CONSUMED. Nothing calls this to block work yet: there is no
    automated scanner to pause, and the on-demand paths are gated by the per-user
    caps instead. This is the kill-switch for the M5 digest scanner — wire it there
    (skip/pause the scheduled scan when this is True) in a later M5 step. It lives
    here, tested and ready, so that wiring is a one-liner.

    The ceiling is set BELOW the real ~$20 Anthropic budget on purpose: cost_estimate
    under-counts actual spend (~15–18% low), so the gap is deliberate headroom that
    keeps the real bill under budget once this eventually gates."""
    return total_cost_this_month(client) > settings.monthly_budget_ceiling_usd


def log_call(
    client: Client, user_id: str, action: str, usage: Any, *, model: str | None = None
) -> None:
    """Log one agent call. `model` selects pricing (default Sonnet). Prompt-cache
    tokens are priced at their discounted multipliers, so a cached match_score row
    shows a much smaller cost_estimate than an uncached one — making the Haiku +
    caching savings visible. `tokens_in` records the full input the model saw
    (fresh input + cache reads + cache writes). The resolved model (the explicit
    one passed, else the configured default that actually ran) is stored too."""
    # Same value used for pricing is the value we persist — never re-derived: a
    # caller that named a model (e.g. the Haiku matcher) gets that; callers that
    # omit it ran on the configured default (settings.anthropic_model), which is
    # exactly what llm.py uses for those calls.
    resolved_model = model or settings.anthropic_model
    price_in, price_out = _PRICING.get(resolved_model, _DEFAULT_PRICING)
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
            "model": resolved_model,
            "tokens_in": fresh_in + cache_read + cache_write,
            "tokens_out": tokens_out,
            "cost_estimate": round(cost, 6),
        }
    ).execute()
