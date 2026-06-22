# STATE — where the build is

## Current position: M0 through M3 done. Next up: M4 (automated matching).
M0, M1, M2, M2.5, M2.6, and M3 are built. M4 through M6 are planned (see
`ROADMAP.md`). Detailed per-milestone notes below; newest refinements first.

## Scored jobs list: role/company labels + clean source link (2026-06-22)
- Row label now shows "Role — Company" (just the role if no company, a short
  fallback if neither) instead of raw description copy.
- Scorer extracts `role` + `company` from the posting text (no fabrication: ""
  when not stated; never guessed from URL/domain). docs/agents/SCORER.md mirrors
  the two new output keys; the existing fit/decision/cleared/gaps keys are
  unchanged. `/ondemand/score` cleans them (`_clean_label`) and stores them.
- Migration `0006_tailorings_role_company.sql`: nullable `role` + `company` on
  tailorings. No new grants (existing RLS + 0002 grants cover them). Idempotent.
- Source link: when `source_url` is set, the row shows a small "View posting →"
  link (new tab, rel=noopener noreferrer); the raw URL only ever lives in href.
  Pasted-text rows (null source_url) show no link.
- Frontend: `jobSnippet` → `jobLabel(role, company, source_url)` in lib/ui.ts,
  used by both the Dashboard list and the Home "Recently scored" peek; the
  fallback never shows description copy. score/band/date/applied + editable
  applied-date and delete are unchanged. Reads stay RLS-scoped to the user.
- EXISTING ROWS: rows scored before 0006 have null role/company and show the
  fallback label (host for link jobs, else "Scored job") — not broken, just
  generic. Two ways to fill them in, operator's choice:
    (A) Leave them — only old rows look generic; every new score is correct. No
        cost, no action.
    (B) One-time backfill — re-run the scorer over each old row's stored job_text
        to extract role/company and UPDATE the row. Accurate, but spends one LLM
        call per old row and counts toward usage. Not built yet; say the word and
        I'll add a small admin-gated backfill (same allowlist as /admin/fetch-jobs)
        so it can't be triggered by a normal user.
  Recommendation: (A) now; (B) only if the old rows matter.
