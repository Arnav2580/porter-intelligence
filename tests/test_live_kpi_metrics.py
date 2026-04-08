"""Reviewed-case KPI helpers."""

from api.routes.live_kpi import _safe_ratio, get_review_confidence


def test_safe_ratio_handles_zero_denominator():
    assert _safe_ratio(0, 0) == 0.0
    assert _safe_ratio(3, 0) == 0.0


def test_safe_ratio_computes_fraction():
    assert _safe_ratio(3, 4) == 0.75


def test_review_confidence_awaiting_reviews():
    result = get_review_confidence(0)
    assert result["status"] == "awaiting_reviews"
    assert "No analyst-reviewed cases" in result["note"]


def test_review_confidence_early_signal():
    result = get_review_confidence(6)
    assert result["status"] == "early_signal"
    assert result["label"] == "Early Signal"


def test_review_confidence_growing_sample():
    result = get_review_confidence(18)
    assert result["status"] == "growing_sample"


def test_review_confidence_decision_support():
    result = get_review_confidence(32)
    assert result["status"] == "decision_support"
    assert result["label"] == "Decision Support Ready"
