# JOB_SOURCES — federation, funnel, and ToS guardrails

## Principle
"Scan all sources" = federate several LEGITIMATE sources behind one swappable
interface and dedupe — never scrape walled gardens. Coverage grows by adding
adapters, not by violating anyone's terms.

## Allowlist (start with 2–3 in M3, add over time)
- **Remote/tech APIs:** Remotive, RemoteOK, Arbeitnow, Himalayas.
- **Aggregators (free tiers / keys):** Adzuna, Jooble, Careerjet.
- **Public ATS boards (clean JSON, per-company):** Greenhouse, Lever, Ashby.
  These are the underrated goldmine — high quality, ToS-clean.
- **Government:** USAJobs.

## Forbidden
LinkedIn, Indeed, Glassdoor scraping — against ToS, fragile, and a liability on a
shared product. Do not build adapters for them. (User-pasted *links* in the
on-demand flow are a single user-initiated fetch with a paste fallback — different
posture, allowed; still expect some links to be unfetchable.)

## Adapter interface (Python, as built in M3)
```python
class JobSource(ABC):
    name: str
    @abstractmethod
    def fetch(self, criteria: SearchCriteria) -> FetchResult: ...  # normalized jobs
```
`SearchCriteria` is built from one user's profile (target roles, location, remote
preference, max days old). `FetchResult` carries the normalized jobs plus counters
(raw items seen, parse failures) so the orchestrator can spot a format regression.
Each source is registered in a small registry (`SOURCES` in `app/admin.py`), so
enabling or disabling a source is a one-line change, not a change scattered
through the codebase.

## Dedupe
Compute `content_hash` per job: prefer `source` + the source's own job id, and
fall back to a hash of title + company + location when no id is present. The
`jobs.content_hash` column is unique, and writes upsert on it, so the same posting
fetched twice is one row. A re-fetch updates `fetched_at` and never inserts a
duplicate.

## Two-stage funnel (cost-critical)
1. **Prefilter (cheap, no LLM):** match job metadata against the profile —
   required skills/keywords overlap, role/seniority match, location/remote fit,
   comp floor if present. Rank; keep top K (e.g. 15) per user per cycle.
2. **LLM score (expensive):** run the Scorer only on the shortlist.
Never send the full pool to the LLM. This is the difference between a hobby bill
and a runaway one.

## On-demand fetch (M2)
Fetch the user's URL once; extract main content (readability-style). If blocked,
empty, or JS-only, return a clear "couldn't read that link — paste the text"
message and accept pasted text. Never retry-hammer a host.

## Per-user ingestion (M3)
We do not run a wide daily sweep of all US jobs. We fetch PER USER, using each
user's own profile keywords, because that is far more API-efficient at our scale
and pulls only relevant postings. The approach is field-agnostic overall (each
user brings their own keywords, whether data science, packaging design, or
copywriting) and targeted per fetch. Results land in the SHARED `jobs` pool with
dedupe, so when two users match the same posting it is stored once.

### Adzuna (first M3 source)
- Adzuna API only. No scraping. Credentials (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`)
  come from the environment and are never hardcoded.
- Country is US (`/v1/api/jobs/us/search`).
- The query is built from the user's profile: target roles go to `title_only`,
  location goes to `where` (unless the user prefers remote, in which case we do
  not pin to a city), and `max_days_old` bounds recency.
- ToS attribution is mandatory: Adzuna requires linking the user back to the
  advertiser, so we store `redirect_url` as `source_url`, and it is required.
  Adzuna truncates the description to about 500 characters; we store it as is.
- Polite and bounded: a modest `results_per_page` (50), a small number of pages
  per keyword query (default 2), and a short delay between page calls. We never
  hammer the API.

### Validation and graceful failure
- Every Adzuna response is parsed through strict Pydantic models. If a required
  field is missing or the structure changed, we fail loudly to the operator: log
  a specific error naming what did not match and skip that item rather than store
  garbage.
- Sanity checks log a WARNING when a fetch returns zero results where some were
  expected, or when the parse-failure rate is high. Either can signal that the
  upstream endpoint or format changed.
- Each source runs inside its own try/except. A source failure (auth 410, a
  non-200, a timeout, the upstream being down) is logged and that source is
  skipped for the run. It never returns a 500 or kills the whole fetch, and no
  exception is swallowed silently.
