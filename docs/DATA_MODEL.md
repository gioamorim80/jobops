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

### jobs  (shared pool — service-role write, authenticated read)  [built in M3]
A shared pool of PUBLIC job postings. It holds NO user data, so it is
intentionally NOT per-user RLS: any authenticated user may read it, and only the
backend service role writes it (RLS denies writes to `authenticated` because no
write policy is defined; the service role bypasses RLS). Per-user isolation lives
in the future `matches` table (M4), not here. Postings are fetched per user from
each user's profile keywords but deduped into this one pool, so a posting two
users both match is stored once.
- `id` uuid PK
- `source` text                    -- adapter name, e.g. 'adzuna'
- `external_id` text               -- the source's own job id
- `source_url` text NOT NULL       -- Adzuna redirect_url; required for ToS attribution
- `title` / `company` / `location_display` text
- `location_area` jsonb            -- e.g. ["US", "California", "San Francisco"]
- `remote` boolean                 -- best-effort
- `description` text               -- Adzuna truncates to ~500 chars; stored as-is
- `category` / `category_tag` text -- human label + stable slug (e.g. 'it-jobs')  [0005]
- `salary_min` / `salary_max` numeric (nullable)
- `salary_is_predicted` boolean    -- True = Adzuna estimate, NOT advertised pay  [0005]
- `contract_time` text             -- full_time / part_time  [0005]
- `contract_type` text             -- permanent / contract  [0005]
- `posted_at` timestamptz          -- parsed/validated in the adapter; null if unparseable
- `content_hash` text UNIQUE       -- dedupe key (one row per posting)
- `fetched_at` timestamptz default now()  -- updated on re-fetch, never a dupe
- indexes on `posted_at` and `source`

Notes:
- `salary_is_predicted` is persisted next to the salary because Adzuna salaries
  are usually Adzuna's own ESTIMATE, not figures from the posting. M4 TODO: the
  scorer must treat a predicted salary as a rough estimate and must NOT apply a
  hard salary-floor penalty based on an Adzuna prediction.
- `description` here is the ~500-char Adzuna excerpt. M4 TODO: decide whether to
  re-fetch the full job description via `source_url` before LLM scoring. The
  existing M2 paste-a-link flow is the intended path for full-text on-demand
  scoring and tailoring of a scanned job.

### matches  (per-user, RLS) — from the automated pipeline  [built in M4, 0007]
This is the isolation boundary the shared `jobs` pool deliberately deferred.
`jobs` holds only PUBLIC postings, so it is authenticated-read and NOT per-user
RLS. `matches` holds PER-USER results (one user's fit score + cleared/gaps for a
job), so it carries `user_id` and enforces per-user RLS: a user may SELECT only
their own matches (`user_id = auth.uid()`), and there is NO write policy for
`authenticated` — only the backend service role writes matches (it bypasses RLS).
- `id` uuid PK
- `user_id` uuid FK -> auth.users (on delete cascade)
- `job_id` uuid FK -> jobs (on delete cascade)
- `score` int                       -- 0–100 fit; PURE, recency never factored in
- `band` text                       -- qualitative band (reuses the scorer bands)
- `cleared` jsonb / `gaps` jsonb    -- requirements cleared (evidence-traced) / honest gaps
- `analysis` text                   -- optional one-line summary (the scorer pitch)
- `posted_at` timestamptz           -- carried from jobs; SEPARATE recency signal for M5
- `model` text                      -- scorer model, e.g. 'claude-haiku-4-5'
- `scored_at` timestamptz default now()
- unique(`user_id`, `job_id`)       -- a job is scored once per user (re-runs upsert)

The fit `score` is stored pure (no recency mixed in). `posted_at` is copied onto
the row so M5's digest can rank/threshold by recency as a separate signal without
contaminating the fit score.

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
