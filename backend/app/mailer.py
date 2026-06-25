"""Backend email sending via Resend — the first place the backend sends mail.

PII-safe by construction (see docs/GUARDRAILS.md): we log ONLY the recipient
address, the Resend message id, and the status. We NEVER log the API key, the
subject/body, or any resume/profile/job content. The send body is built by callers;
this helper does not inspect or persist it.

Uses the already-present `httpx` (no new dependency). Returns a structured result
and never raises for the normal failure modes (missing config, network error,
non-2xx) so callers — e.g. the admin test endpoint — can report what happened.
"""

import httpx

from app.applog import get_logger
from app.config import settings

logger = get_logger("jobops.mailer")

RESEND_ENDPOINT = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 15.0


def send_email(to: str, subject: str, html: str, text: str | None = None) -> dict:
    """Send one email via Resend, from `settings.alert_from_email`.

    Returns:
      success -> {"status": "ok", "id": "<resend message id>"}
      failure -> {"status": "error", "error": "<reason>", ...}  (never raises)

    Failure reasons: "not_configured" (key/from missing), "request_failed"
    (network/timeout), "resend_error" (non-2xx, with status_code). Logs recipient +
    message-id + status only — never the API key, the subject, or the body.
    """
    if not settings.resend_api_key or not settings.alert_from_email:
        # Misconfiguration, not a crash: let the caller surface it.
        logger.warning(
            "email send skipped: Resend not configured (missing API key or from address)"
        )
        return {
            "status": "error",
            "error": "not_configured",
            "detail": "RESEND_API_KEY and ALERT_FROM_EMAIL must both be set.",
        }

    payload: dict = {
        "from": settings.alert_from_email,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        response = httpx.post(
            RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json=payload,
            timeout=_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        # Network/timeout. Log a fixed string + recipient only — never the exception
        # detail or the request (which carries the Authorization header / API key).
        logger.warning("email send failed: to=%s status=request_error", to)
        return {"status": "error", "error": "request_failed"}

    if response.status_code >= 400:
        # Log the status code only, never the response body (it can echo the request).
        logger.warning("email send failed: to=%s status=%s", to, response.status_code)
        return {"status": "error", "error": "resend_error", "status_code": response.status_code}

    message_id = None
    try:
        message_id = response.json().get("id")
    except ValueError:
        pass  # 2xx without a JSON body — still a success; just no id to record.
    logger.info("email sent: to=%s id=%s status=ok", to, message_id)
    return {"status": "ok", "id": message_id}
