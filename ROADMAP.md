# ROADMAP — JobOps milestones

Built one milestone at a time; a milestone is done only when its acceptance
criteria pass AND it deploys. **M0 through M5 are done — the automated scan-and-digest
loop is live and autonomous on a Railway cron service.** Remaining: resume document
export and Batch scoring (M5 step 7).
The on-demand link flow (M2) was sequenced ahead of the automated scanner
(M3–M5) by design.

## M0 — Bootstrap the monorepo ✅ DONE
Goal: skeleton that deploys and proves the agent brain works end to end.
- Monorepo: `/frontend` (Next.js), `/backend` (FastAPI), `/supabase`, `/docs`, `/prompts`.
- Supabase project; backend and frontend read env from `.env`.
- Backend `/health` + `/agent/ping` (a real Anthropic call returning the text).
- Frontend on Vercel; backend on Railway; both green.
**Done:** the deployed frontend hits `/agent/ping` and shows a live model response.

## M1 — Auth + onboarding → profile ✅ DONE
Goal: a new user signs up and is onboarded into a structured profile.
- Supabase magic-link auth in the frontend.
- `profiles`, `preferences` tables + RLS (see `docs/DATA_MODEL.md`).
- Resume upload to a private Supabase storage bucket; onboarding agent
  (`docs/agents/ONBOARDING.md`) parses it, asks a couple of gap questions,
  confirms, and writes the profile (extraction only — never invents).
- Settings screen for alert frequency + score threshold (stored preferences).
**Done:** two different accounts each complete onboarding and see only their own
profile (RLS verified).

## M2 — On-demand: paste a link → score + suggested resume changes ✅ DONE ← MVP wedge
Goal: the instantly-useful single action.
- Endpoint accepts a URL or pasted text; single readability fetch with a
  "paste the text" fallback when a link is blocked/thin (no host hammering).
- Run Scorer (`docs/agents/SCORER.md`) then Tailor (`docs/agents/TAILOR.md`)
  against the user's stored profile.
- UI shows: a **0–100 fit score with a qualitative band** (Strong / Solid /
  Moderate / Likely skip; cutoffs recalibrated to 74/62/48 from real score data,
  labels only) and decision (APPLY / STRETCH / SKIP); cleared
  requirements; honest gaps; **"Suggested changes to your resume"** — each
  showing *where* it applies (role + section), as original → suggestion → why;
  match analysis. The user edits and explicitly approves; results save to
  `tailorings` with a per-user **history**.
- Scoring runs at **temperature 0** for stable, repeatable scores.
- **Exact-match cache** returns a prior result with no model call; "Re-score"
  forces a fresh run.
- **Cost guardrails:** per-user daily caps (a friendly limit, never a crash) and
  per-call **usage logging** (`usage_log`).
**Done:** a user pastes a real posting and gets an accurate, banded fit + honest
suggested resume changes they approve, with no fabricated content; repeat scores
are stable and cached; everything is per-user isolated.

## M2.5 — Profile-enrichment Coach ✅ DONE
Goal: let a user enrich their profile with true context their resume missed,
conversationally.
- A scoped **Coach** chat in the app: warm but professional voice that stays
  strictly on the user's job search and career; off-topic asks get a gentle,
  in-voice redirect (never a scold).
- **No fabrication + human gate:** the agent proposes structured profile changes
  (skills, domains, target roles, corrected attribution notes, seniority, remote
  preference); nothing is saved until the user confirms.
- Confirmed changes merge into `profiles.parsed` (incl. `attribution_notes`), so
  future scoring/suggestions benefit.
- Cost-capped (a generous per-user daily turn cap with a friendly limit) and
  usage-logged; the transcript is not persisted; per-user isolated.
**Done:** a user can hold a real multi-turn conversation, confirm a proposed
change, and see it reflected in their profile; off-topic requests are declined
in-voice.

## M2.6 — Custom domain, branded email, and design polish ✅ DONE
Goal: a production-grade public presence on a custom domain, with branded auth
email and a refined responsive design.
- Custom domain myjobops.app is live on Vercel and serves the app.
- Branded transactional email through Resend: magic-link login emails are sent
  from the domain, with DKIM and SPF verified.
- Supabase auth redirect URLs and the Railway CORS allowlist were updated for the
  new domain.
- Responsive design refinement pass: reduced the overall type and spacing scale
  and added comfortable mobile gutters, so the layout reads well from phone to
  desktop. Visual only, with no change to features or logic.
**Done:** users reach the app at myjobops.app, receive a branded magic-link email
from the domain, sign in successfully, and the layout is comfortable at phone,
tablet, and desktop widths.

## M3 — Job-source ingestion + dedupe + funnel stage 1 ✅ DONE
Goal: a growing pool of real jobs, fetched legitimately, per user.
- `JobSource` interface + an Adzuna adapter (US), in a registry so adding a source
  is one line. Strict response validation; a source failure is logged and skipped,
  never crashing the fetch.
- Per-user targeted fetch: the query is built from a user's own profile (target
  roles, location, remote preference), not a wide daily sweep.
- Normalize + dedupe into the shared `jobs` pool by a unique `content_hash`, so a
  posting two users both match is stored once and a re-fetch never inserts a dupe.
- A cheap, deterministic, no-LLM prefilter that returns a generous ranked
  shortlist (cap ~30) on safe signals (location/remote fit, recency, keyword
  overlap). It narrows the firehose without judging true fit; that is M4's job.
