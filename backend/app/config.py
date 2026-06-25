"""Runtime configuration, read from the environment (never hardcoded).

Locally, values come from a `.env` file in the backend directory (copy it from
the root `.env.example`). In production they come from the Railway dashboard.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Anthropic (the agent brain) ---
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"

    # --- Supabase (backend uses the SERVICE ROLE key only — never the anon key) ---
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    resume_bucket: str = "resumes"

    # --- Email (Resend) — the backend's transactional/digest sender ---
    # resend_api_key is a SECRET, handled exactly like anthropic_api_key: no real
    # default, read from env, never logged. alert_from_email is the verified sender
    # on our Resend domain (e.g. noreply@myjobops.app).
    resend_api_key: str | None = None
    alert_from_email: str | None = None

    # --- Job sources (M3) ---
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    # Comma-separated Supabase user UUIDs allowed to trigger a manual job fetch.
    # Empty = locked (no one can trigger) — fail closed.
    admin_user_ids: str = ""

    # --- Guardrails ---
    # Daily LLM-call cap across ALL of one user's agent actions. With the per-user
    # MONTHLY caps below now doing cost-fairness, this is purely a runaway/abuse
    # brake, so it's generous.
    # NOTE FOR THE OPERATOR: prod (Railway) currently sets PER_USER_DAILY_LLM_CAP=50
    # as an env var, which OVERRIDES this default. Raise it to 100 or remove the env
    # var, otherwise the stale value wins and the new default has no effect.
    per_user_daily_llm_cap: int = 100
    # Per-user MONTHLY caps (calendar month, reset on the 1st, UTC). Separate caps so
    # scoring and tailoring never compete: hitting one does not block the other. Both
    # coexist with the daily brake — a call proceeds only if it clears BOTH the daily
    # cap AND the relevant monthly cap.
    per_user_monthly_score_cap: int = 50
    per_user_monthly_tailor_cap: int = 10
    # Global month-to-date budget ceiling (USD) across ALL users. BUILT BUT INERT for
    # now (see usage.is_over_monthly_budget) — nothing consumes it yet; it is wired to
    # the digest scanner in a later M5 step. Set BELOW the real ~$20 Anthropic budget
    # on purpose: logged cost_estimate under-counts actual spend (~15–18% low), so the
    # headroom keeps the real bill under budget once this eventually gates.
    monthly_budget_ceiling_usd: float = 15.0
    # Coach chat turns are very cheap (~0.6¢ each); this cap only deters abuse,
    # so it's generous and counts ONLY enrich turns (one user message = one turn).
    enrich_daily_turn_cap: int = 50
    # Max matches included in one digest email (top-N by score). The rest stay unsent
    # and surface in the next run.
    digest_max_matches: int = 5

    # --- CORS: comma-separated list of allowed frontend origins ---
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def admin_user_id_list(self) -> list[str]:
        return [uid.strip() for uid in self.admin_user_ids.split(",") if uid.strip()]


settings = Settings()
