"""Demo-control endpoints for safe rehearsal and reset flows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from database.connection import get_db
from database.models import (
    AuditLog,
    DriverAction,
    FraudCase,
    IngestionStagingRecord,
    ShadowCase,
)
from ingestion.live_simulator import get_simulator_summary
from runtime_config import get_runtime_settings

router = APIRouter(prefix="/demo", tags=["demo"])

_DEMO_SCENARIOS = [
    {
        "id": "ring_walkthrough",
        "label": "Ghost Trip — Cancelled with Fare",
        "story": (
            "Trip claimed as completed in 2.5 minutes for 2.8 km — "
            "physically impossible in Bangalore traffic. Cash, late-night, "
            "high surge. Model catches the impossible physics + payment pattern."
        ),
        "form_patch": {
            "payment_mode": "cash",
            "vehicle_type": "two_wheeler",
            "pickup_zone_id": "blr_koramangala",
            "dropoff_zone_id": "blr_hsr",
            "declared_distance_km": 2.8,
            "declared_duration_min": 2.5,
            "fare_inr": 780,
            "surge_multiplier": 1.9,
            "is_night": True,
            "hour_of_day": 23,
            "day_of_week": 5,
            "is_peak_hour": False,
            "zone_demand_at_time": 2.3,
        },
    },
    {
        "id": "cash_extortion",
        "label": "Cash Extortion — Inflated Fare",
        "story": (
            "Mini-truck, 4.1 km, fare claimed at ₹1,250 — 4.6× the expected "
            "₹274 for that route. Cash payment, night, high surge. "
            "Fare inflation + payment mode = strong action signal."
        ),
        "form_patch": {
            "payment_mode": "cash",
            "vehicle_type": "mini_truck",
            "pickup_zone_id": "blr_indiranagar",
            "dropoff_zone_id": "blr_marathahalli",
            "declared_distance_km": 4.1,
            "declared_duration_min": 4.0,
            "fare_inr": 1250,
            "surge_multiplier": 2.4,
            "is_night": True,
            "hour_of_day": 22,
            "day_of_week": 4,
            "is_peak_hour": False,
            "zone_demand_at_time": 2.1,
        },
    },
    {
        "id": "gps_spoofing",
        "label": "GPS Spoof — Inflated Route Distance",
        "story": (
            "Driver claims 17 km for a Hebbal→Yeshwanthpur trip — "
            "straight-line haversine is 4.9 km, road distance ~6 km. "
            "Declared distance is 2.8× the haversine, triggering the "
            "Distance-vs-Haversine ratio signal. Cash payment adds "
            "a second corroborating signal."
        ),
        "form_patch": {
            "payment_mode": "cash",
            "vehicle_type": "auto",
            "pickup_zone_id": "blr_hebbal",
            "dropoff_zone_id": "blr_yeshwanthpur",
            "pickup_lat": 13.0358,
            "pickup_lon": 77.5970,
            "dropoff_lat": 13.0210,
            "dropoff_lon": 77.5540,
            "declared_distance_km": 17.0,
            "declared_duration_min": 35.0,
            "fare_inr": 480,
            "surge_multiplier": 1.0,
            "is_night": False,
            "hour_of_day": 11,
            "day_of_week": 1,
            "is_peak_hour": False,
            "zone_demand_at_time": 0.85,
        },
    },
    {
        "id": "clean_trip",
        "label": "Clean Trip — Legitimate Delivery",
        "story": (
            "Standard two-wheeler UPI delivery, daytime, normal speed, "
            "fare within expected range. Model scores CLEAR — "
            "shows analysts what a legitimate trip looks like."
        ),
        "form_patch": {
            "payment_mode": "upi",
            "vehicle_type": "two_wheeler",
            "pickup_zone_id": "blr_indiranagar",
            "dropoff_zone_id": "blr_koramangala",
            "declared_distance_km": 6.0,
            "declared_duration_min": 24.0,
            "fare_inr": 82,
            "surge_multiplier": 1.0,
            "is_night": False,
            "hour_of_day": 10,
            "day_of_week": 1,
            "is_peak_hour": False,
            "zone_demand_at_time": 0.9,
        },
    },
]


def _require_demo_operator(user: dict) -> None:
    if user.get("role") not in {"admin", "ops_manager"}:
        raise HTTPException(
            status_code=403,
            detail="Demo reset is limited to admin or ops manager roles.",
        )


@router.get("/scenarios")
async def demo_scenarios():
    """Preset walkthrough scenarios for live and backup demos."""
    return {
        "scenario_count": len(_DEMO_SCENARIOS),
        "scenarios": _DEMO_SCENARIOS,
        "recommended_order": [
            "ring_walkthrough",
            "cash_extortion",
            "gps_spoofing",
        ],
        "mapping_hint": "/ingest/schema-map/default",
    }


@router.post("/reset")
async def reset_demo_workspace(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Clear operational demo tables so the workspace can be reset between runs.

    This is intentionally disabled in production runtime mode.
    """
    _require_demo_operator(user)
    runtime = get_runtime_settings()
    if runtime.is_prod:
        raise HTTPException(
            status_code=403,
            detail="Demo reset is disabled in production runtime mode.",
        )

    delete_order = (
        ("audit_logs", AuditLog),
        ("driver_actions", DriverAction),
        ("fraud_cases", FraudCase),
        ("shadow_cases", ShadowCase),
        ("ingestion_staging", IngestionStagingRecord),
    )
    deleted = {}
    for label, model in delete_order:
        result = await db.execute(delete(model))
        deleted[label] = result.rowcount or 0
    await db.commit()

    return {
        "reset": True,
        "deleted": deleted,
        "runtime_mode": runtime.mode.value,
        "simulator_summary": get_simulator_summary(),
        "note": (
            "Workspace tables were cleared for a fresh demo run. "
            "Source benchmark data and model artifacts were not touched."
        ),
    }
