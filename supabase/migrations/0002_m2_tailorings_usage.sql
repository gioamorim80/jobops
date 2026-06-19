-- 0002_m2_tailorings_usage.sql
-- M2 — on-demand "paste a link → score + tailor" storage, plus per-user usage
-- logging for the cost cap. Per-user RLS (user_id = auth.uid()) on both tables.
--
-- New tables are not auto-exposed to the API roles, so this migration ALSO
-- grants table privileges to `authenticated` (RLS still gates rows) and
-- `service_role` (backend; bypasses RLS), and usage on sequences — matching the
-- isolation pattern from 0001. Run in the Supabase SQL editor. Idempotent.

create extension if not exists pgcrypto;  -- gen_random_uuid()

-- =========================================================================
-- tailorings  (per-user, RLS) — results of the on-demand link/paste flow
-- =========================================================================
create table if not exists public.tailorings (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users (id) on delete cascade,
  job_id           uuid,        -- FK -> public.jobs added in M3 (jobs not present yet)
  source_url       text,        -- null when the user pasted text
  job_text         text,        -- the posting text scored/tailored against
  score            jsonb,       -- scorer output (fit, decision, cleared, gaps, pitch, ...)
  tailored_bullets jsonb,       -- [{ original, tailored, why }]
  analysis         text,        -- tailor match analysis
  approved         boolean not null default false,  -- set true only by explicit user action
  created_at       timestamptz not null default now()
);

alter table public.tailorings enable row level security;

drop policy if exists "tailorings_own_rows" on public.tailorings;
create policy "tailorings_own_rows" on public.tailorings
  for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create index if not exists tailorings_user_created_idx
  on public.tailorings (user_id, created_at desc);

-- =========================================================================
-- usage_log  (per-user, RLS) — one row per agent call, for the cost cap
-- =========================================================================
create table if not exists public.usage_log (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  action        text not null,   -- 'score' | 'tailor' | 'onboard' | 'digest'
  tokens_in     int  not null default 0,
  tokens_out    int  not null default 0,
  cost_estimate numeric not null default 0,
  created_at    timestamptz not null default now()
);

alter table public.usage_log enable row level security;

drop policy if exists "usage_log_own_rows" on public.usage_log;
create policy "usage_log_own_rows" on public.usage_log
  for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create index if not exists usage_log_user_created_idx
  on public.usage_log (user_id, created_at desc);

-- =========================================================================
-- grants — expose the new tables to the API roles (RLS still enforces rows)
-- =========================================================================
grant select, insert, update, delete on public.tailorings to authenticated;
grant select, insert, update, delete on public.usage_log  to authenticated;
grant all on public.tailorings to service_role;
grant all on public.usage_log  to service_role;
grant usage, select on all sequences in schema public to authenticated, service_role;