- `approved` (confirmed): a per-tailoring human-approval flag. False on every
  fresh/re-score; set True only by `POST /ondemand/approve` when the user clicks
  "Approve these bullets" on /score after editing the suggested resume changes
  (the rule-#3 human gate). It records that the user reviewed and accepted those
  edits and persists them; it sends nothing anywhere. It gates only UI: on /score
  the bullet textareas lock and a success note shows; the saved-result view shows
  an "Approved" chip. It does NOT gate the dashboard list or scoring.
- 67 backend tests green; frontend lint/prettier/build clean; pre-commit clean.

## Editable applied date on scored jobs (2026-06-22)
- Why: "Mark as applied" auto-set applied_at to now() with no way to correct it;
  users often apply on a different day than they click (real case: applied 2 days
  earlier). The applied date is now editable.
- Backend `POST /ondemand/applied` takes an optional `applied_on` ("YYYY-MM-DD").
  When marking applied it stores that day (default today) at noon UTC so the date
  reads as the same calendar day in any timezone; un-marking clears it. Bad date
  → 422. Logic factored into pure `_applied_at_iso` (unit-tested, no network).
  Still scoped to the caller's own row (JWT user_id + tailorings RLS); applied_at
  stays a timestamptz — no migration.
- Frontend `AppliedToggle`: "Mark as applied" now opens a date input defaulting
  to today (Save/Cancel); the "Applied ✓ <date>" badge gains "Edit date" (same
  input pre-filled) alongside "Un-mark". Display reads the date in UTC so it
  matches the chosen day. On-brand `.input-date`/`.applied-edit` styles wrap on
  mobile; `max=today` prevents future dates.
- 66 backend tests green; frontend lint/prettier/build clean; pre-commit clean.

## M3 dedupe fix — duplicate jobs leaked into the shortlist (2026-06-21)
- Symptom: fetch worked (fetched_raw 157, unique_stored 123, shortlist 30) but the
  shortlist repeated jobs (Justworks twice, Lyft "Causal Inference" three times,
  Capital One twice — same ad id under different tracking-param / URL-form links).
- Root cause was NOT the hash. `content_hash` already keys on the stable
  `source + external_id`, never the redirect_url, so storage dedupe was correct
  (157 → 123). The leak was in `admin.py`: the shortlist was built by
  `prefilter(parsed, all_jobs)` — the RAW 157-item list — so a posting returned by
  two keyword queries/pages reappeared even though it stored as one row.
- Fix (presentation layer, no hash change): `prefilter` now dedupes its ranked
  output by `content_hash` (Adzuna's stable external_id), keeping the best-ranked
  instance, before applying the cap — so the cap counts UNIQUE postings.
- Key choice confirmed: external_id, NOT a title+company key. Same ad id under
  different tracking URLs collapses; genuinely distinct postings that merely share
  a title and company (the EY EDGE Data Scientist role in Stamford / Iselin /
  Hoboken / Grand Central — four ad ids, four cities) all SURVIVE as four rows.
- Verified: group-by(title, company) on the reported clusters drops Justworks 2→1
  and Lyft 3→1 while EY EDGE stays 4; zero repeated ad ids in the shortlist.
  62 backend tests green, pre-commit clean. Still 0 LLM, no migration.

## M3 location/remote query fix — Adzuna returned 0 jobs (2026-06-21)
- Bug: the per-user fetch sent `where='NYC Metro Area'` (Adzuna can't geocode a
  metro label → 0 results) and treated remote_pref `flexible` as a hard
  `remote=False`. Query-building layer only; no schema or profile-UI change.
- LOCATION: `_normalize_location` maps a free-text profile label to a clean,
  geocodable city centre and the adapter passes `distance=45` (km) so a single
  city stands in for its commuter metro. Aliases ("NYC/NYC Metro Area/New York
  Metro" → "New York"; "SF Bay Area/Bay Area" → "San Francisco"; "Greater
  Boston" → "Boston", etc.), generic metro-suffix stripping ("Seattle Metro
  Area" → "Seattle"), plain cities pass through; "remote"/"US"/"anywhere" and
  anything not confidently a place name → OMIT `where` (search nationwide) and log.
- REMOTE: `SearchCriteria.remote: bool` → `remote_pref: str` (the raw profile
  value). `remote`/`remote only` → search nationwide (no `where`); `flexible`
  and `on-site` → pin the city centre + radius. "flexible" never excludes remote:
  Adzuna has no remote filter, so a location search returns remote- and
  onsite-tagged jobs alike.
- GENEROUS: keyword now goes to `what` (broad match), not strict `title_only` —
  honest fit is the scorer's job (M4), not the source's.
- Logs the exact final params built from the profile (page / what / where /
  distance / max_days_old / remote_pref / location); never logs the credentials.
- Verified: 25 source tests (param-building + normalization), 58 backend tests
  green. Dry-run against the user's profile (Senior Data Scientist / Data
  Scientist, "NYC Metro Area", flexible) builds
  `what='Senior Data Scientist' where='New York' distance=45`. Live result count
  needs real Adzuna creds (Railway only; local .env keys are blank). Still 0 LLM.

## M3 audit fixes — Adzuna field mapping (2026-06-21)
- Migration `0005` adds nullable `salary_is_predicted` (bool), `contract_time`,
  `contract_type`, `category_tag` to `jobs`. No new grants (added columns).
- Adapter now captures those fields (Adzuna "1"/"0" → bool), keeps `category.label`
  and adds `category.tag`, and parses `created` defensively in the adapter (null +
  log if unparseable, so one bad date can't fail the whole upsert batch).
- Strict validation kept (`extra` ignored, not forbidden); the batch sanity-check
  now also WARNS when title/description is empty across a high fraction of a batch
  (a likely upstream rename/format change), not just on zero results.
- Docs: predicted-salary note + M4 TODO (treat predicted salary as estimate, no
  hard floor penalty) and the full-JD re-fetch decision (M2 paste path) recorded
  in DATA_MODEL.md and ROADMAP M4. Still zero LLM.

## M3 — Job-source ingestion + dedupe + prefilter (2026-06-21)
- Migration `0004` adds the shared `jobs` pool (public postings, NOT per-user
  RLS: authenticated read, service-role write; `content_hash` unique).
- `app/sources/base.py` (`JobSource` interface) + `app/sources/adzuna.py` (US
  Adzuna adapter, env creds, strict Pydantic validation, polite bounded fetch,
  stores `redirect_url` as `source_url` per ToS). `app/dedupe.py` (content_hash
  upsert), `app/prefilter.py` (no-LLM generous ranked shortlist, cap 30).
- `POST /admin/fetch-jobs` runs a per-user fetch on demand (no scheduler). Gated
  by an `ADMIN_USER_IDS` allowlist checked against the verified JWT; empty = fail
  closed. Source failures are caught per-source and logged, never a 500.
- Zero LLM calls in M3. New env: `ADMIN_USER_IDS` (and the existing
  `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`). Operator must run migration 0004 and set
  these on Railway, plus add their own user id to `ADMIN_USER_IDS`.

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
