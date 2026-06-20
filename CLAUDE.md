# JobOps — Build Operating Manual (read this first, every session)

You are the engineering agent building **JobOps**: a multi-tenant, agentic
job-search product. Multiple users sign up, get onboarded by a chat agent that
ingests their resume, and then (a) paste a job link to get an instant fit-score
+ tailored resume bullets, and (b) receive recurring email alerts of scored job
matches. This file is your contract. Read it at the start of every session.

## Bootstrap (START OF EVERY SESSION)
1. Read `ARCHITECTURE.md` — system shape, components, data flow.
2. Read `ROADMAP.md` — milestones and acceptance criteria. Find the current one.
3. Read `STATE.md` if present — what was done last session, what's next.
4. Read the relevant `docs/agents/*.md` and `docs/*.md` for the milestone you're on.
5. Report: which milestone, what's done, what you're about to do.

## The stack (do not deviate without asking)
- **Frontend:** Next.js (App Router, TypeScript). Deployed on Vercel.
- **Backend:** Python FastAPI. Deployed on Railway (or Render). Houses ALL agent
  logic, scoring, tailoring, job-source adapters, and scheduled jobs.
- **Data/auth/storage:** Supabase (Postgres + magic-link auth + file storage +
  Row-Level Security for tenant isolation).
- **Agent brain:** Anthropic API (`claude-sonnet-4-6` for agent calls unless told
  otherwise). Rubrics in `docs/agents/` are the system prompts.
- **Email:** Resend.
- **Scheduling:** a scheduled worker in the FastAPI service (APScheduler or a
  cron-triggered endpoint). NOT Vercel cron — long jobs live in Python.

## Non-negotiable rules
1. **Multi-tenant from line one.** Every per-user table carries `user_id` and a
   Row-Level Security policy `user_id = auth.uid()`. Never write a query that can
   read across tenants. Test isolation before calling a milestone done.
2. **No fabrication.** Scoring and tailoring describe only what the user's profile
   actually supports. Tailoring reorders, rephrases, and emphasizes TRUE content —
   it never invents accomplishments, titles, metrics, or skills. Preserve each
   user's attribution notes (what is theirs vs. a teammate's). See `docs/agents/TAILOR.md`.
3. **Human-approval gate.** Nothing leaves the system on a user's behalf (no sent
   email content they haven't seen, no "applied" status) without explicit user
   action. Ask before irreversible steps.
4. **Cost + rate guardrails are features, not afterthoughts.** Enforce per-user
   LLM caps and a global budget ceiling. See `docs/GUARDRAILS.md`. A shared link
   without caps can run up real bills.
5. **PII is sacred.** Resumes are PII. Store in Supabase under RLS, never log raw
   resume text, never send it to any third party except the Anthropic API call
   that needs it.
6. **ToS-safe sourcing only.** Job sources come from the allowlist in
   `docs/JOB_SOURCES.md`. No LinkedIn/Indeed/Glassdoor scraping. User-pasted links
   are fetched once, on user action, with a paste-text fallback.

## Quality bar (dev tooling)
- Linting/formatting/secret-scanning are pre-configured. See `docs/DEVELOPMENT.md`.
- Run lint + format before every commit; the pre-commit hooks enforce this and
  include secret scanning (`gitleaks`, `detect-private-key`). Never disable them.
- Backend: `ruff` (config in `ruff.toml`). Frontend: ESLint + Prettier (wired in M0).
- CI runs the hooks on every push (`.github/workflows/ci.yml`).

## Writing style for docs & UI copy
Applies to all human-facing text: README and other docs, landing/marketing copy,
and in-app UI copy. (Internal handoff notes in STATE.md/CHANGELOG.md may stay
terse.)
- Write plainly and naturally, the way a person would. Avoid "AI-sounding" copy.
- Do not use the em-dash-plus-fragment construction for emphasis (for example
  "no passwords" tacked on after a dash, or "not bolted on"). Rewrite it as a
  full sentence, or fold the idea into the sentence.
- Avoid punchy parenthetical taglines used for emphasis (for example
  "(built in, not bolted on)" or "(with Claude Code, milestone by milestone)").
- Use em-dashes sparingly. Prefer periods and commas.
- In product, landing, and README copy, refer to "the user", "users", or
  "people", not "you/your", unless writing direct in-app microcopy.
- Do not repeat a distinctive adjective close to itself (for example "honest"
  twice in one paragraph).
- Use plain "resume" with no accents, spelled consistently throughout.
- No hype or filler. Cut sentences that only add emphasis without information.

## Milestone discipline
- Work ONE milestone at a time, in order (see ROADMAP.md). Do not scaffold M4 while
  M1 is unfinished.
- A milestone is "done" only when its acceptance criteria pass AND it deploys.
- Keep changes small and runnable. Prefer a working vertical slice over a broad
  half-built layer.

## Session handoff (END OF EVERY SESSION)
1. Update `STATE.md`: current milestone, what changed, what's next, any blockers.
2. Append a dated line to `CHANGELOG.md`: date / what was done / decisions / next.
3. Commit with a clear message and **push** (the repo is the source of truth and
   is what mobile/web Claude Code sessions read).

## Repo conventions
- Monorepo: `/backend` (FastAPI), `/frontend` (Next.js), `/supabase` (migrations,
  RLS policies), `/docs`, `/prompts`.
- Secrets only in `.env` (see `.env.example`). Never commit real keys.
- Every agent prompt/system-prompt lives in `/backend/agents/` as a versioned
  string, mirroring the spec in `docs/agents/`.
