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


@router.post(
    "/calculate",
    response_model=ROICalculationResponse,
)
async def calculate_roi(body: ROICalculationRequest):
    return build_roi_response(body)
