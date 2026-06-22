"""Adzuna adapter tests — strict validation, normalization, creds guard.

No network: we validate the documented shapes and the normalize mapping, and
confirm a missing-credentials fetch fails loudly rather than calling out.
"""

import pytest
from app.config import settings
from app.sources.adzuna import (
    _DISTANCE_KM,
    AdzunaJob,
    AdzunaSource,
    _location_params,
    _normalize_location,
)
from app.sources.base import JobSourceError, SearchCriteria
from pydantic import ValidationError

_VALID = {
    "id": "999",
    "redirect_url": "https://www.adzuna.com/land/ad/999",
    "title": "Senior Backend Engineer",
    "company": {"display_name": "Acme"},
    "location": {
        "display_name": "San Francisco, CA",
        "area": ["US", "California", "San Francisco"],
    },
    "description": "Python and FastAPI. Remote friendly.",
    "category": {"label": "IT Jobs", "tag": "it-jobs"},
    "salary_min": 150000,
    "salary_max": 200000,
    "salary_is_predicted": "1",
    "contract_time": "full_time",
    "contract_type": "permanent",
    "created": "2026-06-20T12:00:00Z",
}


def test_valid_job_parses() -> None:
    job = AdzunaJob.model_validate(_VALID)
    assert job.id == "999"
    assert job.redirect_url.endswith("/999")


def test_missing_required_field_raises() -> None:
    broken = {k: v for k, v in _VALID.items() if k != "redirect_url"}
    with pytest.raises(ValidationError):
        AdzunaJob.model_validate(broken)


def test_normalize_maps_redirect_url_to_source_url_and_detects_remote() -> None:
    normalized = AdzunaSource()._normalize(AdzunaJob.model_validate(_VALID))
    assert normalized.source == "adzuna"
    assert normalized.external_id == "999"
    assert normalized.source_url == _VALID["redirect_url"]  # ToS attribution link
    assert normalized.company == "Acme"
    assert normalized.location_area == ["US", "California", "San Francisco"]
    assert normalized.remote is True  # "remote" appears in the description
    assert normalized.category == "IT Jobs"
    assert normalized.category_tag == "it-jobs"  # stable slug kept alongside label
    assert normalized.salary_is_predicted is True  # Adzuna "1" -> True
    assert normalized.contract_time == "full_time"
    assert normalized.contract_type == "permanent"
    assert normalized.posted_at is not None  # created parsed to a real timestamp


def test_salary_predicted_zero_maps_false() -> None:
    raw = {**_VALID, "salary_is_predicted": "0"}
    assert AdzunaSource()._normalize(AdzunaJob.model_validate(raw)).salary_is_predicted is False


def test_unparseable_created_becomes_null_not_a_crash() -> None:
    raw = {**_VALID, "created": "not-a-date"}
    normalized = AdzunaSource()._normalize(AdzunaJob.model_validate(raw))
    # One bad date must not break the row (or the batch); it just stores null.
    assert normalized.posted_at is None


def test_fetch_without_credentials_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "adzuna_app_id", None)
    monkeypatch.setattr(settings, "adzuna_app_key", None)
    with pytest.raises(JobSourceError, match="credentials missing"):
        AdzunaSource().fetch(SearchCriteria(keywords=["engineer"]))


# --------- location normalization (the geocodable-`where` fix) ---------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("NYC Metro Area", "New York"),  # the bug that returned 0 jobs
        ("NYC", "New York"),
        ("New York Metro", "New York"),
        ("SF Bay Area", "San Francisco"),
        ("Bay Area", "San Francisco"),
        ("Greater Boston", "Boston"),  # stripped via the "greater " prefix + alias
        ("Austin", "Austin"),  # plain city passes through
        ("Austin, TX", "Austin Tx"),  # punctuation collapsed, still a place name
        ("Seattle Metro Area", "Seattle"),  # generic suffix strip, not a hard-coded alias
        ("remote", None),  # not a place; handled via remote_pref
        ("United States", None),  # too broad to geocode
        ("", None),
        (None, None),
        ("12345", None),  # not a confident place name -> omit `where`
    ],
)
def test_normalize_location(raw: str | None, expected: str | None) -> None:
    assert _normalize_location(raw) == expected


def test_location_params_flexible_uses_city_centre_plus_radius() -> None:
    # "flexible" must NOT exclude remote: we pin the city centre + radius, and
    # Adzuna (no remote filter) returns both remote- and onsite-tagged jobs.
    where, distance = _location_params(
        SearchCriteria(keywords=["x"], location="NYC Metro Area", remote_pref="flexible")
    )
    assert where == "New York"
    assert distance == _DISTANCE_KM


def test_location_params_onsite_uses_city_centre() -> None:
    where, distance = _location_params(
        SearchCriteria(keywords=["x"], location="Greater Boston", remote_pref="on-site")
    )
    assert where == "Boston"
    assert distance == _DISTANCE_KM


def test_location_params_remote_pref_searches_nationwide() -> None:
    # A remote preference ignores the location and searches without a `where`.
    where, distance = _location_params(
        SearchCriteria(keywords=["x"], location="NYC Metro Area", remote_pref="remote")
    )
    assert where is None
    assert distance is None


def test_location_params_ungeocodable_omits_where() -> None:
    where, distance = _location_params(
        SearchCriteria(keywords=["x"], location="Somewhere Vague 999", remote_pref="flexible")
    )
    assert where is None
    assert distance is None


def test_build_params_is_generous_keyword_not_title_only() -> None:
    criteria = SearchCriteria(keywords=["Data Scientist"], location="NYC Metro Area")
    params = AdzunaSource()._build_params("Data Scientist", criteria)
    assert params["what"] == "Data Scientist"  # broad match
    assert "title_only" not in params  # never the strict title filter
    assert params["where"] == "New York"
    assert params["distance"] == _DISTANCE_KM
