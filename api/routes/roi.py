"""Finance-facing ROI calculator."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.schemas import (
    ROICalculationRequest,
    ROICalculationResponse,
    ROIScenario,
)
from api.state import app_state

router = APIRouter(prefix="/roi", tags=["roi"])

_BENCHMARK_REPORT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "raw"
    / "evaluation_report.json"
)
_SCENARIO_MULTIPLIERS = (
    (
        "conservative",
        0.65,
        "Assumes slower review adoption and lower realised capture than the benchmark.",
    ),
    (
        "realistic",
        1.0,
        "Uses benchmark recovery per trip scaled by the buyer's stated leakage rate.",
    ),
    (
        "aggressive",
        1.35,
        "Assumes strong review throughput, rollout discipline, and high realization of recoverable value.",
    ),
)
_DEFAULT_BOARD_PACK_INPUTS = {
    "gmv_crore": 1000.0,
    "trips_per_day": 43200,
    "fraud_rate_pct": 5.895,
    "platform_price_crore": 3.25,
}


def _load_roi_benchmark() -> dict:
    report = app_state.get("report")
    if isinstance(report, dict) and report:
        return report

    if not _BENCHMARK_REPORT_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Benchmark report not available. "
                "Run the evaluation pipeline first."
            ),
        )

    return json.loads(_BENCHMARK_REPORT_PATH.read_text())


def _scenario_result(
    *,
    scenario: str,
    multiplier: float,
    note: str,
    annual_savings_crore: float,
    gmv_crore: float,
    platform_price_crore: float,
) -> ROIScenario:
    payback_months = (
        (platform_price_crore / annual_savings_crore) * 12
        if annual_savings_crore > 0
        else 0.0
    )
    payback_days = int(round(payback_months * 30.4)) if payback_months else 0
    roi_pct = (
        ((annual_savings_crore - platform_price_crore) / platform_price_crore) * 100
        if platform_price_crore > 0
        else 0.0
    )
    savings_pct_of_gmv = (
        (annual_savings_crore / gmv_crore) * 100
        if gmv_crore > 0
        else 0.0
    )
    savings_bps_of_gmv = savings_pct_of_gmv * 100

    return ROIScenario(
        scenario=scenario,
        realization_multiplier=round(multiplier, 2),
        annual_savings_crore=round(annual_savings_crore, 3),
        monthly_savings_lakh=round((annual_savings_crore * 100) / 12, 2),
        payback_months=round(payback_months, 2),
        payback_days=payback_days,
        roi_pct=round(roi_pct, 1),
        savings_pct_of_gmv=round(savings_pct_of_gmv, 3),
        savings_bps_of_gmv=round(savings_bps_of_gmv, 1),
        note=note,
    )


@router.post(
    "/calculate",
    response_model=ROICalculationResponse,
)
def build_roi_response(body: ROICalculationRequest) -> ROICalculationResponse:
    """
    Buyer-safe ROI calculator tied to the benchmark evaluation artifact.

    Method:
    - start with benchmark net recoverable per trip
    - scale it by the buyer's assumed fraud / leakage rate
    - apply conservative / realistic / aggressive realization bands
    """
    report = _load_roi_benchmark()
    xgb = report.get("xgboost", {})
    two_stage = report.get("two_stage", {})

    benchmark_total_trips = (
        two_stage.get("total_trips")
        or xgb.get("total_trips")
        or 0
    )
    benchmark_total_fraud = xgb.get("total_fraud", 0)
    benchmark_net_rec_trip = (
        two_stage.get("net_recoverable_per_trip")
        or xgb.get("net_recoverable_per_trip")
        or 0.0
    )
    benchmark_fraud_rate_pct = (
        (benchmark_total_fraud / benchmark_total_trips) * 100
        if benchmark_total_trips
        else 0.0
    )

    if benchmark_net_rec_trip <= 0 or benchmark_fraud_rate_pct <= 0:
        raise HTTPException(
            status_code=503,
            detail=(
                "Benchmark recovery inputs are unavailable. "
                "Run the evaluation pipeline first."
            ),
        )

    annual_trip_volume = body.trips_per_day * 365
    fraud_rate_scaler = body.fraud_rate_pct / benchmark_fraud_rate_pct
    realistic_savings_crore = (
        annual_trip_volume
        * benchmark_net_rec_trip
        * fraud_rate_scaler
    ) / 10_000_000

    scenarios = []
    for scenario_name, multiplier, note in _SCENARIO_MULTIPLIERS:
        scenarios.append(
            _scenario_result(
                scenario=scenario_name,
                multiplier=multiplier,
                note=note,
                annual_savings_crore=realistic_savings_crore * multiplier,
                gmv_crore=body.gmv_crore,
                platform_price_crore=body.platform_price_crore,
            )
        )

    realistic = next(
        item for item in scenarios if item.scenario == "realistic"
    )

    return ROICalculationResponse(
        annual_savings_crore=realistic.annual_savings_crore,
        payback_months=realistic.payback_months,
        roi_pct=realistic.roi_pct,
        benchmark_net_recoverable_per_trip=round(
            benchmark_net_rec_trip,
            4,
        ),
        benchmark_fraud_rate_pct=round(
            benchmark_fraud_rate_pct,
            3,
        ),
        platform_price_crore=round(body.platform_price_crore, 2),
        annual_trip_volume=annual_trip_volume,
        savings_pct_of_gmv=realistic.savings_pct_of_gmv,
        savings_bps_of_gmv=realistic.savings_bps_of_gmv,
        scenarios=scenarios,
        assumptions={
            "gmv_crore": round(body.gmv_crore, 2),
            "trips_per_day": body.trips_per_day,
            "fraud_rate_pct": round(body.fraud_rate_pct, 3),
            "benchmark_window": "two-stage scored benchmark",
            "benchmark_precision": round(
                float(two_stage.get("action_precision", 0.0)) * 100,
                2,
            ),
        },
    )


def get_default_board_pack_inputs() -> dict:
    return dict(_DEFAULT_BOARD_PACK_INPUTS)


@router.get("/summary")
def roi_summary(
    trips_per_day:      int   = 43200,
    fraud_rate_pct:     float = 5.9,
    action_tier_pct:    float = 3.77,
    action_precision:   float = 0.883,
    recovery_per_trip:  float = 6.85,
    platform_cost_lakh: float = 75.0,
):
    """
    GET /roi/summary — quick ROI snapshot with conservative defaults.

    All inputs are based on the synthetic benchmark dataset.
    Real-data FPR and precision are validated during the shadow pilot.
    """
    from datetime import datetime

    annual_trips           = trips_per_day * 365
    flagged_per_day        = trips_per_day * (action_tier_pct / 100)
    flagged_annual         = flagged_per_day * 365
    true_positives_annual  = flagged_annual * action_precision
    false_positives_annual = flagged_annual * (1 - action_precision)

    RECOVERY_RATE   = 0.30    # conservative: 30% of flagged fraud recoverable
    REVIEW_COST_INR = 50      # ₹50 ops cost per analyst review
    gross_recovery  = true_positives_annual * recovery_per_trip
    net_recovery    = gross_recovery * RECOVERY_RATE
    ops_cost_annual = (true_positives_annual + false_positives_annual) * REVIEW_COST_INR
    net_annual_benefit = net_recovery - ops_cost_annual

    platform_cost_inr = platform_cost_lakh * 100_000
    payback_months    = (
        (platform_cost_inr / max(net_annual_benefit / 12, 1))
        if net_annual_benefit > 0 else 0.0
    )

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "inputs": {
            "trips_per_day":      trips_per_day,
            "fraud_rate_pct":     fraud_rate_pct,
            "action_tier_pct":    action_tier_pct,
            "action_precision":   action_precision,
            "recovery_per_trip":  recovery_per_trip,
            "platform_cost_lakh": platform_cost_lakh,
        },
        "annual_metrics": {
            "total_trips":            annual_trips,
            "trips_flagged":          round(flagged_annual),
            "true_fraud_caught":      round(true_positives_annual),
            "false_positives":        round(false_positives_annual),
            "gross_recovery_inr":     round(gross_recovery),
            "net_recovery_inr":       round(net_recovery),
            "ops_cost_inr":           round(ops_cost_annual),
            "net_annual_benefit_inr": round(net_annual_benefit),
        },
        "scenarios": {
            "conservative_inr": round(net_annual_benefit * 0.50),
            "realistic_inr":    round(net_annual_benefit),
            "aggressive_inr":   round(net_annual_benefit * 1.80),
        },
        "investment": {
            "platform_cost_inr": round(platform_cost_inr),
            "payback_months":    round(payback_months, 1),
            "year_1_roi_pct":    round(
                (net_annual_benefit - platform_cost_inr)
                / max(platform_cost_inr, 1) * 100, 1
            ),
        },
        "disclosures": [
            "All inputs based on synthetic benchmark data (100K trips, 5.9% fraud rate)",
            "action_precision=88.3% applies to action tier (threshold 0.65) only — top ~3.8% of trips by risk score",
            "overall model precision at threshold 0.40 (watchlist) is lower; two-stage system uses 0.65 for enforcement",
            "Real-data FPR and precision validated during 60-day shadow pilot",
            "Recovery rate (30%) is conservative — actual depends on Porter enforcement process",
            "Net recovery goes negative if action-tier FPR on real data exceeds ~15%",
        ],
        "shadow_pilot_value": (
            "The 90-day validation program runs on Porter's real trip data in shadow mode. "
            "If action-tier precision >= 70% and FPR <= 15%, Tranche 2 (₹2.25 crore) is triggered. "
            "Shadow mode: zero operational risk — read-only, no enforcement writeback."
        ),
        "commercial_structure": {
            "tranche_1":    "₹1,00,00,000 (₹1 crore) on signing — non-refundable, full IP transfer",
            "tranche_2":    "₹2,25,00,000 (₹2.25 crore) on 90-day validation success",
            "total":        "₹3,25,00,000 (₹3.25 crore) total",
            "no_cure_no_pay": "Tranche 2 not due if validation criteria unmet. Porter retains all IP.",
            "exclusivity":  "Not sold to any other Indian logistics company for 24 months",
        },
    }
