"""M5 step 5 — digest composition + per-user send (manually triggered, no scheduler).

For one user: double-gate on email_opt_in (step 1) + the score_threshold gate
(via unsent_matches_for_user, step 4), take the top-N unsent matches, compose a
SCORE-ONLY email, send it via Resend (mailer.send_email, step 3), and — only if the
send succeeds — mark exactly those matches sent (alerts.mark_matches_sent, step 4)
so they never re-send and the rest stay unsent for next time.

LLM-FREE by construction: this surfaces ALREADY-SCORED matches and makes NO Anthropic
call (no scoring, no tailoring) — there is deliberately no llm/anthropic import here.
Tailoring happens later, in-app, when the user clicks the "View & tailor" link.

PII-safe: the email and logs carry only role/company/score/band/decision/pitch/link
and recipient/message-id/status — never resume text, profile JSON, or job text
(GUARDRAILS). The profile is read only for the recipient address.
"""

import html as html_lib

from app.alerts import mark_matches_sent, unsent_matches_for_user
from app.applog import get_logger
from app.config import settings
from app.mailer import send_email

logger = get_logger("jobops.digest")

# Canonical production URL for in-email links (emails always point at prod, never a
# localhost CORS origin). The link routes into the existing paste-full-JD flow.
APP_BASE_URL = "https://myjobops.app"


def _match_label(job: dict | None) -> str:
    """'Role — Company' from the embedded job, with honest fallbacks (no fabrication)."""
    job = job or {}
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    if title and company:
        return f"{title} — {company}"
    return title or company or "New role"


def _match_card_html(match: dict) -> str:
    """One match block. Everything is escaped; only score-level fields are included."""
    label = html_lib.escape(_match_label(match.get("jobs")))
    score = match.get("score")
    band = html_lib.escape(str(match.get("band") or ""))
    decision = html_lib.escape(str(match.get("decision") or ""))
    pitch = html_lib.escape(str(match.get("analysis") or ""))
    link = f"{APP_BASE_URL}/score?match={html_lib.escape(str(match.get('id')))}"

    meta_bits = [b for b in (f"Fit {score}" if score is not None else "", band, decision) if b]
    meta = " · ".join(meta_bits)
    pitch_html = f'<p style="margin:6px 0 0;color:#374151;">{pitch}</p>' if pitch else ""
    return (
        '<tr><td style="padding:14px 0;border-bottom:1px solid #eee;">'
        f'<div style="font-weight:600;color:#111;">{label}</div>'
        f'<div style="margin-top:4px;color:#6b7280;font-size:14px;">{meta}</div>'
        f"{pitch_html}"
        f'<p style="margin:10px 0 0;">'
        f'<a href="{link}" style="color:#2563eb;text-decoration:none;font-weight:600;">'
        "View &amp; tailor →</a></p>"
        "</td></tr>"
    )


def compose_digest_html(matches: list[dict]) -> str:
    """Score-only HTML digest. Inline styles + table layout only (email-client-safe);
    no external CSS/JS. Tailoring is NOT done here — the link routes into the app."""
    cards = "".join(_match_card_html(m) for m in matches)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;">'
        '<p style="color:#111;">Here are your newest matches, scored against your '
        "profile. Open one to see the full posting and tailor your resume in the app.</p>"
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{cards}</table>'
        '<p style="margin-top:18px;color:#9ca3af;font-size:12px;">You receive these '
        "because you turned on match emails. Manage this in Settings.</p>"
        "</div>"
    )


def compose_digest_text(matches: list[dict]) -> str:
    """Plain-text fallback — same score-only fields, no PII."""
    lines = ["Here are your newest matches, scored against your profile.", ""]
    for m in matches:
        bits = [
            b
            for b in (
                f"Fit {m.get('score')}" if m.get("score") is not None else "",
                str(m.get("band") or ""),
                str(m.get("decision") or ""),
            )
            if b
        ]
        lines.append(_match_label(m.get("jobs")))
        if bits:
            lines.append("  " + " · ".join(bits))
        if m.get("analysis"):
            lines.append(f"  {m['analysis']}")
        lines.append(f"  View & tailor: {APP_BASE_URL}/score?match={m.get('id')}")
        lines.append("")
    lines.append("You receive these because you turned on match emails. Manage this in Settings.")
    return "\n".join(lines)


