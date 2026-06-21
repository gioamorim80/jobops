-- 0003_tailorings_applied_at.sql
-- Add an "applied" marker to tailorings: NULL = not applied, a timestamp = the
-- date the user marked it applied. Per-user isolation is unchanged — the
-- existing "tailorings_own_rows" RLS policy and the table-level grants from 0002
-- (select/insert/update/delete to authenticated, all to service_role) already
-- cover this new column, so no new grants are required. Idempotent.

alter table public.tailorings
  add column if not exists applied_at timestamptz;
