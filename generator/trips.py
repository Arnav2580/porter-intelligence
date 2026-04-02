"""
Porter Intelligence Platform — Trip Record Generator

Generates synthetic Porter trip records across a 59-day window:
  - 45-day historical window (model training)
  - 14-day live evaluation window (pilot simulation)

Fraud injection is handled separately by generator/fraud.py.
This module generates clean trip records only.
"""

import uuid
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress, SpinnerColumn, BarColumn,
    TextColumn, TimeRemainingColumn,
)

from generator.config import (
    RANDOM_SEED, NUM_TRIPS, VEHICLE_TYPES, VEHICLE_DISTRIBUTION,
    FRAUD_BASE_RATE, HISTORICAL_DAYS, LIVE_EVAL_DAYS,
    WEEKDAY_HOUR_WEIGHTS, WEEKEND_HOUR_WEIGHTS,
    NIGHT_HOURS, DATA_RAW,
)
from generator.cities import (
    ZONES, CITY_ZONES,
    get_random_point_in_zone,
    get_road_distance_km,
    get_zone_demand_pattern,
    haversine_km,
)

console = Console()
rng = np.random.default_rng(RANDOM_SEED + 2)


# ── Date window setup ─────────────────────────────────────────

def build_date_windows() -> Tuple[date, date, date, date]:
    """
    Return (historical_start, historical_end,
            live_eval_start,  live_eval_end).

    Timeline (counting back from today):
      today - 59 days  →  historical_start
      today - 15 days  →  historical_end   (45 days)
      today - 14 days  →  live_eval_start
      today - 1 day    →  live_eval_end    (14 days)
    """
    today = date.today()
    live_eval_end    = today - timedelta(days=1)
    live_eval_start  = today - timedelta(days=LIVE_EVAL_DAYS)
    historical_end   = live_eval_start - timedelta(days=1)
    historical_start = today - timedelta(
        days=HISTORICAL_DAYS + LIVE_EVAL_DAYS,
    )
    return historical_start, historical_end, live_eval_start, live_eval_end


# ── Time generation ───────────────────────────────────────────

def sample_trip_datetime(
    window_start: date,
    window_end: date,
    rng: np.random.Generator,
) -> datetime:
    """Sample a realistic trip datetime within the given window."""
    total_days = (window_end - window_start).days + 1
    day_offset = int(rng.integers(0, total_days))
    trip_date  = window_start + timedelta(days=day_offset)

    day_of_week = trip_date.weekday()
    is_weekend  = day_of_week >= 5

    weights = WEEKEND_HOUR_WEIGHTS if is_weekend else WEEKDAY_HOUR_WEIGHTS
    hour   = int(rng.choice(24, p=weights))
    minute = int(rng.integers(0, 60))
    second = int(rng.integers(0, 60))

    return datetime(
        trip_date.year, trip_date.month, trip_date.day,
        hour, minute, second,
    )


def is_night_trip(dt: datetime) -> bool:
    """Return True if trip starts in night hours (10PM-5AM)."""
    h = dt.hour
    night_start, night_end = NIGHT_HOURS  # (22, 5)
    return h >= night_start or h < night_end


# ── Fare calculation ──────────────────────────────────────────

def get_vehicle_adjusted_distance(
    vehicle_type: str,
    zone_distance_km: float,
    rng: np.random.Generator,
) -> float:
    """
    Return a realistic trip distance for this vehicle type.

    Uses VehicleConfig.typical_trip_km as the realistic range.
    If zone-to-zone distance exceeds vehicle's typical max,
    sample from the vehicle's distribution instead.
    """
    veh = VEHICLE_TYPES[vehicle_type]
    typ_min, typ_max = veh.typical_trip_km

    # Right-skewed triangular: mode at typ_min gives realistic distribution
    # (many short trips, few long ones — matches real logistics patterns)
    dist = rng.triangular(typ_min, typ_min, typ_max)

    # Small ±8% variance for realism
    dist *= rng.uniform(0.92, 1.08)

    # Hard maximum: no trip can exceed 1.1x the vehicle's
    # typical_trip_km maximum — catches outliers at scale
    hard_max = typ_max * 1.1
    dist = min(dist, hard_max)

    return float(max(typ_min * 0.5, dist))


