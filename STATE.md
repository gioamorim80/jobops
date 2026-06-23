# STATE — where the build is

Self-contained snapshot for a fresh session. Dated history lives in
`CHANGELOG.md`; milestone acceptance criteria live in `ROADMAP.md`; system shape
in `ARCHITECTURE.md`. Read CLAUDE.md first (it is the contract).

## Current position
M0 through M4 are built and verified live, including the M2 flow polish, the M4
decision-consistency fixes, and per-call model cost attribution. The scorer LLM
cap (`PER_USER_DAILY_LLM_CAP`) is default 25 in config.py, set to 50 in prod
(Railway). M4 core is complete bar one tick: confirm a full scoring run at cap=50.
Active focus / next milestone is M5 (scheduled scanner + digest + email).

## Stack and repo (quick orient)
- Frontend: Next.js App Router + TypeScript on Vercel. Routes under
  `frontend/app/(app)/`: `/home` (launcher), `/dashboard` (profile + scored-jobs
  tracker), `/matches` (automated matches), `/score` (paste a link), `/scored/[id]`
  (saved result), `/coach`, `/settings`, plus `/login` + `/auth/callback`.
- Backend: FastAPI on Railway, managed with `uv`. Modules in `backend/app/`:
  `onboarding`, `ondemand`, `enrich` (coach), `admin`, `matcher`, `prefilter`,
  `dedupe`, `sources/` (Adzuna), `llm`, `usage`, `auth`, `supabase_client`,
  `config`. Agent prompts in `backend/agents/` (versioned strings).
- Data/auth: Supabase (Postgres + magic-link + storage + RLS). Backend uses the
  service-role key only; frontend uses the anon key only.
- Models: `claude-sonnet-4-6` for onboarding, on-demand scorer, tailor, and coach;
  `claude-haiku-4-5` for the M4 automated matcher. Each step pins its model as a
  code constant (`SCORE_MODEL`/`TAILOR_MODEL`/`ENRICH_MODEL`/`MATCH_MODEL`) that
  drives both the API call and the `usage_log.model` row, so cost is attributable
  per model. Env in `config.py`: `ANTHROPIC_API_KEY`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `ADMIN_USER_IDS`
  (comma-separated; empty = fail closed), `PER_USER_DAILY_LLM_CAP` (default 25 in
  config.py, set to 50 in prod (Railway)), `ENRICH_DAILY_TURN_CAP` (default 50),
  `CORS_ORIGINS`. Live domain: myjobops.app.
- Checks before commit: `uv run pytest` (78 backend tests), `uv run ruff check`,
  frontend `npm run lint` + `npm run build`, and `pre-commit run --all-files`.

## Done and verified
- **M0–M3 — sealed, verified live.** Bootstrap + deploy; auth + onboarding →
  structured profile (RLS, private resume bucket); on-demand paste-a-link flow;
  coach (M2.5); custom domain + branded email (M2.6); per-user Adzuna fetch into a
  shared `jobs` pool, dedupe on `source+external_id`, and a generous no-LLM
  prefilter shortlist (M3).
- **M2 flow polish.** Score and tailor are SPLIT: `POST /ondemand/score` runs only
  the cheap scorer ("Score" button, auto); tailoring is on demand via
  `POST /ondemand/tailor` ("Tailor my resume for this" button). No auto-tailoring.
  Scorer also extracts role + company (no fabrication) for "Role — Company" row
  labels; clean "View posting →" links (raw URL only in href); applied-date is
  editable and stored at noon UTC so it reads as the chosen calendar day anywhere.
