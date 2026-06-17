# PROMPT — M4: Automated matching (funnel stage 2)

Paste into Claude Code after M3.

---

Read CLAUDE.md, ARCHITECTURE.md, ROADMAP.md (M4), docs/agents/SCORER.md,
docs/DATA_MODEL.md (matches), docs/GUARDRAILS.md. Do only M4.

1. Pipeline: for each active user, take the prefilter shortlist from M3, LLM-score
   ONLY the shortlist with the Scorer, and store results in `matches`
   (unique per user+job). Log usage; enforce per-user cap + global budget ceiling.
2. Frontend matches dashboard: list the user's matches, sortable by fit, filter by
   decision. Link each to the M2 tailor flow.
3. NEVER score the whole pool with the LLM — prefilter first. Treat that as a bug if
   it happens.

Acceptance: the pipeline produces stored per-user matches; the dashboard shows each
user only their own; cost stays bounded by the funnel. Stop after M4.

Before finishing: update STATE.md + CHANGELOG.md, commit, push.
