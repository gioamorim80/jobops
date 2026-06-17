# Supabase

Postgres + magic-link auth + file storage + Row-Level Security for tenant
isolation.

## Status: M0

Empty on purpose. No schema yet.

Schema and RLS policies arrive in **M1** (`profiles`, `preferences` tables with
`user_id = auth.uid()` policies — see `docs/DATA_MODEL.md`). SQL migrations will
live in `migrations/`.
