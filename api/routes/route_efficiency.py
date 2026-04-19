"""Route efficiency API routes."""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timezone

from auth.dependencies import require_permission

logger = logging.getLogger(__name__)
router = APIRouter(tags=["route_efficiency"])
_EFFICIENCY_CACHE_TTL_SECONDS = 3600

_FLEET_ZONES_BENCHMARK = [
    # Bangalore
    {"zone_id": "blr_koramangala", "lat": 12.9352, "lon": 77.6245, "city": "Bangalore",
     "efficiency_score": 0.78, "idle_drivers": 12, "active_drivers": 45, "dead_mile_pct": 18.2, "utilisation_pct": 0.72},
    {"zone_id": "blr_whitefield",  "lat": 12.9698, "lon": 77.7500, "city": "Bangalore",
     "efficiency_score": 0.71, "idle_drivers": 8,  "active_drivers": 31, "dead_mile_pct": 22.1, "utilisation_pct": 0.65},
    {"zone_id": "blr_hebbal",      "lat": 13.0358, "lon": 77.5970, "city": "Bangalore",
     "efficiency_score": 0.84, "idle_drivers": 5,  "active_drivers": 38, "dead_mile_pct": 14.3, "utilisation_pct": 0.81},
    {"zone_id": "blr_hsr",         "lat": 12.9116, "lon": 77.6389, "city": "Bangalore",
     "efficiency_score": 0.76, "idle_drivers": 9,  "active_drivers": 34, "dead_mile_pct": 20.1, "utilisation_pct": 0.70},
    {"zone_id": "blr_indiranagar", "lat": 12.9784, "lon": 77.6408, "city": "Bangalore",
     "efficiency_score": 0.80, "idle_drivers": 7,  "active_drivers": 36, "dead_mile_pct": 16.5, "utilisation_pct": 0.75},
    # Mumbai
    {"zone_id": "mum_bandra",  "lat": 19.0596, "lon": 72.8295, "city": "Mumbai",
     "efficiency_score": 0.69, "idle_drivers": 18, "active_drivers": 52, "dead_mile_pct": 26.4, "utilisation_pct": 0.61},
    {"zone_id": "mum_andheri", "lat": 19.1197, "lon": 72.8464, "city": "Mumbai",
     "efficiency_score": 0.74, "idle_drivers": 14, "active_drivers": 47, "dead_mile_pct": 21.8, "utilisation_pct": 0.67},
    {"zone_id": "mum_thane",   "lat": 19.2183, "lon": 72.9781, "city": "Mumbai",
     "efficiency_score": 0.81, "idle_drivers": 9,  "active_drivers": 35, "dead_mile_pct": 16.2, "utilisation_pct": 0.76},
    # Delhi NCR
    {"zone_id": "del_cp",      "lat": 28.6330, "lon": 77.2194, "city": "Delhi NCR",
     "efficiency_score": 0.66, "idle_drivers": 21, "active_drivers": 58, "dead_mile_pct": 29.1, "utilisation_pct": 0.58},
    {"zone_id": "del_noida",   "lat": 28.5355, "lon": 77.3910, "city": "Delhi NCR",
     "efficiency_score": 0.73, "idle_drivers": 15, "active_drivers": 44, "dead_mile_pct": 22.7, "utilisation_pct": 0.66},
    {"zone_id": "del_gurgaon", "lat": 28.4595, "lon": 77.0266, "city": "Delhi NCR",
     "efficiency_score": 0.77, "idle_drivers": 11, "active_drivers": 39, "dead_mile_pct": 19.3, "utilisation_pct": 0.71},
    # Hyderabad
    {"zone_id": "hyd_hitech",  "lat": 17.4435, "lon": 78.3772, "city": "Hyderabad",
     "efficiency_score": 0.82, "idle_drivers": 7,  "active_drivers": 34, "dead_mile_pct": 15.1, "utilisation_pct": 0.79},
    {"zone_id": "hyd_banjara", "lat": 17.4126, "lon": 78.4482, "city": "Hyderabad",
     "efficiency_score": 0.76, "idle_drivers": 10, "active_drivers": 38, "dead_mile_pct": 20.4, "utilisation_pct": 0.70},
    # Chennai
    {"zone_id": "che_tnagar",    "lat": 13.0418, "lon": 80.2341, "city": "Chennai",
     "efficiency_score": 0.79, "idle_drivers": 9, "active_drivers": 36, "dead_mile_pct": 17.8, "utilisation_pct": 0.74},
    {"zone_id": "che_velachery", "lat": 12.9815, "lon": 80.2180, "city": "Chennai",
     "efficiency_score": 0.83, "idle_drivers": 6, "active_drivers": 29, "dead_mile_pct": 13.9, "utilisation_pct": 0.80},
    # Pune
    {"zone_id": "pun_koregaon", "lat": 18.5362, "lon": 73.8936, "city": "Pune",
     "efficiency_score": 0.80, "idle_drivers": 8, "active_drivers": 32, "dead_mile_pct": 16.7, "utilisation_pct": 0.75},
    # Kolkata
    {"zone_id": "kol_salt_lake", "lat": 22.5726, "lon": 88.4318, "city": "Kolkata",
     "efficiency_score": 0.71, "idle_drivers": 13, "active_drivers": 41, "dead_mile_pct": 23.5, "utilisation_pct": 0.64},
    # Ahmedabad
    {"zone_id": "ahm_sg_highway", "lat": 23.0225, "lon": 72.5714, "city": "Ahmedabad",
     "efficiency_score": 0.76, "idle_drivers": 10, "active_drivers": 35, "dead_mile_pct": 20.1, "utilisation_pct": 0.69},
    # Jaipur
    {"zone_id": "jai_vaishali", "lat": 26.9124, "lon": 75.7873, "city": "Jaipur",
     "efficiency_score": 0.78, "idle_drivers": 8, "active_drivers": 28, "dead_mile_pct": 18.4, "utilisation_pct": 0.72},
    # Lucknow
    {"zone_id": "lko_gomti", "lat": 26.8467, "lon": 80.9462, "city": "Lucknow",
     "efficiency_score": 0.74, "idle_drivers": 9, "active_drivers": 30, "dead_mile_pct": 21.2, "utilisation_pct": 0.67},
    # Surat
    {"zone_id": "sur_adajan", "lat": 21.1702, "lon": 72.8311, "city": "Surat",
     "efficiency_score": 0.81, "idle_drivers": 6, "active_drivers": 26, "dead_mile_pct": 15.8, "utilisation_pct": 0.77},
    # Nagpur
    {"zone_id": "nag_dharampeth", "lat": 21.1458, "lon": 79.0882, "city": "Nagpur",
     "efficiency_score": 0.79, "idle_drivers": 7, "active_drivers": 24, "dead_mile_pct": 17.3, "utilisation_pct": 0.73},
]


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
async def efficiency_summary(
    _user=Depends(require_permission("read:cases")),
):
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
    summary.setdefault("data_source", "synthetic_benchmark")

    return summary


