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
    jobs = [_job(title=f"Unrelated role {i}", description="nothing matching") for i in range(5)]
    ranked = prefilter(_PROFILE, jobs, cap=30)
    assert len(ranked) == 5
    assert all("prefilter_score" in job for job in ranked)


def test_empty_jobs_returns_empty() -> None:
    assert prefilter(_PROFILE, []) == []


def test_shortlist_collapses_same_id_dupes_but_keeps_distinct_postings() -> None:
    """The reported leak: the same posting appears several times in the fetched
    list (one ad id returned by multiple keyword queries/pages, under different
    tracking-param or URL-form links). Those collapse on external_id. But the same
    role title at the same company in DIFFERENT cities (EY EDGE) is four distinct
    ad ids — genuinely distinct postings that must all survive."""
    jobs = [
        # Justworks: one ad id seen twice (two keyword queries returned it).
        _job(
            source="adzuna", external_id="JW1", title="Senior Data Scientist", company="Justworks"
        ),
        _job(
            source="adzuna", external_id="JW1", title="Senior Data Scientist", company="Justworks"
        ),
        # Lyft: one ad id under three tracking-param / URL-form links.
        _job(
            source="adzuna",
            external_id="LY1",
            title="Senior Data Scientist, Causal Inference",
            company="Lyft",
            source_url="https://www.adzuna.com/land/ad/LY1?se=a",
        ),
        _job(
            source="adzuna",
            external_id="LY1",
            title="Senior Data Scientist, Causal Inference",
            company="Lyft",
            source_url="https://www.adzuna.com/details/LY1?se=b",
        ),
        _job(
            source="adzuna",
            external_id="LY1",
            title="Senior Data Scientist, Causal Inference",
            company="Lyft",
            source_url="https://www.adzuna.com/details/LY1?se=c",
        ),
        # EY EDGE: same title + company, four distinct ad ids in four cities.
        _job(
            source="adzuna",
            external_id="EY1",
            title="EY EDGE Data Scientist",
            company="EY",
            location_display="Stamford, CT",
        ),
        _job(
            source="adzuna",
            external_id="EY2",
            title="EY EDGE Data Scientist",
            company="EY",
            location_display="Iselin, NJ",
        ),
        _job(
            source="adzuna",
            external_id="EY3",
            title="EY EDGE Data Scientist",
            company="EY",
            location_display="Hoboken, NJ",
        ),
        _job(
            source="adzuna",
            external_id="EY4",
            title="EY EDGE Data Scientist",
            company="EY",
            location_display="Grand Central, New York",
        ),
    ]
    ranked = prefilter(_PROFILE, jobs)
    ids = sorted(j["external_id"] for j in ranked)
    assert ids == ["EY1", "EY2", "EY3", "EY4", "JW1", "LY1"]  # dupes collapsed, EY rows kept
    assert len(ranked) == len(set(ids))  # no repeated ad id in the shortlist


def test_collapses_same_opening_under_different_external_ids() -> None:
    # Bug 5: one real opening Adzuna listed under two ad ids -> same normalized
    # title+company+location -> collapse to ONE, keeping the best-ranked instance.
    # The strong row (keyword/remote match) outranks the weak one, so it's kept.
    strong = _job(
        source="adzuna",
        external_id="A1",
        title="Senior Backend Engineer",
        company="Acme",
        location_display="New York, NY",
        description="Python, FastAPI, PostgreSQL. Fully remote.",
        remote=True,
    )
    weak = _job(
        source="adzuna",
        external_id="A2",
        title="Senior Backend Engineer",
        company="Acme",
        location_display="New York, NY",
        description="(no keywords here)",
    )
    ranked = prefilter(_PROFILE, [weak, strong])
    assert len(ranked) == 1
    assert ranked[0]["external_id"] == "A1"  # best-ranked representative kept


def test_same_title_company_different_location_both_survive() -> None:
    # GUARDRAIL (NYC/Austin): same role + company in two cities are DISTINCT
    # openings — different normalized locations -> different keys -> both kept.
    nyc = _job(
        source="adzuna",
        external_id="N1",
        title="Data Scientist",
        company="Acme",
        location_display="New York, NY",
    )
    austin = _job(
        source="adzuna",
        external_id="X1",
        title="Data Scientist",
        company="Acme",
        location_display="Austin, TX",
    )
    ranked = prefilter(_PROFILE, [nyc, austin])
    assert sorted(j["external_id"] for j in ranked) == ["N1", "X1"]


def test_opening_key_normalizes_case_and_whitespace() -> None:
    # Keys differing only by case / internal whitespace collapse.
    a = _job(
        source="adzuna",
        external_id="W1",
        title="Data Scientist  ",
        company="Acme",
        location_display="New York, NY",
    )
    b = _job(
        source="adzuna",
        external_id="W2",
        title="data scientist",
        company="ACME",
        location_display="new york,  ny",
    )
    ranked = prefilter(_PROFILE, [a, b])
    assert len(ranked) == 1


def test_empty_location_rows_not_collapsed() -> None:
    # Conservative: same title+company but EMPTY location -> NOT collapsed (an
    # empty discriminating field can't safely merge distinct openings).
    a = _job(source="adzuna", external_id="E1", title="Data Scientist", company="Acme")
    b = _job(source="adzuna", external_id="E2", title="Data Scientist", company="Acme")
    ranked = prefilter(_PROFILE, [a, b])
    assert sorted(j["external_id"] for j in ranked) == ["E1", "E2"]


def test_dedupe_then_cap_counts_unique_jobs() -> None:
    # 40 unique ad ids each fetched twice: the cap returns 30 UNIQUE postings, not
    # 30 rows half of which repeat.
    jobs = []
    for i in range(40):
        for _ in range(2):
            jobs.append(
                _job(
                    source="adzuna",
                    external_id=f"J{i}",
                    title=f"Backend Engineer {i}",
                    description="Python",
                )
            )
    ranked = prefilter(_PROFILE, jobs, cap=30)
    assert len(ranked) == 30
    ids = [j["external_id"] for j in ranked]
    assert len(ids) == len(set(ids))  # all unique
