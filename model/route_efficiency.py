"""
Porter Intelligence Platform — Route Efficiency Engine

Computes fleet utilisation metrics and generates
vehicle reallocation suggestions.

Designed to replace the manual dispatch decisions
that Porter's ops team made before restructuring.

Three core computations:
  1. Dead mile rate per zone and vehicle type
  2. Hourly vehicle utilisation heatmap
  3. Reallocation suggestions (demand-supply matching)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table

from generator.config import (
    RANDOM_SEED, VEHICLE_TYPES, DATA_RAW
)
from generator.cities import ZONES, CITY_ZONES

console = Console()


# ── Dead mile computation ─────────────────────────────────────

def compute_dead_mile_rate(
    trips_df: pd.DataFrame,
) -> Dict[str, Dict]:
    """
    Compute dead mile rate per zone.

    Dead mile definition for gig logistics:
      A trip where:
        - driver travels to pickup but customer cancels
          (cancelled_by_customer after started_at)
        - driver accepts trip in zone A but pickup is in zone B
          (positioning trip = deadhead)
        - completed trip where driver ends in low-demand zone
          with no return order within 30 minutes

    Proxy computation from synthetic data:
      dead_mile_rate = (
          cancelled_after_start + long_accept_delays
      ) / total_trips_in_zone

    cancelled_after_start:
      status == cancelled_by_customer AND started_at IS NOT NULL
      These represent trips where driver moved to pickup
      and was then cancelled on — pure dead miles.

    long_accept_delays:
      accepted_at - requested_at > 8 minutes
      Driver was far from pickup — positioning inefficiency.

    Returns dict: {zone_id: {
        dead_mile_rate, cancelled_after_start,
        long_accept_trips, total_trips,
        estimated_dead_km, cost_inr_per_day
    }}
    """
    df = trips_df.copy()
    df["requested_at"] = pd.to_datetime(
        df["requested_at"], format="ISO8601"
    )
    df["accepted_at"]  = pd.to_datetime(
        df["accepted_at"], format="ISO8601", errors="coerce"
    )
    df["started_at"]   = pd.to_datetime(
        df["started_at"], format="ISO8601", errors="coerce"
    )

    # Accept delay in seconds
    df["accept_delay_s"] = (
        df["accepted_at"] - df["requested_at"]
    ).dt.total_seconds()

    result = {}

    for zone_id in df["pickup_zone_id"].unique():
        zone_df = df[df["pickup_zone_id"] == zone_id]
        total   = len(zone_df)
        if total == 0:
            continue

        # Cancelled after driver started moving
        cancelled_after_start = zone_df[
            (zone_df["status"] == "cancelled_by_customer")
            & zone_df["started_at"].notna()
        ].shape[0]

        # Long accept delay (driver was far away)
        long_accept = zone_df[
            zone_df["accept_delay_s"] > 480   # 8 minutes
        ].shape[0]

        dead_trip_count = cancelled_after_start + long_accept
        dead_mile_rate  = dead_trip_count / max(total, 1)

        # Estimate dead km (avg 3km per dead positioning trip)
        estimated_dead_km = dead_trip_count * 3.0

        # Cost estimate (avg ₹12/km fuel + wear)
        cost_per_day = (
            estimated_dead_km * 12
            / max(
                (
                    df["requested_at"].dt.date.nunique()
                ), 1
            )
        )

        zone_obj  = ZONES.get(zone_id)
        zone_name = zone_obj.name if zone_obj else zone_id

        result[zone_id] = {
            "zone_id":              zone_id,
            "zone_name":            zone_name,
            "total_trips":          int(total),
            "cancelled_after_start":int(cancelled_after_start),
            "long_accept_trips":    int(long_accept),
            "dead_trip_count":      int(dead_trip_count),
            "dead_mile_rate":       round(dead_mile_rate, 4),
            "estimated_dead_km":    round(estimated_dead_km, 1),
            "cost_inr_per_day":     round(cost_per_day, 2),
            "efficiency_score":     round(
                1.0 - dead_mile_rate, 4
            ),
        }

    return result


# ── Hourly utilisation ────────────────────────────────────────

def compute_hourly_utilisation(
    trips_df: pd.DataFrame,
) -> Dict[str, Dict]:
    """
    Compute vehicle utilisation by zone, vehicle type,
    and hour of day.

    Utilisation = active trips / (active trips + idle time proxy)

    Idle time proxy:
      For each driver-hour bucket, if a driver completed
      a trip in the previous hour but has no trip in this
      hour AND the zone has demand > 1.0x — that driver
      is considered idle in a demand zone.

    Returns dict: {zone_id: {
        hour: {vehicle_type: {utilisation, idle_count,
                              active_count, demand_mult}}
    }}

    Also returns fleet_summary: total idle vehicle-hours
    by vehicle type across all zones.
    """
    df = trips_df.copy()
    df["requested_at"] = pd.to_datetime(
        df["requested_at"], format="ISO8601"
    )
    df["hour_of_day"]  = df["requested_at"].dt.hour
    df["dow"]          = df["requested_at"].dt.dayofweek

    result = {}

    for zone_id in df["pickup_zone_id"].unique():
        zone_df  = df[df["pickup_zone_id"] == zone_id]
        zone_obj = ZONES.get(zone_id)
        if zone_obj is None:
            continue

        zone_result = {}

        for hour in range(24):
            hour_df = zone_df[zone_df["hour_of_day"] == hour]
            # Most common day of week in data
            modal_dow = int(
                df["dow"].mode()[0]
            ) if len(df) > 0 else 0

            from generator.cities import get_zone_demand_pattern
            demand = get_zone_demand_pattern(
                zone_obj, hour, modal_dow
            )

            hour_result = {}

            for vtype in VEHICLE_TYPES:
                vtype_df = hour_df[
                    hour_df["vehicle_type"] == vtype
                ]
                active_count = len(vtype_df)

                # Idle estimate: drivers active in prev hour
                # but not this hour (demand zone)
                prev_hour_df = zone_df[
                    zone_df["hour_of_day"] == (hour - 1) % 24
                ]
                prev_drivers = set(
                    prev_hour_df[
                        prev_hour_df["vehicle_type"] == vtype
                    ]["driver_id"].unique()
                )
                curr_drivers = set(
                    vtype_df["driver_id"].unique()
                )
                idle_drivers = prev_drivers - curr_drivers

                # Only count as "idle" if demand is present
                idle_count = (
                    len(idle_drivers)
                    if demand > 1.0
                    else 0
                )

                total = active_count + idle_count
                utilisation = (
                    active_count / max(total, 1)
                )

                hour_result[vtype] = {
                    "active_count": active_count,
                    "idle_count":   idle_count,
                    "utilisation":  round(utilisation, 4),
                    "demand_mult":  round(demand, 3),
                    "opportunity":  (
                        idle_count > 0
                        and demand > 1.5
                    ),
                }

            zone_result[hour] = hour_result

        result[zone_id] = zone_result

    return result


# ── Reallocation engine ───────────────────────────────────────

def generate_reallocation_suggestions(
    trips_df:      pd.DataFrame,
    dead_mile_data: Dict,
    utilisation_data: Dict,
    max_suggestions: int = 8,
) -> List[Dict]:
    """
    Generate actionable vehicle reallocation suggestions.

    Logic:
      For each vehicle type:
        1. Find zones with idle vehicles right now
           (current hour utilisation < 0.4)
        2. Find zones with high current demand
           (demand_multiplier > 1.5)
        3. If idle zone and demand zone are within 8km:
           generate a reallocation suggestion

    Each suggestion includes:
      from_zone:        zone with idle vehicles
      to_zone:          zone with demand
      vehicle_type:     what to move
      idle_count:       how many idle vehicles
      demand_mult:      current demand at destination
      distance_km:      how far to move
      urgency:          IMMEDIATE / HIGH / MEDIUM
      expected_trips:   estimated extra trips if reallocated
      expected_revenue: ₹ revenue from those trips
      reason:           one sentence explanation

    Sorted by expected_revenue descending.
    """
    from generator.cities import haversine_km, ZONES

    current_hour = datetime.now().hour
    suggestions  = []

    # Get current hour utilisation across all zones
    for from_zone_id, zone_util in utilisation_data.items():
        hour_util = zone_util.get(current_hour, {})
        from_zone = ZONES.get(from_zone_id)
        if from_zone is None:
            continue

        for vtype, stats in hour_util.items():
            idle_count  = stats.get("idle_count", 0)
            utilisation = stats.get("utilisation", 1.0)

            # Only consider zones with real idle capacity
            if idle_count < 1 or utilisation > 0.5:
                continue

            # Find demand zones within range
            for to_zone_id, to_zone_util in \
                    utilisation_data.items():

                if to_zone_id == from_zone_id:
                    continue

                to_zone = ZONES.get(to_zone_id)
                if to_zone is None:
                    continue

                # Distance check — max 8km reallocation
                dist = haversine_km(
                    from_zone.lat, from_zone.lon,
                    to_zone.lat,   to_zone.lon
                )
                if dist > 8.0:
                    continue

                # Demand at destination
                to_hour_util = to_zone_util.get(
                    current_hour, {}
                )
                to_stats  = to_hour_util.get(vtype, {})
                to_demand = to_stats.get("demand_mult", 1.0)
                to_active = to_stats.get("active_count", 0)

                # Only suggest if destination has real demand
                if to_demand < 1.5:
                    continue

                # Revenue estimate
                veh = VEHICLE_TYPES[vtype]
                avg_trip_revenue = (
                    veh.base_fare + veh.per_km_rate * 8
                ) * 0.8  # Porter's ~80% share

                # Estimate trips per reallocated vehicle (2hr window)
                trips_per_vehicle = max(1, int(to_demand * 2))
                expected_trips    = idle_count * trips_per_vehicle
                expected_revenue  = expected_trips * avg_trip_revenue

                urgency = (
                    "IMMEDIATE" if to_demand > 2.0 else
                    "HIGH"      if to_demand > 1.7 else
                    "MEDIUM"
                )

                suggestions.append({
                    "suggestion_id":  (
                        f"REALLOC_{from_zone_id[:6].upper()}"
                        f"_{to_zone_id[:6].upper()}"
                        f"_{vtype[:4].upper()}"
                    ),
                    "from_zone_id":   from_zone_id,
                    "from_zone_name": from_zone.name,
                    "to_zone_id":     to_zone_id,
                    "to_zone_name":   to_zone.name,
                    "vehicle_type":   vtype,
                    "idle_count":     int(idle_count),
                    "to_demand_mult": round(to_demand, 3),
                    "distance_km":    round(dist, 1),
                    "urgency":        urgency,
                    "expected_trips": int(expected_trips),
                    "expected_revenue_inr": round(
                        expected_revenue, 2
                    ),
                    "reason": (
                        f"{idle_count} {vtype.replace('_', ' ')}(s) "
                        f"idle in {from_zone.name}. "
                        f"{to_zone.name} showing "
                        f"{to_demand:.1f}x demand surge "
                        f"({dist:.1f}km away). "
                        f"Est. ₹{expected_revenue:,.0f} revenue "
                        f"if reallocated now."
                    ),
                    "generated_at": datetime.now().isoformat(),
                })

    # Sort by expected revenue, take top N
    suggestions.sort(
        key=lambda x: x["expected_revenue_inr"],
        reverse=True
    )

    # ── Fallback: generate from dead-mile data when optimizer finds nothing ──
    if not suggestions and dead_mile_data:
        _suggestions_from_dead_miles(
            dead_mile_data, suggestions, max_suggestions
        )

    return suggestions[:max_suggestions]


def _suggestions_from_dead_miles(
    dead_mile_data: Dict,
    suggestions: List[Dict],
    max_suggestions: int,
) -> None:
    """
    Fallback suggestion generator using dead-mile rates.

    When the utilisation optimizer finds no idle/demand pairs
    (e.g., off-peak hours or sparse data), generate suggestions
    based on zones with the highest dead-mile rates. High dead-mile
    zones have excess supply and are natural sources for reallocation.

    Adds suggestions in-place to the provided list.
    """
    from generator.cities import haversine_km, ZONES

    # Rank zones by dead mile rate descending
    ranked = sorted(
        (
            (zid, z)
            for zid, z in dead_mile_data.items()
            if isinstance(z, dict) and z.get("dead_mile_rate", 0) > 0.05
        ),
        key=lambda x: x[1].get("dead_mile_rate", 0),
        reverse=True,
    )

    seen: set = set()
    for from_zid, from_data in ranked[:6]:
        from_zone = ZONES.get(from_zid)
        if from_zone is None:
            continue

        dead_rate = float(from_data.get("dead_mile_rate", 0.0))
        # Find the nearest zone with lower dead-mile rate as destination
        for to_zid, to_data in sorted(
            dead_mile_data.items(),
            key=lambda x: x[1].get("dead_mile_rate", 0),
        ):
            if to_zid == from_zid:
                continue
            to_zone = ZONES.get(to_zid)
            if to_zone is None:
                continue
            pair_key = f"{from_zid}→{to_zid}"
            if pair_key in seen:
                continue

            dist = haversine_km(
                from_zone.lat, from_zone.lon,
                to_zone.lat,   to_zone.lon,
            )
            if dist > 12.0:
                continue

            idle_count = max(1, int(dead_rate * 10))
            avg_revenue = 250.0  # ₹ per trip — conservative estimate
            expected_trips = idle_count * 2
            expected_revenue = expected_trips * avg_revenue

            seen.add(pair_key)
            suggestions.append({
                "suggestion_id": (
                    f"REALLOC_{from_zid[:6].upper()}"
                    f"_{to_zid[:6].upper()}_DM"
                ),
                "from_zone_id":   from_zid,
                "from_zone_name": from_zone.name,
                "to_zone_id":     to_zid,
                "to_zone_name":   to_zone.name,
                "vehicle_type":   "two_wheeler",
                "idle_count":     idle_count,
                "to_demand_mult": 1.0,
                "distance_km":    round(dist, 1),
                "urgency":        "MEDIUM",
                "expected_trips": expected_trips,
                "expected_revenue_inr": round(expected_revenue, 2),
                "reason": (
                    f"{from_zone.name} has {dead_rate:.0%} dead-mile rate "
                    f"— {idle_count} vehicle(s) repositionable to "
                    f"{to_zone.name} ({dist:.1f} km). "
                    f"Est. ₹{expected_revenue:,.0f} incremental revenue."
                ),
                "generated_at": datetime.now().isoformat(),
            })

            if len(suggestions) >= max_suggestions:
                return


# ── Fleet summary ─────────────────────────────────────────────

def compute_fleet_summary(
    trips_df:         pd.DataFrame,
    dead_mile_data:   Dict,
    utilisation_data: Dict,
    suggestions:      List[Dict],
) -> Dict:
    """
    High-level fleet efficiency summary.
    This is what the KPI panel shows.

    Returns:
      overall_utilisation:     fleet-wide average
      total_dead_mile_rate:    weighted avg dead mile %
      total_dead_cost_per_day: ₹ wasted on dead miles daily
      idle_vehicle_hours:      total idle capacity now
      reallocation_opportunity:₹ recoverable by reallocation
      worst_zone:              lowest efficiency zone
      best_zone:               highest efficiency zone
    """
    # Overall dead mile rate (weighted by trip volume)
    total_trips = sum(
        v["total_trips"] for v in dead_mile_data.values()
    )
    total_dead  = sum(
        v["dead_trip_count"] for v in dead_mile_data.values()
    )
    overall_dead_rate = total_dead / max(total_trips, 1)

    total_dead_cost = sum(
        v["cost_inr_per_day"] for v in dead_mile_data.values()
    )

    # Worst and best efficiency zones
    if dead_mile_data:
        worst_zone = min(
            dead_mile_data.values(),
            key=lambda x: x["efficiency_score"]
        )
        best_zone = max(
            dead_mile_data.values(),
            key=lambda x: x["efficiency_score"]
        )
    else:
        worst_zone = best_zone = {}

    # Total idle vehicle-hours right now
    current_hour = datetime.now().hour
    total_idle   = 0
    for zone_util in utilisation_data.values():
        hour_util = zone_util.get(current_hour, {})
        total_idle += sum(
            s.get("idle_count", 0)
            for s in hour_util.values()
        )

    # Revenue opportunity from suggestions
    realloc_opportunity = sum(
        s["expected_revenue_inr"] for s in suggestions
    )

    # Average utilisation
    utilisation_vals = []
    for zone_util in utilisation_data.values():
        hour_util = zone_util.get(current_hour, {})
        for stats in hour_util.values():
            utilisation_vals.append(
                stats.get("utilisation", 0)
            )
    avg_util = (
        float(np.mean(utilisation_vals))
        if utilisation_vals else 0.0
    )

    return {
        "overall_utilisation":      round(avg_util, 4),
        "total_dead_mile_rate":     round(overall_dead_rate, 4),
        "total_dead_cost_per_day":  round(total_dead_cost, 2),
        "idle_vehicle_hours_now":   int(total_idle),
        "reallocation_opportunity_inr": round(
            realloc_opportunity, 2
        ),
        "active_suggestions":       len(suggestions),
        "worst_efficiency_zone":    worst_zone.get(
            "zone_name", "N/A"
        ),
        "best_efficiency_zone":     best_zone.get(
            "zone_name", "N/A"
        ),
        "worst_efficiency_score":   worst_zone.get(
            "efficiency_score", 0
        ),
        "best_efficiency_score":    best_zone.get(
            "efficiency_score", 0
        ),
        "annual_dead_cost_estimate": round(
            total_dead_cost * 365, 2
        ),
    }


# ── Main entry point ──────────────────────────────────────────

def run_route_efficiency(
    trips_df: pd.DataFrame,
) -> Dict:
    """
    Run the full route efficiency analysis pipeline.

    Returns:
      dead_mile:    per-zone dead mile stats
      utilisation:  per-zone hourly utilisation
      suggestions:  ranked reallocation list
      summary:      fleet-level KPIs
    """
    console.print("[dim]Computing dead mile rates...[/dim]")
    dead_mile = compute_dead_mile_rate(trips_df)

    console.print("[dim]Computing hourly utilisation...[/dim]")
    utilisation = compute_hourly_utilisation(trips_df)

    console.print("[dim]Generating reallocation suggestions...[/dim]")
    suggestions = generate_reallocation_suggestions(
        trips_df, dead_mile, utilisation
    )

    console.print("[dim]Computing fleet summary...[/dim]")
    summary = compute_fleet_summary(
        trips_df, dead_mile, utilisation, suggestions
    )

    return {
        "dead_mile":   dead_mile,
        "utilisation": utilisation,
        "suggestions": suggestions,
        "summary":     summary,
    }


# ── Test block ────────────────────────────────────────────────

if __name__ == "__main__":
    console.rule("[cyan]Route Efficiency — Validation[/cyan]")

    from generator.drivers import generate_drivers
    from generator.customers import generate_customers
    from generator.trips import generate_trips
    from generator.fraud import inject_fraud

    console.print("[dim]Generating sample data...[/dim]")
    drivers_df   = generate_drivers(
        n=3000, city_filter="bangalore"
    )
    customers_df = generate_customers(
        n=3000, city_filter="bangalore"
    )
    trips_df = generate_trips(
        drivers_df, customers_df,
        n=8000, city_filter="bangalore"
    )
    trips_df = inject_fraud(trips_df, drivers_df)

    # Run analysis
    console.rule("[cyan]Running Route Efficiency Analysis[/cyan]")
    results = run_route_efficiency(trips_df)

    dead_mile   = results["dead_mile"]
    utilisation = results["utilisation"]
    suggestions = results["suggestions"]
    summary     = results["summary"]

    # ── Assertions ──────────────────────────────────────
    assert len(dead_mile) > 0, \
        "Dead mile data must have zone entries"
    assert len(utilisation) > 0, \
        "Utilisation data must have zone entries"
    assert all(
        0 <= v["dead_mile_rate"] <= 1
        for v in dead_mile.values()
    ), "Dead mile rates must be 0-1"
    assert all(
        0 <= v["efficiency_score"] <= 1
        for v in dead_mile.values()
    ), "Efficiency scores must be 0-1"
    assert "overall_utilisation" in summary
    assert "total_dead_cost_per_day" in summary
    assert summary["total_dead_mile_rate"] >= 0

    # ── Dead mile table ─────────────────────────────────
    dm_table = Table(title="Dead Mile Rate by Zone")
    dm_table.add_column("Zone",         style="cyan")
    dm_table.add_column("Total Trips",  justify="right")
    dm_table.add_column("Dead Rate",    justify="right")
    dm_table.add_column("Efficiency",   justify="right")
    dm_table.add_column("Cost/Day ₹",  justify="right")

    for zone_id, data in sorted(
        dead_mile.items(),
        key=lambda x: x[1]["dead_mile_rate"],
        reverse=True
    )[:8]:
        rate  = data["dead_mile_rate"]
        color = (
            "red"    if rate > 0.20 else
            "yellow" if rate > 0.10 else
            "green"
        )
        dm_table.add_row(
            data["zone_name"],
            str(data["total_trips"]),
            f"[{color}]{rate*100:.1f}%[/{color}]",
            f"{data['efficiency_score']*100:.1f}%",
            f"₹{data['cost_inr_per_day']:,.0f}",
        )
    console.print(dm_table)

    # ── Suggestions table ───────────────────────────────
    if suggestions:
        sug_table = Table(
            title="Reallocation Suggestions"
        )
        sug_table.add_column("From",     style="dim")
        sug_table.add_column("To",       style="cyan")
        sug_table.add_column("Vehicle",  style="dim")
        sug_table.add_column("Idle",     justify="right")
        sug_table.add_column("Demand",   justify="right")
        sug_table.add_column("Revenue",  justify="right")
        sug_table.add_column("Urgency",  justify="center")

        for s in suggestions[:5]:
            urg_color = (
                "red"    if s["urgency"] == "IMMEDIATE" else
                "yellow" if s["urgency"] == "HIGH" else
                "cyan"
            )
            sug_table.add_row(
                s["from_zone_name"],
                s["to_zone_name"],
                s["vehicle_type"].replace("_", " "),
                str(s["idle_count"]),
                f"{s['to_demand_mult']:.2f}x",
                f"₹{s['expected_revenue_inr']:,.0f}",
                f"[{urg_color}]{s['urgency']}[/{urg_color}]",
            )
        console.print(sug_table)
    else:
        console.print(
            "[yellow]No reallocation suggestions "
            "at current hour — try different time[/yellow]"
        )

    # ── Fleet summary ───────────────────────────────────
    summary_table = Table(title="Fleet Efficiency Summary")
    summary_table.add_column("Metric",  style="cyan")
    summary_table.add_column("Value",   style="green")
    summary_table.add_column("Status",  justify="center")

    util_pct = summary["overall_utilisation"] * 100
    dead_pct = summary["total_dead_mile_rate"] * 100

    summary_table.add_row(
        "Overall utilisation",
        f"{util_pct:.1f}%",
        "✅" if util_pct > 60 else "⚠️"
    )
    summary_table.add_row(
        "Dead mile rate",
        f"{dead_pct:.1f}%",
        "✅" if dead_pct < 20 else "⚠️"
    )
    summary_table.add_row(
        "Dead mile cost/day",
        f"₹{summary['total_dead_cost_per_day']:,.0f}",
        "—"
    )
    summary_table.add_row(
        "Annual dead cost",
        f"₹{summary['annual_dead_cost_estimate']/1e5:.1f}L",
        "—"
    )
    summary_table.add_row(
        "Idle vehicles now",
        str(summary["idle_vehicle_hours_now"]),
        "—"
    )
    summary_table.add_row(
        "Reallocation opportunity",
        f"₹{summary['reallocation_opportunity_inr']:,.0f}",
        "✅" if summary[
            "reallocation_opportunity_inr"
        ] > 0 else "—"
    )
    summary_table.add_row(
        "Active suggestions",
        str(summary["active_suggestions"]),
        "—"
    )
    summary_table.add_row(
        "Worst efficiency zone",
        summary["worst_efficiency_zone"],
        "—"
    )
    console.print(summary_table)

    console.print(
        "\n[green bold]✅ route_efficiency.py "
        "— all checks passed[/green bold]"
    )
