-- 0007_m4_matches.sql
-- M4 — per-user automated LLM scores of the prefilter shortlist.
--
-- ISOLATION: unlike the shared `jobs` pool (0004, NOT per-user RLS — public
-- postings, authenticated-read), `matches` holds PER-USER results: one user's fit
-- score, cleared reqs, and honest gaps for a job. So it carries `user_id` and
-- enforces per-user RLS. This is the isolation boundary the jobs pool deferred:
-- a user may SELECT only their own matches; writes are the backend service role's
-- only (the service role bypasses RLS — no write policy is granted to
-- `authenticated`, so the client can never insert/update/delete matches).
--
-- UNIQUE (user_id, job_id): a job is scored once per user (re-runs upsert).
-- `posted_at` is carried from `jobs` so M5 can use recency as a SEPARATE signal —
-- the fit `score` itself stays pure and never factors recency in.
-- Idempotent. Run in the Supabase SQL editor BEFORE deploying the M4 code.

create extension if not exists pgcrypto;  -- gen_random_uuid()

create table if not exists public.matches (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  job_id     uuid not null references public.jobs (id) on delete cascade,
  score      int,                          -- 0–100 fit (pure: no recency factored in)
  band       text,                         -- qualitative band (reuses scorer bands)
  cleared    jsonb not null default '[]'::jsonb,  -- requirements cleared (evidence-traced)
  gaps       jsonb not null default '[]'::jsonb,  -- honest gaps
  analysis   text,                         -- optional one-line summary (scorer pitch)
  posted_at  timestamptz,                  -- carried from jobs; SEPARATE recency signal (M5)
  model      text,                         -- e.g. 'claude-haiku-4-5'
  scored_at  timestamptz not null default now(),
  unique (user_id, job_id)
);

alter table public.matches enable row level security;

-- Users may SELECT only their own matches. No insert/update/delete policy is
-- defined for `authenticated`, so RLS denies their writes; the backend service
-- role bypasses RLS and is the only writer.
drop policy if exists "matches_select_own" on public.matches;
create policy "matches_select_own" on public.matches
  for select
  using (user_id = auth.uid());

create index if not exists matches_user_score_idx on public.matches (user_id, score desc);
create index if not exists matches_job_idx on public.matches (job_id);

-- Grants: read-only to authenticated (RLS still scopes rows); full to service_role.
grant select on public.matches to authenticated;
grant all on public.matches to service_role;
