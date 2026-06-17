# PROMPT — M0: Bootstrap the monorepo

Paste this into Claude Code (personal account), inside the empty `jobops` repo.

---

Read CLAUDE.md, ARCHITECTURE.md, and ROADMAP.md first. You are starting milestone
M0. Do only M0 — do not scaffold later milestones.

Set up the monorepo exactly per the stack in CLAUDE.md:
- `/frontend`: Next.js (App Router, TypeScript). A single landing page that calls
  the backend `/agent/ping` and renders the response.
- `/backend`: FastAPI. Endpoints: `GET /health` (returns ok) and `GET /agent/ping`
  (makes a real Anthropic call using ANTHROPIC_API_KEY + ANTHROPIC_MODEL and returns
  the model's text). Read keys from env; never hardcode.
- `/supabase`: an empty `migrations/` folder and a README noting we add schema in M1.
- Root: `.env.example` already exists — wire both apps to read env. Add `.gitignore`
  that excludes `.env`, `.env.local`, `node_modules`, `__pycache__`, `.venv`.

Then:
1. Initialize git, make the first commit.
2. Give me exact, copy-pasteable local run instructions for both apps.
3. Give me step-by-step deploy instructions: frontend → Vercel, backend → Railway,
   including which env vars to set in each dashboard.
4. Dev tooling: respect the root `ruff.toml`, `.editorconfig`, and
   `.pre-commit-config.yaml`. Run `pip install pre-commit && pre-commit install`,
   add Prettier + lint/format scripts to /frontend, and ensure
   `pre-commit run --all-files` passes. Extend `.github/workflows/ci.yml` with a
   backend (pytest) and frontend (build/lint) job. See `docs/DEVELOPMENT.md`.
5. Create STATE.md (current milestone M0, what's done, next = M1) and CHANGELOG.md
   with a first dated entry.

Acceptance: the deployed frontend can hit `/agent/ping` and show a live model
response. Stop after M0 and report. Do not start M1.

Before finishing: update STATE.md and CHANGELOG.md, commit, and push.
