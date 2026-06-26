# STATE — where the build is

Self-contained snapshot for a fresh session. Dated history lives in
`CHANGELOG.md`; milestone acceptance criteria live in `ROADMAP.md`; system shape
in `ARCHITECTURE.md`. Read CLAUDE.md first (it is the contract).

## Current position
M0 through M5 are built and verified live. **M5 is COMPLETE** (steps 1–6). The
automated scan-and-digest loop runs autonomously on a separate Railway cron service
(`jobops-scheduler`, start command `python -m app.scheduled`, cron `0 11 */2 * *` =
7am ET every other day). Verified live: a scheduled run scanned, scored, and emailed
a real digest, then exited clean. Step 7 (Batch API for scheduled scoring) is
DEFERRED — a cost optimization, not required for the loop.
Caps today: `PER_USER_DAILY_LLM_CAP` default 100 in config.py (runaway/abuse brake);
`PER_USER_MONTHLY_SCORE_CAP` 50, `PER_USER_MONTHLY_TAILOR_CAP` 10 (calendar-month,
separate caps); `MONTHLY_BUDGET_CEILING_USD` 15 (global — now WIRED as the scanner
kill-switch). See LAUNCH CHECKLIST for env values still to reconcile before the July
community launch.

## Stack and repo (quick orient)
- Frontend: Next.js App Router + TypeScript on Vercel. Routes under
  `frontend/app/(app)/`: `/home` (launcher), `/dashboard` (profile + scored-jobs
  tracker), `/matches` (automated matches), `/score` (paste a link), `/scored/[id]`
  (saved result), `/coach`, `/settings`, plus `/login` + `/auth/callback`.
- Backend: FastAPI on Railway, managed with `uv`. Modules in `backend/app/`:
  `onboarding`, `ondemand`, `enrich` (coach), `admin`, `matches`, `matcher`,
  `prefilter`, `dedupe`, `sources/` (Adzuna), `scanner` (per-user + all-opted-in
  fetch+score), `alerts` (sent-state), `mailer` (Resend), `digest`, `scheduled`
  (the run-and-exit cron entrypoint), `llm`, `usage`, `auth`, `supabase_client`,
  `config`. Agent prompts in `backend/agents/` (versioned strings).
- Data/auth: Supabase (Postgres + magic-link + storage + RLS). Backend uses the
  service-role key only; frontend uses the anon key only.
- Models: `claude-sonnet-4-6` for onboarding, on-demand scorer, tailor, and coach;
  `claude-haiku-4-5` for the M4 automated matcher. Each step pins its model as a
  code constant (`SCORE_MODEL`/`TAILOR_MODEL`/`ENRICH_MODEL`/`MATCH_MODEL`) that
  drives both the API call and the `usage_log.model` row, so cost is attributable
  per model. Env in `config.py`: `ANTHROPIC_API_KEY`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `ADMIN_USER_IDS`
  (comma-separated; empty = fail closed), `PER_USER_DAILY_LLM_CAP` (default 100 in
  config.py; prod Railway still 50), `PER_USER_MONTHLY_SCORE_CAP` (50),
  `PER_USER_MONTHLY_TAILOR_CAP` (10), `MONTHLY_BUDGET_CEILING_USD` (15, inert),
  `ENRICH_DAILY_TURN_CAP` (default 50), `CORS_ORIGINS`. Live domain: myjobops.app.
- Checks before commit: `uv run pytest` (171 backend tests), `uv run ruff check`,
  frontend `npm run lint` + `npm run build` + `npm run format:check`, and
  `pre-commit run --all-files` (includes a frontend Prettier hook).

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
  the flag yet. Commit 09b42b3; migration 0010 applied in prod (toggle is live).
- **M5 step 2 — cost controls (e618b37).** Per-user monthly SCORE (50) and TAILOR
  (10) caps that coexist with the daily brake (raised to 100); calendar-month reset
  on the 1st; score and tailor capped separately. A global `is_over_monthly_budget`
  ceiling ($15) is built + unit-tested but INERT — to be wired to the digest scanner
  in a later step. All four limits env-configurable; no migration (env-config only).
- **Matches→Tailor fix (c0bd8c1, f905a09).** The /matches "Tailor" button routes to
  `/score?match=<id>` (not an unfetchable Adzuna URL). New JWT-scoped
  `POST /matches/context` returns minimal match context (title/company/source_url,
  no stale score). `?match` mode shows a paste-the-full-posting view with one
  "Score & tailor" button that scores then tailors the pasted COMPLETE JD — no URL
  re-fetch, full posting not the snippet. Caps + exact-match cache enforced by
  construction; the score-page Tailor button latches disabled on a `limit_reached`
  response. Normal Score-a-job path unchanged. Cross-user isolation tested.
