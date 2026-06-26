# JobOps

JobOps is a live, multi-tenant web app for running a calmer, more honest job search. It reads a user's resume, scores real job postings against their actual experience, suggests resume edits tailored to each posting, scans for new roles on a schedule, and emails a periodic digest of new matches. Everything it produces is grounded only in what the user has actually done, and nothing is fabricated.

JobOps is a live, deployed product, available at https://myjobops.app. The frontend runs on Vercel, the backend on Railway, with Supabase and Postgres for data and the Anthropic API as the agent brain. It was built incrementally with Claude Code, one milestone at a time.

## What it does today

JobOps is authenticated and multi-tenant, and every user's data is isolated by Postgres Row-Level Security.

**Sign-in and onboarding.** Magic-link sign-in through Supabase, with no passwords. On onboarding, a user uploads a resume in PDF or DOCX, and an onboarding agent extracts a structured profile of skills, roles, seniority, domains, and locations. The user reviews and confirms it and answers a couple of gap questions. Nothing is saved until the user confirms.

**Score a job.** A user pastes a job link or the posting text and gets back a 0–100 fit score with a qualitative band (Strong, Solid, Moderate, or Likely skip) and a decision of APPLY, STRETCH, or SKIP. Scoring runs at temperature 0, so the same posting scores consistently. Alongside the score: the requirements the user clears, the honest gaps, and a one-line pitch.

**Suggested resume edits.** Shown as proposed changes that say where each one applies, meaning the role and section, laid out as the original, the suggestion, and the reason. The user edits the suggestions and explicitly approves them, and nothing is applied automatically. Tailoring runs only on explicit user intent, never automatically.

**History and caching.** Results are saved, and re-opening or re-scoring takes one click. An exact-match cache returns a prior result instantly, without a new model call.

**Coach.** A warm, professional chat that helps users add true context their resume missed, such as what they built, who really owned a project, or a title that a timeline flattened. It stays strictly on the user's job search, does not fabricate, and proposes structured profile changes that the user confirms before anything is saved.

**Automated scanner.** On a schedule, JobOps fetches new postings for each active user from their profile's roles and locations, dedupes into a shared job pool, runs a no-LLM prefilter, and then LLM-scores only the shortlist. This two-stage funnel is the main cost control.

**Matches view.** A dedicated page shows the jobs the scanner found and scored for each user, kept separate from the jobs they score themselves. Users set a score threshold to control what surfaces, and each match offers a one-click path to view the posting or tailor a resume for it.

**Email digests.** Users who opt in receive a periodic email of their new scored matches, sent through Resend. The digest surfaces the score only, with a "View & tailor" link back into the app, in keeping with the principle that scoring is automatic and cheap while tailoring is gated behind explicit intent. Opt-in is off by default and consent is checked on every send. Users who go inactive are paused and sent a single courteous reinvite rather than continued emails.

## Safety, cost, and privacy

**Multi-tenant isolation.** Every per-user table enforces RLS (user_id = auth.uid()), and the backend derives a user's identity only from a verified token, never from request input. Resumes live in a private storage bucket scoped to each user. The scheduled scanner and digest run with a service role and stay scoped per user, so one user's data never reaches another's context.

**No fabrication.** Scoring traces back to the user's profile, suggested edits only reorder and rephrase true content and flag anything missing such as a pending metric, and the Coach proposes changes that the user approves.

**Human-approval gates.** Suggested resume changes and profile enrichments are saved only when the user confirms them.

**Cost guardrails.** A no-LLM prefilter limits how many postings are ever scored. Per-user daily caps return a friendly message instead of failing, and separate per-user monthly score and tailor caps bound ongoing spend. A global monthly budget ceiling acts as a kill-switch that pauses automated scanning if month-to-date spend crosses the limit; digests, which make no model calls, are never blocked by it. Every model call is logged, and an exact-match cache avoids repeat calls.

## Roadmap

These are planned and are not in the live app yet. See ROADMAP.md.

- **Resume document export** — generating a tailored resume file from approved suggestions, behind an approve-then-generate gate so nothing is fabricated.
- **Batch scoring** — using the Anthropic Batch API for scheduled scoring to cut scoring cost further.

## Stack

- **Frontend:** Next.js (App Router, TypeScript) on Vercel.
- **Backend:** Python FastAPI on Railway, which holds all agent logic, scoring, suggested edits, the Coach, the scanner, and the digest. It is managed with uv. A separate Railway cron service runs the scheduled scan-and-digest job.
- **Data, auth, and storage:** Supabase, which provides Postgres, magic-link auth, file storage, and Row-Level Security.
- **Agent brain:** the Anthropic API, with a deliberate model split — a cheaper model (Claude Haiku) for high-volume scoring and scanning, a stronger one (Claude Sonnet) for tailoring and enrichment.
- **Email:** Resend, for magic-link delivery and match digests.

## How it was built

JobOps was built incrementally with Claude Code, one milestone at a time. Each milestone shipped only after it deployed and passed its acceptance criteria.

- **M0:** the monorepo and deploy skeleton, with a real Anthropic call working end to end.
- **M1:** magic-link auth and onboarding into a structured profile, with RLS verified across two accounts.
- **M2:** paste a link to get a banded, stable score plus suggested resume changes with an approve gate, results history, an exact-match cache, and per-user caps with usage logging.
- **M2.5:** the profile-enrichment Coach, scoped to the job search, no fabrication, human confirmation, cost-capped.
- **M3:** per-user job-source ingestion — an Adzuna adapter, a shared job pool, dedupe, and a no-LLM prefilter that narrows the firehose before any model call.
- **M4:** automated matching — the matcher scores each user's shortlist on a cheaper model into a per-user matches table, surfaced on a dedicated Matches page.
- **M5:** the automated loop — email opt-in and consent, cost controls including the monthly budget ceiling, Resend integration, scored-match digests, a 15-day inactivity pause with reinvite, and a scheduled scan-and-digest job on a Railway cron service.

Each session reads CLAUDE.md, updates STATE.md and CHANGELOG.md, and pushes, so a later session or another device can pick up where the last one left off.

## Repo map

- **CLAUDE.md:** the engineering operating manual covering rules, stack, and discipline.
- **ARCHITECTURE.md:** system shape and data flows.
- **ROADMAP.md:** milestones with their status, done or planned.
- **STATE.md and CHANGELOG.md:** the current source of truth for what is built, plus the dated history.
- **backend/:** the FastAPI app, versioned agent prompts in backend/agents/, and tests. It is a uv project.
- **frontend/:** the Next.js app (App Router) and the design system.
- **supabase/migrations/:** SQL schema and RLS policies.
- **docs/:** DATA_MODEL.md, GUARDRAILS.md, JOB_SOURCES.md, DEVELOPMENT.md, and agent specs in docs/agents/ for onboarding, scorer, tailor, and the digest.
- **prompts/:** a historical, point-in-time record of the original build prompts. It is not maintained and is not a complete spec. STATE.md and CHANGELOG.md are the current source of truth.
- **.env.example:** the required environment variables as placeholders only. Real secrets live in Vercel and Railway and are never committed.

## Development quality

pre-commit hooks run linting, formatting, and secret-scanning with gitleaks and detect-private-key. See docs/DEVELOPMENT.md.

ruff covers Python, and ESLint with Prettier covers the frontend. CI runs the hooks, the backend tests, and a frontend build on every push (.github/workflows/ci.yml).

One-time setup: pip install pre-commit && pre-commit install.

## Licensing

No open-source license is included, so all rights are reserved. The code is viewable but not licensed for reuse.
