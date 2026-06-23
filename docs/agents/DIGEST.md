# AGENT: DIGEST

## Role
Scheduled, per-user. Compose and send the recurring alert of new scored matches.

## Trigger
The scheduler runs on each user's `alert_frequency` (daily/weekly; skip if 'off'
or `paused`).

## Input
- New `matches` for the user since their last `alerts_log` entry, above their
  `score_threshold`.
- The user's profile (for tone/context only — never include raw PII in the email).

## Shared threshold rule (must match /matches)
A match is surfaced on `/matches` AND emailed in the digest only when
`score >= score_threshold` (default 60, inclusive). The digest job MUST use this
identical contract so the two surfaces never disagree. (/matches applies it today
as a server-side `.gte("score", threshold)`; this is currently a duplicated rule
across the frontend query and the future Python digest — keep them in sync.)

## Behavior
1. Gather qualifying matches (above threshold, not already alerted).
2. If none, skip silently (don't send empty digests).
3. Compose a concise email: top matches with FIT score, decision, one-line pitch,
   and a link into the app to view/tailor/apply.
4. Send via Resend. Log to `alerts_log` (match_ids, channel, frequency).
5. Respect guardrails: budget ceiling, per-user caps, pause switch.

## Rules
- Never send content the system fabricated; scores trace to real matches.
- Keep emails short and skimmable; the app holds the detail.
- One digest per cycle per user; dedupe against prior alerts.
