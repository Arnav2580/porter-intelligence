"""Route efficiency API routes."""

import asyncio
from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime, timezone

router = APIRouter(tags=["route_efficiency"])
_EFFICIENCY_CACHE_TTL_SECONDS = 3600


def _build_efficiency_snapshot(trips_df):
    from model.route_efficiency import (
        compute_dead_mile_rate,
        compute_hourly_utilisation,
        generate_reallocation_suggestions,
    )

    dead_mile = compute_dead_mile_rate(trips_df)
    utilisation = compute_hourly_utilisation(trips_df)
    suggestions = generate_reallocation_suggestions(
        trips_df,
        dead_mile,
        utilisation,
    )
    return {
        "dead_mile": dead_mile,
        "utilisation": utilisation,
        "suggestions": suggestions,
    }


async def _get_efficiency_snapshot(trips_df):
    from database.redis_client import cache_get, cache_set

    cache_key = (
        "route-efficiency:snapshot:"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    )
    cached = await cache_get(cache_key)
    if isinstance(cached, dict) and cached:
        return cached

    snapshot = await asyncio.to_thread(
        _build_efficiency_snapshot,
        trips_df,
    )
    await cache_set(
        cache_key,
        snapshot,
        ttl_seconds=_EFFICIENCY_CACHE_TTL_SECONDS,
    )
    return snapshot


@router.get("/efficiency/summary")
async def efficiency_summary():
    """
    Fleet-wide efficiency KPIs.
    Dead mile rate, utilisation, reallocation opportunity.
    """
    from api.state import app_state
    from model.route_efficiency import (
        compute_fleet_summary,
    )

    trips_df = app_state.get("trips_df")
    if trips_df is None or trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Trip data not loaded"
        )

    cache = await _get_efficiency_snapshot(trips_df)
    summary = compute_fleet_summary(
        trips_df,
        cache["dead_mile"],
        cache["utilisation"],
        cache["suggestions"],
    )

    return summary


@router.get("/efficiency/reallocation")
async def reallocation_suggestions(limit: int = 8):
    """
    Ranked vehicle reallocation suggestions.
    Sorted by expected revenue descending.
    Suggestions refresh hourly — dead mile and utilisation
    data are reused from startup cache.
    """
    from api.state import app_state

    trips_df = app_state.get("trips_df")
    if trips_df is None or trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Trip data not loaded"
        )

    cache = await _get_efficiency_snapshot(trips_df)
    suggestions = cache["suggestions"]

    return {
        "suggestions":  suggestions[:limit],
        "total":        len(suggestions),
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/efficiency/dead-miles")
async def dead_mile_heatmap():
    """
    Per-zone dead mile rates for map overlay.
    Used by the dashboard map toggle.
    """
    from api.state import app_state
    from generator.cities import ZONES

    trips_df = app_state.get("trips_df")
    if trips_df is None or trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Trip data not loaded"
        )

    cache = await _get_efficiency_snapshot(trips_df)
    dead_mile = cache["dead_mile"]

    zones = []
    for zone_id, data in dead_mile.items():
        zone = ZONES.get(zone_id)
        if zone is None:
            continue
        zones.append({
            "zone_id":          zone_id,
            "zone_name":        data["zone_name"],
            "lat":              zone.lat,
            "lon":              zone.lon,
            "dead_mile_rate":   data["dead_mile_rate"],
            "efficiency_score": data["efficiency_score"],
            "cost_inr_per_day": data["cost_inr_per_day"],
            "risk_level": (
                "CRITICAL" if data["dead_mile_rate"] > 0.20 else
                "HIGH"     if data["dead_mile_rate"] > 0.10 else
                "MEDIUM"   if data["dead_mile_rate"] > 0.05 else
                "LOW"
            ),
        })

    return {
        "zones":        zones,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/efficiency/utilisation/{zone_id}")
async def zone_utilisation(zone_id: str):
    """
    Hourly utilisation breakdown for a specific zone.
    Shows active vs idle by vehicle type per hour.
    """
    from api.state import app_state
    from generator.cities import ZONES

    zone = ZONES.get(zone_id)
    if zone is None:
        raise HTTPException(
            status_code=404,
            detail=f"Zone {zone_id} not found"
        )

    trips_df = app_state.get("trips_df")
    if trips_df is None or trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Trip data not loaded"
        )

    cache = await _get_efficiency_snapshot(trips_df)
    util = cache.get("utilisation", {})
    zone_util = util.get(zone_id, {})

    # Format for API response
    hourly = []
    for hour in range(24):
        hour_data = zone_util.get(hour, {})
        hourly.append({
            "hour":       hour,
            "hour_label": f"{hour:02d}:00",
            "vehicles":   {
                vtype: {
                    "active":      d.get("active_count", 0),
                    "idle":        d.get("idle_count", 0),
                    "utilisation": d.get("utilisation", 0),
                    "demand_mult": d.get("demand_mult", 1.0),
                    "opportunity": d.get("opportunity", False),
                }
                for vtype, d in hour_data.items()
            }
        })

    return {
        "zone_id":    zone_id,
        "zone_name":  zone.name,
        "city":       zone.city,
        "hourly":     hourly,
        "generated_at": datetime.now().isoformat(),
    }
