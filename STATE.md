# STATE — where the build is

## Current position: M0–M2.6 done & deployed. Next up: M3 (job-source adapters).
M0, M1, M2, M2.5, and M2.6 are built, deployed, and live. M3–M6 are planned (see
`ROADMAP.md`). Detailed per-milestone notes below; newest refinements first.

## Applied marker on scored jobs (2026-06-21)
- Migration `0003` adds nullable `applied_at` (timestamptz) to `tailorings`
  (null = not applied). No new grants needed (0002 grants + RLS cover it).
- Backend `POST /ondemand/applied` toggles the marker for the caller's own row
  (now() / null); user_id from the verified JWT, scoped write — isolation intact.
- Dashboard scored-jobs list: "Mark as applied" → "Applied ✓ <date>" badge with
  "Un-mark"; score/decision/date/Delete unchanged; rows wrap on mobile.

## Coach multi-turn 502 fix (2026-06-20)
- Real cause of the 3rd-turn 502: the model drops the JSON envelope and replies
  in prose as the chat grows, so `extract_json_object` raised HTTPException(502)
  ("Agent returned no JSON") — a clean FastAPI 502 with no traceback. Not the cap.
- Fix: Coach uses raw model text (`run_chat_text`) + lenient parsing; prose
  becomes the reply (no proposal), JSON envelope still yields the proposal. All
  post-model handling wrapped to log tracebacks and return clean JSON, never 502.
  Frontend handles a new `error` status. Tests cover prose and JSON cases.

## Coach cap bug fix (2026-06-20)
- Counting was already 1:1 (one `enrich` row per user message, per-user, daily,
  default cap 50). Real cause: deployed `ENRICH_DAILY_TURN_CAP` left at 2 from an
  earlier test. Fix: floor the effective cap at 40 (`max(configured, 40)`) so a
  stray low value can't strangle chat; added turns-vs-cap logging; documented the
  env in `.env.example`; added regression tests for per-user/daily/action-only
  counting. Operator: set ENRICH_DAILY_TURN_CAP back to 50 (or unset it) on
  Railway so the configured value matches intent; the floor covers it either way.

## M2.6 — Custom domain, branded email, design polish ✅ (2026-06-20)
- Custom domain myjobops.app is live on Vercel (canonical URL, linked in README).
- Branded transactional email through Resend: magic-link emails send from the
  domain with DKIM and SPF verified (auth email only; digests remain planned).
- Supabase auth redirect URLs and the Railway CORS allowlist updated for the
  domain.
- Responsive design refinement (smaller type and spacing scale, mobile gutters,
  header gutter fix) folded in. Visual-only; details in the entries below.

### M2 — what was built (the on-demand paste-a-link flow)
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

## Mobile gutters + smaller desktop scale (2026-06-20, visual only)
- Fixed mobile gutter: `.container { padding: 0 22px }` at ≤640px (px, so it
  doesn't shrink with the type scale) — clear left/right breathing room at ~390px.
- Desktop master scale `html { font-size: 80% }` (12.8px, ~9% smaller than the
  prior 14px); mobile ≤640px `77.5%` (12.4px). Knobs to tune: the two
  `html { font-size }` values and the `22px` mobile gutter.

## Design-scale refinement (2026-06-20, visual only)
- Master root font-size scales the whole rem-based system down: desktop
  `html { font-size: 87.5% }` (14px base), mobile ≤640px `81.25%` (13px). Body is
  now 1rem (was fixed 16px). Internal padding trimmed slightly (cards/buttons/
  inputs) while section margins stay generous. Fonts/colors/layout/logic unchanged.
- Tunable knobs: the two `html { font-size: … }` values (desktop / mobile) are the
  master levers; card padding 1.6rem, card gap 1.65rem, hero padding clamp.

## Post-login routing by profile state (2026-06-20, frontend only)
- Magic-link callback routes by the user's own profile state: no completed
  profile to /onboarding, completed profile to /home (an explicit `next` is still
  honored). Middleware sends an already-signed-in user from /login to /home.
- Logged-in logo already points to /home; /dashboard stays the detailed view via
  its nav link. No auth/RLS/backend logic change beyond redirect targets.

## Writing-style rule + README rewrite (2026-06-20, docs only)
- Added a durable "Writing style for docs & UI copy" section to CLAUDE.md (plain,
  natural copy; no em-dash fragments or emphasis taglines; "the user/users" in
  product/README copy; plain "resume"; no hype). Applies to all future docs/UI.
- Rewrote README.md to follow it; factual content unchanged. Relabeled `prompts/`
  as a historical, non-maintained record, with STATE.md/CHANGELOG.md as the
  current source of truth.

## Home hub tweaks (2026-06-20, frontend only)
- Plain-English greeting ("Hi {name} — what would you like to do?"), no "Olá";
  removed the subtitle line. Launcher tiles now equal-height/top-aligned.
- Middle tile is "Edit my profile" (→ Dashboard profile section) instead of the
  redundant "Review my scored jobs"; the "Recently scored" panel + "See all"
  remains the history path. Tiles: Score a new job / Edit my profile / Coach.

## Landing + Home launcher (2026-06-20, frontend only)
- Landing: dropped the standalone "No spray-and-pray." section; feature tiles are
  now a 2×2 (stacks on mobile) — renamed "Suggested changes to your resume",
  added an "An honest coach" tile (live), and the email-alerts tile is labeled
  "Coming soon" (folds in the spray-and-pray line; honest as roadmap).
- New logged-in `/home` light launcher (action cards → Score / Dashboard / Coach
  + a small recent-scored peek); the JobOps logo routes here when logged in.
  Dashboard stays the detailed view. No backend/auth/RLS/logic change.

## M2.5/M2 refinements (2026-06-20)
- Coach voice → v2 "warm friend, professional setting": composed, gentle refusals
  ("Well —"/"Ah, I wish I could —", never "Ha"), no endearments or drink refs.
- Coach cap fixed: counts only the user's own `enrich` turns (1 message = 1 turn),
  generous default 50 (`ENRICH_DAILY_TURN_CAP`); normal conversations don't trip it.
- Tailoring section renamed "Suggested changes to your resume"; each suggestion
  now shows WHERE it applies (real role + section), keeping original→suggested→why.
- No RLS/auth/isolation change, no migration; `ENRICH_DAILY_TURN_CAP` optional (50).

## M2.5 — Conversational profile-enrichment coach ✅ (code complete)
- New "Coach" chat (nav → `/coach`): a warm Trancoso-voiced agent that helps the
  user add TRUE resume-missed context and proposes structured profile changes the
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
- **Profile editing UX:** editing a field no longer requires a resume re-upload.
  Settings is now a full Profile & settings editor; resume replacement is a
  separate optional action. Added additive backend endpoint
  `POST /onboarding/profile` (user_id from verified JWT only; never touches the
  resume columns or `onboarding_complete`).
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
