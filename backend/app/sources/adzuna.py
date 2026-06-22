"""Adzuna job-source adapter (US), queried per-user from a profile.

ToS: Adzuna requires linking users back to the advertiser, so we store
`redirect_url` as `source_url` (required) and never scrape. Credentials come from
the environment. Fetches are bounded and polite. Responses are validated through
strict Pydantic models: a structural change fails loudly to the operator (logged,
source skipped) rather than silently storing garbage.
"""

import re
import time
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.applog import get_logger
from app.config import settings
from app.sources.base import (
    FetchResult,
    JobSource,
    JobSourceError,
    NormalizedJob,
    SearchCriteria,
)

logger = get_logger("jobops.sources.adzuna")

_BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search"
_PAGE_DELAY_S = 1.0  # be polite between page calls
_TIMEOUT_S = 15.0
_MAX_KEYWORDS = 3  # bound the number of role queries per fetch
_HIGH_FAILURE_RATE = 0.5
# If a load-bearing-but-optional field is empty across this fraction of a batch,
# warn: a likely sign the field was renamed/dropped upstream (a format change).
_MISSING_FIELD_RATE = 0.5
_REMOTE_HINTS = ("remote", "work from home", "wfh", "work-from-home")

# Adzuna geocodes `where` from a place name; a metro label like "NYC Metro Area"
# resolves to nothing and returns zero jobs. We normalize a user's free-text
# location label to a clean city centre and search that centre + a radius. The
# radius makes a single city stand in for its commuter metro.
_DISTANCE_KM = 45  # ~metro radius around the resolved city centre

# Known metro/abbreviation labels that need an explicit map to a city centre
# (suffix-stripping alone won't get there). Keys are normalized (lowercased,
# punctuation collapsed to spaces).
_METRO_ALIASES = {
    "nyc": "New York",
    "nyc metro": "New York",
    "nyc metro area": "New York",
    "new york metro": "New York",
    "new york metro area": "New York",
    "new york city": "New York",
    "sf": "San Francisco",
    "sf bay area": "San Francisco",
    "bay area": "San Francisco",
    "san francisco bay area": "San Francisco",
    "silicon valley": "San Francisco",
    "greater boston": "Boston",
    "greater los angeles": "Los Angeles",
    "la": "Los Angeles",
    "dc": "Washington",
    "washington dc": "Washington",
    "washington dc metro": "Washington",
    "dmv": "Washington",
}

# Labels that mean "no geographic filter" (handle remote/anywhere via remote_pref,
# not as a place name Adzuna would fail to geocode).
_DROP_LOCATIONS = {
    "remote",
    "anywhere",
    "us",
    "usa",
    "united states",
    "united states of america",
    "worldwide",
    "global",
    "nationwide",
}

# Metro-style decorations stripped from an otherwise-plain city name.
_METRO_SUFFIXES = (
    " metropolitan area",
    " metro area",
    " metropolitan",
    " metro",
    " area",
    " region",
)

# Remote-preference values that mean "search remote nationwide, don't pin a city".
_REMOTE_PREFS = {"remote", "remote only", "fully remote", "remote-only"}


def _normalize_location(raw: str | None) -> str | None:
    """Turn a free-text profile location into a clean, geocodable place name for
    Adzuna's `where`, or None when it can't be confidently resolved (caller then
    omits `where` and searches without a location filter).

    Handles aliases ("NYC Metro Area" -> "New York"), strips metro-style
    decorations ("Greater Boston" -> "Boston"), passes plain cities through, and
    drops "remote"/"US"/"anywhere"-style labels (those are not a place to geocode).
    """
    if not raw:
        return None
    s = re.sub(r"[^a-z0-9 ]", " ", raw.lower())
    s = re.sub(r"\s+", " ", s).strip()
    if not s or s in _DROP_LOCATIONS:
        return None
    if s in _METRO_ALIASES:
        return _METRO_ALIASES[s]
    if s.startswith("greater "):
        s = s[len("greater ") :].strip()
    for suffix in _METRO_SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
            break
    if not s or s in _DROP_LOCATIONS:
        return None
    if s in _METRO_ALIASES:
        return _METRO_ALIASES[s]
    # Looks like a plain place name (letters, with spaces/.'-): use it title-cased.
    if re.fullmatch(r"[a-z][a-z .'-]*", s):
        return s.title()
    return None


