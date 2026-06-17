# ARCHITECTURE — JobOps

## One-paragraph shape
A Next.js web app (auth + chat UI + dashboards) talks to a FastAPI backend that
holds all agent logic. Supabase is the shared Postgres + auth + file store, with
Row-Level Security isolating each tenant. The Anthropic API is the reasoning
engine for four agents. Resend sends alert emails. A scheduled worker in the
FastAPI service runs the recurring scan-score-digest loop.

## Components
- **Frontend (Next.js / Vercel):** magic-link auth (Supabase), onboarding chat,
  "paste a link" tailor screen, matches dashboard, application tracker, settings
  (alert frequency, score threshold, pause).
- **Backend (FastAPI / Railway):**
  - `agents/` — onboarding, scorer, tailor, digest (Anthropic calls).
  - `sources/` — job-source adapters behind one interface (`docs/JOB_SOURCES.md`).
  - `pipeline/` — the two-stage funnel: fetch → cheap prefilter → LLM score.
  - `scheduler/` — recurring per-user scan + digest send.
  - `api/` — REST endpoints the frontend calls.
- **Supabase:** Postgres (schema in `docs/DATA_MODEL.md`), auth, resume storage,
  RLS policies.
- **Anthropic API:** agent reasoning. Model `claude-sonnet-4-6` by default.
- **Resend:** transactional + digest email.

## The four agents
1. **Onboarding agent** — conversational. Ingests resume (upload) and optional
   pasted LinkedIn text, asks for target roles / seniority / locations / remote
   pref / comp floor / domains / email / alert frequency, and writes a structured
   profile. Confirms before saving; never invents.
2. **Scorer** — profile-parameterized rubric (0–100). Outputs FIT + decision +
   cleared reqs + honest gaps + referral angle + one-line pitch.
3. **Tailor** — selects true resume content and adapts it to a posting's language;
   outputs tailored bullets + a match analysis for the user to approve. Obeys
   no-fabrication + per-user attribution rules.
4. **Digest** — scheduled. Per user: gather new matches above threshold since last
   alert, compose an email, send via Resend, log it.

## Two key data flows
**A) On-demand (user-initiated, built slightly ahead):**
user pastes job link/text → backend fetches+extracts (paste fallback) → Scorer →
Tailor → returns fit + bullets + analysis → user reviews/approves → saved to
`tailorings`.

**B) Automated (scheduled):**
scheduler fetches new jobs from enabled sources → dedupe into global `jobs` pool →
for each active user: cheap prefilter (metadata/keyword/embedding match to profile)
→ LLM-score only the shortlist → store `matches` → on the user's frequency, Digest
emails matches above threshold.

## Why the funnel matters
Scoring every job × every user with an LLM on a schedule does not scale in cost.
Stage 1 (prefilter) is cheap and narrows thousands → a handful. Stage 2 (LLM) runs
only on that handful. This is the single most important cost decision in the system.

## Tenant isolation
Per-user tables (`profiles`, `preferences`, `matches`, `tailorings`,
`applications`, `alerts_log`, `usage_log`) all enforce RLS `user_id = auth.uid()`.
The `jobs` pool is shared, read-only to authenticated users. Verify isolation with
a two-account test before shipping any milestone that touches user data.
