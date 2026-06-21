"""Adzuna job-source adapter (US), queried per-user from a profile.

ToS: Adzuna requires linking users back to the advertiser, so we store
`redirect_url` as `source_url` (required) and never scrape. Credentials come from
the environment. Fetches are bounded and polite. Responses are validated through
strict Pydantic models: a structural change fails loudly to the operator (logged,
source skipped) rather than silently storing garbage.
"""

import time

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
_REMOTE_HINTS = ("remote", "work from home", "wfh", "work-from-home")


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
    created: str | None = None  # ISO posted time


class AdzunaEnvelope(BaseModel):
    results: list[dict]
    count: int | None = None


def _missing(exc: ValidationError) -> str:
    return ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())


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
        return result

    def _get_page(
        self, client: httpx.Client, keyword: str, criteria: SearchCriteria, page: int
    ) -> tuple[list[dict], int | None]:
        params: dict = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "results_per_page": criteria.results_per_page,
            "max_days_old": criteria.max_days_old,
            "content-type": "application/json",
        }
        if keyword:
            params["title_only"] = keyword  # role must appear in the title
        # Respect remote preference: when the user wants remote, don't pin to a
        # city; otherwise narrow to their location if they gave one.
        if criteria.location and not criteria.remote:
            params["where"] = criteria.location

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
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            posted_at=job.created,
        )
