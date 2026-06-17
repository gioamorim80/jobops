# PROMPT — M2: Paste a link → score + tailor (MVP wedge)

Paste into Claude Code after M1.

---

Read CLAUDE.md, ARCHITECTURE.md, ROADMAP.md (M2), docs/agents/SCORER.md,
docs/agents/TAILOR.md, docs/JOB_SOURCES.md (the on-demand fetch section), and
docs/DATA_MODEL.md (tailorings). Do only M2.

1. Backend endpoint that accepts EITHER a job URL or pasted text. If a URL: fetch
   once and readability-extract the posting; if blocked/thin/JS-only, return a clear
   "couldn't read that link — paste the text" response. Never hammer a host.
2. Run the Scorer (docs/agents/SCORER.md) against the current user's profile, then
   the Tailor (docs/agents/TAILOR.md). Enforce per-user LLM cap from GUARDRAILS.md.
3. Frontend screen: input for link/text → shows FIT score + decision + cleared/gaps
   + tailored bullets (each with its "why") + match analysis. User can edit bullets
   and click Approve. Save to `tailorings` (approved flag).
4. Honor no-fabrication: surface any `metric pending` / attribution flags visibly.

Acceptance: paste a REAL posting, get an accurate fit + honest tailored bullets with
zero fabricated content, edit and approve, and see it saved (and only to this user).
Stop after M2.

Before finishing: update STATE.md + CHANGELOG.md, commit, push.