- **Tooling — Prettier pre-commit hook (1a107d6).** Frontend Prettier hook
  (auto-fix + restage, like the ruff hooks), pinned to 3.4.2 via pre-commit's own
  node env so it works in CI's quality job and reads `.prettierrc`. Frontend format
  issues are now caught locally, not only at CI's `format:check`.
- **M5 steps 3–5 — email + sent-state + digest.** Resend wired in the backend
  (`mailer.send_email`, httpx, PII-safe logs, sends from `noreply@myjobops.app` with
  display name `JobOps`; admin `POST /admin/test-email`, 8a7c05e + 8a58b19).
  `alerts_log` sent-state (migration 0011, unique user_id+match_id, RLS select-own,
  service-role writes) with `unsent_matches_for_user` (reuses the threshold gate) +
  idempotent `mark_matches_sent` (42429a0). Digest composition: `send_user_digest`
  (score-only, PII-safe, double-gated on opt-in + threshold, mark-on-send-success)
  and admin `POST /admin/send-digests` (6ec804b).
- **M5 step 6 — the autonomous loop (1c82dbe, 214471d, 8de33ba, 0a13801).**
  `scanner.scan_all_opted_in` runs per-user fetch+score for every opted-in user
  (shared cores reused by the admin endpoints; per-user failure isolated). It is
  gated by the now-wired `is_over_monthly_budget` (top-of-run + per-user re-check,
  scanner only) and the 15-day inactivity pause (active = recent sign-in OR recent
  usage_log; first inactive crossing sets `preferences.paused` + one reinvite;
  paused users skipped for both scan and digest; returning auto-unpauses). The
  scheduler entrypoint `python -m app.scheduled` runs `scan_all_opted_in` then
  `digest_all_opted_in` and exits (0/1); the digest still runs when the scan is
  budget-skipped. Runs on the `jobops-scheduler` Railway cron service; verified live.

## Migrations
Run in the Supabase SQL editor; all idempotent. Applied: 0001 (profiles +
preferences), 0002 (tailorings + usage_log), 0003 (tailorings.applied_at), 0004
(jobs pool), 0005 (jobs extra fields: salary_is_predicted, contract_time/type,
category_tag), 0006 (tailorings role/company), 0007 (matches table), 0008
(matches.decision), 0009 (usage_log.model, nullable, no backfill), 0010
(preferences.email_opt_in, bool, default false), 0011 (alerts_log: sent-state,
unique user_id+match_id, RLS select-own, service-role writes). 0008–0011 are applied
in prod — the email_opt_in toggle and the digest/sent-state loop are live.

## Open
- M5 is complete. The only deferred M5 work is step 7 (Batch API for scheduled
  scoring) — a cost optimization, not blocking. See LAUNCH CHECKLIST for env values
  to reconcile before the July community launch, and the Backlog for carried items.

Resolved this session: M5 step 6 shipped end to end — scan-all loop + shared scanner
core, budget kill-switch wired, 15-day inactivity pause + one-time reinvite, and the
run-and-exit scheduler entrypoint now live on the `jobops-scheduler` Railway cron
service. See CHANGELOG (2026-06-25) for the per-commit log and the recorded decisions.

## LAUNCH CHECKLIST (before the July community launch)
Still-open items to reconcile before opening to strangers:
- **Revert the BACKEND web service's test-bumped `PER_USER_MONTHLY_TAILOR_CAP` to
  10** (the code default). The `jobops-scheduler` cron service already has 10; the
  web service is the one to fix.
- `PER_USER_MONTHLY_SCORE_CAP` → back to **50** if it was bumped during testing.
- `PER_USER_DAILY_LLM_CAP`: if prod Railway still overrides it, set deliberately for
  launch (raise to 100 or remove the env var so the code default wins).
- General rule: audit Railway env on BOTH services for any cap/budget var bumped for
  testing and reset to the code default. The budget ceiling and monthly caps are
  code defaults (not prod env vars), so they need no action unless someone overrode.
- **Cron DST note:** the scheduler cron `0 11 */2 * *` is UTC = 7am ET while EDT is
  in effect. At the fall EDT→EST change it shifts to 6am ET; bump to `0 12 */2 * *`
  if holding 7am matters.

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

## Backlog (current)
The active list, re-curated this session. Standing decisions are above; deeper
investigation notes are below.
- Coach-wiring into the score page: let the user correct or add info on analysis
  points inline, routed through the coach's no-fabrication guardrails. Beta-validate
  before shipping.
- Admin cap-exemption allowlist (Option 3): exempt listed admin user_ids from the
  per-user caps. Deferred; in the interim, bump caps via Railway env vars for
  testing (revert before launch — see LAUNCH CHECKLIST).
- Design revamp: pills-first, done all-at-once, post-M5 (see Deferred). Includes the
  digest email template and the Matches→Tailor button spacing.
