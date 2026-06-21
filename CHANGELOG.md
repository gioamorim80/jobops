# CHANGELOG

## 2026-06-20 — Mobile gutters + smaller desktop scale (visual only)
- Mobile horizontal gutter: the page container now uses a fixed `22px` left/right
  padding at ≤640px (in px so it doesn't shrink with the type scale), replacing
  the old `1.15rem` that had collapsed to ~15px. Applies to the hero, feature
  cards, and every section via `.container`, so nothing runs edge-to-edge on a
  ~390px phone.
- Desktop scale reduced further: master root `html { font-size: 87.5% → 80% }`
  (14px → 12.8px base, about 9% smaller), hierarchy intact via the rem system.
- Mobile base eased from 81.25% (13px) to 77.5% (12.4px) so it stays just under
  the desktop base (no inversion) while the new gutter does the breathing-room work.
- Fonts, colors, layout, content, and logic unchanged.

## 2026-06-20 — Design-scale refinement (visual only, globals.css)
- Reduced the overall type and spacing scale so the composition at 100% zoom
  feels the way it used to at about 80%. Implemented with a master root font-size
  (`html { font-size: 87.5% }` = 14px base on desktop) so the whole rem-based
  system scales down together with hierarchy intact; body switched from a fixed
  16px to 1rem.
- Reduced internal padding a little while keeping section margins generous: card
  padding 1.75rem → 1.6rem, card-title margin 1.1rem → 0.9rem, button padding
  0.7/1.4rem → 0.6/1.25rem, input padding 0.7/0.85rem → 0.6/0.8rem; card-to-card
  gap kept generous at 1.65rem. Hero top padding trimmed
  (clamp 3.5/12vh/8rem → 2.75/9vh/6rem), hero lead 1.08rem → 1.05rem.
- Mobile (≤640px) now uses a distinctly smaller base (`html { font-size: 81.25% }`
  = 13px), replacing the old fixed 15.5px body override; line-height and section
  spacing stay comfortable. Bumped the "Coming soon" pill 0.68rem → 0.74rem so it
  stays legible at the smaller base.
- Fonts, colors, layout, content, and logic unchanged.

## 2026-06-20 — Post-login routing by profile state (frontend only)
- The magic-link callback now routes by the authenticated user's own profile
  state instead of always landing on /dashboard: no completed profile yet goes
  to /onboarding, and a completed profile goes to the Home hub (/home). An
  explicit `next` deep link is still honored. Reads only the caller's own profile
  row (RLS-scoped).
- Middleware: an already-signed-in user hitting /login now goes to /home (which
  itself funnels not-yet-onboarded users to onboarding) instead of /dashboard.
- Confirmed the logged-in JobOps logo already routes to /home. /dashboard stays
  reachable via its nav link as the detailed profile + history view.
- Frontend only; no auth/RLS/backend logic changes beyond redirect targets.

## 2026-06-20 — Writing-style rule + README rewrite (docs only)
- Added a "Writing style for docs & UI copy" section to CLAUDE.md so it applies
  to all future docs and UI copy: write plainly, no em-dash-plus-fragment
  emphasis, no punchy parenthetical taglines, sparing em-dashes, "the user/users"
  rather than "you/your" in product/README copy, no repeating a distinctive
  adjective next to itself, plain "resume" with no accents, and no hype or filler.
- Rewrote README.md to follow the rule: removed every em-dash fragment and
  emphasis tagline, switched descriptive copy to "the user/users", fixed the
  doubled "honest" in the opening paragraph, and changed all "résumé" to "resume".
  Factual content (current features vs. roadmap) is unchanged.
- Relabeled the `prompts/` entry in the repo map as a historical, point-in-time
  record that is not maintained or complete, and noted STATE.md and CHANGELOG.md
  as the current source of truth.

## 2026-06-20 — Home hub tweaks (frontend only)
- Greeting is now plain English ("Hi {firstName} — what would you like to do?",
  or "What would you like to do?" with no name) — removed "Olá"; no non-English
  words user-facing.
- Removed the "Pick a place to start…" subtitle; the heading stands alone.
- Fixed launcher tile alignment: equal-height, top-aligned row (zeroed the
  global stacked-card top margin inside `.launcher-grid` + explicit
  `align-items: stretch`); stacks cleanly on mobile.
- Replaced the middle tile "Review my scored jobs" with **"Edit my profile"**
  (→ Dashboard's profile section), removing the redundancy with the "Recently
  scored" panel below. Tiles are now Score a new job / Edit my profile / Chat
  with the Coach. The "Recently scored" panel + "See all" remains the path to
  scored-job history.
- Frontend only; design system + tone unchanged, no logic/auth/RLS change.

## 2026-06-20 — Landing tiles + logged-in Home launcher (frontend only)
- **Landing:** removed the standalone "No spray-and-pray." section (the hero is
  the single intro). Reworked the feature tiles into a clean 2×2 (stacks on
  mobile): renamed "Tailored, truthful bullets" → "Suggested changes to your
  résumé" to match the app; added an "An honest coach" tile (live); and reworded
  the email-alerts tile as upcoming with a "Coming soon" label, folding in the
  spray-and-pray line — honest as roadmap, not a current capability.
- **Logged-in Home:** new `/home` light launcher — a warm "what would you like
  to do?" with action cards (Score a new job → /score, Review my scored jobs →
  /dashboard, Chat with the Coach → /coach) plus a small recent-scored peek
  (max 3, "See all" → Dashboard). It does NOT duplicate the Dashboard. The
  JobOps logo now routes here when logged in; logged-out logo unchanged.
- Frontend only; design system + tone unchanged. No backend/auth/RLS/logic
  changes; the Home peek reads the user's own tailorings via existing RLS.
  build/lint/pre-commit green.

## 2026-06-20 — M2.5/M2 refinements: coach tone, chat cap fix, tailoring labels
- **Coach tone (M2.5):** recalibrated the system prompt to v2 — "a warm friend, in
  a professional setting": composed, not over-familiar. Refusals open gently
  ("Well —" / "Ah, I wish I could —"), never "Ha"; no terms of endearment and no
  references to drinks/going out (removed the caipirinha example and the "love"
  in the limit message). Still firmly in-scope and no-fabrication.
- **Coach rate-limit fix (M2.5):** the chat cap now counts ONLY this user's
  `enrich` turns (one user message = exactly one turn) instead of the shared
  all-actions total, and is generous (`ENRICH_DAILY_TURN_CAP`, default 50) since
  turns are ~0.6¢. A normal multi-turn conversation no longer trips it; the
  in-voice "let's pick this up tomorrow" shows only at the real cap.
  (`count_calls_today` gained an optional `action` filter.)
- **Tailoring output (M2):** renamed "Tailored bullets" → "Suggested changes to
  your résumé", and each suggestion now shows WHERE it applies — the real role
  (title + employer/dates) and section it belongs under (e.g. "Senior Engineer,
  Acme (2021–2024) — Experience"), drawn from the user's real résumé, never
  invented. Kept the original → suggested → why structure (added a `where` field
  to the Tailor output, the bullet model, and both result views).
- No RLS/auth/isolation change, no migration. `ENRICH_DAILY_TURN_CAP` is a new
  optional setting (defaults to 50). 16 backend tests + build/lint/pre-commit green.

## 2026-06-20 — M2.5: conversational profile-enrichment coach
- **New feature:** a warm chat ("Coach", reachable from the nav) where a logged-in
  user enriches their profile with TRUE context the résumé missed — stories of
  what they built, corrected project attribution, fixed title/timelines, real
  skills/domains. The agent has the user's profile as context and asks targeted
  questions, then proposes a structured change the user must confirm.
- **Voice:** a chic, warm, witty friend-from-Trancoso system prompt
  (`agents/enrich.py`) — light and funny by default, genuinely caring when
  someone's discouraged; warmth in the words, no emoji.
- **Hard guardrails (in the prompt + code):**
  - Scope fence: off-topic asks (recipes, homework, coding, chitchat) get a warm,
    playful redirect back to the job hunt — never a scold.
  - No fabrication + human gate: the agent proposes structured changes; nothing
    is written until the user clicks "Add to profile". `/enrich/apply` merges only
    confirmed changes into `profiles.parsed` (append + case-insensitive dedupe;
    other fields preserved).
  - Cost cap: each chat turn counts against the shared per-user daily LLM cap;
    on exceed, a friendly in-voice "let's pick this up tomorrow" (not a crash).
    Conversation bounded (last 20 turns, 2000 chars/msg). Usage logged
    (action `enrich`).
  - PII: the transcript is not persisted; raw message content is never logged.
- **Backend:** `/enrich/chat` + `/enrich/apply`; shared `run_json_chat` helper
  for multi-turn JSON. user_id always from the verified JWT; reads/writes touch
  only the caller's own profile.
- **Frontend:** `/coach` chat in the Trancoso design system (bubbles, proposal
  card with Add/Not-now, typing indicator, aria-live log, on-brand error/limit
  states); nav wraps cleanly to a second row on phones.
- No migration (profiles/attribution_notes already exist), no new env var.
  16 backend tests + build/lint/pre-commit green.

## 2026-06-19 — M2 refinements: score stability, delete, loading loop, copy
- **Scoring stability:** the Scorer call now runs at `temperature=0` (added an
  optional `temperature` to `run_json_agent`; the Tailor call is unchanged for
  natural writing), so the same job + profile scores consistently. The result
  views now show a qualitative band beside the 0–100 number and APPLY/STRETCH/
  SKIP: 80–100 "Strong fit", 65–79 "Solid fit", 50–64 "Stretch", <50 "Likely
  skip" (derived client-side from `fit`, so cached/history results show it too).
- **Delete saved results:** each Scored-jobs row has a delete action with a small
  inline confirm. Deletes go through the Supabase client under RLS
  (`user_id = auth.uid()`), so a user can only ever delete their own rows; the
  list refreshes after.
- **Loading messages:** the score+tailor wait now loops continuously (~3.5s per
  line) through six honest, warm lines (incl. gentle "still working" ones)
  instead of freezing on the last — same `aria-live` status region, no focus trap.
- **Landing copy:** replaced generic "uses AI" with specificity ("reads each
  posting in full and reasons against your real experience — purpose-built
  analysis, not keyword matching"); tightened the differentiator to one confident
  paragraph and removed the unfinished-looking dashed list (kept the
  "no spray-and-pray" idea).
- No RLS/auth/isolation change, no migration, no new env var. Scoring/tailoring
  prompts and output shape unchanged. 13 backend tests + build/lint/pre-commit green.

## 2026-06-19 — M2 improvements: cache, history, loading UX, landing copy
- **Exact-match cache (cost saver):** before any LLM call, `/ondemand/score`
  checks whether the user already scored this exact job — matched on normalized
  `source_url` (tracking params/fragment/trailing slash stripped) when a URL was
  given, else a SHA-256 of the normalized pasted text. A hit returns the saved
  result with `cached: true`, consuming NO daily-cap budget and logging NO usage.
  A new `force` flag (the "Re-score" action) bypasses the cache; re-scoring
  overwrites that one job's row instead of duplicating it. (Tailor `flags` are
  not persisted, so a cached/reopened result shows an empty flags list.)
- **Results history:** the Dashboard now lists the user's past scored jobs
  (snippet/host, fit, decision, date), read via RLS — only ever their own rows.
  Each links to `/scored/[id]`, a read-only view of the full saved result
  (score, cleared/gaps, tailored bullets, analysis, approval state); a non-owner
  id 404s.
- **Rotating loading messages:** the score+tailor wait now cycles five honest,
  on-brand steps (~2.5s each, stopping on the last), in an `aria-live="polite"`
  `role="status"` region (no focus trap), cleanly replaced by the result or an
  error state.
- **Landing differentiator:** sharpened the hero subtext (AI tailors each score
  and bullet to the specific posting, grounded only in real experience) and
  added a calm "No spray-and-pray matches / No inflated bullets / No roles you'd
  never want / Just honest fit…" section. No competitor named, no fake
  testimonials or invented stats.
- Unchanged: scoring/tailoring logic + output format, auth, RLS, agent behavior.
  Per-user isolation preserved (user_id always from the verified JWT). No
  migration, no new env var. 13 backend tests pass; build/lint/pre-commit green.

## 2026-06-19 — M2: on-demand paste-a-link → score + tailor
- **Migration `0002`:** `tailorings` + `usage_log` with per-user RLS, indexes,
  and explicit GRANTs to `authenticated` + `service_role` (+ sequence usage) so
  the new tables are reachable through PostgREST. `job_id` left as a nullable
  column (FK → `jobs` deferred to M3).
- **Backend:** `POST /ondemand/score` accepts a job URL or pasted text; a single
  readability-style fetch (`readability-lxml` + `httpx`, one GET, no retries)
  with a friendly "paste the text instead" fallback when a link is blocked/
  empty/JS-only. Runs the Scorer then the Tailor (new versioned prompts in
  `agents/scorer.py`, `agents/tailor.py`; default `ANTHROPIC_MODEL`; prompt
  caching intentionally off) against the user's stored profile, saves the result
  to `tailorings` (approved=false). `POST /ondemand/approve` saves the
  user-edited bullets and sets approved=true (human-approval gate).
- **Guardrails:** per-user daily LLM-call cap (`PER_USER_DAILY_LLM_CAP`, default
  25) enforced before any model call, returning a friendly "limit reached"
  status instead of crashing; every agent call logged to `usage_log` with token
  counts + a cost estimate (no raw resume/profile/job text is ever logged).
  user_id always derived from the verified JWT; every read/write scoped to the
  caller's own rows.
- **No fabrication:** Scorer evidence must trace to the profile; Tailor only
  reorders/rephrases true content and emits "metric pending"/attribution flags,
  which the UI surfaces prominently. Nothing is auto-applied.
- **Frontend `/score`:** link/text input → loading → calm results (fit score +
  decision badge, cleared/gaps, pitch, flags, editable bullets with "why", match
  analysis, explicit Approve). Trancoso design system, responsive, on-brand
  error/notice states; nav + dashboard entry points. No always-on backend status.
- **Verified:** 13 backend tests pass, ruff + pre-commit clean, frontend
  build/lint/format green. Live score→tailor + two-account isolation is the
  operator's end-to-end step. No new env var.
- **Next:** M3 — job-source adapters + dedupe + funnel stage 1.

## 2026-06-18 — M1 hero cleanup (frontend only)
- Removed the duplicate sign-in entry point: kept only the top-right nav "Sign
  in" link; deleted "Already have an account? Sign in" under Get started.
- Removed both hero status pills ("Considered job search" and the agent-status
  indicator). Hero is now just headline + subtext + Get started.
- Replaced the always-on agent-status ping with graceful on-action failure:
  the landing shows no backend status during normal use; when a backend-needing
  action (onboarding parse/save, profile update) can't reach the service, the
  existing error UI now shows a calm, lightly humorous on-brand message instead
  of a raw fetch/5xx error (`backendPost` maps network errors + 5xx to it;
  actionable 4xx still show the real reason). Deleted the unused AgentStatus
  component. Design system, palette, and logic unchanged.

## 2026-06-18 — M1 landing fixes (frontend only)
- **Feature cards aligned:** the three landing cards no longer stagger. Root
  cause was the global `.card + .card` top-margin applying to grid siblings;
  zeroed it inside `.feature-grid` and set `align-items: stretch` for equal
  heights and a shared top edge. Stacks cleanly on mobile (grid `gap` spacing).
- **Sign-in path for returning users:** added a "Sign in" link in a new public
  top nav and an "Already have an account? Sign in" link beside Get started.
  Both route to the existing magic-link `/login` — no auth logic changed.
- **Repo link moved out of the hero:** removed "View the repo" from the primary
  CTA area; it now lives as an understated link in a new site footer.
- Design system, palette, and logic unchanged. pre-commit + build/lint/format
  green.

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
