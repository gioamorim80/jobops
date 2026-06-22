-- 0005_jobs_extra_fields.sql
-- Capture a few more Adzuna fields on the shared jobs pool. All nullable. No new
-- grants needed: the 0004 table grants (select to authenticated, all to
-- service_role) and the jobs_read_authenticated RLS policy already cover added
-- columns. Idempotent.
--
-- NOTE on salary_is_predicted: Adzuna salaries are usually Adzuna's own ESTIMATE
-- (salary_is_predicted = '1'), not figures from the posting. We persist the flag
-- alongside salary_min/max so downstream never treats a prediction as advertised
-- comp. M4 TODO: the scorer must treat a predicted salary as a rough estimate and
-- must NOT apply a hard salary-floor penalty based on an Adzuna prediction.

alter table public.jobs
  add column if not exists salary_is_predicted boolean,
  add column if not exists contract_time       text,   -- e.g. full_time / part_time
  add column if not exists contract_type        text,   -- e.g. permanent / contract
  add column if not exists category_tag         text;   -- stable slug, e.g. it-jobs
