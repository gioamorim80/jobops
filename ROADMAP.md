# ROADMAP — JobOps milestones

Built one milestone at a time; a milestone is done only when its acceptance
criteria pass AND it deploys. **M0–M2.5 are done and live; M3–M6 are planned.**
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
- Résumé upload to a private Supabase storage bucket; onboarding agent
  (`docs/agents/ONBOARDING.md`) parses it, asks a couple of gap questions,
  confirms, and writes the profile (extraction only — never invents).
- Settings screen for alert frequency + score threshold (stored preferences).
**Done:** two different accounts each complete onboarding and see only their own
profile (RLS verified).

## M2 — On-demand: paste a link → score + suggested résumé changes ✅ DONE ← MVP wedge
Goal: the instantly-useful single action.
- Endpoint accepts a URL or pasted text; single readability fetch with a
  "paste the text" fallback when a link is blocked/thin (no host hammering).
- Run Scorer (`docs/agents/SCORER.md`) then Tailor (`docs/agents/TAILOR.md`)
  against the user's stored profile.
- UI shows: a **0–100 fit score with a qualitative band** (Strong / Solid /
  Stretch / Likely skip) and decision (APPLY / STRETCH / SKIP); cleared
  requirements; honest gaps; **"Suggested changes to your résumé"** — each
  showing *where* it applies (role + section), as original → suggestion → why;
  match analysis. The user edits and explicitly approves; results save to
  `tailorings` with a per-user **history**.
- Scoring runs at **temperature 0** for stable, repeatable scores.
- **Exact-match cache** returns a prior result with no model call; "Re-score"
  forces a fresh run.
- **Cost guardrails:** per-user daily caps (a friendly limit, never a crash) and
  per-call **usage logging** (`usage_log`).
**Done:** a user pastes a real posting and gets an accurate, banded fit + honest
suggested résumé changes they approve, with no fabricated content; repeat scores
are stable and cached; everything is per-user isolated.

## M2.5 — Profile-enrichment Coach ✅ DONE
Goal: let a user enrich their profile with true context their résumé missed,
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

## M3 — Job-source adapters + dedupe + funnel stage 1 ⬜ PLANNED
Goal: a growing pool of real jobs, fetched legitimately.
- Adapter interface + 2–3 sources from the allowlist (`docs/JOB_SOURCES.md`).
- Normalize + dedupe into the global `jobs` pool (content hash).
- Cheap prefilter that ranks jobs against a profile without LLM calls.
**Done when:** a scheduled/manual fetch populates `jobs`, dedupes correctly, and
prefilter returns a sensible shortlist for a test profile.

## M4 — Automated matching (funnel stage 2) ⬜ PLANNED
Goal: scored matches per user.
- For each active user: prefilter shortlist → LLM-score → store `matches`.
- Matches dashboard in the frontend (sortable by fit, filter by decision).
**Done when:** the pipeline produces stored, per-user matches and the dashboard
shows each user only their own.

## M5 — Scheduled digests + email + guardrails ⬜ PLANNED
Goal: recurring alerts, safely. **Decision: digests and saved links surface the
SCORE ONLY** — each match shows its fit score/decision with an on-demand
**"Tailor my résumé for this"** button in the app. Tailoring is never run
automatically; the user triggers it when they choose.
- Scheduler runs the loop on each user's frequency (off / daily / weekly).
- Digest agent (`docs/agents/DIGEST.md`) composes a score-only summary; Resend
  sends; log to `alerts_log`.
- Enforce the remaining guardrails (`docs/GUARDRAILS.md`): global monthly budget
  ceiling, rate limiting, pause switch honored. (Per-user daily caps + usage
  logging already shipped in M2.)
**Done when:** a test user receives a correctly-scoped, score-only digest email
on schedule, can click through to tailor on demand, and exceeding a cap is
blocked gracefully.

## M6 — Optional capstone ⬜ PLANNED
Pick any: Telegram digest channel; tailored-résumé document export (docx/PDF);
referral-network features; share-link hardening + onboarding polish.
