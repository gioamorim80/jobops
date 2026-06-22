-- 0008_matches_decision.sql
-- M4 polish — close the cross-path drift: the on-demand flow shows the scorer's
-- decision (APPLY/STRETCH/SKIP) alongside the fit band, but the automated matcher
-- (0007) stored only score + band, so /matches couldn't show the decision. Add it
-- so both paths surface the same information for the same job.
--
-- Nullable: rows scored before this migration keep decision = NULL and the UI
-- simply omits the decision chip for them (a re-score fills it in). No new grants
-- (the matches RLS policy + 0007 grants already cover the column). Idempotent.
-- Run BEFORE deploying the M4-polish code.

alter table public.matches
  add column if not exists decision text;  -- 'APPLY' | 'STRETCH' | 'SKIP'
