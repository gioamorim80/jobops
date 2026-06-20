"""Enrich-coach tests — auth gate + the pure merge helper (no network)."""

from app.enrich import merge_changes
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_chat_requires_auth() -> None:
    response = client.post(
        "/enrich/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 401


def test_apply_requires_auth() -> None:
    response = client.post(
        "/enrich/apply",
        json={"changes": {"add_skills": ["Kubernetes"]}},
    )
    assert response.status_code == 401


def test_merge_changes_appends_dedupes_and_preserves() -> None:
    parsed = {
        "skills": ["Python"],
        "domains": ["fintech"],
        "attribution_notes": [],
        "comp_floor": "150k",  # unrelated field must be preserved
        "seniority": "mid",
    }
    changes = {
        "add_skills": ["Kubernetes", "python"],  # 'python' is a dup (case-insensitive)
        "add_domains": [],
        "add_target_roles": ["Staff Engineer"],
        "add_attribution_notes": ["Payments rewrite was led by a teammate."],
        "set_seniority": "senior",
        "set_remote_pref": "",
    }
    result = merge_changes(parsed, changes)

    assert result["skills"] == ["Python", "Kubernetes"]
    assert result["target_roles"] == ["Staff Engineer"]
    assert result["attribution_notes"] == ["Payments rewrite was led by a teammate."]
    assert result["seniority"] == "senior"  # set (non-empty)
    assert "remote_pref" not in result or result.get("remote_pref") in (None, "")
    assert result["comp_floor"] == "150k"  # preserved
    # input not mutated
    assert parsed["skills"] == ["Python"]
