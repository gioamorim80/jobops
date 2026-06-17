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

## Adapter interface (Python)
```python
class JobSourceAdapter(ABC):
    name: str
    @abstractmethod
    def fetch(self, since: datetime, query: ProfileQuery) -> list[RawJob]: ...
    @abstractmethod
    def normalize(self, raw: RawJob) -> Job: ...   # -> jobs table shape
```
Each adapter is registered in a registry; enabling/disabling a source is a config
flag, not a code change elsewhere.

## Dedupe
Compute `content_hash` from normalized (company + title + location + first N chars
of description). Upsert on (`source`,`source_job_id`); collapse cross-source
duplicates by `content_hash`.

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
