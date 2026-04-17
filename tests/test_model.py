"""Model integrity tests. Run without live services."""

import json

from generator.config import DATA_RAW, MODEL_WEIGHTS


def test_evaluation_report_exists():
    assert (DATA_RAW / "evaluation_report.json").exists()


def test_kpi_math_consistent():
    with open(DATA_RAW / "evaluation_report.json") as f:
        report = json.load(f)
    xgb = report["xgboost"]
    computed = xgb["net_recoverable_inr"] / xgb["total_trips"]
    assert abs(computed - xgb["net_recoverable_per_trip"]) < 0.10, (
        f"KPI mismatch: {computed} vs {xgb['net_recoverable_per_trip']}"
    )


def test_pilot_criteria_pass():
    with open(DATA_RAW / "evaluation_report.json") as f:
        report = json.load(f)
    pilot_pass = report["xgboost"]["pilot_pass"]
    assert all(pilot_pass.values()), f"Failing: {pilot_pass}"


def test_model_weights_present():
    for fname in [
        "xgb_fraud_model.json",
        "threshold.json",
        "feature_names.json",
        "two_stage_config.json",
    ]:
        assert (MODEL_WEIGHTS / fname).exists(), f"Missing: {fname}"


def test_two_stage_config():
    with open(MODEL_WEIGHTS / "two_stage_config.json") as f:
        cfg = json.load(f)
    assert 0.50 <= cfg["action_threshold"] <= 0.95, (
        f"action_threshold {cfg['action_threshold']} outside expected range [0.50, 0.95]"
    )
    assert 0.30 <= cfg["watchlist_threshold"] < cfg["action_threshold"], (
        f"watchlist_threshold {cfg['watchlist_threshold']} invalid"
    )
    assert cfg["action_threshold"] > cfg["watchlist_threshold"]


def test_action_precision_above_85():
    with open(MODEL_WEIGHTS / "two_stage_config.json") as f:
        cfg = json.load(f)
    precision = cfg.get("evaluation", {}).get("action_precision", 0)
    assert precision >= 0.85, (
        f"Action precision {precision:.2f} below 0.85"
    )


def test_no_leakage_features():
    with open(MODEL_WEIGHTS / "feature_names.json") as f:
        features = json.load(f)
    forbidden = [
        "is_fraud",
        "fraud_type",
        "fraud_confidence_score",
        "has_complaint",
        "driver_fraud_rate_rolling_14d",
    ]
    for feat in forbidden:
        assert feat not in features, f"Leakage feature in model: {feat}"
