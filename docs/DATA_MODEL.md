# DATA_MODEL — Postgres (Supabase)

All per-user tables enforce Row-Level Security: `user_id = auth.uid()`.
`jobs` is a shared pool, readable by authenticated users, writable only by the
backend service role.

## Tables

### profiles  (per-user, RLS)
- `user_id` uuid PK, references `auth.users`
- `full_name` text
- `email` text
- `raw_resume_text` text          -- extracted from upload; PII, never logged
- `resume_file_path` text          -- Supabase storage path
- `linkedin_text` text             -- optional pasted experience text
- `parsed` jsonb                   -- { skills[], target_roles[], seniority,
                                   --   domains[], locations[], remote_pref,
                                   --   comp_floor, attribution_notes }
- `onboarding_complete` boolean default false
- `created_at` / `updated_at` timestamptz

### preferences  (per-user, RLS)
- `user_id` uuid PK/FK
- `alert_frequency` text check in ('off','daily','weekly') default 'weekly'
- `score_threshold` int default 60
- `channels` jsonb default '{"email": true}'
- `paused` boolean default false

### jobs  (shared pool — service-role write, authenticated read)
- `id` uuid PK
- `source` text                    -- adapter name
- `source_job_id` text
- `title` / `company` / `location` text
- `remote` boolean
- `description` text
- `url` text
- `posted_at` timestamptz
- `content_hash` text              -- for dedupe
- `raw` jsonb
- `fetched_at` timestamptz
- unique(`source`, `source_job_id`); index on `content_hash`

### matches  (per-user, RLS) — from the automated pipeline
- `id` uuid PK
- `user_id` uuid FK
- `job_id` uuid FK -> jobs
- `prefilter_score` numeric
- `llm_score` int
- `decision` text check in ('APPLY','STRETCH','SKIP')
- `cleared` jsonb / `gaps` jsonb
- `pitch` text / `referral_angle` text
- `scored_at` timestamptz
- unique(`user_id`, `job_id`)

### tailorings  (per-user, RLS) — from the on-demand link/paste flow
- `id` uuid PK
- `user_id` uuid FK
- `job_id` uuid FK nullable        -- null if pasted, not from pool
- `source_url` text / `job_text` text
- `score` jsonb                    -- scorer output
- `tailored_bullets` jsonb
- `analysis` text
- `approved` boolean default false
- `created_at` timestamptz

### applications  (per-user, RLS)
- `id` uuid PK / `user_id` uuid FK / `job_id` uuid FK nullable
- `status` text                    -- e.g. interested / applied / interviewing / closed
- `applied_at` / `follow_up_at` timestamptz
- `notes` text

### alerts_log  (per-user, RLS)
- `id` uuid PK / `user_id` uuid FK
- `sent_at` timestamptz / `channel` text
- `match_ids` uuid[] / `frequency` text

### usage_log  (per-user, RLS) — cost guardrails
- `id` uuid PK / `user_id` uuid FK
- `action` text                    -- 'score' | 'tailor' | 'onboard' | 'digest'
- `tokens_in` / `tokens_out` int
- `cost_estimate` numeric
- `created_at` timestamptz

## RLS policy pattern (apply to every per-user table)
```sql
alter table <t> enable row level security;
create policy "own rows" on <t>
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
```
For `jobs`: enable RLS, `for select using (auth.role() = 'authenticated')`, and
restrict writes to the service role only.

## Isolation test (run before any user-data milestone is "done")
Create two accounts, write data as each, confirm neither can read the other's
rows via the client (anon/auth key), only via the backend service role.
