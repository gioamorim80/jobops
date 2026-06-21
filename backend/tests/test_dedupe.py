"""Dedupe tests — stable content_hash and batch collapsing (no network)."""

from app.dedupe import content_hash, dedupe_batch


def test_hash_prefers_source_and_external_id() -> None:
    a = {"source": "adzuna", "external_id": "123", "title": "X"}
    b = {"source": "adzuna", "external_id": "123", "title": "different title"}
    # Same source + external_id => same identity regardless of other fields.
    assert content_hash(a) == content_hash(b)


def test_hash_falls_back_to_title_company_location() -> None:
    a = {"source": "x", "title": "Engineer", "company": "Acme", "location_display": "SF"}
    b = {"source": "x", "title": "engineer", "company": "ACME", "location_display": "sf"}
    # No external_id => hash of title+company+location, case-insensitive.
    assert content_hash(a) == content_hash(b)
    c = {"source": "x", "title": "Engineer", "company": "Other", "location_display": "SF"}
    assert content_hash(a) != content_hash(c)


def test_dedupe_batch_collapses_and_stamps() -> None:
    jobs = [
        {"source": "adzuna", "external_id": "1", "title": "A", "source_url": "u1"},
        {"source": "adzuna", "external_id": "1", "title": "A again", "source_url": "u1"},
        {"source": "adzuna", "external_id": "2", "title": "B", "source_url": "u2"},
    ]
    deduped = dedupe_batch(jobs)
    assert len(deduped) == 2  # the two id="1" rows collapse to one
    for row in deduped:
        assert "content_hash" in row
        assert "fetched_at" in row