def _location_params(criteria: SearchCriteria) -> tuple[str | None, int | None]:
    """Decide Adzuna's `where`/`distance` from a profile's remote preference and
    location. Remote-preferring users search nationwide (no `where`); everyone
    else is pinned to their resolved city centre plus a metro radius. A "flexible"
    preference never excludes remote jobs — Adzuna has no remote filter, so a
    location search returns both remote- and onsite-tagged postings."""
    pref = (criteria.remote_pref or "").strip().lower()
    if pref in _REMOTE_PREFS:
        return None, None
    place = _normalize_location(criteria.location)
    if place is None:
        if criteria.location:
            logger.info(
                "adzuna: location %r not confidently geocodable; omitting `where`"
                " (searching without a location filter)",
                criteria.location,
            )
        return None, None
    return place, _DISTANCE_KM


# --------- strict models of the documented Adzuna response shape ---------
class _AdzunaCompany(BaseModel):
    display_name: str | None = None


class _AdzunaLocation(BaseModel):
    display_name: str | None = None
    area: list[str] = Field(default_factory=list)


class _AdzunaCategory(BaseModel):
    label: str | None = None
    tag: str | None = None


class AdzunaJob(BaseModel):
    id: str  # required
    redirect_url: str  # required — ToS attribution link
    title: str | None = None
    company: _AdzunaCompany | None = None
    location: _AdzunaLocation | None = None
    description: str | None = None
    category: _AdzunaCategory | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_is_predicted: str | None = None  # Adzuna sends "1"/"0"
    contract_time: str | None = None  # full_time / part_time
    contract_type: str | None = None  # permanent / contract
    created: str | None = None  # ISO posted time


class AdzunaEnvelope(BaseModel):
    results: list[dict]
    count: int | None = None


def _missing(exc: ValidationError) -> str:
    return ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())


