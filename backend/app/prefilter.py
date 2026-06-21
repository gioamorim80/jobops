"""No-LLM prefilter: narrow the firehose to a generous shortlist.

This is deterministic and cheap. It ranks candidate jobs on safe, high-confidence
signals only — location/remote fit, recency, and light keyword overlap with the
user's target roles and skills — and returns the top `cap`. It is GENEROUS by
design: it removes only clearly-irrelevant jobs and otherwise prefers to pass a
borderline posting through. Honest fit judgement is the LLM scorer's job in M4;
the prefilter must never make that call.
"""

import re
from datetime import UTC, datetime

DEFAULT_CAP = 30

_TOKEN_RE = re.compile(r"[a-z0-9+#]+")
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "for",
    "to",
    "in",
    "on",
    "with",
    "at",
    "by",
    "is",
    "as",
    "we",
    "you",
}


def _tokens(text: str) -> set[str]:
    return {
        t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS and len(t) > 1
    }


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _score(
    job: dict, profile_tokens: set[str], locations: list[str], remote_pref: str, now: datetime
) -> float:
    text = f"{job.get('title') or ''} {job.get('description') or ''} {job.get('category') or ''}"
    overlap = len(profile_tokens & _tokens(text))
    score = float(min(overlap, 8))  # light keyword/skill overlap (capped)

    # location / remote fit
    if job.get("remote") and remote_pref in ("remote", "flexible", ""):
        score += 3.0
    if locations:
        place = f"{job.get('location_display') or ''} {' '.join(job.get('location_area') or [])}".lower()
        if any(loc in place for loc in locations):
            score += 3.0

    # recency: ~3 for fresh, fading over a couple of weeks
    posted = _parse_dt(job.get("posted_at"))
    if posted:
        age_days = max(0, (now - posted).days)
        score += max(0.0, 3.0 - age_days / 14.0)

    return score


def prefilter(parsed: dict, jobs: list[dict], cap: int = DEFAULT_CAP) -> list[dict]:
    """Rank candidate jobs for a profile and return a generous top-`cap` shortlist,
    each annotated with a numeric `prefilter_score`. No LLM, no hard fit judgement."""
    target_roles = parsed.get("target_roles") or []
    skills = parsed.get("skills") or []
    profile_tokens = _tokens(" ".join(target_roles) + " " + " ".join(skills))
    locations = [loc.lower() for loc in (parsed.get("locations") or []) if loc]
    remote_pref = (parsed.get("remote_pref") or "").lower()
    now = datetime.now(UTC)

    scored = [
        (_score(job, profile_tokens, locations, remote_pref, now), index, job)
        for index, job in enumerate(jobs)
    ]
    # Sort by score desc; the original index keeps it stable for equal scores.
    scored.sort(key=lambda item: (-item[0], item[1]))

    return [{**job, "prefilter_score": round(score, 2)} for score, _, job in scored[:cap]]
