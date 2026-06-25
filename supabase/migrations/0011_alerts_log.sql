-- 0011_alerts_log.sql
-- M5 step 4 — sent-state for the digest: one row per (user, match) that has been
-- emailed, so the digest never sends the same match to the same user twice.
--
-- ISOLATION: per-user data (a user's send history), so it carries `user_id` and
-- enforces per-user RLS — mirrors `matches` (0007). A user may SELECT only their own
-- rows; there is NO insert/update/delete policy for `authenticated`, so RLS denies
-- their writes and the backend service role (which bypasses RLS) is the only writer
-- (the digest). UNIQUE (user_id, match_id) is the DB-level dedup guarantee: a match
-- can be logged sent to a user at most once; the writer uses ON CONFLICT DO NOTHING,
-- so a race or double-call is a safe no-op.
--
-- Add-only. Idempotent. Run in the Supabase SQL editor BEFORE deploying the M5
-- step-4 code.

create extension if not exists pgcrypto;  -- gen_random_uuid()

create table if not exists public.alerts_log (
  id        uuid primary key default gen_random_uuid(),
  user_id   uuid not null references auth.users (id) on delete cascade,
  match_id  uuid not null references public.matches (id) on delete cascade,
  channel   text not null default 'email',  -- delivery channel (email today)
  sent_at   timestamptz not null default now(),
  unique (user_id, match_id)                -- a match is emailed to a user at most once
);

comment on table public.alerts_log is
  'Per-user record of which matches have been emailed, so the digest never re-sends '
  'the same match to the same user. Writes are service-role only; '
  'UNIQUE(user_id, match_id) enforces dedup at the DB level.';
comment on column public.alerts_log.user_id is
  'Owner of the send record; RLS scopes SELECT to user_id = auth.uid().';
comment on column public.alerts_log.match_id is 'The matches.id that was emailed.';
comment on column public.alerts_log.channel is 'Delivery channel; defaults to email.';
comment on column public.alerts_log.sent_at is 'When the send was logged.';

alter table public.alerts_log enable row level security;

-- Users may SELECT only their own send history. No insert/update/delete policy is
-- defined for `authenticated`, so RLS denies their writes; the service role bypasses
-- RLS and is the only writer (the digest).
drop policy if exists "alerts_log_select_own" on public.alerts_log;
create policy "alerts_log_select_own" on public.alerts_log
  for select
  using (user_id = auth.uid());

-- (user_id, match_id) lookups are already served by the UNIQUE constraint's index;
-- add a plain user_id index for the per-user "what's unsent" dedup scan.
create index if not exists alerts_log_user_idx on public.alerts_log (user_id);

-- Grants: read-only to authenticated (RLS still scopes rows); full to service_role.
grant select on public.alerts_log to authenticated;
grant all on public.alerts_log to service_role;
