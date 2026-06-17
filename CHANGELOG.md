# CHANGELOG

## 2026-06-17 — M0: Bootstrap the monorepo
- **What:** Scaffolded the monorepo. `/backend` (FastAPI via `uv`) with
  `GET /health` and `GET /agent/ping` (real Anthropic call, model + key from env).
  `/frontend` (Next.js App Router + TypeScript) single landing page that calls
  `/agent/ping` and renders the live model response. `/supabase` with an empty
  `migrations/` and a README noting schema arrives in M1.
- **Tooling:** `pre-commit install`; `pre-commit run --all-files` passes. Added
  Prettier + `lint`/`format`/`format:check` to the frontend. Extended
  `.github/workflows/ci.yml` with `backend` (uv + pytest) and `frontend`
  (npm install + prettier check + lint + build) jobs alongside `quality`.
- **Verified:** backend tests (3 passed), ruff clean, frontend build/lint/format
  green, uvicorn serves both endpoints (`/agent/ping` returns a graceful 503 with
  no key configured).
- **Decisions:** Python deps managed with `uv` (`pyproject.toml` + `uv.lock`,
  run via `uv run`); Python pinned to 3.11. Agent model read from `ANTHROPIC_MODEL`
  (default `claude-sonnet-4-6` per the stack), key from `ANTHROPIC_API_KEY` — never
  hardcoded. Backend never logs raw secrets.
- **Next:** Deploy frontend→Vercel and backend→Railway to satisfy M0's "live"
  acceptance criterion, then start **M1** (auth + onboarding chat → profile).
