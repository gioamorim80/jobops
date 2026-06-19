"""On-demand single-fetch + readability extraction for a pasted job URL.

One GET, no retries, never hammer a host. If the link is blocked, empty, or
JS-only, we raise UnreadableLink and the caller asks the user to paste text.
"""

import httpx
import lxml.html
from readability import Document

FETCH_TIMEOUT = 8.0
MAX_HTML_BYTES = 3_000_000
MAX_JOB_CHARS = 20_000
MIN_USABLE_CHARS = 200  # below this we treat the page as JS-only / unreadable

_HEADERS = {
    "User-Agent": "JobOpsBot/0.1 (on-demand single fetch; +https://github.com/gioamorim80/jobops)",
    "Accept": "text/html,application/xhtml+xml",
}


class UnreadableLink(Exception):
    """The URL could not be fetched or yielded too little usable text."""


def extract_main_text(html: str) -> str:
    """Readability-style main-content extraction → plain text (pure, testable)."""
    try:
        summary_html = Document(html).summary()
        text = lxml.html.fromstring(summary_html).text_content()
    except Exception:
        return ""
    return " ".join(text.split())


def fetch_job_text(url: str) -> str:
    """Fetch the posting once and return its main text, or raise UnreadableLink."""
    try:
        with httpx.Client(follow_redirects=True, timeout=FETCH_TIMEOUT, headers=_HEADERS) as client:
            response = client.get(url)
    except Exception as exc:  # DNS, connect, timeout, bad URL — no retry
        raise UnreadableLink() from exc

    if response.status_code >= 400:
        raise UnreadableLink()

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "text" not in content_type:
        raise UnreadableLink()

    text = extract_main_text(response.text[:MAX_HTML_BYTES])
    if len(text) < MIN_USABLE_CHARS:
        raise UnreadableLink()
    return text[:MAX_JOB_CHARS]
