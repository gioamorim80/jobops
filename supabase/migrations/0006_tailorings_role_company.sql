-- 0006_tailorings_role_company.sql
-- Row labels for the Scored jobs list. The scorer extracts the role title and the
-- hiring company from the posting text (never invents them; see agents/scorer.py
-- and docs/agents/SCORER.md), and we store them here so the history list can show
-- "Role — Company" instead of raw description text.
--
-- Both columns are nullable. Rows scored before this migration stay NULL; the UI
-- shows a sensible fallback label for them, and they can be filled in by the
-- optional one-time backfill described in STATE.md. The existing
-- "tailorings_own_rows" RLS policy and the 0002 table grants (select/insert/
-- update/delete to authenticated, all to service_role) already cover these
-- columns, so no new grants are required. Idempotent.

alter table public.tailorings
  add column if not exists role text;
alter table public.tailorings
  add column if not exists company text;
