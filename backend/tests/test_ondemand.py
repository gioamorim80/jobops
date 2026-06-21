"""On-demand score/tailor tests — auth gate + the pure readability extractor.

The full score→tailor happy path needs Supabase + Anthropic and is covered by
the manual end-to-end test in the M2 docs.
"""

from app.jobfetch import extract_main_text
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_score_requires_auth() -> None:
    response = client.post("/ondemand/score", json={"text": "Some job posting"})
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
