-- 0001_m1_profiles_preferences.sql
-- M1 — per-user profiles + preferences with Row-Level Security, and a PRIVATE
-- resume storage bucket. Multi-tenant from line one: every per-user table and
-- the storage bucket enforce isolation via `user_id = auth.uid()`.
--
-- Run this in the Supabase SQL editor (or `supabase db push`). Idempotent.

-- =========================================================================
-- profiles  (per-user, RLS)
-- =========================================================================
create table if not exists public.profiles (
  user_id             uuid primary key references auth.users (id) on delete cascade,
  full_name           text,
  email               text,
  raw_resume_text     text,        -- extracted from upload; PII, never logged
  resume_file_path    text,        -- path in the private `resumes` bucket
  linkedin_text       text,        -- optional pasted experience text (unused in M1)
  parsed              jsonb,       -- { skills[], target_roles[], seniority, domains[],
                                   --   locations[], remote_pref, comp_floor, attribution_notes[] }
  onboarding_complete boolean not null default false,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles_own_rows" on public.profiles;
create policy "profiles_own_rows" on public.profiles
  for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- =========================================================================
-- preferences  (per-user, RLS)
-- =========================================================================
create table if not exists public.preferences (
  user_id         uuid primary key references auth.users (id) on delete cascade,
  alert_frequency text    not null default 'weekly'
                          check (alert_frequency in ('off', 'daily', 'weekly')),
  score_threshold int     not null default 60
                          check (score_threshold between 0 and 100),
  channels        jsonb   not null default '{"email": true}'::jsonb,
  paused          boolean not null default false
);

alter table public.preferences enable row level security;

drop policy if exists "preferences_own_rows" on public.preferences;
create policy "preferences_own_rows" on public.preferences
  for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- =========================================================================
-- keep profiles.updated_at fresh
-- =========================================================================
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- =========================================================================
-- private resume storage bucket + per-user RLS on storage.objects
-- Files live under a top-level folder named after the user's uid:
--   "<auth.uid()>/<filename>"
-- so the folder check is the tenant boundary. The backend service role
-- bypasses RLS to read files for the onboarding agent.
-- =========================================================================
insert into storage.buckets (id, name, public)
values ('resumes', 'resumes', false)
on conflict (id) do nothing;

drop policy if exists "resumes_select_own" on storage.objects;
create policy "resumes_select_own" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "resumes_insert_own" on storage.objects;
create policy "resumes_insert_own" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "resumes_update_own" on storage.objects;
create policy "resumes_update_own" on storage.objects
  for update to authenticated
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  )
  with check (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "resumes_delete_own" on storage.objects;
create policy "resumes_delete_own" on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