- A manual, admin-gated trigger `POST /admin/fetch-jobs` runs a fetch for one
  user on demand (no scheduler; the multi-user loop is M5). Zero LLM spend.
**Done:** an admin triggers a per-user fetch, `jobs` populates, a second fetch
adds no duplicates, and the prefilter returns a sensible generous shortlist for a
test profile, all with no model calls.

## M4 — Automated matching (funnel stage 2) ✅ DONE
Goal: scored matches per user.
- Per user: the cheap M3 prefilter shortlist → LLM-score with the EXISTING honest
  scorer → store per-user `matches` (migration `0007`, per-user RLS).
- Cost architecture from the start: the scorer runs on **Haiku 4.5** (Sonnet stays
  reserved for on-demand tailoring); **prompt caching** marks the rubric+profile
  prefix so only the per-job snippet is uncached; each score logs to `usage_log`
  as **`match_score`** (model-priced, cache-aware) so the savings are visible; the
  per-user daily cap is respected (score what fits, report what was skipped).
- The fit score is PURE — recency/`posted_at` is never factored in. `posted_at` is
  carried onto the match row only so M5 can use recency as a separate signal.
- Dedicated **Matches** UI section (separate from the Scored-jobs tracker): each
  match shows role/company, location, score + band, honest cleared/gaps, a
  "View posting →" link, and a "Tailor my resume for this" button that reuses the
  on-demand tailor flow (no auto-tailoring).
- Trigger: gated `POST /admin/score-matches` (same fail-closed `ADMIN_USER_IDS`
  gate as M3). No scheduler (that is M5).
- Carried over from M3 (still open for M5): the pooled `description` is Adzuna's
  ~500-char excerpt — M4 scores on that snippet; full-JD scoring stays the M2
  paste-a-link path. And treat `salary_is_predicted = true` as a rough estimate,
  never a hard salary-floor penalty.
**Done:** the admin trigger produces stored, per-user matches scored by the same
honest rubric on Haiku with caching, and the Matches section shows each user only
their own (RLS).

## M5 — Scheduled scan + email digest + guardrails ✅ DONE
Goal: recurring alerts, safely. **Decision: digests surface the SCORE ONLY** —
each match shows its fit score, band, and decision with an on-demand
**"Tailor my resume for this"** button in the app. Tailoring is never run
automatically; the user triggers it when they choose.

Built guardrail-first (cost controls before the scanner), so the automated loop
could never run up real bills before opening to strangers. All six steps shipped:
1. **Opt-in flag — ✅** `preferences.email_opt_in` (single opt-in, no cadence
   toggle), migration 0010.
2. **Cost controls — ✅** Per-user monthly score (50) + tailor (10) caps alongside
   the daily brake, plus a global monthly budget ceiling. Per `docs/GUARDRAILS.md`.
3. **Resend / email — ✅** Backend email via Resend (`mailer.send_email`, PII-safe),
   sending from `noreply@myjobops.app` as "JobOps".
4. **Sent-state — ✅** `alerts_log` (migration 0011) so a match is never emailed
   twice; `unsent_matches_for_user` reuses the `/matches` threshold gate.
5. **Digest composition — ✅** Score-only digest, double-gated on `email_opt_in` AND
   `score >= score_threshold`, marked sent only on send success; never auto-tailors.
6. **Scheduler — ✅** Budget kill-switch wired into the scanner; a 15-day inactivity
   pause with a one-time reinvite (returning auto-unpauses); a run-and-exit
   `python -m app.scheduled` entrypoint running on a Railway native cron service.
7. **Batch API — ⬜ DEFERRED.** Move the non-interactive scheduled scoring onto the
   Batch API (50 percent off). A cost optimization, not required for the loop.

**Recency is separate** throughout: a ranking/flagging signal in the digest, never
baked into the fit score (the score stays pure; `matches.posted_at` carries it).

**Done:** a signed-up user with opt-in on receives a correctly-scoped, score-only
digest of their new matches, can click through to tailor on demand, a match is never
re-sent, inactive users are paused with one reinvite, and exceeding a cap or the
budget ceiling is handled gracefully. Verified live on the `jobops-scheduler` cron
service: a scheduled run scanned, scored, and emailed a real digest, then exited clean.

## Shipped since M5 (not milestones)
Not roadmap milestones, but the status should reflect current reality — these landed
after M5 sealed (see CHANGELOG 2026-06-26):
- **Coach on the score page** — a "Something's missing?" block on the score result page
  lets a user add true context the profile missed, routed through the existing enrich
  flow (confirm-gated `ProposalCard` → `/enrich/apply`), then auto re-scores the job and
  shows the new fit. Reuses the Coach's no-fabrication guardrails; the job text is never
  sent to enrichment.
- **Design pass** — restored the original design intent (hairline borders, a three-note
  palette, semantic decision chips, a borderless tag cloud) and clearer UX/copy
  ("Check a job for fit", "minimum fit score"). Labels/visuals only; no routes,
  endpoints, or logic changed.
- **Fit-band recalibration** — band cutoffs moved to 74/62/48 to match the real score
  distribution. Labels only; scores and the scorer rubric are unchanged.

## Remaining
The live app does what it set out to do. Two planned items remain (see README):
- **Resume document export** — generate a tailored resume file from approved
  suggestions, behind an approve-then-generate gate so nothing is fabricated.
- **Batch scoring (M5 step 7)** — use the Anthropic Batch API for scheduled scoring
  to cut cost further.

(The earlier "optional capstone" ideas — a Telegram digest channel, referral-network
features — are not planned.)
