# STATE — where the build is

## Current milestone: M1 — Auth + onboarding → profile (in progress)

## M0 — Bootstrap the monorepo ✅ COMPLETE & VERIFIED LIVE
Verified in production: Vercel frontend → Railway backend → live Anthropic call.
The deployed landing page hits `/agent/ping` and renders a real model response.
Acceptance criterion met. Next.js later patched to 15.5.19 (security fix).

### M0 scope (done)
- Monorepo scaffolded: `/frontend` (Next.js App Router + TS), `/backend` (FastAPI,
  managed with `uv`), `/supabase` (empty `migrations/` + README; schema lands in M1).
- Backend endpoints:
  - `GET /health` → `{"status":"ok"}`.
  - `GET /agent/ping` → real Anthropic call using `ANTHROPIC_API_KEY` +
    `ANTHROPIC_MODEL` (default `claude-sonnet-4-6`), returns the model's text.
    Missing key → graceful 503. Keys read from env only, never hardcoded.
- Frontend: single landing page that calls the backend `/agent/ping` and renders
  the live model response (reads `NEXT_PUBLIC_BACKEND_URL`).
- Dev tooling: `pre-commit install` done; `pre-commit run --all-files` passes
  (hygiene, `detect-private-key`, `gitleaks`, `ruff` + `ruff-format`). Prettier +
  `lint`/`format`/`format:check` scripts added to the frontend.
- CI (`.github/workflows/ci.yml`) extended: `quality` (pre-commit), `backend`
  (uv sync + pytest), `frontend` (npm install + prettier check + lint + build).
- Verified locally: `uv run pytest` (3 passed), `ruff` clean, frontend
  `format:check`/`lint`/`build` all green, uvicorn boots and serves both endpoints.

### Deploy (done)
- Backend live on Railway; frontend live on Vercel; both green. `ANTHROPIC_API_KEY`
  set in Railway; `NEXT_PUBLIC_BACKEND_URL` set in Vercel; CORS allows the Vercel
  origin. End-to-end `/agent/ping` confirmed working in production.

### Next: M1 — Auth + onboarding chat → profile
- Supabase magic-link auth in the frontend.
- `profiles`, `preferences` tables + RLS (`user_id = auth.uid()`) — see
  `docs/DATA_MODEL.md`. First SQL migrations land in `/supabase/migrations/`.
- Onboarding agent (`docs/agents/ONBOARDING.md`): resume upload → parse → gap
  questions in chat → confirm → write profile. Settings screen (alert freq +
  score threshold). Verify tenant isolation with two accounts before calling done.

### Blockers
- None. To finish M0's acceptance criterion, deploy both apps and set env vars.
