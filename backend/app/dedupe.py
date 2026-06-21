"""Dedupe for the shared jobs pool.

content_hash gives each posting a stable identity: prefer source + external_id;
fall back to title + company + location when there's no external id. Upserting on
content_hash means the same posting fetched twice is one row — a re-fetch updates
fetched_at, never inserts a duplicate.
"""

import hashlib
from datetime import UTC, datetime
from typing import Any


def content_hash(job: dict) -> str:
    source = (job.get("source") or "").strip().lower()
    external_id = (job.get("external_id") or "").strip()
    if external_id:
        basis = f"{source}:{external_id}"
    else:
        title = (job.get("title") or "").strip().lower()
        company = (job.get("company") or "").strip().lower()
        location = (job.get("location_display") or "").strip().lower()
        basis = f"{title}|{company}|{location}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def dedupe_batch(jobs: list[dict]) -> list[dict]:
    """Collapse duplicates within one batch (so a single upsert has unique keys)
    and stamp each with its content_hash and fetched_at."""
    now = datetime.now(UTC).isoformat()
    unique: dict[str, dict] = {}
    for job in jobs:
        digest = content_hash(job)
        unique[digest] = {**job, "content_hash": digest, "fetched_at": now}
    return list(unique.values())


def upsert_jobs(client: Any, jobs: list[dict]) -> int:
    """Upsert jobs into the shared pool on content_hash. Returns the number of
    unique postings written (inserted or refreshed). Service-role client only."""
    deduped = dedupe_batch(jobs)
    if not deduped:
        return 0
    client.table("jobs").upsert(deduped, on_conflict="content_hash").execute()
    return len(deduped)
