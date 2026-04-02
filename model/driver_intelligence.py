"""
Porter Intelligence Platform — Driver Intelligence Engine

Computes comprehensive risk profiles for individual drivers.
Designed to replace the manual driver review process that
Porter's ops team performed before the restructuring.

Three core outputs per driver:
  1. Risk timeline:      30-day daily fraud probability trend
  2. Peer comparison:    driver metrics vs zone median
  3. Ring intelligence:  ring membership and coordination data
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table

from generator.config import RANDOM_SEED
from generator.cities import ZONES

console = Console()


def compute_risk_timeline(
    driver_id: str,
    trips_df: pd.DataFrame,
    window_days: int = 30,
) -> List[Dict]:
    """
    Compute daily fraud risk score for a driver
    over the last window_days days.

    For each day:
      - Count trips that day
      - Count fraud trips that day
      - Compute rolling 3-day fraud rate
      - Assign risk level

    Returns list of {date, trips, fraud_count,
                     fraud_rate, risk_level, risk_score}
    sorted oldest to newest.

    Risk score formula:
      base = fraud_rate x 10
      boost if any fake_cancellation: +0.3
      boost if any cash_extortion: +0.4
      clipped to [0.0, 1.0]
    """
    driver_trips = trips_df[
        trips_df["driver_id"] == driver_id
    ].copy()

    if driver_trips.empty:
        return []

    driver_trips["requested_at"] = pd.to_datetime(
        driver_trips["requested_at"], format="mixed"
    )
    driver_trips["date"] = driver_trips["requested_at"].dt.date

    today = driver_trips["requested_at"].max().date()
    start = today - timedelta(days=window_days - 1)

    # Build daily stats
    daily = (
        driver_trips.groupby("date")
        .agg(
            trips       = ("trip_id", "count"),
            fraud_count = ("is_fraud", "sum"),
            has_cancel_fraud = (
                "fraud_type",
                lambda x: (x == "fake_cancellation").any()
            ),
            has_extortion = (
                "fraud_type",
                lambda x: (x == "cash_extortion").any()
            ),
        )
        .reset_index()
    )

    # Fill missing days with zeros
    date_range = pd.date_range(start=start, end=today, freq="D")
    full_dates = pd.DataFrame({"date": date_range.date})
    daily = full_dates.merge(daily, on="date", how="left").fillna(0)

    daily["fraud_rate"] = (
        daily["fraud_count"] / daily["trips"].clip(lower=1)
    )

    # 3-day rolling fraud rate (smoother trend line)
    daily["fraud_rate_rolling"] = (
        daily["fraud_rate"]
        .rolling(3, min_periods=1)
        .mean()
    )

    # Risk score
    def risk_score(row):
        score = row["fraud_rate_rolling"] * 10
        if row["has_cancel_fraud"]:
            score += 0.3
        if row["has_extortion"]:
            score += 0.4
        return float(np.clip(score, 0.0, 1.0))

    daily["risk_score"] = daily.apply(risk_score, axis=1)

    daily["risk_level"] = daily["risk_score"].apply(
        lambda s:
        "CRITICAL" if s > 0.7 else
        "HIGH"     if s > 0.4 else
        "MEDIUM"   if s > 0.2 else
        "LOW"
    )

    return [
        {
            "date":               str(row["date"]),
            "trips":              int(row["trips"]),
            "fraud_count":        int(row["fraud_count"]),
            "fraud_rate":         round(float(row["fraud_rate"]), 4),
            "fraud_rate_rolling": round(
                float(row["fraud_rate_rolling"]), 4
            ),
            "risk_score":         round(float(row["risk_score"]), 4),
            "risk_level":         row["risk_level"],
        }
        for _, row in daily.iterrows()
    ]


def compute_peer_comparison(
    driver_id: str,
    trips_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
) -> Dict:
    """
    Compare this driver's metrics against the median
    driver in the same zone.

    Metrics compared:
      fraud_rate:        driver vs zone median
      cancellation_rate: driver vs zone median
      cash_trip_ratio:   driver vs zone median
      avg_fare:          driver vs zone median (higher = suspicious)
      trips_per_day:     driver vs zone median
    """
    # Get driver's zone
    driver_row = drivers_df[
        drivers_df["driver_id"] == driver_id
    ]
    if driver_row.empty:
        return {}

    driver_zone = driver_row["zone_id"].iloc[0]

    # Get all trips for this driver
    driver_trips = trips_df[
        trips_df["driver_id"] == driver_id
    ]
    if driver_trips.empty:
        return {}

    # Get all trips for drivers in same zone
    zone_driver_ids = drivers_df[
        drivers_df["zone_id"] == driver_zone
    ]["driver_id"].values

    zone_trips = trips_df[
        trips_df["driver_id"].isin(zone_driver_ids)
    ]

    # Compute per-driver stats for zone
    def driver_stats(df):
        total = len(df)
        if total == 0:
            return None
        return {
            "fraud_rate":    df["is_fraud"].mean(),
            "cancel_rate":   df["status"].isin(
                ["cancelled_by_driver"]
            ).mean(),
            "cash_ratio":    (df["payment_mode"] == "cash").mean(),
            "avg_fare":      df["fare_inr"].mean(),
            "trips_per_day": total / max(
                (
                    pd.to_datetime(df["requested_at"]).dt.date.nunique()
                ), 1
            ),
        }

    this_stats = driver_stats(driver_trips)
    zone_stats_per_driver = {}

    for did in zone_driver_ids[:200]:  # cap for performance
        d_trips = zone_trips[zone_trips["driver_id"] == did]
        s = driver_stats(d_trips)
        if s:
            zone_stats_per_driver[did] = s

    if not zone_stats_per_driver or not this_stats:
        return {}

    zone_df = pd.DataFrame(zone_stats_per_driver).T

    def percentile_rank(value, series):
        """What percentage of drivers are below this value."""
        return float(
            (series <= value).mean() * 100
        )

    from generator.cities import ZONES as ZONE_DATA
    zone_name = ZONE_DATA.get(
        driver_zone,
        type('Z', (), {'name': driver_zone})()
    ).name

    return {
        "zone_id":   driver_zone,
        "zone_name": zone_name,
        "n_drivers_in_zone": len(zone_stats_per_driver),
        "metrics": {
            "fraud_rate": {
                "driver":     round(this_stats["fraud_rate"], 4),
                "zone_median": round(
                    float(zone_df["fraud_rate"].median()), 4
                ),
                "percentile": round(percentile_rank(
                    this_stats["fraud_rate"],
                    zone_df["fraud_rate"]
                ), 1),
                "flag": this_stats["fraud_rate"] > (
                    zone_df["fraud_rate"].median() * 2
                ),
            },
            "cancellation_rate": {
                "driver":     round(this_stats["cancel_rate"], 4),
                "zone_median": round(
                    float(zone_df["cancel_rate"].median()), 4
                ),
                "percentile": round(percentile_rank(
                    this_stats["cancel_rate"],
                    zone_df["cancel_rate"]
                ), 1),
                "flag": this_stats["cancel_rate"] > (
                    zone_df["cancel_rate"].median() * 2
                ),
            },
            "cash_trip_ratio": {
                "driver":     round(this_stats["cash_ratio"], 4),
                "zone_median": round(
                    float(zone_df["cash_ratio"].median()), 4
                ),
                "percentile": round(percentile_rank(
                    this_stats["cash_ratio"],
                    zone_df["cash_ratio"]
                ), 1),
                "flag": this_stats["cash_ratio"] > (
                    zone_df["cash_ratio"].median() * 2.5
                ),
            },
            "avg_fare": {
                "driver":     round(this_stats["avg_fare"], 2),
                "zone_median": round(
                    float(zone_df["avg_fare"].median()), 2
                ),
                "percentile": round(percentile_rank(
                    this_stats["avg_fare"],
                    zone_df["avg_fare"]
                ), 1),
                "flag": this_stats["avg_fare"] > (
                    zone_df["avg_fare"].median() * 1.8
                ),
            },
            "trips_per_day": {
                "driver":     round(this_stats["trips_per_day"], 2),
                "zone_median": round(
                    float(zone_df["trips_per_day"].median()), 2
                ),
                "percentile": round(percentile_rank(
                    this_stats["trips_per_day"],
                    zone_df["trips_per_day"]
                ), 1),
                "flag": False,
            },
        }
    }


def compute_ring_intelligence(
    driver_id: str,
    drivers_df: pd.DataFrame,
    trips_df: pd.DataFrame,
) -> Dict:
    """
    Compute fraud ring membership and coordination data
    for a driver.
    """
    driver_row = drivers_df[
        drivers_df["driver_id"] == driver_id
    ]
    if driver_row.empty:
        return {"is_ring_member": False}

    row = driver_row.iloc[0]

    ring_id   = row.get("fraud_ring_id")
    ring_role = row.get("ring_role")

    if pd.isna(ring_id) or ring_id is None:
        # Check if this driver has high cancellation velocity
        # that might indicate undiscovered ring membership
        driver_trips = trips_df[
            trips_df["driver_id"] == driver_id
        ]
        if not driver_trips.empty:
            cancel_trips = driver_trips[
                driver_trips["status"] == "cancelled_by_driver"
            ]
            suspected = len(cancel_trips) > 5 and (
                len(cancel_trips) / len(driver_trips) > 0.25
            )
        else:
            suspected = False

        return {
            "is_ring_member":      False,
            "ring_id":             None,
            "ring_role":           str(ring_role)
                                   if pd.notna(ring_role)
                                   else None,
            "suspected_ring":      suspected,
            "risk_multiplier":     1.0,
            "coordination_events": 0,
        }

    # Get all ring members
    ring_members_df = drivers_df[
        drivers_df["fraud_ring_id"] == ring_id
    ]
    other_members = ring_members_df[
        ring_members_df["driver_id"] != driver_id
    ]["driver_id"].tolist()

    # Count coordination events for this driver
    driver_trips = trips_df[
        trips_df["driver_id"] == driver_id
    ]
    coordination_events = 0
    if not driver_trips.empty and "ring_coordination" in driver_trips.columns:
        coordination_events = int(
            driver_trips["ring_coordination"].sum()
        )

    # Get ring zone
    ring_zone      = row.get("zone_id", "unknown")
    zone_obj       = ZONES.get(ring_zone)
    ring_zone_name = zone_obj.name if zone_obj else ring_zone

    return {
        "is_ring_member":      True,
        "ring_id":             str(ring_id),
        "ring_role":           str(ring_role)
                               if pd.notna(ring_role)
                               else "member",
        "ring_size":           len(ring_members_df),
        "ring_zone":           ring_zone,
        "ring_zone_name":      ring_zone_name,
        "other_members_count": len(other_members),
        "coordination_events": coordination_events,
        "risk_multiplier":     1.5,
        "suspected_ring":      False,
    }


def generate_recommendation(
    risk_score:   float,
    ring_intel:   Dict,
    peer_comp:    Dict,
    timeline:     List[Dict],
) -> Dict:
    """
    Generate a clear, actionable recommendation for
    Porter's ops team.

    Actions:
      SUSPEND:         risk > 0.7 OR ring leader
      FLAG_REVIEW:     risk 0.4-0.7 OR ring member
      MONITOR:         risk 0.2-0.4 OR suspected ring
      CLEAR:           risk < 0.2 and no flags
    """
    is_ring_member  = ring_intel.get("is_ring_member", False)
    ring_role       = ring_intel.get("ring_role")
    suspected_ring  = ring_intel.get("suspected_ring", False)
    coord_events    = ring_intel.get("coordination_events", 0)

    # Check for rising trend in last 7 days
    recent = timeline[-7:] if len(timeline) >= 7 else timeline
    trend_rising = (
        len(recent) >= 2
        and recent[-1]["risk_score"] > recent[0]["risk_score"] * 1.3
    )

    # Check flagged peer metrics
    flagged_metrics = []
    if peer_comp.get("metrics"):
        for metric, vals in peer_comp["metrics"].items():
            if vals.get("flag"):
                flagged_metrics.append(metric)

    # Determine action
    if ring_role == "leader" or risk_score > 0.7:
        action = "SUSPEND"
        priority = "IMMEDIATE"
        reason = (
            f"Driver is {'ring leader' if ring_role == 'leader' else 'chronic fraudster'} "
            f"with {coord_events} coordinated fraud events detected."
        )
    elif is_ring_member or risk_score > 0.4:
        action = "FLAG_REVIEW"
        priority = "HIGH"
        reason = (
            f"{'Ring member' if is_ring_member else 'High-risk driver'} "
            f"— {len(flagged_metrics)} metrics above zone median x 2."
        )
    elif suspected_ring or trend_rising or risk_score > 0.2:
        action = "MONITOR"
        priority = "MEDIUM"
        reason = (
            f"{'Rising fraud trend' if trend_rising else 'Elevated metrics'} "
            f"detected over last 7 days. Watch for escalation."
        )
    else:
        action = "CLEAR"
        priority = "LOW"
        reason = "No significant fraud indicators. Operating within normal parameters."

    return {
        "action":          action,
        "priority":        priority,
        "reason":          reason,
        "flagged_metrics": flagged_metrics,
        "trend_rising":    trend_rising,
        "auto_actionable": action in ("SUSPEND", "FLAG_REVIEW"),
    }


def get_driver_intelligence(
    driver_id:  str,
    trips_df:   pd.DataFrame,
    drivers_df: pd.DataFrame,
) -> Dict:
    """
    Full driver intelligence profile.
    Combines timeline, peer comparison, ring intel,
    and recommendation into one response.

    This is the output of GET /intelligence/driver/{id}
    """
    # Overall risk score (latest rolling value)
    timeline = compute_risk_timeline(driver_id, trips_df)
    current_risk = (
        timeline[-1]["risk_score"]
        if timeline else 0.0
    )

    peer_comp  = compute_peer_comparison(
        driver_id, trips_df, drivers_df
    )
    ring_intel = compute_ring_intelligence(
        driver_id, drivers_df, trips_df
    )

    # Apply ring multiplier
    risk_multiplier = ring_intel.get("risk_multiplier", 1.0)
    final_risk = float(
        np.clip(current_risk * risk_multiplier, 0.0, 1.0)
    )

    risk_level = (
        "CRITICAL" if final_risk > 0.7 else
        "HIGH"     if final_risk > 0.4 else
        "MEDIUM"   if final_risk > 0.2 else
        "LOW"
    )

    recommendation = generate_recommendation(
        final_risk, ring_intel, peer_comp, timeline
    )

    # Summary stats
    driver_trips = trips_df[trips_df["driver_id"] == driver_id]
    total_trips  = len(driver_trips)
    fraud_trips  = int(driver_trips["is_fraud"].sum()) \
                   if not driver_trips.empty else 0

    return {
        "driver_id":          driver_id,
        "total_trips":        total_trips,
        "fraud_trips":        fraud_trips,
        "fraud_rate":         round(
            fraud_trips / max(total_trips, 1), 4
        ),
        "current_risk_score": round(final_risk, 4),
        "risk_level":         risk_level,
        "timeline":           timeline,
        "peer_comparison":    peer_comp,
        "ring_intelligence":  ring_intel,
        "recommendation":     recommendation,
        "generated_at":       datetime.now().isoformat(),
    }


if __name__ == "__main__":
    console.rule("[cyan]Driver Intelligence — Validation[/cyan]")

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
        n=8000, city_filter="bangalore",
    )
    trips_df = inject_fraud(trips_df, drivers_df)

    # Find a high-risk driver
    fraud_by_driver = (
        trips_df[trips_df["is_fraud"]]
        .groupby("driver_id")["trip_id"]
        .count()
        .nlargest(1)
    )

    if len(fraud_by_driver) == 0:
        console.print("[yellow]No fraud trips found — try larger n[/yellow]")
        exit(1)

    test_driver_id = fraud_by_driver.index[0]
    console.print(
        f"[dim]Testing with high-risk driver: "
        f"{test_driver_id[:12]}...[/dim]"
    )

    profile = get_driver_intelligence(
        test_driver_id, trips_df, drivers_df
    )

    # ── Assertions ──────────────────────────────────────
    assert "timeline" in profile, "Missing timeline"
    assert "peer_comparison" in profile, "Missing peer comparison"
    assert "ring_intelligence" in profile, "Missing ring intelligence"
    assert "recommendation" in profile, "Missing recommendation"
    assert len(profile["timeline"]) > 0, "Empty timeline"
    assert profile["recommendation"]["action"] in [
        "SUSPEND", "FLAG_REVIEW", "MONITOR", "CLEAR"
    ], "Invalid recommendation action"

    # ── Timeline table ──────────────────────────────────
    tl_table = Table(
        title=f"30-day Risk Timeline — {test_driver_id[:12]}..."
    )
    tl_table.add_column("Date",        style="dim")
    tl_table.add_column("Trips",       justify="right")
    tl_table.add_column("Fraud",       justify="right")
    tl_table.add_column("Risk Score",  justify="right")
    tl_table.add_column("Level",       justify="center")

    for day in profile["timeline"][-10:]:  # show last 10 days
        color = (
            "red"    if day["risk_level"] == "CRITICAL" else
            "yellow" if day["risk_level"] == "HIGH" else
            "cyan"   if day["risk_level"] == "MEDIUM" else
            "green"
        )
        tl_table.add_row(
            day["date"],
            str(day["trips"]),
            str(day["fraud_count"]),
            f"[{color}]{day['risk_score']:.3f}[/{color}]",
            f"[{color}]{day['risk_level']}[/{color}]",
        )
    console.print(tl_table)

    # ── Peer comparison table ───────────────────────────
    if profile["peer_comparison"].get("metrics"):
        pc_table = Table(title="Peer Comparison vs Zone Median")
        pc_table.add_column("Metric",      style="cyan")
        pc_table.add_column("Driver",      justify="right")
        pc_table.add_column("Zone Median", justify="right")
        pc_table.add_column("Percentile",  justify="right")
        pc_table.add_column("Flag",        justify="center")

        for metric, vals in profile[
            "peer_comparison"
        ]["metrics"].items():
            flagged = vals.get("flag", False)
            pc_table.add_row(
                metric.replace("_", " ").title(),
                str(vals["driver"]),
                str(vals["zone_median"]),
                f"{vals['percentile']:.0f}th",
                "[red]FLAG[/red]" if flagged else "ok",
            )
        console.print(pc_table)

    # ── Recommendation ──────────────────────────────────
    rec = profile["recommendation"]
    rec_color = (
        "red"    if rec["action"] == "SUSPEND" else
        "yellow" if rec["action"] == "FLAG_REVIEW" else
        "cyan"   if rec["action"] == "MONITOR" else
        "green"
    )
    console.print(
        f"\n[{rec_color}]Recommendation: "
        f"{rec['action']} ({rec['priority']})[/{rec_color}]"
    )
    console.print(f"Reason: {rec['reason']}")

    # ── Summary ─────────────────────────────────────────
    summary = Table(title="Driver Intelligence Summary")
    summary.add_column("Metric",  style="cyan")
    summary.add_column("Value",   style="green")
    summary.add_row(
        "Timeline days",    str(len(profile["timeline"]))
    )
    summary.add_row(
        "Current risk",
        f"{profile['current_risk_score']:.4f} "
        f"({profile['risk_level']})"
    )
    summary.add_row(
        "Ring member",
        str(profile["ring_intelligence"]["is_ring_member"])
    )
    summary.add_row(
        "Peer metrics flagged",
        str(len(rec["flagged_metrics"]))
    )
    summary.add_row(
        "Recommendation",
        rec["action"]
    )
    summary.add_row(
        "Auto-actionable",
        "yes" if rec["auto_actionable"] else "—"
    )
    console.print(summary)

    console.print(
        "\n[green bold]driver_intelligence.py "
        "— all checks passed[/green bold]"
    )
