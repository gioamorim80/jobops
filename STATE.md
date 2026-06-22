# STATE — where the build is

Self-contained snapshot for a fresh session. Dated history lives in
`CHANGELOG.md`; milestone acceptance criteria live in `ROADMAP.md`; system shape
in `ARCHITECTURE.md`. Read CLAUDE.md first (it is the contract).

## Current position
M0 through M4 are built and verified live, including the M2 flow polish and the
M4 decision-consistency fixes. Next milestone is M5 (scheduled scan + email
digest). Three small OPEN items should be cleared early next session (below).

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
  `claude-haiku-4-5` for the M4 automated matcher. Env in `config.py`:
  `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ADZUNA_APP_ID`,
  `ADZUNA_APP_KEY`, `ADMIN_USER_IDS` (comma-separated; empty = fail closed),
  `PER_USER_DAILY_LLM_CAP` (default 25), `ENRICH_DAILY_TURN_CAP` (default 50),
  `CORS_ORIGINS`. Live domain: myjobops.app.
- Checks before commit: `uv run pytest` (73 backend tests), `uv run ruff check`,
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
  confirmed.
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
category_tag), 0006 (tailorings role/company), 0007 (matches table). **Confirm
0008 (matches.decision column) has been run in Supabase** — it is required for the
decision-consistency fixes above and should be applied before relying on them.

## Open — clear early next session (priority order)
1. **Raise the LLM cap.** `PER_USER_DAILY_LLM_CAP=25` caused `skipped_for_cap: 17`
   on the M4 run (only 13 of ~30 scored), while real spend was tiny (about 80
   cents). Bump it to 50–75 in Railway, keeping a ceiling for runaway/abuse
   protection, then re-run `/admin/score-matches` for a full shortlist.
2. **Make prompt caching actually engage.** The M4 run showed
   `cache_read_tokens: 0` / `cache_write_tokens: 0`: the rubric + profile prefix is
   below Haiku's minimum cacheable length, so caching is wired but not saving
   (still paying cheap Haiku rates). Enlarge the cached prefix to clear the
   minimum, or verify the minimum is reachable, and confirm `cache_read_tokens > 0`
   on a re-run.
3. **Verify the 0008 fixes on the deployed app.** A 72-scored job should read
   "72/100 · Solid fit · Decision: STRETCH" with no vocabulary collision, and
   `/matches` should show the same score + band + decision as `/score` for the same
   job.

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
- Use the Batch API for the scheduled, non-interactive scoring (50 percent off,
  and it combines with prompt caching once caching engages).
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
