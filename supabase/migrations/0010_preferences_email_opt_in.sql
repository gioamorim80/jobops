-- 0010_preferences_email_opt_in.sql
-- M5 step 1 — a dedicated email opt-in flag for the digest. The ROADMAP decision
-- is "single opt-in, no cadence", so the old alert_frequency dropdown (off/daily/
-- weekly) is being retired in favour of one clear boolean. This migration only
-- ADDS the flag; alert_frequency is left untouched and dropped in a later commit
-- once nothing writes it.
--
-- Default false is deliberate: consent. Nobody is opted into email by default,
-- including every existing user backfilled by this column add. They must turn it
-- on explicitly in onboarding or Settings.
--
-- No new grants (the preferences RLS policy from 0001 already covers the column).
-- Idempotent. Run BEFORE deploying the M5-step-1 code.

alter table public.preferences
  add column if not exists email_opt_in boolean not null default false;

comment on column public.preferences.email_opt_in is
  'Single opt-in for match digest emails. Default false (consent: no email unless the user turns it on). Replaces the retired alert_frequency cadence dropdown.';