- Rewrite `test_usage.py::test_budget_ceiling_is_built_but_not_wired_to_block` — the
  ceiling IS now wired (into the scanner), so the test name is stale. New assertion:
  the ceiling gates the SCANNER but NOT ondemand / matcher / digest.
- Usage indicator: show "X/Y tailors left this month" (and scores). Also upgrades
  the tailor cap-button from the reactive latch to a load-time disable.
- Dead-column drop: drop `preferences.alert_frequency` in its own migration (nothing
  reads/writes it since M5 step 1). HOLD `paused` and `channels` — kept for the M5
  pause switch and future multi-channel sends.
- Digest truncation honesty: the email "tailor" action must route to the
  paste-the-full-JD flow, exactly like the /matches path — never tailor the
  ~500-char snippet.
- Match vs. scored-job score divergence after a full-JD tailor: the full-JD re-score
  IS saved to the scored-jobs/tailorings record (and shows there), but the original
  `matches` row keeps its snippet score — same job, two scores across two surfaces.
  DEFERRED decision: leave them as distinct artifacts (triage score vs. user-
  evaluated score) OR reconcile the match row to the full-JD score (which then
  interacts with the threshold filter).
- Reply-able digest sender: set `Reply-To` to a monitored address so a user can
  reply to a digest — folds with the login sender address work (hello@ → noreply@,
  or Cloudflare email routing).
- Smaller tidy-ups: recently-scored title cleanup (cosmetic).
- Parked (carried from earlier, not prioritized): resume view link (signed URL);
  PDF resume export (its own post-M5 milestone — see M6).

RESOLVED (investigation done — decisions to honor when the related work comes up):
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

## Deferred (not blocking; intentional)
- One coherent UX/design pass, done POST-M5 all at once via the design skills, not
  piecemeal. Hold all UI-polish items for it. Driver: per feedback, the pills and
  several surfaces read as AI-default and want an intentional revamp. Known item:
  `/scored/[id]` shows an empty "Suggested changes" section for un-tailored rows.
- Re-scoring a job silently un-approves a previously approved tailoring (minor).
- Whether user-pasted jobs should also feed the shared `jobs` pool (currently
  tailorings-only, which is fine for now). Open design question.
- Full-JD scoring: automated matching still scores the ~500-char Adzuna snippet
  (fine for triage). On-demand TAILORING now runs on the full posting — the
  Matches→Tailor flow routes the user to paste the complete JD, which re-scores +
  tailors it. The snippet-vs-full-JD score divergence this creates is tracked in
  the backlog above.

## Operational lessons (keep in mind)
- **Hand the migration as step 1.** Run migrations in Supabase BEFORE the deploy
  settles. We hit deploy-before-migrate races twice: the read path showed a blank
  list, the write path 500'd on insert. Always apply the SQL first.
- **The friendly error masks the cause.** The "wandered off for coffee" message
  hides the real exception. Check Railway logs for the actual error or cap, never
  assume from the user-facing message.
- **A Railway env var earns its place only as a secret or an active override.**
  Inert defaults belong in code (`.env.example` is the catalog), so config stays
  versioned and CI-gated. Corollary: any env var bumped temporarily for testing
  must be reverted before launch (see LAUNCH CHECKLIST) or it silently overrides a
  guardrail.
- **CI's quality job runs pre-commit with no `npm install`.** A frontend hook that
  shells out to `frontend/node_modules` fails there; pin tools via pre-commit's own
  env (`additional_dependencies`) instead. Also: frontend Prettier is enforced both
  locally (pre-commit) and in CI (`format:check`) — keep them on the same version.

## M5 — scheduled scan + email digest (COMPLETE)
Build order (guardrail-first — cost controls before the digest, because a July
community launch means a hard cost cap must exist before opening to strangers):
1. Opt-in flag — ✅ DONE (`preferences.email_opt_in`, migration 0010).
2. Cost controls — ✅ DONE. Per-user monthly caps + the global budget ceiling.
3. Email / Resend — ✅ DONE. `mailer.send_email` (httpx, PII-safe, sends from
   `noreply@myjobops.app` as "JobOps"); admin `POST /admin/test-email`.
4. Sent-state — ✅ DONE. `alerts_log` (migration 0011) + `unsent_matches_for_user`
   (reuses the threshold gate) + idempotent `mark_matches_sent`.
5. Digest composition — ✅ DONE. `send_user_digest` (score-only, double-gated on
   opt-in + threshold + paused, mark-on-send-success); admin `POST /admin/send-digests`.
6. Scheduler — ✅ DONE. Budget kill-switch wired; 15-day inactivity pause + one-time
   reinvite; run-and-exit `python -m app.scheduled` on the `jobops-scheduler` Railway
   cron service. Verified live.
7. Batch API — ⬜ DEFERRED. Move the scheduled, non-interactive scoring onto the
   Batch API (50 percent off). A cost optimization, not required for the loop.

Design decisions (shipped):
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
