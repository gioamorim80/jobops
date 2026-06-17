# ROADMAP — JobOps milestones

Build one milestone at a time, in order. A milestone is done only when its
acceptance criteria pass AND it deploys. Link-tailor (M2) is sequenced ahead of
the automated scanner (M3–M5) by design.

## M0 — Bootstrap the monorepo
Goal: skeleton that deploys and proves the agent brain works end to end.
- Monorepo: `/frontend` (Next.js), `/backend` (FastAPI), `/supabase`, `/docs`, `/prompts`.
- Supabase project created; backend and frontend read env from `.env`.
- Backend `/health` endpoint; one `/agent/ping` endpoint that makes a real
  Anthropic call and returns the text.
- Frontend deploys on Vercel; backend on Railway; both green.
**Done when:** visiting the deployed frontend can hit `/agent/ping` and show a
live model response.

## M1 — Auth + onboarding chat → profile
Goal: a new user signs up and is onboarded into a structured profile.
- Supabase magic-link auth wired in the frontend.
- `profiles`, `preferences` tables + RLS (see `docs/DATA_MODEL.md`).
- Resume upload to Supabase storage; onboarding agent (`docs/agents/ONBOARDING.md`)
  parses it, asks the gap questions in chat, confirms, writes the profile.
- Settings screen for alert frequency + score threshold.
**Done when:** two different accounts can each complete onboarding and see only
their own profile (RLS verified).

## M2 — On-demand: paste a link → score + tailor  ← MVP wedge
Goal: the instantly-useful single action.
- Endpoint: accept a URL or pasted text. Fetch + readability-extract the posting;
  fall back to "paste the text" if blocked/thin.
- Run Scorer (`docs/agents/SCORER.md`) then Tailor (`docs/agents/TAILOR.md`).
- UI shows: FIT score + decision + cleared/gaps + tailored bullets + match
  analysis. User edits/approves; result saved to `tailorings`.
**Done when:** a user pastes a real posting and gets an accurate fit + honest
tailored bullets they can approve, with no fabricated content.

## M3 — Job-source adapters + dedupe + funnel stage 1
Goal: a growing pool of real jobs, fetched legitimately.
- Adapter interface + 2–3 sources from the allowlist (`docs/JOB_SOURCES.md`).
- Normalize + dedupe into the global `jobs` pool (content hash).
- Cheap prefilter that ranks jobs against a profile without LLM calls.
**Done when:** a scheduled/manual fetch populates `jobs`, dedupes correctly, and
prefilter returns a sensible shortlist for a test profile.

## M4 — Automated matching (funnel stage 2)
Goal: scored matches per user.
- For each active user: prefilter shortlist → LLM-score → store `matches`.
- Matches dashboard in the frontend (sortable by fit, filter by decision).
**Done when:** the pipeline produces stored, per-user matches and the dashboard
shows each user only their own.

## M5 — Scheduled digests + email + guardrails
Goal: recurring alerts, safely.
- Scheduler runs the loop on each user's frequency (off/daily/weekly).
- Digest agent (`docs/agents/DIGEST.md`) composes; Resend sends; log to `alerts_log`.
- Enforce guardrails (`docs/GUARDRAILS.md`): per-user LLM cap, global budget
  ceiling, rate limiting, pause switch honored.
**Done when:** a test user receives a correctly-scoped digest email on schedule,
and exceeding a cap is blocked gracefully.

## M6 — Optional capstone
Pick any: Telegram digest channel; tailored-resume document export (docx/PDF);
referral-network features; share-link hardening + onboarding polish.