- **M4 core — verified live.** `POST /admin/score-matches` (admin-gated, fail
  closed) prefilters a user's candidates from the pool and scores the shortlist on
  `claude-haiku-4-5` into the per-user `matches` table (RLS-isolated: users SELECT
  only their own; service role is the only writer). The matcher REUSES the existing
  rubric (`SCORER_SYSTEM_PROMPT_V1` + `_normalize_score`) on the ~500-char snippet.
  The fit score is pure (recency never factored in). A dedicated `/matches` UI
  section is separate from the scored-jobs tracker. Live run scored 13 matches;
  `usage_log` shows `match_score` rows cheaper than Sonnet `score` rows; RLS
  confirmed. The scorer LLM cap is now 50 (was 25, which skipped 17 jobs in one
  run): `PER_USER_DAILY_LLM_CAP`, default 25 in config.py, set to 50 in prod
  (Railway). Each call's serving model is recorded in `usage_log.model` (migration
  0009), so cost is attributed per model. M4 core is complete bar one tick: a full
  scoring run at cap=50.
- **M4 decision-consistency fixes (migration 0008).** Band 50–64 relabeled
  "Stretch" → "Moderate fit" (kills the band/decision word collision); the decision
  chip is framed "Decision: APPLY/STRETCH/SKIP" on `/score`, `/scored/[id]`, and
  `/matches`; a `decision` column was added to `matches` so both paths show the
  same score + band + decision; the missing/invalid-decision fallback still
  defaults to STRETCH but now logs a WARNING instead of masking it. Scorer rubric
  unchanged — decision stays the model's holistic call, not a function of the score.

## Migrations
Run in the Supabase SQL editor; all idempotent. Applied: 0001 (profiles +
preferences), 0002 (tailorings + usage_log), 0003 (tailorings.applied_at), 0004
(jobs pool), 0005 (jobs extra fields: salary_is_predicted, contract_time/type,
category_tag), 0006 (tailorings role/company), 0007 (matches table), 0008
(matches.decision), 0009 (usage_log.model, nullable, no backfill). 0008 and 0009
are applied in prod.

## Open
- Confirm a full scoring run at cap=50 has been executed — last tick before sealing
  M4 core.
- Low-priority backlog: login email sender → noreply@myjobops.app via Cloudflare
  routing; clean company/role title on the "recently scored" list.

Resolved this session: raised the LLM cap 25 → 50 (`PER_USER_DAILY_LLM_CAP`, env
var; default 25 in config.py, set to 50 in prod on Railway); scorer prompt caching
evaluated and DECLINED (prefix ~1.1k tokens is below Haiku 4.5's 4096 cacheable
minimum and the per-job text dominates input — caching deferred to the tailor step,
where a large stable per-user context repeats); the 0008 decision-consistency fixes
verified live.

## Backlog (pre-M5 cleanup)
Prioritized cleanup to clear before M5. One line each; tiers are priority order.

TIER 1 — correctness / data integrity:
- Merge-fix: `/onboarding/profile` full-overwrites `parsed`; the settings page
  round-trips `comp_floor`/`attribution_notes` via hidden state, so a save can
  silently wipe coach-written `attribution_notes`. Fix: server-side field-scoped
  merge (replace the shown fields, preserve the unshown ones).
- Bugs 1+2 (likely the same root): bad / JS-rendered job links (e.g. Google
  careers) fail to fetch — one path scores nav-disclaimer garbage as 0/100, another
  500s into the "coffee" message. Add a "did I fetch a real posting?" guard; check
  Railway logs for the masked exception.
- Bug 5: duplicate jobs in `/matches` despite M3 dedupe — likely dedupe runs on the
  pool but not the matches/presentation layer. Dedupe at both.

TIER 2 — scorer credibility:
- Bug 4: the scorer returns DECISION: APPLY on thin / under-scoped postings it
  admits it couldn't scope (e.g. Capital One Principal: 62 "Moderate fit", analysis
  says "posting incomplete / not a natural fit", pill says APPLY). Calibrate the
  decision so low-confidence / incomplete postings don't yield APPLY.