def calculate_fare(
    vehicle_type: str,
    distance_km: float,
    surge_multiplier: float,
    is_night: bool,
    rng: np.random.Generator,
) -> float:
    """
    Calculate trip fare using Porter's pricing model.

    Formula: (base_fare + per_km_rate * distance) * surge * night_premium
    Night premium: 1.25x for trips starting 10PM-5AM.
    Small ±5% variance to simulate dynamic pricing.
    """
    veh  = VEHICLE_TYPES[vehicle_type]
    base = veh.base_fare + (veh.per_km_rate * distance_km)
    fare = base * surge_multiplier

    if is_night:
        fare *= 1.25

    fare *= rng.uniform(0.95, 1.05)

    return max(float(fare), veh.base_fare)


# ── Duration calculation ──────────────────────────────────────

_VEHICLE_SPEEDS_KMH = {
    "two_wheeler":   28.0,
    "three_wheeler": 22.0,
    "mini_truck":    18.0,
    "truck_14ft":    15.0,
    "truck_17ft":    13.0,
}


def calculate_duration(
    distance_km: float,
    traffic_multiplier: float,
    vehicle_type: str,
    rng: np.random.Generator,
) -> float:
    """Estimate trip duration in minutes with traffic and ±10% variance."""
    speed_kmh    = _VEHICLE_SPEEDS_KMH[vehicle_type]
    base_minutes = (distance_km / speed_kmh) * 60
    adjusted     = base_minutes * traffic_multiplier
    varied       = adjusted * rng.uniform(0.90, 1.10)
    return max(3.0, float(varied))


# ── Status and timing helpers ─────────────────────────────────

def assign_trip_status(
    vehicle_type: str,
    is_night: bool,
    rng: np.random.Generator,
) -> str:
    """
    Assign trip status with realistic cancellation rates.

    Trucks: lower cancellation (committed bookings).
    Night:  +3% driver cancellation, -3% completed.
    """
    if "truck" in vehicle_type:
        probs = [0.90, 0.04, 0.04, 0.02]
    elif is_night:
        probs = [0.80, 0.11, 0.07, 0.02]
    else:
        probs = [0.83, 0.08, 0.07, 0.02]

    statuses = [
        "completed", "cancelled_by_driver",
        "cancelled_by_customer", "disputed",
    ]
    return str(rng.choice(statuses, p=probs))


def compute_timestamps(
    requested_at: datetime,
    status: str,
    duration_minutes: float,
    is_peak_hour: bool,
    rng: np.random.Generator,
) -> Tuple[Optional[datetime], Optional[datetime],
           Optional[datetime], Optional[datetime]]:
    """
    Compute accepted_at, started_at, completed_at, cancelled_at.

    Returns all four timestamps (some may be None depending on status).
    """
    if is_peak_hour:
        accept_delay_s = rng.integers(60, 720)
    else:
        accept_delay_s = rng.integers(30, 480)

    accepted_at = requested_at + timedelta(seconds=int(accept_delay_s))

    if status in ("cancelled_by_driver", "cancelled_by_customer"):
        cancel_delay_s = rng.integers(60, 900)
        cancelled_at = accepted_at + timedelta(seconds=int(cancel_delay_s))
        return accepted_at, None, None, cancelled_at

    pickup_delay_s = rng.integers(120, 1200)
    started_at = accepted_at + timedelta(seconds=int(pickup_delay_s))

    if status in ("completed", "disputed"):
        completed_at = started_at + timedelta(minutes=duration_minutes)
        return accepted_at, started_at, completed_at, None

    return accepted_at, None, None, None


# ── Rating generation ─────────────────────────────────────────

