"""JobSource interface + shared shapes for the per-user job-source ingestion.

A source takes search criteria built from one user's profile (target roles,
location, remote preference) and returns normalized jobs that map onto the shared
`jobs` table. Adding a source is registering one more JobSource — no change
elsewhere. No LLM is involved anywhere in this layer.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class JobSourceError(Exception):
    """A source failed for this run (auth failure, format change, timeout, or the
    upstream being down). Caught per-source by the orchestrator: logged and the
    source is skipped for the run, never crashing the whole fetch."""


class SearchCriteria(BaseModel):
    """What to search for, built from a single user's profile."""

    keywords: list[str] = Field(default_factory=list)  # target roles
    location: str | None = None
    remote: bool = False
    max_days_old: int = 30
    max_pages: int = 2  # bounded pages per keyword, to stay polite
    results_per_page: int = 50


class NormalizedJob(BaseModel):
    """One posting in the shared `jobs` table's shape (minus content_hash, which
    dedupe computes, and fetched_at, which the DB/upsert sets)."""

    source: str
    external_id: str | None = None
    source_url: str  # required — we must be able to link back to the advertiser
    title: str | None = None
    company: str | None = None
    location_display: str | None = None
    location_area: list[str] = Field(default_factory=list)
    remote: bool | None = None
    description: str | None = None
    category: str | None = None
    category_tag: str | None = None  # stable slug, e.g. "it-jobs"
    salary_min: float | None = None
    salary_max: float | None = None
    salary_is_predicted: bool | None = None  # True = Adzuna estimate, not advertised
    contract_time: str | None = None  # full_time / part_time
    contract_type: str | None = None  # permanent / contract
    posted_at: str | None = None  # ISO 8601 timestamp (validated; None if unparseable)


class FetchResult(BaseModel):
    """Jobs plus counters so the orchestrator can spot a format regression
    (zero results when some were expected, or a high parse-failure rate)."""

    jobs: list[NormalizedJob] = Field(default_factory=list)
    raw_count: int = 0  # raw items seen across pages
    parse_failures: int = 0  # items that failed strict validation and were skipped


class JobSource(ABC):
    name: str

    @abstractmethod
    def fetch(self, criteria: SearchCriteria) -> FetchResult:
        """Fetch + normalize for these criteria. Raises JobSourceError on a source
        failure; never returns silently-garbage data."""
        raise NotImplementedError
