"""Driver intelligence API routes."""

import asyncio
import pandas as pd
from fastapi import APIRouter, HTTPException
from typing import List, Optional

router = APIRouter(tags=["intelligence"])
_TOP_RISK_CACHE_TTL_SECONDS = 3600


def _compute_top_risk(
    trips_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
    limit: int = 20,
) -> list:
    """
    Compute top-risk driver rankings from trip + driver data.
    Extracted for startup caching — called once, served many times.
    """
    fraud_by_driver = (
        trips_df.groupby("driver_id")
        .agg(
            total_trips  = ("trip_id", "count"),
            fraud_trips  = ("is_fraud", "sum"),
            cancel_trips = (
                "status",
                lambda x: x.isin(
                    ["cancelled_by_driver"]
                ).sum()
            ),
            cash_trips   = (
                "payment_mode",
                lambda x: (x == "cash").sum()
            ),
        )
        .assign(
            fraud_rate   = lambda d: (
                d["fraud_trips"] / d["total_trips"]
            ),
            cancel_rate  = lambda d: (
                d["cancel_trips"] / d["total_trips"]
            ),
            cash_ratio   = lambda d: (
                d["cash_trips"] / d["total_trips"]
            ),
        )
        .query("total_trips >= 3")
        .reset_index()
    )

    fraud_by_driver = fraud_by_driver.merge(
        drivers_df[[
            "driver_id", "zone_id",
            "fraud_ring_id", "ring_role"
        ]],
        on="driver_id",
        how="left"
    )

    fraud_by_driver["risk_score"] = (
        fraud_by_driver["fraud_rate"] * 0.6
        + fraud_by_driver["cancel_rate"] * 0.25
        + fraud_by_driver["cash_ratio"] * 0.15
    ).clip(0, 1)

    ring_mask = fraud_by_driver["fraud_ring_id"].notna()
    fraud_by_driver.loc[ring_mask, "risk_score"] = (
        fraud_by_driver.loc[ring_mask, "risk_score"] * 1.5
    ).clip(0, 1)

    top_drivers = fraud_by_driver.nlargest(limit, "risk_score")

    results = []
    for _, row in top_drivers.iterrows():
        risk = float(row["risk_score"])
        action = (
            "SUSPEND"     if risk > 0.7 else
            "FLAG_REVIEW" if risk > 0.4 else
            "MONITOR"     if risk > 0.2 else
            "CLEAR"
        )
        results.append({
            "driver_id":   str(row["driver_id"]),
            "zone_id":     str(row.get("zone_id", "unknown")),
            "total_trips": int(row["total_trips"]),
            "fraud_trips": int(row["fraud_trips"]),
            "fraud_rate":  round(float(row["fraud_rate"]), 4),
            "risk_score":  round(risk, 4),
            "risk_level":  (
                "CRITICAL" if risk > 0.7 else
                "HIGH"     if risk > 0.4 else
                "MEDIUM"   if risk > 0.2 else
                "LOW"
            ),
            "is_ring_member": bool(
                pd.notna(row.get("fraud_ring_id"))
            ),
            "ring_role": str(row.get("ring_role", ""))
                         if pd.notna(row.get("ring_role"))
                         else None,
            "recommended_action": action,
        })

    return results


async def _get_top_risk_cache(
    trips_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
) -> list[dict]:
    from datetime import datetime, timezone

    from database.redis_client import cache_get, cache_set

    cache_key = (
        "driver-intelligence:top-risk:"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    )
    cached = await cache_get(cache_key)
    if isinstance(cached, list) and cached:
        return cached

    computed = await asyncio.to_thread(
        _compute_top_risk,
        trips_df,
        drivers_df,
        50,
    )
    await cache_set(
        cache_key,
        computed,
        ttl_seconds=_TOP_RISK_CACHE_TTL_SECONDS,
    )
    return computed


@router.get("/intelligence/driver/{driver_id}")
async def driver_intelligence_profile(driver_id: str):
    """
    Full intelligence profile for a specific driver.
    Includes 30-day risk timeline, peer comparison,
    ring membership, and recommended action.

    This is the ops team's primary decision-support tool.
    Replaces the manual driver review process.
    """
    from api.state import app_state
    from model.driver_intelligence import get_driver_intelligence

    trips_df   = app_state.get("trips_df")
    drivers_df = app_state.get("drivers_df")

    if trips_df is None or drivers_df is None:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )

    profile = get_driver_intelligence(
        driver_id, trips_df, drivers_df
    )

    return profile


@router.get("/intelligence/top-risk")
async def top_risk_drivers(
    limit: int = 10,
    zone_id: Optional[str] = None,
    action_filter: Optional[str] = None,
):
    """
    Returns the top N highest-risk drivers.
    Optionally filtered by zone or recommended action.
    Uses startup cache with hourly invalidation.
    """
    from api.state import app_state

    trips_df   = app_state.get("trips_df")
    drivers_df = app_state.get("drivers_df")

    if trips_df is None or drivers_df is None:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )

    cached = await _get_top_risk_cache(trips_df, drivers_df)

    # Apply filters on cached results
    results = cached
    if zone_id:
        results = [d for d in results if d["zone_id"] == zone_id]
    if action_filter:
        results = [
            d for d in results
            if d["recommended_action"] == action_filter
        ]

    results = results[:limit]

    return {
        "summary": {
            "total_suspend":      sum(1 for d in results if d["recommended_action"] == "SUSPEND"),
            "total_flag_review":  sum(1 for d in results if d["recommended_action"] == "FLAG_REVIEW"),
            "total_monitor":      sum(1 for d in results if d["recommended_action"] == "MONITOR"),
            "total_ring_members": sum(1 for d in results if d["is_ring_member"]),
        },
        "drivers":      results,
        "total_shown":  len(results),
        "zone_filter":  zone_id,
        "generated_at": pd.Timestamp.now().isoformat(),
    }
