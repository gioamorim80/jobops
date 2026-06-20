# JobOps — agentic job search, grounded in your real experience

JobOps is a **live, multi-tenant web app** for running a calmer, more honest job
search. It reads your résumé, scores real job postings against your actual
experience, suggests honest résumé edits tailored to each posting, and includes
a profile-enrichment chat — all grounded only in what you've truly done, never
fabricated.

> **Live, deployed product** — Next.js on Vercel · FastAPI on Railway ·
> Supabase/Postgres · Anthropic API. _(Public link omitted here for now.)_
> Built incrementally with Claude Code, one milestone at a time.

## What it does today

Authenticated and **multi-tenant**, with every user's data isolated by Postgres
Row-Level Security.

- **Magic-link sign-in** (Supabase) — no passwords.
- **Onboarding** — upload a résumé (PDF/DOCX); an onboarding agent extracts a
  structured profile (skills, roles, seniority, domains, locations). You review
  and confirm it and answer a couple of gap questions — nothing is saved until
  you confirm.
- **Score a job** — paste a job link or the posting text and get:
  - a **0–100 fit score** with a qualitative **band** (Strong / Solid / Stretch /
    Likely skip) and a **decision** (APPLY / STRETCH / SKIP). Scoring runs at
    temperature 0, so the same posting scores consistently.
  - the **requirements you clear**, **honest gaps**, and a one-line pitch.
  - **"Suggested changes to your résumé"** — proposed edits that show *where*
    each applies (which role + section), as original → suggestion → why. You edit
    and **explicitly approve**; nothing is auto-applied.
  - **History** — results are saved; re-opening or re-scoring is one click, and an
    **exact-match cache** returns a prior result instantly with no new model call.
- **Coach** — a warm, professional chat that helps you add **true** context your
  résumé missed (what you built, corrected attribution, fixed titles/timelines,
  real skills/domains). It stays strictly on your job search, never fabricates,
  and proposes structured profile changes you confirm before anything is saved.

### Safety, cost & privacy (built in, not bolted on)

- **Multi-tenant isolation** — every per-user table enforces RLS
  (`user_id = auth.uid()`); the backend derives your identity only from a verified
  token, never from request input. Résumés live in a private storage bucket
  scoped to you.
- **No fabrication** — scoring traces to your profile; suggested résumé edits only
  reorder/rephrase true content and flag anything missing (e.g. "metric pending");
  the Coach proposes, you confirm.
- **Human-approval gates** — suggested résumé changes and profile enrichments are
  saved only when you click to confirm.
- **Cost guardrails** — per-user daily caps with friendly limits (never a crash),
  usage logging, and an exact-match cache to avoid repeat model calls.

## Roadmap / not yet built

Planned, and **not** in the live app yet (see `ROADMAP.md`):

- **Recurring email alerts / digests** (via Resend) — scheduled emails of new
  scored matches on your chosen frequency. The plan: digests and saved links
  surface the **score only**, with an on-demand **"Tailor my résumé for this"**
  button — no auto-tailoring.
- **Automated job-source scanner** — fetching from a ToS-safe source allowlist,
  deduping into a shared pool, a cheap no-LLM prefilter, then LLM-scoring only the
  shortlist (the cost funnel).
- **Matches dashboard** for the automated pipeline, and optional capstones (résumé
  document export, a Telegram channel, etc.).

## Stack

- **Frontend:** Next.js (App Router, TypeScript) on **Vercel**.
- **Backend:** Python **FastAPI** on **Railway** — all agent logic, scoring,
  suggested-edits, and the Coach; managed with `uv`.
- **Data / auth / storage:** **Supabase** (Postgres + magic-link auth + file
  storage + Row-Level Security).
- **Agent brain:** **Anthropic API** (`claude-sonnet-4-6`).
- **Email:** **Resend** — _planned, not yet integrated._

## How it's built (with Claude Code, milestone by milestone)

JobOps was built incrementally with Claude Code, one milestone at a time, each
shipped only when it deployed and passed its acceptance criteria:

- **M0** — monorepo + deploy skeleton; a real Anthropic call working end to end.
- **M1** — magic-link auth + onboarding → structured profile (RLS verified across
  two accounts).
- **M2** — paste-a-link → banded, stable score + "Suggested changes to your
  résumé" with an approve gate; results history; exact-match cache; per-user caps
  + usage logging.
- **M2.5** — the profile-enrichment **Coach** (scoped, no-fabrication,
  human-confirm, cost-capped).
- **M3–M6** — planned.

Each session reads `CLAUDE.md` (the operating manual), updates `STATE.md` +
`CHANGELOG.md`, and pushes — so a fresh session (or another device) picks up
exactly where the last left off.

## Repo map

- `CLAUDE.md` — the engineering operating manual (rules, stack, discipline).
- `ARCHITECTURE.md` — system shape and data flows.
- `ROADMAP.md` — milestones with status (done / planned).
- `STATE.md` · `CHANGELOG.md` — current state and dated history.
- `backend/` — FastAPI app, versioned agent prompts (`backend/agents/`), tests;
  `uv` project.
- `frontend/` — Next.js app (App Router) and the design system.
- `supabase/migrations/` — SQL schema + RLS policies.
- `docs/` — `DATA_MODEL.md`, `GUARDRAILS.md`, `JOB_SOURCES.md`, `DEVELOPMENT.md`,
  and agent specs in `docs/agents/` (onboarding, scorer, tailor, and the planned
  digest).
- `prompts/` — the original milestone prompts used to drive the build.
- `.env.example` — required environment variables (placeholders only; real
  secrets live in Vercel/Railway, never committed).

## Development quality

- `pre-commit` hooks: lint, format, and secret-scanning (`gitleaks`,
  `detect-private-key`) — see `docs/DEVELOPMENT.md`.
- `ruff` for Python; ESLint + Prettier for the frontend.
- CI runs the hooks, backend tests, and a frontend build on every push
  (`.github/workflows/ci.yml`).
- One-time: `pip install pre-commit && pre-commit install`.

## Licensing

No open-source license is included, so all rights are reserved — the code is
viewable but not licensed for reuse.
