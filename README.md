# JobOps

JobOps is a live, multi-tenant web app for running a calmer, more honest job
search. It reads a user's resume, scores real job postings against their actual
experience, suggests resume edits tailored to each posting, and includes a
profile-enrichment chat. Everything it produces is grounded only in what the
user has actually done, and nothing is fabricated.

JobOps is a live, deployed product, available at https://myjobops.app. The
frontend runs on Vercel, the backend on Railway, with Supabase and Postgres for
data and the Anthropic API as the agent brain. It was built incrementally with
Claude Code, one milestone at a time.

## What it does today

JobOps is authenticated and multi-tenant, and every user's data is isolated by
Postgres Row-Level Security.

- Magic-link sign-in through Supabase, with no passwords.
- Onboarding: a user uploads a resume in PDF or DOCX, and an onboarding agent
  extracts a structured profile of skills, roles, seniority, domains, and
  locations. The user reviews and confirms it and answers a couple of gap
  questions. Nothing is saved until the user confirms.
- Score a job: a user pastes a job link or the posting text and gets back
  several things.
  - A 0–100 fit score with a qualitative band (Strong, Solid, Stretch, or Likely
    skip) and a decision of APPLY, STRETCH, or SKIP. Scoring runs at temperature
    0, so the same posting scores consistently.
  - The requirements the user clears, the honest gaps, and a one-line pitch.
  - Suggested resume edits, shown as proposed changes that say where each one
    applies, meaning the role and section, laid out as the original, the
    suggestion, and the reason. The user edits the suggestions and explicitly
    approves them, and nothing is applied automatically.
  - History: results are saved, and re-opening or re-scoring takes one click. An
    exact-match cache returns a prior result instantly, without a new model call.
- Coach: a warm, professional chat that helps users add true context their resume
  missed, such as what they built, who really owned a project, or a title that a
  timeline flattened. It stays strictly on the user's job search, does not
  fabricate, and proposes structured profile changes that the user confirms
  before anything is saved.

### Safety, cost, and privacy

- Multi-tenant isolation: every per-user table enforces RLS
  (`user_id = auth.uid()`), and the backend derives a user's identity only from a
  verified token, never from request input. Resumes live in a private storage
  bucket scoped to each user.
- No fabrication: scoring traces back to the user's profile, suggested edits only
  reorder and rephrase true content and flag anything missing such as a pending
  metric, and the Coach proposes changes that the user approves.
- Human-approval gates: suggested resume changes and profile enrichments are
  saved only when the user confirms them.
- Cost guardrails: per-user daily caps return a friendly message instead of
  failing, every model call is logged, and an exact-match cache avoids repeat
  calls.

## Roadmap / not yet built

These are planned and are not in the live app yet. See `ROADMAP.md`.

- Recurring email alerts and digests through Resend: scheduled emails of new
  scored matches on the user's chosen frequency. The plan is for digests and
  saved links to surface the score only, with an on-demand "Tailor my resume for
  this" button rather than automatic tailoring.
- An automated job-source scanner that fetches from a ToS-safe source allowlist,
  dedupes into a shared pool, runs a cheap prefilter without an LLM, and then
  LLM-scores only the shortlist. This two-stage funnel is the main cost control.
- A matches dashboard for the automated pipeline, plus optional capstones such as
  resume document export or a Telegram channel.

## Stack

- Frontend: Next.js (App Router, TypeScript) on Vercel.
- Backend: Python FastAPI on Railway, which holds all agent logic, scoring,
  suggested edits, and the Coach. It is managed with `uv`.
- Data, auth, and storage: Supabase, which provides Postgres, magic-link auth,
  file storage, and Row-Level Security.
- Agent brain: the Anthropic API (`claude-sonnet-4-6`).
- Email: Resend, which is planned and not yet integrated.

## How it was built

JobOps was built incrementally with Claude Code, one milestone at a time. Each
milestone shipped only after it deployed and passed its acceptance criteria.

- M0: the monorepo and deploy skeleton, with a real Anthropic call working end to
  end.
- M1: magic-link auth and onboarding into a structured profile, with RLS verified
  across two accounts.
- M2: paste a link to get a banded, stable score plus suggested resume changes
  with an approve gate, results history, an exact-match cache, and per-user caps
  with usage logging.
- M2.5: the profile-enrichment Coach, which is scoped to the job search, avoids
  fabrication, requires human confirmation, and is cost-capped.
- M3 through M6: planned.

Each session reads `CLAUDE.md`, updates `STATE.md` and `CHANGELOG.md`, and pushes,
so a later session or another device can pick up where the last one left off.

## Repo map

- `CLAUDE.md`: the engineering operating manual covering rules, stack, and
  discipline.
- `ARCHITECTURE.md`: system shape and data flows.
- `ROADMAP.md`: milestones with their status, done or planned.
- `STATE.md` and `CHANGELOG.md`: the current source of truth for what is built,
  plus the dated history.
- `backend/`: the FastAPI app, versioned agent prompts in `backend/agents/`, and
  tests. It is a `uv` project.
- `frontend/`: the Next.js app (App Router) and the design system.
- `supabase/migrations/`: SQL schema and RLS policies.
- `docs/`: `DATA_MODEL.md`, `GUARDRAILS.md`, `JOB_SOURCES.md`, `DEVELOPMENT.md`,
  and agent specs in `docs/agents/` for onboarding, scorer, tailor, and the
  planned digest.
- `prompts/`: a historical, point-in-time record of the original build prompts.
  It is not maintained and is not a complete spec. `STATE.md` and `CHANGELOG.md`
  are the current source of truth.
- `.env.example`: the required environment variables as placeholders only. Real
  secrets live in Vercel and Railway and are never committed.

## Development quality

- `pre-commit` hooks run linting, formatting, and secret-scanning with `gitleaks`
  and `detect-private-key`. See `docs/DEVELOPMENT.md`.
- `ruff` covers Python, and ESLint with Prettier covers the frontend.
- CI runs the hooks, the backend tests, and a frontend build on every push
  (`.github/workflows/ci.yml`).
- One-time setup: `pip install pre-commit && pre-commit install`.

## Licensing

No open-source license is included, so all rights are reserved. The code is
viewable but not licensed for reuse.
