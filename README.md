# JobOps — multi-tenant agentic job-search product

Users sign up, get onboarded by a chat agent that reads their resume, then:
- **paste a job link → instant fit score + tailored resume bullets** (they approve), and
- **receive recurring email alerts** of scored job matches.

Built with Claude Code. FastAPI + Next.js + Supabase + Anthropic API + Resend.

## How to build it
This repo ships as a **spec + prompt bundle**. You run the prompts in order in your
(personal) Claude Code account, one milestone at a time.

1. Put this folder in a **private GitHub repo** (unlocks laptop-free runs via
   Claude Code on the web / mobile).
2. Open Claude Code in the repo. It reads `CLAUDE.md` automatically.
3. Run `prompts/M0_bootstrap.md`, verify it deploys, then `M1`, `M2`, ... in order.
4. Each prompt ends by updating `STATE.md` + `CHANGELOG.md` and pushing — so any
   device picks up exactly where the last left off.

## Map
- `CLAUDE.md` — the agent's operating manual (rules, stack, discipline). Read first.
- `ARCHITECTURE.md` — system shape and the two data flows.
- `ROADMAP.md` — milestones M0–M6 with acceptance criteria.
- `docs/DATA_MODEL.md` — Postgres schema + RLS (tenant isolation).
- `docs/JOB_SOURCES.md` — legitimate source allowlist, dedupe, the cost funnel.
- `docs/GUARDRAILS.md` — cost caps, PII, no-fabrication, approval gate.
- `docs/agents/` — onboarding, scorer, tailor, digest specs (the agent brains).
- `prompts/` — copy-paste Claude Code prompts, one per milestone.
- `.env.example` — every key you'll need.

## Order of operations
M0 bootstrap → M1 auth+onboarding → **M2 paste-a-link tailor (the wedge)** →
M3 job sources → M4 automated matching → M5 scheduled digests → M6 optional capstone.

## Development quality
- `pre-commit` hooks (lint, format, secret-scan) — see `docs/DEVELOPMENT.md`.
- `ruff` for Python, ESLint + Prettier for the frontend (wired in M0).
- CI runs the hooks on every push (`.github/workflows/ci.yml`).
- Setup once: `pip install pre-commit && pre-commit install`.

## Licensing
No open-source license is included by default, so all rights are reserved — the
code is viewable on a public repo but not licensed for reuse. If you later want to
allow reuse, add a LICENSE file (e.g. MIT). Keep it closed if this becomes a product.
