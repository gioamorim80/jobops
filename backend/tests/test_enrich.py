"""Enrich-coach tests — auth gate, merge helper, and lenient reply parsing."""

from app.enrich import _parse_coach_reply, merge_changes
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


def test_parse_coach_reply_handles_plain_prose() -> None:
    # This is the bug: as a conversation grows the model replies in prose without
    # the JSON envelope. It must NOT raise (no more 502) — the prose becomes the
    # reply, with no proposal.
    reply, proposal = _parse_coach_reply(
        "That's a great example to lead with. What was the impact on the team?"
    )
    assert reply.startswith("That's a great example")
    assert proposal is None


def test_parse_coach_reply_parses_json_envelope_with_proposal() -> None:
    raw = (
        '{"reply": "Got it, adding that.", "proposal": {"summary": "Add Rust", '
        '"changes": {"add_skills": ["Rust"]}}}'
    )
    reply, proposal = _parse_coach_reply(raw)
    assert reply == "Got it, adding that."
    assert proposal is not None
    assert proposal["changes"]["add_skills"] == ["Rust"]


def test_parse_coach_reply_json_envelope_without_proposal() -> None:
    reply, proposal = _parse_coach_reply('{"reply": "Tell me more.", "proposal": null}')
    assert reply == "Tell me more."
    assert proposal is None


def test_parse_coach_reply_empty_falls_back() -> None:
    reply, proposal = _parse_coach_reply("")
    assert reply == "Tell me a little more?"
    assert proposal is None
