# JobOps backend (FastAPI)

Houses all agent logic, scoring, tailoring, job-source adapters, and scheduled
jobs. Managed with [uv](https://docs.astral.sh/uv/). Python pinned in
`.python-version`; dependencies in `pyproject.toml` and locked in `uv.lock`.

## Local run

```bash
cd backend
cp ../.env.example .env          # then fill in ANTHROPIC_API_KEY
uv sync                          # creates .venv and installs from uv.lock
uv run uvicorn app.main:app --reload --port 8000
```

Then:

```bash
curl http://localhost:8000/health        # {"status":"ok"}
curl http://localhost:8000/agent/ping     # {"model":"...","text":"..."} (live model call)
```

`/agent/ping` makes a real Anthropic call using `ANTHROPIC_API_KEY` and
`ANTHROPIC_MODEL` from the environment. Without a key it returns a graceful 503.

## Tests, lint, format

```bash
uv run pytest                    # unit tests (Anthropic call is stubbed)
ruff check .                     # lint (config in ../ruff.toml)
ruff format .                    # format
```

## Environment variables

| Variable            | Required | Default              | Purpose                          |
| ------------------- | -------- | -------------------- | -------------------------------- |
| `ANTHROPIC_API_KEY` | yes      | —                    | Auth for the Anthropic API.      |
| `ANTHROPIC_MODEL`   | no       | `claude-sonnet-4-6`  | Model used for agent calls.      |
| `CORS_ORIGINS`      | no       | `http://localhost:3000` | Comma-separated allowed origins. |
