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


def test_same_id_different_tracking_url_is_one_identity() -> None:
    # The same Adzuna ad id served under different tracking-param / URL-form
    # redirect links is ONE posting: content_hash keys on source + external_id, so
    # the differing source_url does not matter.
    a = {
        "source": "adzuna",
        "external_id": "LY1",
        "title": "Senior Data Scientist, Causal Inference",
        "company": "Lyft",
        "source_url": "https://www.adzuna.com/land/ad/LY1?se=a",
    }
    b = {
        "source": "adzuna",
        "external_id": "LY1",
        "title": "Senior Data Scientist, Causal Inference",
        "company": "Lyft",
        "source_url": "https://www.adzuna.com/details/LY1?se=b",  # different URL form + param
    }
    assert content_hash(a) == content_hash(b)


def test_same_title_company_different_id_are_distinct() -> None:
    # Same role title + company but DIFFERENT Adzuna ad ids (e.g. the EY EDGE Data
    # Scientist role posted in four different cities) are genuinely distinct
    # postings and must NOT collapse.
    base = {"source": "adzuna", "title": "EY EDGE Data Scientist", "company": "EY"}
    stamford = {**base, "external_id": "EY1", "location_display": "Stamford, CT"}
    iselin = {**base, "external_id": "EY2", "location_display": "Iselin, NJ"}
    assert content_hash(stamford) != content_hash(iselin)


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
