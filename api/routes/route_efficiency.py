"""Route efficiency API routes."""

from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime

router = APIRouter()


@router.get("/efficiency/summary")
async def efficiency_summary():
    """
    Fleet-wide efficiency KPIs.
    Dead mile rate, utilisation, reallocation opportunity.
    """
    from api.state import app_state
    from model.route_efficiency import (
        compute_dead_mile_rate,
        compute_hourly_utilisation,
        generate_reallocation_suggestions,
        compute_fleet_summary,
    )

    trips_df = app_state.get("trips_df")
    if trips_df is None or trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Trip data not loaded"
        )

    # Use cached efficiency data if available
    if "efficiency_cache" not in app_state:
        dead_mile   = compute_dead_mile_rate(trips_df)
        utilisation = compute_hourly_utilisation(trips_df)
        suggestions = generate_reallocation_suggestions(
            trips_df, dead_mile, utilisation
        )
        app_state["efficiency_cache"] = {
            "dead_mile":   dead_mile,
            "utilisation": utilisation,
            "suggestions": suggestions,
        }

    cache = app_state["efficiency_cache"]
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
    from model.route_efficiency import (
        compute_dead_mile_rate,
        compute_hourly_utilisation,
        generate_reallocation_suggestions,
    )

    trips_df = app_state.get("trips_df")
    if trips_df is None or trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Trip data not loaded"
        )

    if "efficiency_cache" not in app_state:
        dead_mile   = compute_dead_mile_rate(trips_df)
        utilisation = compute_hourly_utilisation(trips_df)
        suggestions = generate_reallocation_suggestions(
            trips_df, dead_mile, utilisation
        )
        app_state["efficiency_cache"] = {
            "dead_mile":   dead_mile,
            "utilisation": utilisation,
            "suggestions": suggestions,
        }
        app_state["efficiency_cache_hour"] = datetime.now().hour

    # Hourly cache invalidation for suggestions only
    cache = app_state["efficiency_cache"]
    cache_hour = app_state.get("efficiency_cache_hour", -1)
    current_hour = datetime.now().hour

    if current_hour != cache_hour:
        suggestions = generate_reallocation_suggestions(
            trips_df,
            cache.get("dead_mile", {}),
            cache.get("utilisation", {}),
        )
        app_state["efficiency_cache"]["suggestions"] = suggestions
        app_state["efficiency_cache_hour"] = current_hour

    suggestions = app_state["efficiency_cache"]["suggestions"]

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
    from model.route_efficiency import compute_dead_mile_rate
    from generator.cities import ZONES

    trips_df = app_state.get("trips_df")
    if trips_df is None or trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Trip data not loaded"
        )

    if "efficiency_cache" not in app_state:
        dead_mile = compute_dead_mile_rate(trips_df)
        app_state["efficiency_cache"] = {
            "dead_mile": dead_mile
        }

    dead_mile = app_state["efficiency_cache"]["dead_mile"]

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
    from model.route_efficiency import compute_hourly_utilisation
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

    if "efficiency_cache" not in app_state:
        utilisation = compute_hourly_utilisation(trips_df)
        app_state["efficiency_cache"] = {
            "utilisation": utilisation
        }

    util = app_state["efficiency_cache"].get(
        "utilisation", {}
    )
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
