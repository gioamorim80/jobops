# STATE — where the build is

Self-contained snapshot for a fresh session. Dated history lives in
`CHANGELOG.md`; milestone acceptance criteria live in `ROADMAP.md`; system shape
in `ARCHITECTURE.md`. Read CLAUDE.md first (it is the contract).

## Current position
M0 through M4 are built and verified live, including the M2 flow polish, the M4
decision-consistency fixes, and per-call model cost attribution. The full pre-M5
cleanup is cleared (correctness fixes + the whole `/matches` surface), and M5 has
started: step 1 is the email opt-in flag (`preferences.email_opt_in`).
Active focus / next milestone is M5 (scheduled scanner + digest + email). The M5
order was deliberately reset: cost controls FIRST (global budget ceiling +
per-user monthly caps), THEN email/Resend, sent-state, digest composition,
scheduler, and Batch API scoring. Reason: a community launch is planned for July,
so a hard cost cap must exist before the product opens to strangers.
The scorer LLM cap (`PER_USER_DAILY_LLM_CAP`) is default 25 in config.py, set to
50 in prod (Railway).

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
  0009), so cost is attributed per model. M4 core is SEALED: a later
  `/admin/score-matches` run at cap=50 returned `scored=18`, `skipped_for_cap=0`.
- **M4 decision-consistency fixes (migration 0008).** Band 50–64 relabeled
  "Stretch" → "Moderate fit" (kills the band/decision word collision); the decision
  chip is framed "Decision: APPLY/STRETCH/SKIP" on `/score`, `/scored/[id]`, and
  `/matches`; a `decision` column was added to `matches` so both paths show the
  same score + band + decision; the missing/invalid-decision fallback still
  defaults to STRETCH but now logs a WARNING instead of masking it. Scorer rubric
  unchanged — decision stays the model's holistic call, not a function of the score.
- **Pre-M5 cleanup — cleared.** Correctness: field-scoped profile-edit merge
  (f257e96), 5xx server-side cause logging (634ec7a), scorer-v2 with `scorable` +
  `posting_seniority` + APPLY→STRETCH seniority cap (2d73597), prefilter
  title+company dedupe (9761a95). The `/matches` surface: threshold filter (edddde4)
  with a context line + Settings link (9b08560), consistent nav active-state
  (45ab474), per-row delete via a JWT-scoped backend endpoint (fbe81af), and
  logged-out app-route visits landing on the marketing page (e16b735).
- **M5 step 1 — email opt-in (migration 0010).** `preferences.email_opt_in` (bool,
  default false for consent) replaces the alert-frequency dropdown with a single
  "Email me new matches" toggle in onboarding and settings; the backend writes the
  flag instead of `alert_frequency`. `score_threshold` is unchanged. Nothing reads
  the flag yet. Commit 09b42b3; migration 0010 is pending a manual apply in prod.

## Migrations
Run in the Supabase SQL editor; all idempotent. Applied: 0001 (profiles +
preferences), 0002 (tailorings + usage_log), 0003 (tailorings.applied_at), 0004
(jobs pool), 0005 (jobs extra fields: salary_is_predicted, contract_time/type,
category_tag), 0006 (tailorings role/company), 0007 (matches table), 0008
(matches.decision), 0009 (usage_log.model, nullable, no backfill), 0010
(preferences.email_opt_in, bool, default false). 0008 and 0009 are applied in
prod. 0010 is PENDING a manual apply in Supabase — run it BEFORE the M5-step-1
deploy settles (the backend already writes `email_opt_in`).

## Open
- Apply migration 0010 (`preferences.email_opt_in`) in Supabase before the
  M5-step-1 deploy settles.
- Low-priority backlog: login email sender → noreply@myjobops.app via Cloudflare
  routing; clean company/role title on the "recently scored" list.

Resolved this session: the full pre-M5 backlog (correctness fixes + the `/matches`
surface) cleared; M5 step 1 (email opt-in) shipped; the M5 order reset to put cost
controls before the digest. See CHANGELOG (2026-06-23/24) for the per-commit log
and the recorded decisions.

## Backlog (pre-M5 cleanup) — CLEARED
The prioritized pre-M5 cleanup is fully done. Per-commit detail and the recorded
decisions are in CHANGELOG (2026-06-23/24); the standing decisions are kept here.