TIER 3 — matches display:
- Feedback 5 + Bug 3 (same surface): hide matches below the user's score threshold
  (settings, e.g. 75); and make the decision pill consistent (some matches show one,
  some don't). The threshold filter may resolve part of Bug 3.

TIER 4 — low-risk polish:
- Shared links to `/home` (and app routes) bounce to login when logged out, skipping
  the marketing/intro page beta users loved. Unauthenticated shared links should
  reach the intro page, not silently redirect to login.
- Nav: highlight the active page in the top menu.

RESOLVED (investigation done):
- raw_resume_text: read by the TAILOR path only (verbatim into the tailor prompt);
  the scorer and matcher are parsed-only; write-once at `/onboarding/parse`.
  DECISION: surface it READ-ONLY on the profile/settings view ("Resume text on
  file"). Not editable — editing it would change tailoring output un-gated,
  bypassing the parse + coach-confirm gate. The editable truth stays in `parsed`.
- linkedin_text: pure scaffolding — declared in migration 0001 ("unused in M1"),
  zero readers/writers, not in ParsedProfile, no frontend field. DECISION: Option A
  — build it as a user-paste field that MIRRORS the resume flow: pasted text stored
  in the top-level `linkedin_text` column (parallel to `raw_resume_text`), then
  parsed into `parsed` via the same merge. This doubles as the zero-resume on-ramp
  (LinkedIn paste for users with no resume PDF), so build it WITH the zero-resume
  onboarding work, not standalone. Do NOT drop the column.

QUEUED FEATURES (after the above):
- Resume view link (signed URL — net-new, no helper exists).
- Score-page → open the coach seeded with that job's context.
- Surface raw_resume_text read-only on the profile/settings view (small).
- LinkedIn-paste field (Option A) — bundle with the zero-resume onboarding work.
- PDF resume export — its OWN post-M5 milestone (base template + approve-then-
  generate no-fabrication gate).

## Deferred (not blocking; intentional)
- One coherent UX/design pass (hold all UI-polish items for it). Known item:
  `/scored/[id]` shows an empty "Suggested changes" section for un-tailored rows.
- Re-scoring a job silently un-approves a previously approved tailoring (minor).
- Whether user-pasted jobs should also feed the shared `jobs` pool (currently
  tailorings-only, which is fine for now). Open design question.
- Full-JD scoring: M4 scores the ~500-char Adzuna snippet; full text stays the M2
  paste-a-link path.

## Operational lessons (keep in mind)
- **Hand the migration as step 1.** Run migrations in Supabase BEFORE the deploy
  settles. We hit deploy-before-migrate races twice: the read path showed a blank
  list, the write path 500'd on insert. Always apply the SQL first.
- **The friendly error masks the cause.** The "wandered off for coffee" message
  hides the real exception. Check Railway logs for the actual error or cap, never
  assume from the user-facing message.

## Next milestone: M5 — scheduled scan + email digest
Design already sketched:
- Single "email me matches" signup. No daily/weekly cadence toggle: the pool is
  not fresh enough daily to justify one.
- Send the top-N unsent matches about every two days, and ONLY when there is
  genuine signal. Do not email mediocre jobs just because time has passed.
- Recency is a SEPARATE ranking and flagging signal in the digest, never baked
  into the fit score (the score stays pure; `matches.posted_at` carries recency).
- Use the Batch API for the scheduled, non-interactive scoring (50 percent off).
  Prompt caching does not help the scorer (prefix below the cacheable minimum); it
  is deferred to the tailor step.
- Track sent state so a match is not emailed twice.
- Email via Resend; respect the remaining guardrails in `docs/GUARDRAILS.md`
  (global monthly budget ceiling, pause switch). Agent spec in
  `docs/agents/DIGEST.md`.

## How to trigger and verify (admin)
Add your Supabase user UUID to `ADMIN_USER_IDS`. With a bearer token:
`POST /admin/fetch-jobs` populates the pool (M3); `POST /admin/score-matches`
scores the shortlist into `matches` (M4) and returns counts plus
`cache_read_tokens`/`cache_write_tokens`. Inspect spend with
`select action, count(*), round(sum(cost_estimate)::numeric, 4) from usage_log
group by action;` — `match_score` (Haiku) should be well below `score`/`tailor`
(Sonnet).
