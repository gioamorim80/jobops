# CHANGELOG

## 2026-06-18 — M1 polish: "Chic Trancoso" restyle + inline profile editing
- **Design (frontend only):** rebuilt the design system around a calm, boutique
  aesthetic — warm-ivory + soft-lavender base, deep forest-green accent used
  sparingly, soft purple for focus/secondary touches. Serif display (Fraunces) +
  humanist sans (Inter), smaller/lighter type scale, generous whitespace, pill
  buttons, hairline borders, soft shadows, page-wide soft purple wash. No
  tropical motifs. Tokens in `globals.css`; reusable classes applied across
  landing, login, onboarding, dashboard, settings. Responsive (clamp type,
  auto-fit grids, mobile media query); accessible focus rings; spinner uses
  currentColor so it reads on both buttons and light backgrounds. Loading/empty/
  error states restyled.
- **UX fix — edit profile without re-uploading:** Settings is now a full
  Profile & settings editor (name, target roles, seniority, locations, remote
  pref, skills, domains + alert frequency + score threshold). Dashboard "Edit
  profile" → Settings; résumé replacement is a separate, optional action.
- **Backend (additive only):** new `POST /onboarding/profile` updates the
  current user's profile fields + preferences and never touches
  `raw_resume_text` / `resume_file_path` / `onboarding_complete`. user_id comes
  from the verified JWT only (same security pattern). Validated via Pydantic.
- **Unchanged:** auth, RLS, storage policies, the onboarding agent, existing API
  contracts, env handling, and the schema. No migration and no new env var.
- **Verified:** 9 backend tests pass, ruff + pre-commit clean, frontend
  build/lint/format green, prod server renders the restyled pages.

## 2026-06-18 — M1: auth + lightweight onboarding → structured profile
- **What:** Multi-tenant auth and onboarding, RLS from line one.
  - Migration `0001_m1_profiles_preferences.sql`: `profiles` + `preferences`
    with RLS (`user_id = auth.uid()`), `updated_at` trigger, and a PRIVATE
    `resumes` storage bucket with per-user storage RLS (folder = uid).
  - Frontend: Supabase magic-link auth (`@supabase/ssr`), protected app shell
    via middleware + `(app)` layout, login/callback/signout routes. Anon key only.
  - Onboarding: upload resume to the private bucket → backend extracts text
    (service role) → onboarding agent produces an extraction-only draft (never
    invents) → user reviews/edits + answers 3 gap questions → confirm saves
    `profiles.parsed` + `preferences`. Raw resume text stored under RLS, never
    logged, sent only to the Anthropic onboarding call.
  - Settings: alert frequency + score threshold (default 60).
  - Cohesive dark design system (Inter, tokens, components), responsive, with
    loading/empty/error states.
- **Backend:** `auth.py` (user_id from verified JWT only), `supabase_client.py`
  (service role only), `resume.py` (PDF/DOCX), `onboarding.py` routes,
  `agents/onboarding.py` (versioned prompt). uv deps: supabase, pypdf, python-docx.
- **Security:** service_role key backend-only (never `NEXT_PUBLIC`, never
  committed); user_id never taken from request input; human-approval gate before
  save.
- **Verified:** 8 backend tests pass, ruff clean, frontend build/lint/format
  green, routes gated (401 without auth). Live two-account RLS test is the
  operator's closeout step.
- **Next:** M2 — paste-a-link → score + tailor.

## 2026-06-18 — M0 complete: verified live in production
- **What:** Deployed and verified the M0 vertical slice end to end — Vercel
  frontend → Railway backend → live Anthropic call. The deployed landing page
  hits `/agent/ping` and renders a real model response. M0 acceptance met.
- **Status:** M0 ✅ closed. Beginning **M1** (auth + onboarding → profile).

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
