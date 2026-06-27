# CHANGELOG

## 2026-06-26 — Cap-exemption allowlist, fit-band recalibration, a design pass, routing fix, and coach-on-score

With M5 sealed, this sprint closed the post-launch rough edges: an owner cap-exemption
that still respects the budget ceiling, fit bands recalibrated to the real score
distribution, a design pass that restores the original intent, a post-onboarding routing
fix, and the coach wired into the score page so a user can correct a gap and see the
re-score immediately.

**Cap-exemption allowlist**
- `CAP_EXEMPT_USER_IDS` exempts trusted user_ids from ALL per-user caps (daily LLM,
  monthly score, monthly tailor, matcher daily) while STILL enforcing the global
  `MONTHLY_BUDGET_CEILING_USD`; usage is still logged; empty default = nobody exempt.
  `is_cap_exempt` lives in `usage.py` (not `admin.py`) to avoid an import cycle. Set on
  the backend service for the owner; the test-bumped tailor cap was reverted to 10 for
  the community.
- Decision: the exemption bypasses per-user caps but NOT the account-wide budget
  ceiling — the runaway brake applies to everyone, including exempt users.
- Rewrote the stale `test_budget_ceiling_is_built_but_not_wired_to_block` to assert the
  real invariant (the ceiling gates the scanner + the ondemand exempt path, NOT the
  digest/matcher).

**Fit-band recalibration (labels only)**
- A heavy user observed scores seemed to ceiling around 72–78; investigation found the
  all-time max fit across all users was 78, yet "Strong fit" required ≥80 — so
  "Strong fit" had never appeared. Recalibrated the cutoffs to 74/62/48 (Strong ≥74,
  Solid 62–73, Moderate 48–61, Likely skip <48) in BOTH `score_band` (backend) and
  `fitBand` (frontend), kept identical (boundary parity verified).
- Decision: labels-only — the scores and the scorer rubric are UNCHANGED, not inflation.
  The deeper finding: the scorer marking real experience as gaps is the no-fabrication
  rule working correctly (scoring is parsed-profile-only); the first-order fix is profile
  completeness (the Coach), not a more generous scorer. The bands are documented as an
  early-data calibration to revisit.

