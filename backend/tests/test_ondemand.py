"""On-demand score/tailor tests — auth gate + the pure readability extractor.

The full score→tailor happy path needs Supabase + Anthropic and is covered by
the manual end-to-end test in the M2 docs.
"""

import pytest
from app.jobfetch import extract_main_text
from app.main import app
from app.ondemand import _applied_at_iso, _clean_label, _normalize_score
from fastapi import HTTPException
from fastapi.testclient import TestClient

client = TestClient(app)


def test_score_requires_auth() -> None:
    response = client.post("/ondemand/score", json={"text": "Some job posting"})
    assert response.status_code == 401


def test_tailor_requires_auth() -> None:
    response = client.post(
        "/ondemand/tailor",
        json={"id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


def test_approve_requires_auth() -> None:
    response = client.post(
        "/ondemand/approve",
        json={"id": "00000000-0000-0000-0000-000000000000", "tailored_bullets": []},
    )
    assert response.status_code == 401


def test_applied_requires_auth() -> None:
    response = client.post(
        "/ondemand/applied",
        json={"id": "00000000-0000-0000-0000-000000000000", "applied": True},
    )
    assert response.status_code == 401


def test_applied_at_iso_uses_chosen_day_at_noon_utc() -> None:
    # A user-chosen day is stored at noon UTC so it reads as the same calendar
    # date in any timezone.
    assert _applied_at_iso(True, "2026-06-20") == "2026-06-20T12:00:00+00:00"


def test_applied_at_iso_defaults_to_today_when_no_date() -> None:
    iso = _applied_at_iso(True, None)
    assert iso is not None and iso.endswith("T12:00:00+00:00")


def test_applied_at_iso_unmark_is_none() -> None:
    assert _applied_at_iso(False, "2026-06-20") is None


def test_applied_at_iso_rejects_bad_date() -> None:
    with pytest.raises(HTTPException) as exc:
        _applied_at_iso(True, "not-a-date")
    assert exc.value.status_code == 422


def test_clean_label_trims_collapses_and_caps() -> None:
    assert _clean_label("  Senior  Data\nScientist ") == "Senior Data Scientist"
    assert _clean_label(None) == ""  # nothing extracted -> empty, never fabricated
    assert _clean_label("") == ""
    assert len(_clean_label("x" * 500)) == 140  # capped


def test_normalize_score_preserves_valid_decision() -> None:
    # decision is the model's holistic call, carried through verbatim (not derived
    # from the fit number).
    assert _normalize_score({"fit": 72, "decision": "apply"})["decision"] == "APPLY"
    assert _normalize_score({"fit": 72, "decision": "STRETCH"})["decision"] == "STRETCH"


def test_normalize_score_invalid_decision_defaults_and_logs(caplog) -> None:
    # A missing/garbled decision falls back to STRETCH but is surfaced (logged),
    # never silently swallowed.
    with caplog.at_level("WARNING"):
        result = _normalize_score({"fit": 72, "decision": "MAYBE"})
    assert result["decision"] == "STRETCH"
    assert any("invalid decision" in r.message for r in caplog.records)


def test_extract_main_text_pulls_article_body() -> None:
    html = """
    <html><head><title>Senior Engineer</title></head>
    <body>
      <nav>home about careers</nav>
      <article>
        <h1>Senior Backend Engineer</h1>
        <p>We are hiring a senior backend engineer to build scalable payment
        systems in Python and FastAPI. You will own services end to end and
        mentor other engineers across the platform team.</p>
      </article>
      <footer>copyright</footer>
    </body></html>
    """
    text = extract_main_text(html)
    assert "senior backend engineer" in text.lower()
    assert "FastAPI" in text


def test_extract_main_text_handles_empty_html() -> None:
    assert extract_main_text("") == ""
