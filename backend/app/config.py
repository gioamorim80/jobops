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

    # --- Guardrails ---
    per_user_daily_llm_cap: int = 25

    # --- CORS: comma-separated list of allowed frontend origins ---
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
