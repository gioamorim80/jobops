-- 0009_usage_log_model.sql
-- Persist WHICH model served each logged LLM call. Today the model is inferred
-- from the cost ratio; this stores it directly alongside the token counts and
-- cost_estimate already in usage_log.
--
-- Nullable + NO backfill: existing usage_log rows stay valid as NULL, and inserts
-- from the currently-deployed code (which does not pass model yet) keep working.
-- Does NOT touch RLS or any policy on usage_log — isolation is unchanged (this is
-- metadata, not user data). Idempotent.

alter table public.usage_log
  add column if not exists model text;

comment on column public.usage_log.model is
  'Anthropic model that served this call (e.g. claude-haiku-4-5, claude-sonnet-4-6). NULL for rows logged before this column existed.';
