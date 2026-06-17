# JobOps frontend (Next.js, App Router, TypeScript)

The web app. In M0 it is a single landing page that calls the backend
`/agent/ping` and renders the live model response.

## Local run

```bash
cd frontend
cp ../.env.example .env.local     # set NEXT_PUBLIC_BACKEND_URL if not localhost:8000
npm install
npm run dev                       # http://localhost:3000
```

The backend must be running (see `../backend/README.md`). Click **Ping the
agent** to call `/agent/ping` and see the model's reply.

## Scripts

| Command                | What it does                     |
| ---------------------- | -------------------------------- |
| `npm run dev`          | Dev server on :3000.             |
| `npm run build`        | Production build.                |
| `npm run start`        | Serve the production build.      |
| `npm run lint`         | ESLint (`next/core-web-vitals`). |
| `npm run format`       | Prettier write.                  |
| `npm run format:check` | Prettier check (used in CI).     |

## Environment variables

| Variable                  | Default                 | Purpose                          |
| ------------------------- | ----------------------- | -------------------------------- |
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | Base URL of the FastAPI backend. |
