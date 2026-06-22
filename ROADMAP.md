# ROADMAP — JobOps milestones

Built one milestone at a time; a milestone is done only when its acceptance
criteria pass AND it deploys. **M0 through M4 are done; M5 and M6 are planned.**
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
  Stretch / Likely skip) and decision (APPLY / STRETCH / SKIP); cleared
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

## M5 — Scheduled scan + email digest + guardrails ⬜ PLANNED
Goal: recurring alerts, safely. **Decision: digests surface the SCORE ONLY** —
each match shows its fit score, band, and decision with an on-demand
**"Tailor my resume for this"** button in the app. Tailoring is never run
automatically; the user triggers it when they choose.
- **Signup, not cadence.** A single "email me matches" opt-in, with no daily or
  weekly toggle: the pool is not fresh enough daily to justify a cadence choice.
- **Signal-gated send.** Send the top-N unsent matches about every two days, and
  ONLY when there is genuine signal. Do not email mediocre jobs just because time
  has passed. Track sent state so a match is never emailed twice.
- **Recency is separate.** Recency is a ranking and flagging signal in the digest,
  never baked into the fit score (the score stays pure; `matches.posted_at`
  carries recency).
- **Cheaper scheduled scoring.** Use the Batch API for the non-interactive
  scheduled scoring (50 percent off, and it combines with prompt caching once
  caching engages — see the M4 open item).
- Digest agent (`docs/agents/DIGEST.md`) composes the score-only summary; Resend
  sends; log to `alerts_log`.
- Enforce the remaining guardrails (`docs/GUARDRAILS.md`): global monthly budget
  ceiling, rate limiting, pause switch honored. (Per-user daily caps + usage
  logging already shipped in M2.)
**Done when:** a signed-up test user receives a correctly-scoped, score-only
digest email when there is genuine signal, can click through to tailor on demand,
a match is never re-sent, and exceeding a cap is blocked gracefully.

## M6 — Optional capstone ⬜ PLANNED
Pick any: Telegram digest channel; tailored-resume document export (docx/PDF);
referral-network features; share-link hardening + onboarding polish.
