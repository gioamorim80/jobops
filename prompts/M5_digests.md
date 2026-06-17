# PROMPT — M5: Scheduled digests + email + guardrails

Paste into Claude Code after M4.

---

Read CLAUDE.md, ARCHITECTURE.md, ROADMAP.md (M5), docs/agents/DIGEST.md,
docs/GUARDRAILS.md, docs/DATA_MODEL.md (alerts_log, usage_log). Do only M5.

1. Scheduler in the FastAPI service (APScheduler or cron-triggered endpoint) that
   runs the loop per user on their frequency (off/daily/weekly; skip if paused).
2. Digest agent (docs/agents/DIGEST.md): gather new matches above threshold not yet
   alerted; if none, skip silently; compose a concise email; send via Resend; log to
   alerts_log.
3. Enforce ALL guardrails: per-user daily LLM cap, global monthly budget ceiling
   (pause automated work when hit + notify operator), rate limiting, pause switch.
4. Provide a way to trigger a test digest for one user on demand.

Acceptance: a test user receives a correctly-scoped digest email; exceeding a cap is
blocked gracefully (no crash); paused users get nothing. Stop after M5.

Before finishing: update STATE.md + CHANGELOG.md, commit, push.