def _parse_created(value: str | None, job_id: str) -> str | None:
    """Validate Adzuna's `created` to a real timestamp in the adapter. Return a
    canonical ISO string, or None (logged) if it doesn't parse — so one bad date
    can never fail the whole upsert batch when Postgres casts to timestamptz."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning(
            "adzuna: unparseable created=%r for job id=%s; storing posted_at=null", value, job_id
        )
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def _salary_predicted(value: str | None) -> bool | None:
    if value == "1":
        return True
    if value == "0":
        return False
    return None


class AdzunaSource(JobSource):
    name = "adzuna"

    def fetch(self, criteria: SearchCriteria) -> FetchResult:
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            raise JobSourceError("Adzuna credentials missing (ADZUNA_APP_ID / ADZUNA_APP_KEY).")

        result = FetchResult()
        keywords = [k for k in criteria.keywords if k.strip()][:_MAX_KEYWORDS] or [""]

        with httpx.Client(timeout=_TIMEOUT_S, headers={"User-Agent": "JobOpsBot/0.1"}) as client:
            first_call = True
            for keyword in keywords:
                for page in range(1, criteria.max_pages + 1):
                    if not first_call:
                        time.sleep(_PAGE_DELAY_S)
                    first_call = False

                    raw_items, count = self._get_page(client, keyword, criteria, page)
                    result.raw_count += len(raw_items)
                    if page == 1 and count == 0:
                        logger.warning(
                            "adzuna: 0 results for keyword=%r where=%r — query may be"
                            " too narrow, or the endpoint/format changed",
                            keyword,
                            criteria.location,
                        )

                    for raw in raw_items:
                        try:
                            job = AdzunaJob.model_validate(raw)
                        except ValidationError as exc:
                            result.parse_failures += 1
                            logger.warning(
                                "adzuna: job failed validation (missing/changed: %s)",
                                _missing(exc),
                            )
                            continue
                        result.jobs.append(self._normalize(job))

                    if len(raw_items) < criteria.results_per_page:
                        break  # short page = last page for this keyword

        if result.raw_count and result.parse_failures / result.raw_count > _HIGH_FAILURE_RATE:
            logger.warning(
                "adzuna: high parse-failure rate %s/%s — upstream format may have changed",
                result.parse_failures,
                result.raw_count,
            )
        self._warn_on_missing_fields(result.jobs)
        return result

    def _warn_on_missing_fields(self, jobs: list[NormalizedJob]) -> None:
        """Catch an optional-but-important field going systematically missing
        (a likely rename/format change), not just the zero-results case."""
        total = len(jobs)
        if not total:
            return
        for field in ("title", "description"):
            empty = sum(1 for job in jobs if not (getattr(job, field) or "").strip())
            if empty / total > _MISSING_FIELD_RATE:
                logger.warning(
                    "adzuna: %s empty on %s/%s parsed jobs — field may have been"
                    " renamed/dropped upstream (format change)",
                    field,
                    empty,
                    total,
                )

    def _build_params(self, keyword: str, criteria: SearchCriteria) -> dict:
        """Build the Adzuna query params from the criteria. Kept separate from the
        HTTP call so the query shape is unit-testable without a network round-trip.

        Uses a broad `what` keyword (not strict `title_only`) so the fetch stays
        generous — honest fit is the scorer's job (M4), not the source's.
        """
        params: dict = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "results_per_page": criteria.results_per_page,
            "max_days_old": criteria.max_days_old,
            "content-type": "application/json",
        }
        if keyword:
            params["what"] = keyword  # broad keyword match, not title-only
        where, distance = _location_params(criteria)
        if where:
            params["where"] = where
            params["distance"] = distance
        return params

    def _get_page(
        self, client: httpx.Client, keyword: str, criteria: SearchCriteria, page: int
    ) -> tuple[list[dict], int | None]:
        params = self._build_params(keyword, criteria)
        # Log the exact query we built from the profile (never the credentials).
        logger.info(
            "adzuna query: page=%s what=%r where=%r distance=%r"
            " max_days_old=%s (remote_pref=%r location=%r)",
            page,
            params.get("what"),
            params.get("where"),
            params.get("distance"),
            params.get("max_days_old"),
            criteria.remote_pref,
            criteria.location,
        )

        try:
            response = client.get(f"{_BASE_URL}/{page}", params=params)
        except httpx.HTTPError as exc:
            raise JobSourceError(f"Adzuna request failed: {exc}") from exc

        if response.status_code == 410:
            raise JobSourceError(
                "Adzuna returned 410 (authentication failed — check ADZUNA_APP_ID / ADZUNA_APP_KEY)."
            )
        if response.status_code != 200:
            raise JobSourceError(
                f"Adzuna returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            envelope = AdzunaEnvelope.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise JobSourceError(
                f"Adzuna response not in the expected shape (missing 'results' list?): {exc}"
            ) from exc
        return envelope.results, envelope.count

    def _normalize(self, job: AdzunaJob) -> NormalizedJob:
        location_display = job.location.display_name if job.location else None
        haystack = f"{job.title or ''} {job.description or ''} {location_display or ''}".lower()
        remote = any(hint in haystack for hint in _REMOTE_HINTS)
        return NormalizedJob(
            source=self.name,
            external_id=job.id,
            source_url=job.redirect_url,
            title=job.title,
            company=job.company.display_name if job.company else None,
            location_display=location_display,
            location_area=job.location.area if job.location else [],
            remote=remote,
            description=job.description,
            category=job.category.label if job.category else None,
            category_tag=job.category.tag if job.category else None,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_is_predicted=_salary_predicted(job.salary_is_predicted),
            contract_time=job.contract_time,
            contract_type=job.contract_type,
            posted_at=_parse_created(job.created, job.id),
        )
