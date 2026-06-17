# DEVELOPMENT — quality tooling

This repo ships with linting, formatting, secret-scanning, and CI configured so the
codebase stays clean and no secret or PII slips into git history. Set it up once,
right after M0 scaffolds the apps.

## One-time setup
```bash
pip install pre-commit
pre-commit install            # install the git hook into this repo
pre-commit run --all-files    # run every hook once across the repo
pre-commit autoupdate         # (optional) pin the latest hook versions
```

## What runs on every commit (.pre-commit-config.yaml)
- Hygiene: trailing whitespace, final-newline, YAML/JSON validity, merge-conflict
  guard, large-file guard.
- **Secret protection:** `detect-private-key` + `gitleaks` block credentials from
  ever being committed. Do not disable these.
- **Python:** `ruff` (lint, autofix) + `ruff-format` on /backend.

## Backend (Python / FastAPI)
- Lint:   `ruff check backend`
- Format: `ruff format backend`
- Config: `ruff.toml` (incl. `S` security lint rules).

## Frontend (Next.js / TypeScript)
- Next.js ships ESLint. In M0, also add Prettier and `npm run lint` / `npm run
  format` scripts in /frontend. Keep formatting automatic.

## CI (.github/workflows/ci.yml)
Runs `pre-commit` on every push/PR. Green on the spec bundle as-is. M0 extends it
with a backend test job (pytest) and a frontend build/lint job.

## Instruction to the build agent (M0)
After scaffolding /backend and /frontend:
1. Respect `ruff.toml`, `.editorconfig`, and `.pre-commit-config.yaml` at the root.
2. Add Prettier + lint/format scripts to /frontend.
3. Run `pre-commit install`; ensure `pre-commit run --all-files` passes before the
   first milestone commit.
4. Extend `.github/workflows/ci.yml` with backend + frontend jobs.
5. Never weaken or remove the secret-scanning hooks.
