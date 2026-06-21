"""Prefilter tests — deterministic ranking, generous cap, no LLM, no network."""

from datetime import UTC, datetime

from app.prefilter import prefilter

_PROFILE = {
    "target_roles": ["Senior Backend Engineer"],
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "locations": ["Lisbon"],
    "remote_pref": "remote",
}


def _job(**kwargs) -> dict:
    base = {
        "title": "",
        "description": "",
        "category": "",
        "location_display": "",
        "location_area": [],
        "remote": False,
        "posted_at": datetime.now(UTC).isoformat(),
        "source_url": "https://example.com/job",
    }
    base.update(kwargs)
    return base


def test_keyword_and_remote_signals_rank_higher() -> None:
    strong = _job(
        title="Senior Backend Engineer",
        description="Python, FastAPI, PostgreSQL. Fully remote.",
        remote=True,
    )
    weak = _job(title="Warehouse Associate", description="Forklift experience.")
    ranked = prefilter(_PROFILE, [weak, strong])
    assert ranked[0]["title"] == "Senior Backend Engineer"
    assert ranked[0]["prefilter_score"] > ranked[1]["prefilter_score"]


def test_caps_to_requested_size() -> None:
    jobs = [_job(title=f"Backend Engineer {i}", description="Python") for i in range(50)]
    ranked = prefilter(_PROFILE, jobs, cap=30)
    assert len(ranked) == 30


def test_generous_returns_all_when_under_cap() -> None:
    # Even low-signal jobs are passed through (generous): the prefilter narrows by
    # cap, it does not judge true fit.
    jobs = [_job(title="Unrelated role", description="nothing matching") for _ in range(5)]
    ranked = prefilter(_PROFILE, jobs, cap=30)
    assert len(ranked) == 5
    assert all("prefilter_score" in job for job in ranked)


def test_empty_jobs_returns_empty() -> None:
    assert prefilter(_PROFILE, []) == []
