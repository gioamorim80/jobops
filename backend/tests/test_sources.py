"""Adzuna adapter tests — strict validation, normalization, creds guard.

No network: we validate the documented shapes and the normalize mapping, and
confirm a missing-credentials fetch fails loudly rather than calling out.
"""

import pytest
from app.config import settings
from app.sources.adzuna import AdzunaJob, AdzunaSource
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


def test_fetch_without_credentials_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "adzuna_app_id", None)
    monkeypatch.setattr(settings, "adzuna_app_key", None)
    with pytest.raises(JobSourceError, match="credentials missing"):
        AdzunaSource().fetch(SearchCriteria(keywords=["engineer"]))
