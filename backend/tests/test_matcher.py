"""Matcher tests — band thresholds + Haiku model choice (no network)."""

from app.matcher import MATCH_MODEL, score_band


def test_score_band_thresholds_match_frontend() -> None:
    # Mirrors lib/ui.ts fitBand so automated matches read like on-demand scores.
    assert score_band(80) == "Strong fit"
    assert score_band(90) == "Strong fit"
    assert score_band(65) == "Solid fit"
    assert score_band(79) == "Solid fit"
    # 50–64 band is "Moderate fit", NOT "Stretch" — that word is reserved for the
    # separate STRETCH decision label (avoids the vocabulary collision).
    assert score_band(50) == "Moderate fit"
    assert score_band(64) == "Moderate fit"
    assert "Stretch" not in {score_band(s) for s in range(0, 101)}
    assert score_band(49) == "Likely skip"
    assert score_band(0) == "Likely skip"


def test_matcher_uses_haiku_not_sonnet() -> None:
    # Automated scoring is the cheap step; Sonnet stays reserved for tailoring.
    assert MATCH_MODEL == "claude-haiku-4-5"
