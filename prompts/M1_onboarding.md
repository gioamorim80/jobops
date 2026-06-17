# PROMPT — M1: Auth + onboarding chat → profile

Paste into Claude Code after M0 is deployed and green.

---

Read CLAUDE.md, ARCHITECTURE.md, ROADMAP.md (M1), docs/DATA_MODEL.md, and
docs/agents/ONBOARDING.md. Do only M1.

1. Supabase: create the `profiles` and `preferences` tables with the columns and
   RLS policies in docs/DATA_MODEL.md. Add a migration in /supabase/migrations.
   Enable resume file storage (a private bucket).
2. Frontend: Supabase magic-link auth (sign in with email). Protected app shell.
3. Onboarding (LIGHTWEIGHT chat — decided): user uploads a resume; the agent parses
   it and asks ONLY 2-3 gap questions (target role/seniority, locations/remote,
   alert frequency), then shows the extracted draft profile for confirmation.
   Keep it minimal — not an elaborate multi-turn interview. (Full conversational
   onboarding can come post-Route.)
4. Backend: implement the onboarding agent per docs/agents/ONBOARDING.md — parse the
   resume, ask gap questions, do the attribution check, and on confirmation write
   `profiles.parsed` + `preferences`. Log usage to usage_log.
5. Settings screen: alert frequency (off/daily/weekly) + score threshold.

Hard rules (CLAUDE.md): multi-tenant via RLS, no fabrication, never log raw resume
text, confirm before saving.

Acceptance: two separate accounts each complete onboarding and can see ONLY their
own profile. Run the two-account isolation test in docs/DATA_MODEL.md and show me
the result. Stop after M1.

Before finishing: update STATE.md + CHANGELOG.md, commit, push.