@router.get("/efficiency/reallocation")
async def reallocation_suggestions(
    limit: int = 8,
    _user=Depends(require_permission("read:cases")),
):
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
async def dead_mile_heatmap(
    _user=Depends(require_permission("read:cases")),
):
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
async def zone_utilisation(
    zone_id: str,
    _user=Depends(require_permission("read:cases")),
):
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


@router.get("/efficiency/fleet-zones")
async def fleet_zones(
    _user=Depends(require_permission("read:cases")),
):
    """
    Fleet efficiency and utilisation data by zone for map display.
    Returns all active zones with idle/active driver counts and dead-mile %.
    Falls back to benchmark data if DB is unavailable.
    """
    try:
        from api.state import app_state
        from generator.cities import ZONES

        trips_df = app_state.get("trips_df")
        if trips_df is None or trips_df.empty:
            raise RuntimeError("Trip data not loaded")

        cache = await _get_efficiency_snapshot(trips_df)
        dead_mile = cache.get("dead_mile", {})
        utilisation = cache.get("utilisation", {})

        zones_out = []
        for zone_id_key, dm_data in dead_mile.items():
            zone = ZONES.get(zone_id_key)
            if zone is None:
                continue
            util_data = utilisation.get(zone_id_key, {})
            active = sum(
                v.get("active_count", 0)
                for hour in util_data.values()
                for v in (hour.values() if isinstance(hour, dict) else [])
            )
            idle = sum(
                v.get("idle_count", 0)
                for hour in util_data.values()
                for v in (hour.values() if isinstance(hour, dict) else [])
            )
            total = max(active + idle, 1)
            zones_out.append({
                "zone_id":          zone_id_key,
                "lat":              zone.lat,
                "lon":              zone.lon,
                "city":             zone.city,
                "efficiency_score": round(dm_data.get("efficiency_score", 0.75), 4),
                "idle_drivers":     int(idle),
                "active_drivers":   int(active),
                "dead_mile_pct":    round(dm_data.get("dead_mile_rate", 0.18) * 100, 1),
                "utilisation_pct":  round(active / total, 4),
            })

        # Supplement live zones with benchmark data for cities not yet in live data
        live_zone_ids = {z["zone_id"] for z in zones_out}
        for bz in _FLEET_ZONES_BENCHMARK:
            if bz["zone_id"] not in live_zone_ids:
                zones_out.append(bz)

        if zones_out:
            return {
                "zones":        zones_out,
                "source":       "live+benchmark",
                "generated_at": datetime.now().isoformat(),
                "data_source":  "synthetic_benchmark",
            }
        raise RuntimeError("No zones computed")

    except Exception as exc:
        logger.warning("fleet_zones falling back to benchmark: %s", exc)
        return {
            "zones":        _FLEET_ZONES_BENCHMARK,
            "source":       "benchmark",
            "generated_at": datetime.now().isoformat(),
            "data_source":  "synthetic_benchmark",
        }
