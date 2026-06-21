-- 0004_m3_jobs_pool.sql
-- M3 — shared pool of PUBLIC job postings, fetched per-user but stored once.
--
-- ISOLATION: this table holds NO user data (only public postings), so it is
-- intentionally NOT per-user RLS. Any authenticated user may READ the pool; only
-- the backend service role WRITES it (RLS denies writes to authenticated since no
-- write policy is defined; the service role bypasses RLS). Per-user isolation
-- lives in the future matches table (M4), not here. Idempotent.

create extension if not exists pgcrypto;  -- gen_random_uuid()

create table if not exists public.jobs (
  id               uuid primary key default gen_random_uuid(),
  source           text not null,           -- adapter name, e.g. 'adzuna'
  external_id      text,                     -- the source's own job id
  source_url       text not null,           -- Adzuna redirect_url; required (ToS: link back)
  title            text,
  company          text,
  location_display text,
  location_area    jsonb,                    -- e.g. ["US", "California", "San Francisco"]
  remote           boolean,                  -- best-effort
  description      text,                     -- Adzuna truncates to ~500 chars; stored as-is
  category         text,
  salary_min       numeric,
  salary_max       numeric,
  posted_at        timestamptz,
  content_hash     text not null unique,     -- dedupe key (one row per posting)
  fetched_at       timestamptz not null default now()
);

create index if not exists jobs_posted_at_idx on public.jobs (posted_at desc);
create index if not exists jobs_source_idx on public.jobs (source);

alter table public.jobs enable row level security;

-- Authenticated users may READ the shared pool. No insert/update/delete policy is
-- defined for them, so RLS denies their writes; only the service role writes.
drop policy if exists "jobs_read_authenticated" on public.jobs;
create policy "jobs_read_authenticated" on public.jobs
  for select to authenticated
  using (true);

grant select on public.jobs to authenticated;
grant all on public.jobs to service_role;