**Design pass — tokens, components, and UX/copy clarity**
- Tokens: a cooler/lighter background (#faf8f4), card drop-shadows replaced by hairline
  borders (restoring the original Chic Trancoso intent), lavender neutralized to a
  focus-only accent, and a radius scale (lg/md/chip) replacing the single radius.
- Components: decision chips restyled with semantic treatment (solid-green APPLY,
  ochre-outline STRETCH, muted-ghost SKIP) instead of three pale fills; the dashboard
  skills/domains pill-wall lightened to a borderless tag cloud.
- UX/copy clarity: renamed the user-facing action "Score a job" → "Check a job for fit"
  (labels only; routes/endpoints unchanged); promoted primary actions to clear buttons;
  rewrote technical copy in plain language ("score threshold" → "minimum fit score";
  friendlier empty states).
- Decision: framed as RESTORING the original design intent (hairline borders, a
  three-note palette) that had drifted to an AI-default look, not a redesign.

**Post-onboarding routing fix**
- The onboarding-completion redirect was hard-coded to `/dashboard` (the data-heavy
  screen), so first-time users landed there and felt lost; fixed to `/home` (the
  launcher), matching the login-callback routing. Added warm empty-state nudges on
  `/home` and the dashboard scored-jobs section.

**Coach on the score page (add context → confirm → re-score)**
- On the score result page, a "Something's missing?" block lets the user add true
  context the profile missed, routed through the EXISTING enrich flow: single-message
  `/enrich/chat` → shared `ProposalCard` (extracted from the coach page) → confirm →
  `/enrich/apply` updates `profiles.parsed` → auto re-score this job via the existing
  force path, showing the new fit inline and routing to Tailor. A mini-chat lets the
  user refine the proposal before saving (a hint on `ProposalCard` tells them they can
  reply to adjust).
- Decisions (integrity-preserving): reuses the enrich flow, never forks it; profile
  writes only via `/enrich/apply` (the single writer); the confirm gate is intact
  (nothing auto-applies); the job text is NEVER sent to `/enrich/chat` — enrichment is
  profile-level true experience, not job-fitting, to avoid fabrication pressure;
  re-score fires only on a confirmed apply.

## 2026-06-25 — M5 step 6: the automated scan-and-digest loop, now autonomous on a Railway cron service

M5 is complete. The scanner and digest, previously manual admin endpoints, now run
on their own on a schedule: a Railway cron service runs one process that scans for
new matches and emails the digests, then exits. The loop is budget-gated,
inactivity-aware, and was verified live.

**What shipped**
- **6.1 — scan-all loop + shared scanner core (1c82dbe).** Extracted the per-user
  fetch+score into `scanner.py` cores (`fetch_into_pool` / `score_from_pool` /
  `scan_user`) that the existing `/admin/fetch-jobs` and `/admin/score-matches`
  endpoints now call (one path, no duplication). Added `scan_all_opted_in`, which
  loops every `email_opt_in = true` user with per-user failure isolation (one bad
  profile/source never aborts the run), plus admin-gated `POST /admin/scan-all`.
- **6.2 — budget kill-switch (214471d).** Wired the previously-inert
  `is_over_monthly_budget` into `scan_all_opted_in` — checked at the top of the run
  AND re-checked before each user, so a long run stops the moment month-to-date
  spend crosses `MONTHLY_BUDGET_CEILING_USD` ($15) rather than blowing past it. This
  activates the ceiling built inert in step 2. It gates the scanner ONLY (the only
  LLM-spending path); the LLM-free digest is never blocked by it.
- **6.3 — 15-day inactivity pause + one-time reinvite (8de33ba).** "Active" is a
  UNION: a recent sign-in (`auth.users.last_sign_in_at`) OR any recent `usage_log`
  row. Inactive users are skipped to save cost; the first time a user crosses into
  inactive, `preferences.paused` is set and ONE courteous reinvite email is sent
  (links to `/home` — returning to the app auto-unpauses them). Paused users are
  skipped for BOTH scan and digest until they return. The reinvite respects consent
  (only opted-in users are ever in the loop).
- **6.4 — scheduler entrypoint (0a13801).** `python -m app.scheduled` runs
  `scan_all_opted_in` then `digest_all_opted_in` and exits (0 on success, 1 if
  either raised). Scan completes before digest so the digest emails freshly-scored
  matches; the digest runs even when the scan was budget-skipped (it spends nothing
  and emails already-scored matches); scan and digest failures are isolated; logs
  are counts/status only (PII-safe). Extracted the shared `digest_all_opted_in`,
  reused by the `/admin/send-digests` no-user_id path.
- **Friendly sender name (8a58b19).** `ALERT_FROM_NAME=JobOps` so digests read from
  "JobOps", not "noreply"; the address is unchanged and it falls back to the bare
  address when unset.

**Operational**
- A separate Railway cron service (`jobops-scheduler`) runs `python -m app.scheduled`
  on its own schedule, sharing the backend image and env. Cron schedule `0 11 */2 * *`
  (7am ET, every other day, UTC).
- Verified live: a scheduled run scanned, scored, and emailed a real digest, then
  exited clean.

**Decisions recorded (with the why)**
- Scheduler mechanism: a Railway NATIVE CRON SERVICE (run-and-exit entrypoint), NOT
  in-process APScheduler — avoids redeploy-miss and multi-replica double-fire for a
  money-spending, user-emailing job.
- "Active" is a UNION (sign-in OR usage_log) so a user who browses but runs no LLM
  action isn't wrongly paused. It degrades to the usage_log signal if the admin API
  is unavailable (fails toward "might keep an active user active", acceptable).
- The reinvite link routes into the app (returning auto-unpauses), NOT a tokenized
  resume endpoint — avoids adding a new secure-link surface.
- The budget ceiling gates the scanner only; the digest is LLM-free and
  intentionally ungated.

## 2026-06-24 — M5 cost controls, the Matches→Tailor fix, and a Prettier hook

M5 continued guardrail-first: per-user monthly caps landed, the Matches→Tailor
flow was fixed to tailor the complete posting, and frontend formatting is now
caught locally. (M5 step 1, the email opt-in flag (09b42b3), shipped in the entry
below.)

**M5 step 2 — cost controls**
- Per-user monthly caps + inert budget ceiling (e618b37): per-user monthly SCORE
  (50) and TAILOR (10) caps that coexist with the daily runaway brake (raised to
  100); calendar-month reset on the 1st; score and tailor capped separately so one
  never blocks the other. A global monthly budget ceiling (`is_over_monthly_budget`,
  $15) is built and unit-tested but INERT — wired to the digest scanner in a later
  step. All four limits env-configurable.

**Matches → Tailor fix**
- Tailor button disables on a cap-limit response (c0bd8c1): the score-page Tailor
  button latches disabled when a tailor call returns `limit_reached`, keyed off the
  status (not message text or generic errors), so repeat clicks can't keep hitting
  the cap.
- Paste-full-JD score+tailor (f905a09): the /matches "Tailor" button now routes to
  `/score?match=<id>` instead of an unfetchable Adzuna URL. A new JWT-scoped
  `POST /matches/context` returns minimal match context (title/company/source_url,
  no stale snippet score). `?match` mode shows a paste-the-full-posting view with
  one "Score & tailor" button that scores then tailors the pasted COMPLETE JD — no
  URL re-fetch, and tailoring runs on the full posting rather than the ~500-char
  snippet. Caps + the exact-match cache are enforced by construction; the normal
  Score-a-job path is unchanged. Cross-user isolation tested.

**Tooling**
- Prettier pre-commit hook (1a107d6): a local frontend Prettier hook (auto-fix +
  restage, matching the ruff hooks), Prettier 3.4.2 pinned via pre-commit's own
  node env so it runs in CI's quality job (no `npm install` there) and reads
  `.prettierrc`. Closes the gap where frontend format issues only surfaced at CI's
  `format:check`. Scoped to frontend file types; backend stays with ruff.

**Decisions recorded (with the why)**
- Tailoring runs on the COMPLETE posting, never the Adzuna ~500-char snippet. The
  matches Tailor control routes the user to paste the full JD, which re-scores and
  tailors in one click ("Score & tailor", matches-arrival path only). Truncation is
  fine for triage scoring but is gated for tailoring, where accuracy matters.
- Admin cap-exemption allowlist (Option 3): deferred to the post-milestone backlog.
  In the interim, test-time cap bumps go through Railway env vars (revert before
  launch — see STATE's launch checklist).
- Config principle: a Railway env var earns its place only as a secret or an active
  override. Inert defaults stay in code; `.env.example` is the catalog. (This is why
  the budget ceiling and monthly caps are code defaults, not new prod env vars.)

## 2026-06-23/24 — Pre-M5 cleanup, the /matches cluster, and M5 step 1 (email opt-in)

Cleared the pre-M5 backlog (correctness fixes + the /matches surface), recorded
the decisions that close out several open questions, and started M5 with the
email opt-in flag. Migration order reminder: 0010 runs in Supabase before the
M5-step-1 deploy.

**Correctness / bug fixes**
- Field-scoped merge on profile edit (f257e96): a settings save now replaces only
  the form-owned fields and preserves coach-written `attribution_notes` from the
  DB row, so a stale client can no longer wipe them.
- 5xx observability (634ec7a): the real cause of a 5xx is now logged server-side,
  PII-safe; the user-facing "coffee" message is unchanged.
- Scorer-v2 (2d73597): adds a `scorable` flag (skip-save on non-postings),
  `posting_seniority`, and a deterministic APPLY→STRETCH cap at ≥2 levels above the
  target. Fixes Bug 1 (non-postings) and Bug 4 (auto-APPLY of thin/too-senior roles).
- Bug 5 dedupe (9761a95): the prefilter collapses same title+company openings and
  keeps the best-ranked instance; location is intentionally dropped, trading a few
  merged distinct openings for fewer, stronger cards. Applies to future runs only.

**/matches cluster + UX**
- Threshold filter (edddde4) + context line (9b08560): `/matches` shows only
  matches scoring at or above the user's `score_threshold`, with a self-explaining
  line and a Settings link. The threshold check is written so the M5 digest reuses
  the same rule.
- Nav active-state (45ab474): the top nav now highlights the current route (the
  highlight was never fully implemented); uses `aria-current` and a prefix guard so
  `/scored` does not light up `/score`.
- Per-row delete on /matches (fbe81af): delete a single match through a JWT-scoped
  backend endpoint, keeping the `matches` table service-role-write-only.
- Landing redirect (e16b735): logged-out visitors to app routes land on the
  marketing page instead of being bounced silently to login.

**M5 started**
- Email opt-in (09b42b3): adds `preferences.email_opt_in` (bool, default false for
  consent) via migration 0010, and replaces the alert-frequency dropdown with a
  single "Email me new matches" toggle in onboarding and settings. The flag is
  written but nothing reads it yet.

**Decisions recorded (with the why)**
- Bug 3 (legacy null-decision pills): WON'T-FIX. `decision` is null only on the
  fixed set of pre-0008 legacy rows, which render harmlessly; every new row gets a
  decision, and the threshold filter plus per-row delete handle stale rows.
- Stale matches: covered by the threshold filter and the delete button, not by an
  automatic re-score mechanism. Accepted residual: a high-scoring row with
  now-stale reasoning must be deleted by hand.
- Deep-link preservation after login: CONSIDERED, NOT WANTED. Shared links are
  product intros, not deep links, so an unauthenticated visit should reach the
  intro page rather than resume a specific destination.
- M5 reorder: the budget guardrail and per-user monthly caps move BEFORE the
  digest. A community launch is planned for July, so a hard cost cap must exist
  before the product opens to strangers.
- Design revamp: the pills and several surfaces read as AI-default (per feedback).
  Deferred to post-M5 and done all at once via the design skills, not piecemeal.

## 2026-06-22 — Close M4 open items: LLM cap raised, caching declined, per-call model recorded

**What was done**
- Closed the two open M4 items. Raised the scorer LLM cap from 25 to 50:
  `PER_USER_DAILY_LLM_CAP` (default 25 in config.py, set to 50 in prod (Railway)),
  so a full ~30-job shortlist scores in one run; kept a ceiling for runaway/abuse
  protection.
- Evaluated prompt caching on the scorer and DECLINED it (see decisions).
- Added a `model` column to `usage_log` (migration 0009, nullable, no backfill).
  Made the score, tailor, and enrich steps pass their model explicitly via per-step
  constants (`SCORE_MODEL` / `TAILOR_MODEL` / `ENRICH_MODEL` = `claude-sonnet-4-6`),
  mirroring `matcher.py`'s `MATCH_MODEL`. Each constant now drives BOTH the Anthropic
  call and the `usage_log` row from one source, so per-call cost is attributable by
  model.
- Added routing tests (`backend/tests/test_llm.py`) that patch the Anthropic client
  at the lowest layer and prove the passed model wins over `settings.anthropic_model`.
  Suite went 73 → 78 passing.
- Migration 0009 applied to prod by hand; commit 7e92ce2 shipped, CI run #39 green;
  verified live — a post-deploy `score` row recorded `claude-sonnet-4-6` while
  pre-deploy rows stay NULL as designed.

**Decisions (with the why)**
- Scorer prompt caching declined: the scorer prefix (~1.1k tokens) is below the
  cacheable minimum (Haiku 4.5 = 4096 tokens), and the per-job posting text
  dominates the input anyway, so caching there would save almost nothing. Caching is
  deferred to the TAILOR step, where a large stable per-user context (profile + base
  resume + rubric) repeats across calls and clears the minimum.
- Per-call model is now recorded from a single source that drives both the API call
  and the log, replacing two independent env fallbacks that agreed only by
  coincidence and could silently drift if the global default changed.
- Per-step model is a CODE CONSTANT, not an env var: model changes are now
  versioned, CI-gated, and leave a git trace. Chose auditability over the
  flexibility of an `ANTHROPIC_MODEL` override, on purpose. (The per-user LLM cap, by
  contrast, stays an env var — `PER_USER_DAILY_LLM_CAP`, default 25 in config.py, set
  to 50 in prod (Railway) — because an operational throttle should be tunable without
  a deploy.)
- `usage_log.model` is nullable with no backfill; pre-existing rows stay NULL.

**Open items**
- Confirm a full scoring run at cap=50 has been executed (last tick before sealing
  M4 core).
- Low-priority backlog (unchanged): login email sender → noreply@myjobops.app via
  Cloudflare routing; clean company/role title on the "recently scored" list.

**Next step**
- M5: the automated scanner/digest loop with email delivery.

## 2026-06-22 — Handoff: M4 verified live; STATE.md rewritten self-contained
- M4 verified live: `/admin/score-matches` scored 13 matches on `claude-haiku-4-5`,
  `usage_log` `match_score` rows came in cheaper than Sonnet `score` rows, the
  Matches UI renders, and RLS isolation was confirmed.
- Two findings from the live run, logged as OPEN for next session: (1) the run hit
  `skipped_for_cap: 17` because `PER_USER_DAILY_LLM_CAP=25` — real spend was about
  80 cents, so raise the cap to 50–75 (keep a ceiling) and re-run; (2) prompt
  caching did not engage (`cache_read_tokens: 0` / `cache_write_tokens: 0`) because
  the rubric + profile prefix is under Haiku's minimum cacheable length — caching
  is wired but not yet saving (still cheap Haiku rates); enlarge the prefix to
  clear the minimum.
- Rewrote STATE.md as a concise, self-contained handoff snapshot (current
  position, what is done, migrations, open items in priority order, deferred items,
  operational lessons, and the M5 design sketch). Dated history stays here in
  CHANGELOG.md. Refined the M5 roadmap entry: single "email me matches" signup (no
  cadence toggle), signal-gated sends about every two days, recency as a separate
  digest signal, Batch API for scheduled scoring, sent-state tracking.
- Reminder for next session: confirm migration 0008 (matches.decision) is applied
  in Supabase. Docs-only change; no code touched.

## 2026-06-22 — M4 polish: score / band / decision consistency
- The scorer logic was already correct (decision is a holistic model judgment, not
  a function of the numeric score — two equal scores can legitimately differ).
  These were the presentation/storage gaps around it:
- Vocabulary collision: the fit band's 50–64 label was "Stretch", which read as
  contradictory next to the separate STRETCH decision. Renamed the band to
  "Moderate fit" (in both frontend `fitBand` and backend `matcher.score_band`), and
  framed the decision chip as "Decision: APPLY/STRETCH/SKIP" on /score, /scored/[id],
  and /matches so the fit band and the decision read as two different axes.
- Cross-path drift: the `matches` table (0007) stored band but no decision, so
  /matches showed only a band while /score showed band + decision for the same job.
  Migration `0008_matches_decision.sql` adds a nullable `decision` column; the
  matcher now stores it and /matches renders it. Run 0008 BEFORE deploying. Rows
  scored before it keep decision = NULL and simply omit the chip until re-scored.
- Silent fallback: `_normalize_score` still defaults a missing/invalid decision to
  STRETCH (never crashes) but now logs a WARNING with the offending value, so a
  malformed scorer reply is surfaced rather than masked.
- No change to the scorer rubric. 73 backend tests pass; frontend lint + build
  clean; pre-commit clean.

## 2026-06-22 — M4: automated matching (prefilter shortlist → LLM scores → matches)
- New per-user `matches` table (migration `0007_m4_matches.sql`): id, user_id,
  job_id (FK→jobs), score, band, cleared, gaps, analysis, posted_at, model,
  scored_at; UNIQUE (user_id, job_id). Per-user RLS — users SELECT only their own
  rows; no write policy for authenticated, so only the backend service role writes
  (it bypasses RLS). This is the tenant-isolation boundary the shared, non-RLS
  jobs pool deferred. Run the migration BEFORE deploying the code.
- Backend `app/matcher.py`: scores each shortlisted job not yet scored for the
  user, reusing the EXISTING honest scorer (same `SCORER_SYSTEM_PROMPT_V1` and
  `_normalize_score`) on the ~500-char snippet + profile, and upserts a match. The
  fit score stays pure — recency/posted_at is never mixed in; posted_at is carried
  onto the row only so M5 can rank by recency separately.
- Cost architecture, all on from the start: the scorer runs on Haiku 4.5 (Sonnet
  stays reserved for on-demand tailoring); prompt caching marks the rubric+profile
  prefix so only the per-job snippet is uncached (`llm.run_cached_json_agent`);
  `usage.log_call` is now model- and cache-aware and logs action `match_score`,
  so Haiku + caching savings show up in usage_log; the per-user daily cap is
  respected — a run scores what fits and reports `skipped_for_cap`, never crashing.
- Trigger: gated `POST /admin/score-matches` (same fail-closed ADMIN_USER_IDS gate
  as fetch-jobs) prefilters the user's candidates from the pool and scores the
  shortlist. No scheduler (that is M5), no email, no auto-tailoring.
- Frontend: a dedicated `/matches` section (new nav link), separate from the
  Scored-jobs tracker. Each match shows role/company, location, score + band,
  honest cleared/gaps, a "View posting →" link, and a "Tailor my resume for this"
  button that deep-links into the on-demand score+tailor flow (`/score?url=…`,
  which now auto-runs). Tailoring stays gated behind the click.
- Multi-tenant throughout: matches RLS, RLS-scoped reads, user_id from the verified
  JWT (admin target is gated). 71 backend tests pass; frontend lint + build clean;
  pre-commit clean.

## 2026-06-22 — Split "Score a job" into two gated steps (score, then tailor)
- Enforces the core cost principle: scoring is cheap and automatic; tailoring is
  the expensive Sonnet step and is now gated behind explicit user intent. Before,
  one "Score & tailor" button auto-tailored every scored job.
- `POST /ondemand/score` runs ONLY the scorer (usage_log action "score") and saves
  the tailoring scored-but-not-tailored (empty bullets/analysis, approved=false).
  It no longer loads the resume text. A forced re-score resets any prior tailoring
  and approval.
- New `POST /ondemand/tailor {id}` runs the tailor on demand for one of the
  caller's own scored rows (usage_log action "tailor"), saves the suggested
  bullets + analysis, and returns them. An already-tailored row returns its saved
  bullets with no model call. Same per-user daily cap; 404 if the row isn't the
  caller's, 422 if there's no saved job text. Scoped by JWT user_id.
- `/score` response now includes `tailored` (bool) and `tailor` (the saved
  tailoring or null). Frontend `/score`: the primary button is "Score"; the result
  shows score, band, decision, cleared, and gaps, then either the saved
  suggestions (if already tailored) or a "Tailor my resume for this" button that
  runs tailoring only when clicked. The approve flow, review flags, match
  analysis, no-fabrication copy, role/company extraction, source link, and applied
  controls are unchanged.
- Cost visibility: usage_log already distinguishes "score" from "tailor"; tailoring
  now only appears there on an explicit Tailor click. A low-fit job can be scored
  and left untailored, spending nothing on tailoring.
- flags and "Match analysis" come from the tailor step, so they surface after
  tailoring (not on the cheap score view). All reads/writes stay scoped to the
  user's own rows (RLS + JWT). No migration, no new env. 68 backend tests pass;
  frontend lint + build clean; pre-commit clean.

## 2026-06-22 — Scored jobs list: role/company labels + clean source link
- The history row now reads "Role — Company" instead of the first line of the job
  description. Shows just the role when the company can't be determined, and a
  short fallback (the posting's host, else "Scored job") when neither is known —
  never raw description copy.
- The scorer now also extracts `role` and `company` from the posting text. This is
  extraction, not fabrication: it returns "" when the posting doesn't state one,
  and never guesses a company from the URL or the kind of work. docs/agents/
  SCORER.md mirrors the two new output keys; the existing fit/decision/cleared/
  gaps/referral_angle/pitch keys are unchanged. The score endpoint tidies the
  values (`_clean_label`) and stores them.
- Migration `0006_tailorings_role_company.sql` adds nullable `role` and `company`
  to tailorings. No new grants needed (existing RLS policy + 0002 grants cover the
  columns). Idempotent.
- Source link: when a tailoring has a `source_url`, the row shows a small
  "View posting →" link that opens in a new tab (rel="noopener noreferrer"). The
  long URL stays in the href and is never rendered as text. Pasted-text rows (no
  source_url) show no link.
- Frontend `jobSnippet` was replaced by `jobLabel(role, company, source_url)` and
  used by both the Dashboard scored list and the Home "Recently scored" peek.
  Score, band, date, the applied controls, the editable applied date, and delete
  are unchanged. All reads stay scoped to the user's own rows via RLS.
- Existing rows scored before this change have null role/company and show the
  fallback label until an optional one-time backfill re-extracts them (see
  STATE.md for the two options). No data is broken.
- 67 backend tests pass; frontend lint, prettier, and build are clean; pre-commit
  clean. No new env.

## 2026-06-22 — Editable applied date on the Scored jobs list
- "Mark as applied" previously stamped applied_at with now() and offered no way to
  correct it, but users often apply on a different day than they click the button.
  The applied date is now editable.
- Backend `POST /ondemand/applied` accepts an optional `applied_on` ("YYYY-MM-DD").
  Marking applied stores that day (defaulting to today) at noon UTC, so it reads
  as the same calendar date in any timezone; un-marking clears it; an invalid date
  returns 422. The conversion lives in a pure `_applied_at_iso` helper with
  no-network unit tests. The write stays scoped to the caller's own row (JWT
  user_id + existing tailorings RLS); applied_at remains a timestamptz, so there
  is no migration.
- Frontend `AppliedToggle`: marking applied opens a date input defaulting to today
  (Save / Cancel); the "Applied ✓ <date>" badge gains an "Edit date" action that
  reopens the input pre-filled, beside "Un-mark". The badge reads the stored date
  in UTC so it matches the chosen day. New on-brand `.applied-edit` / `.input-date`
  styles wrap on mobile, and the input caps at today.
- 66 backend tests pass; frontend lint, prettier, and build are clean; pre-commit
  clean. No migration, no new env.

## 2026-06-21 — M3 fix: duplicate jobs in the prefilter shortlist
- Symptom: the fetch worked (fetched_raw 157, unique_stored 123) but the returned
  shortlist repeated jobs — the same posting under different tracking-param or
  URL-form redirect links (Justworks twice, Lyft "Causal Inference" three times,
  Capital One twice).
- Root cause was not the hash. `content_hash` already keys on the stable
  `source + external_id` (never the redirect_url), so the shared pool deduped
  correctly (157 → 123). The leak was that `admin.py` built the shortlist with
  `prefilter(parsed, all_jobs)` over the RAW fetched list, so a posting returned
  by more than one keyword query or page reappeared in the shortlist even though
  it stored as a single row.
- Fix (presentation layer, no hash change): `prefilter` now dedupes its ranked
  output by `content_hash` (Adzuna's stable external_id), keeping the best-ranked
  instance, before applying the cap. The cap now counts unique postings.
- Dedupe key is external_id, deliberately NOT title+company. Same ad id under
  different tracking URLs collapses to one; genuinely distinct postings that share
  a title and company — the EY EDGE Data Scientist role advertised in Stamford,
  Iselin, Hoboken, and Grand Central (four ad ids, four cities) — all survive.
- Verified with a group-by(title, company): Justworks 2→1, Lyft 3→1, EY EDGE stays
  4; no repeated ad id in the shortlist. 62 backend tests green, pre-commit clean.
  No migration, no new env, zero LLM.

## 2026-06-21 — M3 fix: Adzuna location/remote query (was returning 0 jobs)
- Cause: the per-user fetch passed the profile location verbatim as Adzuna
  `where` (e.g. `where='NYC Metro Area'`, which Adzuna cannot geocode → 0
  results) and mapped remote_pref `flexible` to a hard `remote=False`.
- Location: new `_normalize_location` turns a free-text profile label into a
  clean, geocodable city centre, and the adapter passes `distance=45` (km) so a
  single city covers its commuter metro. Handles aliases (NYC/NYC Metro/New York
  Metro → New York; SF Bay Area/Bay Area → San Francisco; Greater Boston →
  Boston), generic metro-suffix stripping (Seattle Metro Area → Seattle), and
  plain cities pass through. Labels that aren't a geocodable place
  (remote/US/anywhere, or anything not confidently a city) omit `where` and log
  the decision, so the fetch falls back to a nationwide search instead of 0.
- Remote: `SearchCriteria.remote: bool` → `remote_pref: str` (the raw profile
  value). `remote`/`remote only` searches nationwide (no `where`); `flexible` and
  `on-site` pin the resolved city centre + radius. A `flexible` preference no
  longer excludes remote jobs — Adzuna has no remote filter, so a location search
  returns both remote- and onsite-tagged postings.
- Generosity: the role keyword now goes to `what` (broad match) instead of strict
  `title_only`, per the prefilter philosophy (honest fit is M4's job).
- Logs the exact final params built from the profile (page / what / where /
  distance / max_days_old / remote_pref / location); credentials are never logged.
- Query-building/adapter layer only: no migration, no profile-UI change, zero
  LLM. Tests: 25 source tests (normalization + param building), 58 backend total,
  all green. Dry-run on the user's profile builds
  `what='Senior Data Scientist' where='New York' distance=45`; a non-NYC profile
  (Austin) builds `where='Austin' distance=45`. A live result count needs real
  Adzuna creds (set on Railway; local .env keys are blank).

## 2026-06-21 — M3 audit fixes: Adzuna field mapping
- Migration `0005` adds nullable columns to `jobs`: `salary_is_predicted`
  (boolean), `contract_time`, `contract_type`, `category_tag`. No new grants
  needed (added columns on an existing table; 0004 grants + RLS cover them).
- Adapter: the strict `AdzunaJob` model and `NormalizedJob` now capture
  `salary_is_predicted` (Adzuna "1"/"0" → bool), `contract_time`, `contract_type`,
  and `category.tag` (kept alongside the existing `category.label`).
- `created` is now parsed/validated in the adapter to a canonical timestamp; if it
  doesn't parse, `posted_at` is set null and logged, so one bad date can never
  fail the whole upsert batch (Postgres would otherwise reject the batch cast).
- `salary_is_predicted` is always persisted next to the salary. DATA_MODEL.md and
  ROADMAP M4 note that the M4 scorer must treat a predicted salary as a rough
  estimate and never apply a hard salary-floor penalty on an Adzuna prediction.
- Robustness: kept `extra="ignore"` (not `forbid` — Adzuna adds fields routinely).
  Extended the batch sanity-check to also WARN when `title`/`description` is empty
  across a high fraction of a batch — catching an optional-but-important field
  going systematically missing (a likely rename/format change), not just the
  zero-results case.
- Left the ~500-char description as-is for M3; documented (DATA_MODEL.md, ROADMAP
  M4) that M4 should decide whether to re-fetch the full JD via `source_url`, and
  that the M2 paste-a-link flow is the path for full-text on-demand scoring.
- Still zero LLM calls. 39 backend tests pass; pre-commit green.

## 2026-06-21 — M3: per-user job-source ingestion, dedupe, no-LLM prefilter
- Schema: migration `0004` adds the shared `jobs` pool of public postings. It
  holds no user data, so it is intentionally not per-user RLS: authenticated read,
  service-role write, with a unique `content_hash`. The shared-pool rationale and
  the per-user isolation note are documented in DATA_MODEL.md.
- Sources: a `JobSource` interface (`app/sources/base.py`) and an Adzuna US
  adapter (`app/sources/adzuna.py`) in a small registry. Credentials come from the
  environment. The query is built per user from the profile (target roles to
  `title_only`, location to `where`, remote preference respected), country US,
  with a polite bounded fetch (50 per page, a couple of pages per role, a short
  delay). `redirect_url` is stored as `source_url` per Adzuna ToS.
- Strict validation and graceful failure: every response is parsed through strict
  Pydantic models; a structural change or missing required field is logged
  specifically and skipped rather than stored as garbage. Zero-result and high
  parse-failure batches log warnings. Each source runs in its own try/except, so a
  source failure (410 auth, non-200, timeout, upstream down) is logged and skipped
  and never 500s the app or kills the fetch. No exception is swallowed silently.
- Dedupe (`app/dedupe.py`): a stable `content_hash` (source + external id, else
  title + company + location) and an upsert on it, so a posting fetched twice is
  one row and a re-fetch only updates `fetched_at`.
- Prefilter (`app/prefilter.py`): a deterministic, no-LLM, generous ranked
  shortlist (cap ~30) on safe signals (location/remote fit, recency, keyword
  overlap). It narrows the firehose without judging true fit; that is M4's job.
- Trigger: `POST /admin/fetch-jobs` runs a per-user fetch on demand (no scheduler;
  the multi-user loop is M5). It is gated by an `ADMIN_USER_IDS` allowlist checked
  against the caller's verified JWT; an empty allowlist denies everyone (fail
  closed). Target user defaults to the caller; an admin may pass a user_id.
- Cost: $0 LLM spend (no model calls anywhere in M3). New env `ADMIN_USER_IDS`
  plus the existing `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` (placeholders in
  `.env.example`). 37 backend tests pass; pre-commit green.

## 2026-06-21 — Applied marker on scored jobs
- Schema: migration `0003` adds a nullable `applied_at` (timestamptz) to
  `tailorings` (null = not applied, a timestamp = applied on that date). No new
  grants needed; the 0002 table grants and the `tailorings_own_rows` RLS policy
  already cover the new column.
- Backend: `POST /ondemand/applied` toggles the marker for one of the current
  user's tailorings — `applied_at = now()` when marking, null when un-marking.
  user_id comes from the verified JWT; the write is scoped to the caller's own
  row, so isolation is preserved.
- Frontend (Dashboard scored-jobs list): not-applied rows show a "Mark as
  applied" action; applied rows show an "Applied ✓ <date>" badge with an
  "Un-mark" action. Score, decision, date, and Delete controls are unchanged.
  On-brand styling; the row wraps on narrow screens so it stays usable on mobile.
- Tests: added an auth-gate test for the new endpoint. 23 backend tests pass;
  frontend build/lint + pre-commit green.

## 2026-06-20 — Fix Coach 502 on multi-turn (silent JSON-parse crash)
- Actual cause (confirmed): after a few turns the model replies in plain prose
  without the JSON envelope the Coach expects, and `extract_json_object` raised
  `HTTPException(502, "Agent returned no JSON.")`. FastAPI returns HTTPException
  as a clean response with no traceback, which is why it looked like a silent
  Railway 502. The cap was not involved.
- Fix: the Coach now gets the raw model text (new `run_chat_text` in `llm.py`,
  which does not force JSON) and parses it leniently. A prose reply becomes the
  chat reply with no proposal, so a 6–8 turn conversation completes instead of
  crashing; a real JSON envelope still yields the structured proposal.
- Visibility: all response handling after the model call is wrapped to log the
  full exception/traceback and return a clean JSON error (`status: "error"`)
  instead of a 502; the non-JSON-reply case logs an INFO line.
- Frontend: `EnrichResponse` gains an `error` status; the coach page shows the
  message and lets the user retry (only the daily limit disables input).
- Tests: added cases proving prose replies no longer raise, and that JSON
  envelopes (with and without a proposal) still parse. 22 backend tests pass.

## 2026-06-20 — Fix Coach chat cap tripping after ~2 messages
- Diagnosis: the counting was already correct (one logged "enrich" turn per user
  message, filtered to that user and to today, against a default cap of 50), so
  the code could not trip at message 3. The cause was the deployed
  `ENRICH_DAILY_TURN_CAP` being left at a tiny test value (we had set it to 2
  earlier to demo the limit and never reverted it), so the cap itself was 2.
- Fix: added a generous abuse-only floor (`ENRICH_TURN_FLOOR = 40`); the
  effective cap is `max(configured, 40)`, so a stray low value can no longer cut
  off real conversations. Default with no env stays 50.
- Added visibility: the chat endpoint now logs `turns_today`, the configured cap,
  and the effective cap on every turn (and a warning when the limit is genuinely
  reached), so the count vs cap is clear in server logs.
- Documented `ENRICH_DAILY_TURN_CAP=50` in `.env.example` with a note not to set
  it low in production.
- Added regression tests proving the count is per-user, daily (since 00:00 UTC),
  and filtered to only `enrich` turns (so history length and other features never
  inflate it). One user message increments the count by exactly one.
- Multi-tenant isolation and no-fabrication unchanged.

## 2026-06-20 — Spell "resume" without the accent everywhere
- Swept all "résumé" to "resume" across the whole repo: frontend UI copy and
  card titles (for example "Suggested changes to your resume", "Replace resume",
  the "Resume" card), backend agent prompts and comments, types, and the docs.
  Capitalized "Résumé" became "Resume". Spelling is now consistent with the
  CLAUDE.md style rule. Copy/spelling only, no logic or behavior change; backend
  tests and the frontend build pass.

## 2026-06-20 — M2.6: custom domain, branded email, design polish
- Custom domain myjobops.app is live on Vercel and serves the app. README now
  links it as the canonical URL.
- Branded transactional email through Resend: magic-link login emails are sent
  from the domain, with DKIM and SPF verified. (Recurring digests remain planned;
  this covers auth email only.)
- Supabase auth redirect URLs and the Railway CORS allowlist were updated for the
  new domain.
- Marked the responsive design refinement pass (smaller type and spacing scale,
  comfortable mobile gutters, header gutter fix) as part of this milestone. These
  were visual-only changes already shipped in the entries below.
- Docs: ROADMAP adds M2.6 as DONE; M3–M6 stay planned.

## 2026-06-20 — Mobile header gutter fix (visual only)
- The mobile `.app-header-inner` override set `padding: 0.5rem 0`, which zeroed
  the horizontal padding and overrode the `.container` gutter, pinning the
  "JobOps" logo to the left edge and clipping "Sign in" on the right. Changed it
  to `padding: 0.5rem 22px` so the header matches the body container's gutter at
  phone widths. Logo and Sign in now sit clearly inside the screen on both edges.

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
  doubled "honest" in the opening paragraph, and standardized the resume spelling
  to drop the accent. Factual content (current features vs. roadmap) is unchanged.
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
  resume" to match the app; added an "An honest coach" tile (live); and reworded
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
  your resume", and each suggestion now shows WHERE it applies — the real role
  (title + employer/dates) and section it belongs under (e.g. "Senior Engineer,
  Acme (2021–2024) — Experience"), drawn from the user's real resume, never
  invented. Kept the original → suggested → why structure (added a `where` field
  to the Tailor output, the bullet model, and both result views).
- No RLS/auth/isolation change, no migration. `ENRICH_DAILY_TURN_CAP` is a new
  optional setting (defaults to 50). 16 backend tests + build/lint/pre-commit green.

## 2026-06-20 — M2.5: conversational profile-enrichment coach
- **New feature:** a warm chat ("Coach", reachable from the nav) where a logged-in
  user enriches their profile with TRUE context the resume missed — stories of
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
  profile" → Settings; resume replacement is a separate, optional action.
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
