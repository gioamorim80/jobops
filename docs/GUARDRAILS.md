# GUARDRAILS — cost, safety, privacy

These are features. Build them in, don't bolt them on.

## Cost
- **Per-user daily LLM cap:** max N agent calls/user/day (configurable, e.g. 25).
  Exceeding it returns a friendly "daily limit reached" — never a crash.
- **Global monthly budget ceiling:** track estimated spend in `usage_log`; when the
  ceiling is hit, pause automated scoring/digests (on-demand may stay on or also
  pause — decide and document). Alert the operator.
- **Funnel first:** the prefilter (no LLM) is the primary cost control. If the LLM
  is scoring the whole pool, that is a bug.
- Log every agent call to `usage_log` (action, tokens, cost estimate).

## Rate
- Per-user request rate limiting on the on-demand endpoint (prevent paste-spam).
- Polite fetching: one attempt per link, no host hammering, respect robots where
  applicable.

## Privacy / PII
- Resumes and parsed profiles are PII. Store in Supabase under RLS.
- Never log raw resume text or full profile JSON.
- Send resume content only in the specific Anthropic call that needs it.
- Honor deletion: a user can delete their account and all rows (cascade).

## No fabrication (hard constraint)
- Scoring and tailoring use only what the profile supports.
- Tailoring rephrases/reorders/emphasizes TRUE content; it never invents titles,
  metrics, employers, skills, or scope. Preserve attribution notes.
- If a metric is missing (placeholder), the agent flags "metric pending" — it does
  not invent a number.

## Human-approval gate
- Nothing leaves on the user's behalf without their explicit action.
- Tailored output is always shown for review/edit before it's marked approved.
- "Applied" and similar irreversible states are set only by the user.
