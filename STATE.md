# STATE — where the build is

## Current milestone: M2 — On-demand paste-a-link → score + tailor ✅ (code complete)
Status: code complete & locally verified (tests/lint/build/pre-commit green).
Operator to-do: run migration `0002`, then the end-to-end test below. No new env var.

### M2 — what was built
- **Migration** `supabase/migrations/0002_m2_tailorings_usage.sql`: `tailorings`
  and `usage_log` tables, per-user RLS (`user_id = auth.uid()`), indexes, and
  explicit GRANTs to `authenticated` + `service_role` (+ sequence usage) so the
  new tables are exposed to the API roles. `job_id` is a plain nullable column
  for now (FK → `jobs` arrives in M3).
- **Backend** (`/ondemand/score`, `/ondemand/approve`): accepts a job URL or
  pasted text; single readability fetch with a paste fallback (no host
  hammering); runs Scorer then Tailor (versioned prompts in `agents/`, default
  `ANTHROPIC_MODEL`, no prompt caching) against the user's stored profile; saves
  to `tailorings` (approved=false); approve saves edited bullets + approved=true.
  Per-user daily LLM cap enforced (friendly "limit reached", not a crash) and
  every call logged to `usage_log`. user_id always from the verified JWT.
- **Frontend** `/score`: link/text input → loading → calm results (fit + decision
  badge, cleared/gaps, pitch, visible tailor flags, editable bullets with "why",
  match analysis, explicit Approve). Trancoso design system; responsive;
  on-brand error/notice states. Nav + dashboard entry points added.

### M2 improvements (2026-06-19, still M2)
- Exact-match cache before the LLM (normalized URL, else text hash); cache hits
  cost no daily-cap budget and log no usage; "Re-score" (`force`) overwrites the
  job's existing row. Tailor flags are not persisted (cached results show none).
- Results history: Dashboard lists the user's own tailorings (RLS); `/scored/[id]`
  reopens the full saved result read-only (non-owner → 404).
- Rotating, accessible loading messages on the score+tailor wait.
- Landing copy sharpened + a calm differentiator section (no competitor named).
- No migration, no new env var. Scoring/tailoring logic+format, auth, RLS, and
  agent behavior unchanged; per-user isolation intact.

## M2.5 — Conversational profile-enrichment coach ✅ (code complete)
- New "Coach" chat (nav → `/coach`): a warm Trancoso-voiced agent that helps the
  user add TRUE résumé-missed context and proposes structured profile changes the
  user must confirm. Backend `/enrich/chat` + `/enrich/apply`; confirmed changes
  merge into `profiles.parsed` (attribution_notes included).
- Guardrails: scope fence (off-topic → warm redirect), no fabrication + human
  gate, shared per-user daily cap with friendly limit message, bounded
  conversation, usage logged (`enrich`); transcript not persisted, content not
  logged. user_id always from the verified JWT.
- No migration, no new env var. Operator test: open Coach, share a real project,
  confirm a proposed change, see it in Settings; try an off-topic ask for the
  refusal voice.

### M2 refinements (2026-06-19, still M2)
- Scorer runs at `temperature=0` (Tailor unchanged) for stable scores; result
  views show a qualitative fit band (Strong/Solid/Stretch/Likely skip) beside
  the number + decision.
- Per-item delete on the Scored-jobs list (inline confirm), via Supabase client
  under RLS — own rows only.
- Loading messages loop continuously (~3.5s, six warm lines) instead of freezing.
- Landing copy: specificity over "uses AI"; tightened differentiator to one
  paragraph, removed the dashed list.
- No RLS/auth/isolation change, no migration, no new env var.

### M1 — Auth + onboarding → profile ✅ (code complete; live RLS test = operator)

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

## M1 hero cleanup (2026-06-18, still M1, frontend only)
- Single sign-in entry point (top-right nav only); removed the secondary
  "Already have an account?" link.
- Removed both hero status pills; hero = headline + subtext + Get started.
- No always-on backend status on the landing. Backend failures now surface a
  calm, on-brand message via `backendPost` (network + 5xx → friendly; 4xx keep
  the real reason) in the onboarding/settings flows. Deleted unused AgentStatus.

### Next: M3 — Job-source adapters + dedupe + funnel stage 1. NOT started.

### Blockers
- None. M1 acceptance is a live verification step for the operator.