def send_user_digest(client, user_id: str) -> dict:
    """Compose + send one user's digest, then mark sent on success. Returns a
    per-user summary; never raises for the normal skip/fail cases."""
    # 1) DOUBLE-GATE, part one: opt-in. Never email someone who opted out, even if a
    #    user_id explicitly targets them. Also skip PAUSED users (inactivity pause —
    #    no point emailing matches to someone the scanner has paused, until they
    #    return and are auto-unpaused).
    prefs = (
        client.table("preferences")
        .select("email_opt_in, paused")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not (prefs and prefs[0].get("email_opt_in")):
        return {"user": user_id[:8], "status": "skipped_opt_out"}
    if prefs[0].get("paused"):
        return {"user": user_id[:8], "status": "skipped_paused"}

    # 2) Recipient address (profile read is for the email address ONLY — no PII else).
    profile = (
        client.table("profiles").select("email").eq("user_id", user_id).limit(1).execute().data
        or []
    )
    to_email = (profile[0].get("email") if profile else None) or None
    if not to_email:
        return {"user": user_id[:8], "status": "skipped_no_email"}

    # 3) Gather unsent qualifying matches (part two of the gate: score >= threshold,
    #    not already alerted). Already sorted by score desc.
    unsent = unsent_matches_for_user(client, user_id)
    if not unsent:
        return {"user": user_id[:8], "status": "skipped_no_matches"}  # no empty digests

    # 4) Top-N only; the rest stay unsent for the next run.
    top = unsent[: settings.digest_max_matches]
    count = len(top)
    subject = f"JobOps — {count} new match{'es' if count != 1 else ''} for you"

    # 5/6) Compose (score-only) and send.
    result = send_email(
        to=to_email,
        subject=subject,
        html=compose_digest_html(top),
        text=compose_digest_text(top),
    )
    if result.get("status") != "ok":
        # 7) Do NOT mark sent on failure → these re-surface next run.
        logger.warning("digest send failed: user=%s error=%s", user_id[:8], result.get("error"))
        return {"user": user_id[:8], "status": "send_failed", "error": result.get("error")}

    # 7) Mark EXACTLY the included matches sent (idempotent).
    marked = mark_matches_sent(client, user_id, [m["id"] for m in top])
    logger.info("digest sent: user=%s matches=%s marked=%s", user_id[:8], count, marked)
    return {
        "user": user_id[:8],
        "status": "sent",
        "sent": count,
        "marked": marked,
        "message_id": result.get("id"),
    }


# ------------------------------- inactivity reinvite ---------------------------
def compose_reinvite_html() -> str:
    """The one-time 'we paused your alerts, come back' email. No PII — just a nudge
    and a link into the app. Returning to the app is what auto-unpauses the user."""
    link = f"{APP_BASE_URL}/home"
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;">'
        '<p style="color:#111;">We\'ve paused your JobOps match emails since we '
        "haven't seen you in a while.</p>"
        f'<p style="margin:10px 0;"><a href="{link}" '
        'style="color:#2563eb;text-decoration:none;font-weight:600;">Come back to '
        "JobOps →</a> and we'll start sending matches again.</p>"
        '<p style="margin-top:18px;color:#9ca3af;font-size:12px;">You can turn match '
        "emails off anytime in Settings.</p>"
        "</div>"
    )


def compose_reinvite_text() -> str:
    return (
        "We've paused your JobOps match emails since we haven't seen you in a while.\n"
        f"Come back to JobOps to resume: {APP_BASE_URL}/home\n\n"
        "You can turn match emails off anytime in Settings."
    )


def send_user_reinvite(client, user_id: str) -> dict:
    """Send the ONE-TIME inactivity reinvite. Called by the scanner only when a user
    first crosses into paused, and only for opted-in users (the scanner loops opted-in
    users), so consent holds. PII-safe: the profile is read for the recipient address
    only; the email carries no resume/profile/job content. Returns the send result."""
    profile = (
        client.table("profiles").select("email").eq("user_id", user_id).limit(1).execute().data
        or []
    )
    to_email = (profile[0].get("email") if profile else None) or None
    if not to_email:
        return {"status": "error", "error": "no_email"}

    result = send_email(
        to=to_email,
        subject="We've paused your JobOps match emails",
        html=compose_reinvite_html(),
        text=compose_reinvite_text(),
    )
    logger.info("reinvite: user=%s status=%s", user_id[:8], result.get("status"))
    return result
