# PROMPT — M3: Job-source adapters + dedupe + prefilter

Paste into Claude Code after M2.

---

Read CLAUDE.md, ARCHITECTURE.md, ROADMAP.md (M3), docs/JOB_SOURCES.md,
docs/DATA_MODEL.md (jobs). Do only M3.

1. Implement the JobSourceAdapter interface and a registry (enable/disable by config).
2. Build 2-3 adapters from the ALLOWLIST only (suggest: Remotive + Arbeitnow + one
   ATS board like Greenhouse). NO LinkedIn/Indeed/Glassdoor.
3. Normalize + dedupe into the shared `jobs` pool (upsert on source+source_job_id,
   collapse cross-source dups by content_hash).
4. Implement the cheap prefilter (NO LLM): rank jobs against a profile by
   skill/keyword overlap, role/seniority, location/remote, comp floor. Return top K.
5. A manual trigger endpoint to run a fetch now (scheduling comes in M5).

Acceptance: a manual fetch populates `jobs`, dedupe works, and prefilter returns a
sensible shortlist for a test profile. Show me counts and a sample shortlist.
Stop after M3.

Before finishing: update STATE.md + CHANGELOG.md, commit, push.