Cleared:
- Correctness: field-scoped profile-edit merge (f257e96), 5xx server-side cause
  logging (634ec7a), scorer-v2 (`scorable` + `posting_seniority` + APPLY→STRETCH
  seniority cap, 2d73597), prefilter title+company dedupe (9761a95).
- `/matches` surface: threshold filter + context line + Settings link (edddde4,
  9b08560), consistent nav active-state (45ab474), per-row delete (fbe81af),
  logged-out app-route visits land on the marketing page (e16b735).

Standing decisions (do not re-litigate):
- STALE MATCHES — do NOT build an auto-rescore mechanism. Existing `matches` rows
  are not retroactively updated by scorer/prefilter changes (the matcher skips
  job_ids already in `matches`). This is covered by the threshold filter plus the
  per-row Delete button. Accepted residual: a high-scoring row with now-stale
  reasoning won't be filtered and must be deleted by hand (tolerated).
- Bug 3 (legacy null-decision pills) — WON'T-FIX. `decision` is null only on the
  fixed set of pre-0008 legacy rows, which render harmlessly; every new row gets a
  decision, and the threshold filter + delete handle stale rows.
- Deep-link preservation after login — NOT WANTED. Shared links are product
  intros, not deep links; an unauthenticated visit should reach the intro page
  rather than resume a specific destination.

Queued cleanup (small, do when convenient):
- Drop the dead `preferences.alert_frequency` column in its own migration, now
  that nothing reads or writes it (M5 step 1 retired it). Hold `preferences.paused`
  and `preferences.channels` — they are kept for the M5 guardrails (pause switch)
  and future multi-channel sends.

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
- One coherent UX/design pass, done POST-M5 all at once via the design skills, not
  piecemeal. Hold all UI-polish items for it. Driver: per feedback, the pills and
  several surfaces read as AI-default and want an intentional revamp. Known item:
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
Build order (reset this session — cost controls FIRST, because a July community
launch means a hard cost cap must exist before opening to strangers):
1. Cost controls — global monthly budget ceiling + per-user monthly caps, with a
   pause switch. Per `docs/GUARDRAILS.md`. Must land before any automated loop.
2. Email / Resend — wire Resend in the backend (net-new; auth email is handled by
   Supabase today, the backend has never sent mail).
3. Sent-state — track which matches were emailed so none is sent twice (net-new:
   an `alerts_log` table and/or a sent marker on `matches`).
4. Digest composition — the DIGEST.md agent: score-only, no auto-tailoring,
   skip-if-no-signal.
5. Scheduler — a background worker on Railway (net-new; no scheduler today).
6. Batch API — move the scheduled, non-interactive scoring onto the Batch API
   (50 percent off; net-new — all calls are synchronous today).

Step 1 DONE: email opt-in flag (`preferences.email_opt_in`, migration 0010).

Design decisions already fixed:
- Single "email me matches" opt-in. No daily/weekly cadence toggle: the pool is
  not fresh enough daily to justify one (shipped as the toggle in step 1).
- Send the top-N unsent matches about every two days, and ONLY when there is
  genuine signal. Do not email mediocre jobs just because time has passed.
- Surface contract: a match is shown on `/matches` AND emailed only when
  `score >= score_threshold` (default 60, inclusive). The digest MUST reuse this
  exact rule so the two surfaces never disagree.
- Recency is a SEPARATE ranking and flagging signal in the digest, never baked
  into the fit score (the score stays pure; `matches.posted_at` carries recency).
- Prompt caching does not help the scorer (prefix below the cacheable minimum); it
  is deferred to the tailor step.
- Agent spec in `docs/agents/DIGEST.md`; guardrails in `docs/GUARDRAILS.md`.

## How to trigger and verify (admin)
Add your Supabase user UUID to `ADMIN_USER_IDS`. With a bearer token:
`POST /admin/fetch-jobs` populates the pool (M3); `POST /admin/score-matches`
scores the shortlist into `matches` (M4) and returns counts plus
`cache_read_tokens`/`cache_write_tokens`. Inspect spend with
`select action, count(*), round(sum(cost_estimate)::numeric, 4) from usage_log
group by action;` — `match_score` (Haiku) should be well below `score`/`tailor`
(Sonnet).