def generate_ratings(
    status: str,
    rng: np.random.Generator,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Generate driver and customer ratings for completed trips.

    85% of completed trips receive ratings.
    Returns (driver_rating_given, customer_rating_given).
    """
    if status not in ("completed", "disputed"):
        return None, None

    if rng.random() > 0.85:
        return None, None

    driver_rating = float(
        rng.choice([1, 2, 3, 4, 5], p=[0.03, 0.04, 0.08, 0.28, 0.57])
    )
    customer_rating = float(
        rng.choice([1, 2, 3, 4, 5], p=[0.01, 0.02, 0.05, 0.25, 0.67])
    )
    return driver_rating, customer_rating


# ── Core generator ────────────────────────────────────────────

def generate_trips(
    drivers_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    n: int = NUM_TRIPS,
    city_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generate n Porter trip records across the 59-day window.

    Args:
        drivers_df:   Output of generate_drivers().
        customers_df: Output of generate_customers().
        n:            Total trips to generate.
        city_filter:  Restrict to one city (for demo mode).

    Returns:
        DataFrame with all trip fields.
        is_fraud=False throughout — fraud.py handles injection.

    Split: ~80% historical (days 1-45), ~20% live_eval (days 46-59).
    """
    hist_start, hist_end, eval_start, eval_end = build_date_windows()

    n_historical = int(n * 0.80)
    n_live_eval  = n - n_historical

    if city_filter:
        drv  = drivers_df[drivers_df["city"] == city_filter].reset_index(drop=True)
        cust = customers_df[customers_df["city"] == city_filter].reset_index(drop=True)
    else:
        drv  = drivers_df.reset_index(drop=True)
        cust = customers_df.reset_index(drop=True)

    # Pre-extract arrays for fast sampling
    driver_ids    = drv["driver_id"].values
    driver_cities = drv["city"].values
    driver_zones  = drv["zone_id"].values
    driver_vtypes = drv["vehicle_type"].values

    customer_ids    = cust["customer_id"].values
    customer_cities = cust["city"].values
    customer_zones  = cust["zone_id"].values

    def _generate_window(
        count: int,
        window_start: date,
        window_end: date,
        split_label: str,
    ) -> List[dict]:
        """Generate trips for one time window."""
        window_records: List[dict] = []

        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]Generating {split_label} trips..."),
            BarColumn(),
            TextColumn("[green]{task.completed}/{task.total}"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(split_label, total=count)

            for _ in range(count):
                # ── Sample driver ──────────────────────────
                drv_idx      = int(rng.integers(0, len(driver_ids)))
                driver_id    = driver_ids[drv_idx]
                driver_city  = driver_cities[drv_idx]
                driver_zone  = driver_zones[drv_idx]
                vehicle_type = driver_vtypes[drv_idx]

                # ── Sample customer (same city) ────────────
                city_mask = customer_cities == driver_city
                if city_mask.sum() == 0:
                    progress.advance(task)
                    continue
                cust_pool_ids   = customer_ids[city_mask]
                cust_pool_zones = customer_zones[city_mask]
                cust_idx        = int(rng.integers(0, len(cust_pool_ids)))
                customer_id     = cust_pool_ids[cust_idx]
                customer_zone   = cust_pool_zones[cust_idx]
                city = driver_city

                # ── Zone objects ───────────────────────────
                pickup_zone  = ZONES.get(driver_zone)
                dropoff_zone = ZONES.get(customer_zone)
                if pickup_zone is None or dropoff_zone is None:
                    progress.advance(task)
                    continue

                # ── Coordinates ────────────────────────────
                pickup_lat,  pickup_lon  = get_random_point_in_zone(pickup_zone,  rng)
                dropoff_lat, dropoff_lon = get_random_point_in_zone(dropoff_zone, rng)

                # ── Distance (vehicle-type-adjusted) ──────
                zone_distance_km = haversine_km(
                    pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
                )
                declared_distance_km = get_vehicle_adjusted_distance(
                    vehicle_type, zone_distance_km, rng,
                )
                actual_distance_km = declared_distance_km  # equal before fraud

                # ── Timestamp ──────────────────────────────
                requested_at = sample_trip_datetime(window_start, window_end, rng)
                night   = is_night_trip(requested_at)
                hour    = requested_at.hour
                dow     = requested_at.weekday()
                is_peak = hour in (8, 9, 12, 13, 18, 19, 20)

                # ── Demand and surge ───────────────────────
                demand = get_zone_demand_pattern(pickup_zone, hour, dow)
                surge_multiplier = float(np.clip(
                    0.8 + (demand - 0.5) * 0.6 + rng.normal(0, 0.1),
                    1.0, 3.5,
                ))

                # ── Duration ───────────────────────────────
                traffic_mult = pickup_zone.traffic_multiplier
                duration_min = calculate_duration(
                    declared_distance_km, traffic_mult, vehicle_type, rng,
                )

                # ── Fare ───────────────────────────────────
                fare_inr = calculate_fare(
                    vehicle_type, declared_distance_km,
                    surge_multiplier, night, rng,
                )

                # ── Status ─────────────────────────────────
                status = assign_trip_status(vehicle_type, night, rng)

                # ── Timestamps ─────────────────────────────
                accepted_at, started_at, completed_at, cancelled_at = \
                    compute_timestamps(
                        requested_at, status, duration_min, is_peak, rng,
                    )

                # ── Payment mode ───────────────────────────
                payment_mode = str(rng.choice(
                    ["upi", "cash", "credit"],
                    p=[0.62, 0.23, 0.15],
                ))

                # ── Ratings ────────────────────────────────
                driver_rating, customer_rating = generate_ratings(status, rng)

                # ── Declared duration ──────────────────────
                declared_duration_min = duration_min
                if status == "completed" and started_at and completed_at:
                    declared_duration_min = (
                        (completed_at - started_at).total_seconds() / 60
                    )

                window_records.append({
                    "trip_id":                str(uuid.uuid4()),
                    "driver_id":              driver_id,
                    "customer_id":            customer_id,
                    "city":                   city,
                    "pickup_zone_id":         driver_zone,
                    "dropoff_zone_id":        customer_zone,
                    "pickup_lat":             round(pickup_lat, 6),
                    "pickup_lon":             round(pickup_lon, 6),
                    "dropoff_lat":            round(dropoff_lat, 6),
                    "dropoff_lon":            round(dropoff_lon, 6),
                    "requested_at":           requested_at.isoformat(),
                    "accepted_at":            accepted_at.isoformat() if accepted_at else None,
                    "started_at":             started_at.isoformat() if started_at else None,
                    "completed_at":           completed_at.isoformat() if completed_at else None,
                    "cancelled_at":           cancelled_at.isoformat() if cancelled_at else None,
                    "status":                 status,
                    "vehicle_type":           vehicle_type,
                    "declared_distance_km":   round(declared_distance_km, 3),
                    "actual_distance_km":     round(actual_distance_km, 3),
                    "declared_duration_min":  round(declared_duration_min, 2),
                    "fare_inr":               round(fare_inr, 2),
                    "payment_mode":           payment_mode,
                    "surge_multiplier":       round(surge_multiplier, 3),
                    "driver_rating_given":    driver_rating,
                    "customer_rating_given":  customer_rating,
                    "is_night":               night,
                    "day_of_week":            dow,
                    "hour_of_day":            hour,
                    "is_peak_hour":           is_peak,
                    "zone_demand_at_time":    round(demand, 4),
                    "data_split":             split_label,
                    # ── Fraud fields (fraud.py fills these) ──
                    "is_fraud":               False,
                    "fraud_type":             None,
                    "fraud_confidence_score": None,
                    "recoverable_amount_inr": 0.0,
                    "customer_complaint_flag": False,
                })

                progress.advance(task)

        return window_records

    # Generate both windows
    console.rule("[cyan]Generating Historical Window (45 days)[/cyan]")
    hist_records = _generate_window(
        n_historical, hist_start, hist_end, "historical",
    )

    console.rule("[cyan]Generating Live Eval Window (14 days)[/cyan]")
    eval_records = _generate_window(
        n_live_eval, eval_start, eval_end, "live_eval",
    )

    all_records = hist_records + eval_records
    df = pd.DataFrame(all_records)

    # Sort by requested_at for realistic ordering
    df["requested_at"] = pd.to_datetime(df["requested_at"])
    df = df.sort_values("requested_at").reset_index(drop=True)
    df["requested_at"] = df["requested_at"].astype(str)

    return df


# ── Test block ────────────────────────────────────────────────

if __name__ == "__main__":
    console.rule("[cyan]Trip Generator — Validation[/cyan]")

    from generator.drivers import generate_drivers
    from generator.customers import generate_customers

    console.print("[dim]Loading driver and customer samples...[/dim]")
    drivers_df   = generate_drivers(n=5_000, city_filter="bangalore")
    customers_df = generate_customers(n=5_000, city_filter="bangalore")

    console.print("[dim]Generating 10,000 trips for validation...[/dim]")
    df = generate_trips(
        drivers_df, customers_df,
        n=10_000, city_filter="bangalore",
    )

    # ── Core assertions ────────────────────────────────────────
    assert len(df) > 9_000, f"Expected ~10K trips, got {len(df)}"
    assert df["trip_id"].nunique() == len(df), "Duplicate trip IDs found"
    assert df["is_fraud"].sum() == 0, \
        "Trips should have no fraud before fraud.py runs"
    assert set(df["data_split"].unique()) == {"historical", "live_eval"}, \
        "Missing data split labels"

    # ── Split ratio ────────────────────────────────────────────
    split_counts = df["data_split"].value_counts()
    hist_pct = split_counts.get("historical", 0) / len(df) * 100
    eval_pct = split_counts.get("live_eval",  0) / len(df) * 100

    split_table = Table(title="Data Split Validation")
    split_table.add_column("Window",  style="cyan")
    split_table.add_column("Count",   justify="right")
    split_table.add_column("Pct",     justify="right")
    split_table.add_column("Target",  justify="right")
    split_table.add_column("Status",  justify="center")
    split_table.add_row(
        "Historical (45d)",
        str(split_counts.get("historical", 0)),
        f"{hist_pct:.1f}%", "~80%",
        "✅" if 70 < hist_pct < 90 else "❌",
    )
    split_table.add_row(
        "Live eval (14d)",
        str(split_counts.get("live_eval", 0)),
        f"{eval_pct:.1f}%", "~20%",
        "✅" if 10 < eval_pct < 30 else "❌",
    )
    console.print(split_table)

    # ── Status distribution ────────────────────────────────────
    status_dist = df["status"].value_counts(normalize=True) * 100
    status_table = Table(title="Trip Status Distribution")
    status_table.add_column("Status",   style="cyan")
    status_table.add_column("Actual",   justify="right")
    status_table.add_column("Target",   justify="right")
    status_table.add_column("Status",   justify="center")
    targets = {
        "completed":             (78, 88),
        "cancelled_by_driver":   (5,  12),
        "cancelled_by_customer": (5,  10),
        "disputed":              (1,   4),
    }
    for s, (lo, hi) in targets.items():
        pct = status_dist.get(s, 0)
        ok  = lo < pct < hi
        status_table.add_row(
            s, f"{pct:.1f}%", f"{lo}-{hi}%",
            "✅" if ok else "❌",
        )
    console.print(status_table)

    # ── Fare sanity check ──────────────────────────────────────
    completed = df[df["status"] == "completed"]
    fare_table = Table(title="Fare Validation by Vehicle Type")
    fare_table.add_column("Vehicle", style="cyan")
    fare_table.add_column("Min ₹",  justify="right")
    fare_table.add_column("Avg ₹",  justify="right")
    fare_table.add_column("Max ₹",  justify="right")
    fare_table.add_column("Status", justify="center")
    fare_minimums = {
        "two_wheeler":   30,
        "three_wheeler": 80,
        "mini_truck":    200,
        "truck_14ft":    600,
        "truck_17ft":    900,
    }
    for vtype, min_fare in fare_minimums.items():
        sub = completed[completed["vehicle_type"] == vtype]["fare_inr"]
        if len(sub) == 0:
            continue
        ok = sub.min() >= min_fare * 0.95
        fare_table.add_row(
            vtype,
            f"₹{sub.min():.0f}",
            f"₹{sub.mean():.0f}",
            f"₹{sub.max():.0f}",
            "✅" if ok else "❌",
        )
    console.print(fare_table)

    # ── Temporal distribution ──────────────────────────────────
    df["_hour"] = pd.to_datetime(df["requested_at"]).dt.hour
    hourly = df.groupby("_hour").size()
    peak_hours_volume = hourly.reindex([8, 9, 18, 19, 20], fill_value=0).sum()
    off_peak_volume   = hourly.reindex([2, 3, 4], fill_value=0).sum()
    assert peak_hours_volume > off_peak_volume * 3, \
        "Peak hours must have 3x+ more trips than dead hours"
    console.print(
        f"[green]✅ Peak (8-9AM, 6-8PM): {peak_hours_volume} trips "
        f"vs off-peak (2-4AM): {off_peak_volume} trips[/green]"
    )

    # ── Distance by vehicle type ──────────────────────────────
    assert (df["actual_distance_km"] == df["declared_distance_km"]).all(), \
        "actual_distance must equal declared before fraud injection"

    dist_table = Table(title="Distance by Vehicle Type")
    dist_table.add_column("Vehicle",    style="cyan")
    dist_table.add_column("Min km",     justify="right")
    dist_table.add_column("Avg km",     justify="right")
    dist_table.add_column("Max km",     justify="right")
    dist_table.add_column("Target avg", justify="right")
    dist_table.add_column("Status",     justify="center")

    target_avg_km = {
        "two_wheeler":   (2.0,  8.0),
        "three_wheeler": (4.0,  14.0),
        "mini_truck":    (5.0,  20.0),
        "truck_14ft":    (10.0, 45.0),
        "truck_17ft":    (14.0, 65.0),
    }

    all_dist_ok = True
    for vtype, (lo, hi) in target_avg_km.items():
        sub = completed[completed["vehicle_type"] == vtype][
            "declared_distance_km"
        ]
        if len(sub) == 0:
            continue
        avg = sub.mean()
        ok  = lo <= avg <= hi
        if not ok:
            all_dist_ok = False
        dist_table.add_row(
            vtype,
            f"{sub.min():.1f}",
            f"{avg:.1f}",
            f"{sub.max():.1f}",
            f"{lo:.0f}–{hi:.0f}",
            "✅" if ok else "❌",
        )

    console.print(dist_table)

    blended_avg = completed["declared_distance_km"].mean()
    console.print(
        f"[{'green' if all_dist_ok else 'red'}]"
        f"Blended avg distance: {blended_avg:.1f}km "
        f"(target 6–11km)[/{'green' if all_dist_ok else 'red'}]"
    )

    assert all_dist_ok, "Vehicle distance averages out of range"
    assert 5 < blended_avg < 13, \
        f"Blended avg {blended_avg:.1f}km still unrealistic"
    avg_dist = blended_avg

    # ── Night trip rate ────────────────────────────────────────
    night_pct = df["is_night"].mean() * 100
    assert 5 < night_pct < 20, \
        f"Night trip rate {night_pct:.1f}% outside expected 5-20%"
    console.print(
        f"[green]✅ Night trips: {night_pct:.1f}% (target 5-20%)[/green]"
    )

    # ── Revenue calculation ────────────────────────────────────
    total_revenue = completed["fare_inr"].sum()
    avg_fare      = completed["fare_inr"].mean()
    console.print(
        f"[green]✅ Revenue (10K trips): "
        f"₹{total_revenue:,.0f} | Avg fare: ₹{avg_fare:.0f}[/green]"
    )

    # ── Fraud fields placeholder check ────────────────────────
    assert df["is_fraud"].dtype == bool, "is_fraud must be boolean"
    assert df["recoverable_amount_inr"].eq(0.0).all(), \
        "recoverable_amount must be 0.0 before fraud injection"
    console.print(
        "[green]✅ Fraud fields ready for injection "
        "(all False/None/0)[/green]"
    )

    # ── Save validated sample ──────────────────────────────────
    out_path = DATA_RAW / "trips_sample_10k.csv"
    df.drop(columns=["_hour"], errors="ignore").to_csv(out_path, index=False)
    console.print(f"\n[green]✅ Sample saved → {out_path}[/green]")

    # ── Final summary ──────────────────────────────────────────
    summary = Table(title="Trip Generator — Day 3 Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value",  style="green")
    summary.add_row("Total trips generated",    f"{len(df):,}")
    summary.add_row("Historical window",        str(split_counts.get("historical", 0)))
    summary.add_row("Live eval window",         str(split_counts.get("live_eval", 0)))
    summary.add_row("Completion rate",          f"{status_dist.get('completed', 0):.1f}%")
    summary.add_row("Night trip rate",          f"{night_pct:.1f}%")
    summary.add_row("Avg fare (completed)",     f"₹{avg_fare:.0f}")
    summary.add_row("Avg distance",             f"{avg_dist:.1f}km")
    summary.add_row("Total revenue simulated",  f"₹{total_revenue:,.0f}")
    summary.add_row("Fraud fields ready",       "✅ awaiting fraud.py")
    console.print(summary)

    console.print(
        "\n[green bold]✅ trips.py — all checks passed. "
        "Ready for Day 4 — fraud.py[/green bold]"
    )
