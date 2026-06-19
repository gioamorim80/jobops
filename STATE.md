# STATE — where the build is

## Current milestone: M1 — Auth + onboarding → profile
Status: **code complete & locally verified.** Live two-account RLS isolation
test must be run by the operator against the real Supabase project + deploys
(steps in the M1 session report / below).

## M0 — Bootstrap the monorepo ✅ COMPLETE & VERIFIED LIVE
Vercel frontend → Railway backend → live Anthropic call. `/agent/ping` confirmed
in production. Next.js later patched to 15.5.19 (security fix).

## M1 — what was built
- **Supabase migration** `supabase/migrations/0001_m1_profiles_preferences.sql`:
  `profiles` + `preferences` tables, RLS `user_id = auth.uid()` on both, an
  `updated_at` trigger, and a PRIVATE `resumes` storage bucket with per-user
  storage RLS (folder = uid). Idempotent; run in the Supabase SQL editor.
- **Auth (frontend):** Supabase magic-link via `@supabase/ssr`. `/login`,
  `/auth/callback` (PKCE code + token_hash), `/auth/signout`. `middleware.ts`
  refreshes the session and blocks unauthenticated access to `/dashboard`,
  `/onboarding`, `/settings`; the `(app)` layout re-checks server-side. Frontend
  uses the anon key only.
- **Onboarding (lightweight):** upload PDF/DOCX to the private bucket (client,
  RLS-scoped) → backend `POST /onboarding/parse` downloads via service role,
  extracts text, runs the onboarding agent (extraction only, never invents),
  stores `raw_resume_text` under RLS, returns a draft (no PII to the browser) →
  user reviews/edits + answers 3 gap questions (target roles, location/remote,
  alert frequency) → `POST /onboarding/complete` saves `profiles.parsed` +
  `preferences` (human-approval gate). user_id always derives from the verified
  JWT, never request input.
- **Settings:** alert frequency (off/daily/weekly) + score threshold (default 60),
  read/written via RLS.
- **Design system:** dark theme tokens in `globals.css` (consistent with the
  landing page), Inter font, reusable card/button/field/badge/alert/spinner
  classes, responsive, with loading/empty/error states throughout.
- **Backend:** new modules `auth.py`, `supabase_client.py` (service role only),
  `resume.py`, `onboarding.py`, `agents/onboarding.py` (versioned prompt). Deps
  added via uv: `supabase`, `pypdf`, `python-docx`.

### Verified locally
- `uv run pytest` (8 passed), ruff clean, frontend `format:check`/`lint`/`build`
  green, backend boots with `/onboarding/parse` + `/onboarding/complete`
  registered and gated (401 without a valid bearer token).

### Operator to-do to close M1 acceptance (needs live Supabase + deploys)
1. Run the migration SQL in the Supabase SQL editor.
2. Set env vars (see session report): Supabase URL + anon key (frontend/Vercel),
   Supabase URL + service_role key (backend/Railway), backend URL (frontend),
   CORS_ORIGINS (backend). Add the Vercel domain to Supabase Auth → URL
   Configuration (Site URL + redirect allowlist).
3. Run the two-account isolation test (steps in the report): two accounts each
   onboard; each sees ONLY their own profile + resume, verified via RLS.

## M1 polish pass (2026-06-18, still M1)
- **Design overhaul:** new "Chic Trancoso" design system in `globals.css` (warm
  ivory + soft lavender base, sparing forest-green accent, Fraunces serif +
  Inter, lighter type, airy spacing, responsive, accessible focus). Applied
  across all pages.
- **Profile editing UX:** editing a field no longer requires a résumé re-upload.
  Settings is now a full Profile & settings editor; résumé replacement is a
  separate optional action. Added additive backend endpoint
  `POST /onboarding/profile` (user_id from verified JWT only; never touches the
  résumé columns or `onboarding_complete`).
- **No** schema change, **no** new env var, and **no** change to auth / RLS /
  storage policies / the onboarding agent / existing API contracts / env handling.

## M1 landing fixes (2026-06-18, still M1, frontend only)
- Feature cards: equal-height, top-aligned row (zeroed the stacked `.card`
  top-margin inside `.feature-grid` + `align-items: stretch`); stacks on mobile.
- Added a returning-user sign-in path: "Sign in" in a public top nav + "Already
  have an account? Sign in" beside Get started (both → existing `/login`).
- Moved "View the repo" from the hero into an understated site footer.
- Design system / palette / logic unchanged.

### Next: M2 — On-demand paste-a-link → score + tailor (the MVP wedge). NOT started.

### Blockers
- None. M1 acceptance is a live verification step for the operator.
