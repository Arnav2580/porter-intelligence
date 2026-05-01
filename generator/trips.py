"""
Porter Intelligence Platform — Trip Record Generator v2

Key fixes from v1:
  - Duration derived from distance/speed (fixes 1819 km/hr bug)
  - 15 new schema fields: driver_arrived_at, otp_verified, loading_time,
    gps_ping_count, gps_accuracy_avg_m, mock_location_flag, goods_category,
    goods_weight_kg, floor_pickup, floor_dropoff, toll_charge_inr,
    waiting_time_mins, pod_photo_captured, cancellation_at_stage
  - Removed fraud_confidence_score (model output, not input)
  - Timestamps are all consistently derived (no independent generation)
"""

import uuid
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from generator.config import (
    RANDOM_SEED, NUM_TRIPS, VEHICLE_TYPES, VEHICLE_DISTRIBUTION,
    FRAUD_BASE_RATE, HISTORICAL_DAYS, LIVE_EVAL_DAYS,
    WEEKDAY_HOUR_WEIGHTS, WEEKEND_HOUR_WEIGHTS, NIGHT_HOURS, DATA_RAW,
    CITY_AVG_SPEED_KMH, DEFAULT_SPEED_KMH, TRAFFIC_HOUR_MULTIPLIER,
    GOODS_CATEGORIES, GOODS_WEIGHT_RANGE_KG, GOODS_VEHICLE_PREFS,
    LOADING_TIME_NORMS_MIN, FLOOR_LOADING_PENALTY_MINS,
    ASSIGN_LATENCY_SEC, ACCEPT_TO_ARRIVE_MINS, WAITING_TIME_MINS,
    CANCELLATION_STAGES, CANCELLATION_STAGE_PROBS,
    TOLL_RANGE_INR, TOLL_PROBABILITY, NIGHT_PREMIUM_MULTIPLIER,
    SURGE_MIN, SURGE_MAX, CITY_CASH_PCT,
    GPS_ACCURACY_NORMAL_M, GPS_PINGS_PER_MIN_NORMAL,
)
from generator.cities import (
    ZONES, CITY_ZONES, get_random_point_in_zone,
    get_zone_demand_pattern, haversine_km,
)

console = Console()
rng = np.random.default_rng(RANDOM_SEED + 2)

WEEKDAY_HOUR_WEIGHTS = list(WEEKDAY_HOUR_WEIGHTS)
WEEKEND_HOUR_WEIGHTS = list(WEEKEND_HOUR_WEIGHTS)


def build_date_windows() -> Tuple[date, date, date, date]:
    today            = date.today()
    live_eval_end    = today - timedelta(days=1)
    live_eval_start  = today - timedelta(days=LIVE_EVAL_DAYS)
    historical_end   = live_eval_start - timedelta(days=1)
    historical_start = today - timedelta(days=HISTORICAL_DAYS + LIVE_EVAL_DAYS)
    return historical_start, historical_end, live_eval_start, live_eval_end


def sample_trip_datetime(window_start: date, window_end: date, rng) -> datetime:
    total_days  = (window_end - window_start).days + 1
    day_offset  = int(rng.integers(0, total_days))
    trip_date   = window_start + timedelta(days=day_offset)
    is_weekend  = trip_date.weekday() >= 5
    weights     = WEEKEND_HOUR_WEIGHTS if is_weekend else WEEKDAY_HOUR_WEIGHTS
    hour        = int(rng.choice(24, p=weights))
    minute      = int(rng.integers(0, 60))
    second      = int(rng.integers(0, 60))
    return datetime(trip_date.year, trip_date.month, trip_date.day, hour, minute, second)


def is_night_trip(dt: datetime) -> bool:
    h = dt.hour
    night_start, night_end = NIGHT_HOURS
    return h >= night_start or h < night_end


def sample_distance(vehicle_type: str, rng) -> float:
    veh = VEHICLE_TYPES[vehicle_type]
    lo, hi = veh.typical_trip_km
    mode = lo + (hi - lo) * 0.3
    dist = rng.triangular(lo, mode, hi)
    dist *= rng.uniform(0.92, 1.08)
    return float(max(lo * 0.5, min(dist, hi * 1.1)))


def calculate_duration(
    distance_km: float,
    vehicle_type: str,
    city: str,
    hour: int,
    rng,
) -> float:
    """
    Derive duration from distance and speed — fixing the 1819 km/hr bug.
    Duration = distance / (city_avg_speed * traffic_factor) * 60 minutes
    """
    city_speeds  = CITY_AVG_SPEED_KMH.get(city, DEFAULT_SPEED_KMH)
    base_speed   = city_speeds.get(vehicle_type, 18.0)
    traffic_mult = TRAFFIC_HOUR_MULTIPLIER[hour]   # 0.55–1.00
    effective_speed = base_speed * traffic_mult
    effective_speed = max(effective_speed, 4.0)    # floor at 4 km/hr
    base_minutes    = (distance_km / effective_speed) * 60.0
    varied          = base_minutes * rng.uniform(0.88, 1.12)
    return float(max(2.0, varied))


def calculate_fare(
    vehicle_type: str,
    distance_km: float,
    surge: float,
    is_night: bool,
    loading_charge: float,
    waiting_charge: float,
    toll_charge: float,
    rng,
) -> float:
    veh  = VEHICLE_TYPES[vehicle_type]
    base = veh.base_fare + veh.per_km_rate * distance_km
    fare = base * surge
    if is_night:
        fare *= NIGHT_PREMIUM_MULTIPLIER
    fare += loading_charge + waiting_charge + toll_charge
    fare *= rng.uniform(0.96, 1.04)
    return float(max(fare, veh.base_fare))


def sample_goods(vehicle_type: str, rng) -> Tuple[str, float, int, int]:
    """Returns (goods_category, weight_kg, floor_pickup, floor_dropoff)."""
    compatible = [
        g for g, vehs in GOODS_VEHICLE_PREFS.items()
        if vehicle_type in vehs
    ]
    if not compatible:
        compatible = GOODS_CATEGORIES
    cat    = str(rng.choice(compatible))
    lo, hi = GOODS_WEIGHT_RANGE_KG[cat]
    weight = float(rng.uniform(lo, min(hi, VEHICLE_TYPES[vehicle_type].capacity_kg)))

    # Floor distribution: 70% ground (0), 20% floor 1-2, 10% floor 3+
    draw = rng.random()
    if draw < 0.70:
        pickup_floor = 0
    elif draw < 0.90:
        pickup_floor = int(rng.integers(1, 3))
    else:
        pickup_floor = int(rng.integers(3, 7))

    dropoff_floor = 0 if rng.random() < 0.75 else int(rng.integers(0, 5))
    return cat, round(weight, 1), pickup_floor, dropoff_floor


def sample_loading_time(
    goods_category: str,
    floor_pickup: int,
    floor_dropoff: int,
    vehicle_type: str,
    rng,
) -> float:
    """Realistic loading time in minutes. 0 for 2W/3W (no loading charge)."""
    if vehicle_type in ("two_wheeler", "three_wheeler"):
        return 0.0
    p50, p75, p95 = LOADING_TIME_NORMS_MIN[goods_category]
    base = rng.triangular(p50 * 0.6, p50, p75)
    floor_penalty = (floor_pickup + floor_dropoff) * FLOOR_LOADING_PENALTY_MINS
    total = base + floor_penalty * rng.uniform(0.7, 1.3)
    return float(max(0.0, round(total, 1)))


def sample_gps_stats(duration_mins: float, rng) -> Tuple[int, float]:
    """Normal GPS: ~3 pings/min, accuracy 4–18m. Returns (ping_count, accuracy_m)."""
    expected_pings = duration_mins * GPS_PINGS_PER_MIN_NORMAL
    ping_count     = max(1, int(rng.normal(expected_pings, expected_pings * 0.15)))
    accuracy_m     = float(rng.uniform(*GPS_ACCURACY_NORMAL_M))
    return ping_count, round(accuracy_m, 1)


def assign_trip_status(vehicle_type: str, is_night: bool, rng) -> str:
    if "truck" in vehicle_type:
        probs = [0.90, 0.04, 0.04, 0.02]
    elif is_night:
        probs = [0.80, 0.11, 0.07, 0.02]
    else:
        probs = [0.83, 0.08, 0.07, 0.02]
    return str(rng.choice(
        ["completed", "cancelled_by_driver", "cancelled_by_customer", "disputed"],
        p=probs,
    ))


def compute_timestamps(
    requested_at: datetime,
    status: str,
    duration_minutes: float,
    loading_time_mins: float,
    vehicle_type: str,
    is_peak: bool,
    rng,
) -> dict:
    """
    Build all timestamps from requested_at.
    Every downstream field derives from this — no independent generation.
    """
    # 1. Assign latency
    if is_peak:
        assign_sec = int(rng.integers(*ASSIGN_LATENCY_SEC["peak"]))
    else:
        assign_sec = int(rng.integers(*ASSIGN_LATENCY_SEC["off_peak"]))
    assigned_at = requested_at + timedelta(seconds=assign_sec)

    # 2. Accept = assigned (driver sees and accepts — typically within seconds)
    accept_delay = int(rng.integers(5, 60))
    accepted_at  = assigned_at + timedelta(seconds=accept_delay)

    # Cancellation before arrival
    if status in ("cancelled_by_driver", "cancelled_by_customer"):
        cancel_stage = str(rng.choice(CANCELLATION_STAGES, p=CANCELLATION_STAGE_PROBS))
        if cancel_stage == "pre_arrive":
            cancel_sec  = int(rng.integers(30, 300))
            cancelled_at = accepted_at + timedelta(seconds=cancel_sec)
            return {
                "driver_assigned_at": assigned_at.isoformat(),
                "accepted_at":        accepted_at.isoformat(),
                "driver_arrived_at":  None,
                "otp_verified_at":    None,
                "loading_ended_at":   None,
                "trip_started_at":    None,
                "trip_completed_at":  None,
                "cancelled_at":       cancelled_at.isoformat(),
                "cancellation_at_stage": cancel_stage,
            }
        else:
            # Post-arrive cancel
            arrive_mins = float(rng.uniform(*ACCEPT_TO_ARRIVE_MINS[vehicle_type]))
            arrived_at  = accepted_at + timedelta(minutes=arrive_mins)
            cancel_sec  = int(rng.integers(60, 600))
            cancelled_at = arrived_at + timedelta(seconds=cancel_sec)
            return {
                "driver_assigned_at": assigned_at.isoformat(),
                "accepted_at":        accepted_at.isoformat(),
                "driver_arrived_at":  arrived_at.isoformat(),
                "otp_verified_at":    None,
                "loading_ended_at":   None,
                "trip_started_at":    None,
                "trip_completed_at":  None,
                "cancelled_at":       cancelled_at.isoformat(),
                "cancellation_at_stage": "post_arrive",
            }

    # Completed / disputed
    arrive_mins  = float(rng.uniform(*ACCEPT_TO_ARRIVE_MINS[vehicle_type]))
    arrived_at   = accepted_at + timedelta(minutes=arrive_mins)
    wait_mins    = float(rng.uniform(*WAITING_TIME_MINS[vehicle_type]))
    otp_at       = arrived_at + timedelta(minutes=wait_mins)
    loading_end  = otp_at + timedelta(minutes=loading_time_mins)
    started_at   = loading_end
    completed_at = started_at + timedelta(minutes=duration_minutes)

    return {
        "driver_assigned_at":    assigned_at.isoformat(),
        "accepted_at":           accepted_at.isoformat(),
        "driver_arrived_at":     arrived_at.isoformat(),
        "otp_verified_at":       otp_at.isoformat(),
        "loading_ended_at":      loading_end.isoformat() if loading_time_mins > 0 else None,
        "trip_started_at":       started_at.isoformat(),
        "trip_completed_at":     completed_at.isoformat(),
        "cancelled_at":          None,
        "cancellation_at_stage": None,
    }


def generate_trips(
    drivers_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    n: int = NUM_TRIPS,
    city_filter: Optional[str] = None,
) -> pd.DataFrame:
    hist_start, hist_end, eval_start, eval_end = build_date_windows()
    n_historical = int(n * 0.80)
    n_live_eval  = n - n_historical

    if city_filter:
        drv  = drivers_df[drivers_df["city"] == city_filter].reset_index(drop=True)
        cust = customers_df[customers_df["city"] == city_filter].reset_index(drop=True)
    else:
        drv  = drivers_df.reset_index(drop=True)
        cust = customers_df.reset_index(drop=True)

    driver_ids    = drv["driver_id"].values
    driver_cities = drv["city"].values
    driver_zones  = drv["zone_id"].values
    driver_vtypes = drv["vehicle_type"].values

    customer_ids    = cust["customer_id"].values
    customer_cities = cust["city"].values
    customer_zones  = cust["zone_id"].values

    def _generate_window(count, window_start, window_end, split_label):
        records = []
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]Generating {split_label}..."),
            BarColumn(),
            TextColumn("[green]{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task(split_label, total=count)

            for _ in range(count):
                drv_idx      = int(rng.integers(0, len(driver_ids)))
                driver_id    = driver_ids[drv_idx]
                driver_city  = driver_cities[drv_idx]
                driver_zone  = driver_zones[drv_idx]
                vehicle_type = driver_vtypes[drv_idx]

                city_mask = customer_cities == driver_city
                if city_mask.sum() == 0:
                    progress.advance(task)
                    continue
                cust_pool_ids   = customer_ids[city_mask]
                cust_pool_zones = customer_zones[city_mask]
                cust_idx        = int(rng.integers(0, len(cust_pool_ids)))
                customer_id     = cust_pool_ids[cust_idx]
                customer_zone   = cust_pool_zones[cust_idx]
                city            = driver_city

                pickup_zone  = ZONES.get(driver_zone)
                dropoff_zone = ZONES.get(customer_zone)
                if pickup_zone is None or dropoff_zone is None:
                    progress.advance(task)
                    continue

                pickup_lat,  pickup_lon  = get_random_point_in_zone(pickup_zone,  rng)
                dropoff_lat, dropoff_lon = get_random_point_in_zone(dropoff_zone, rng)
                haversine    = haversine_km(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)

                requested_at = sample_trip_datetime(window_start, window_end, rng)
                night        = is_night_trip(requested_at)
                hour         = requested_at.hour
                dow          = requested_at.weekday()
                is_peak      = hour in (8, 9, 12, 13, 18, 19, 20)
                is_weekend   = dow >= 5
                is_late_month = requested_at.day >= 25

                # Distance — vehicle-adjusted
                declared_distance_km = sample_distance(vehicle_type, rng)
                # GPS tracked distance adds road-factor noise (1.1–1.4x haversine)
                road_factor          = rng.uniform(1.15, 1.45)
                gps_tracked_km       = round(haversine * road_factor, 3)

                # Duration — derived from distance/speed (v2 physics fix)
                duration_min = calculate_duration(
                    declared_distance_km, vehicle_type, city, hour, rng
                )

                # Surge
                demand = get_zone_demand_pattern(pickup_zone, hour, dow)
                surge  = float(np.clip(
                    0.8 + (demand - 0.5) * 0.6 + rng.normal(0, 0.08),
                    SURGE_MIN, SURGE_MAX,
                ))

                # Status
                status = assign_trip_status(vehicle_type, night, rng)

                # Goods & loading
                goods_cat, goods_weight, floor_pickup, floor_dropoff = sample_goods(vehicle_type, rng)
                loading_time = sample_loading_time(
                    goods_cat, floor_pickup, floor_dropoff, vehicle_type, rng
                ) if status not in ("cancelled_by_driver", "cancelled_by_customer") else 0.0

                # Charges
                loading_charge = round(
                    loading_time * VEHICLE_TYPES[vehicle_type].per_min_rate, 2
                )
                wait_mins = float(rng.uniform(
                    *WAITING_TIME_MINS[vehicle_type]
                )) if status == "completed" else 0.0
                waiting_charge = round(
                    wait_mins * VEHICLE_TYPES[vehicle_type].per_min_rate * 0.5, 2
                )
                has_toll   = rng.random() < TOLL_PROBABILITY[vehicle_type]
                toll_lo, toll_hi = TOLL_RANGE_INR.get(city, (0, 60))
                toll_charge = round(float(rng.uniform(toll_lo, toll_hi)), 2) if has_toll else 0.0

                fare_inr = calculate_fare(
                    vehicle_type, declared_distance_km, surge, night,
                    loading_charge, waiting_charge, toll_charge, rng
                )

                # Timestamps
                ts = compute_timestamps(
                    requested_at, status, duration_min, loading_time,
                    vehicle_type, is_peak, rng
                )

                # Payment
                city_cash = CITY_CASH_PCT.get(city, 0.25)
                payment_mode = str(rng.choice(
                    ["cash", "upi", "credit"],
                    p=[
                        city_cash,
                        (1 - city_cash) * 0.75,
                        (1 - city_cash) * 0.25,
                    ],
                ))

                # GPS stats (normal for clean trips)
                gps_pings, gps_accuracy = sample_gps_stats(duration_min, rng)

                # Ratings
                driver_rating = customer_rating = None
                if status in ("completed", "disputed") and rng.random() < 0.82:
                    driver_rating   = float(rng.choice([1,2,3,4,5], p=[0.03,0.04,0.08,0.28,0.57]))
                    customer_rating = float(rng.choice([1,2,3,4,5], p=[0.01,0.02,0.05,0.25,0.67]))

                # OTP verified on completed trips
                otp_verified = status in ("completed", "disputed")
                otp_attempts = 1 if otp_verified else 0

                # POD (proof of delivery) — trucks only
                pod_captured = (
                    status == "completed"
                    and "truck" in vehicle_type
                    and rng.random() < 0.78
                )

                # Speed stats
                if status in ("completed", "disputed") and duration_min > 0:
                    avg_speed = round(declared_distance_km / (duration_min / 60), 1)
                    max_speed = round(avg_speed * rng.uniform(1.2, 1.8), 1)
                else:
                    avg_speed = max_speed = 0.0

                records.append({
                    # Identity
                    "trip_id":                    str(uuid.uuid4()),
                    "driver_id":                  driver_id,
                    "customer_id":                customer_id,
                    "city":                       city,
                    "pickup_zone_id":             driver_zone,
                    "dropoff_zone_id":            customer_zone,

                    # Coordinates
                    "pickup_lat":                 round(pickup_lat, 6),
                    "pickup_lon":                 round(pickup_lon, 6),
                    "dropoff_lat":                round(dropoff_lat, 6),
                    "dropoff_lon":                round(dropoff_lon, 6),
                    "haversine_km":               round(haversine, 3),

                    # Timestamps
                    **ts,
                    "requested_at":               requested_at.isoformat(),

                    # Route
                    "declared_distance_km":       round(declared_distance_km, 3),
                    "gps_tracked_distance_km":    gps_tracked_km,
                    "distance_vs_haversine":      round(
                        declared_distance_km / max(haversine, 0.1), 3
                    ),
                    "actual_trip_duration_mins":  round(duration_min, 2),
                    "loading_time_mins":          round(loading_time, 1),
                    "waiting_time_mins":          round(wait_mins, 1),

                    # GPS signals
                    "gps_ping_count":             gps_pings,
                    "gps_accuracy_avg_m":         gps_accuracy,
                    "avg_speed_kmh":              avg_speed,
                    "max_speed_kmh":              max_speed,
                    "mock_location_flag":         False,
                    "gps_provider":               "gps",

                    # Vehicle & goods
                    "vehicle_type":               vehicle_type,
                    "goods_category":             goods_cat,
                    "goods_weight_kg":            goods_weight,
                    "floor_pickup":               floor_pickup,
                    "floor_dropoff":              floor_dropoff,

                    # Financial
                    "base_fare_inr":              round(
                        VEHICLE_TYPES[vehicle_type].base_fare
                        + VEHICLE_TYPES[vehicle_type].per_km_rate * declared_distance_km,
                        2
                    ),
                    "loading_charge_inr":         loading_charge,
                    "waiting_charge_inr":         waiting_charge,
                    "toll_charge_inr":            toll_charge,
                    "surge_multiplier":           round(surge, 3),
                    "fare_inr":                   round(fare_inr, 2),
                    "payment_mode":               payment_mode,

                    # Status
                    "trip_status":                status,
                    "otp_verified":               otp_verified,
                    "otp_attempt_count":          otp_attempts,
                    "pod_photo_captured":         pod_captured,
                    "pod_location_match":         pod_captured,   # true for clean trips

                    # Contextual
                    "day_of_week":                dow,
                    "hour_of_day":                hour,
                    "is_night":                   night,
                    "is_peak_hour":               is_peak,
                    "is_weekend":                 is_weekend,
                    "is_late_month":              is_late_month,
                    "zone_demand_at_time":        round(demand, 4),
                    "data_split":                 split_label,

                    # Ratings
                    "driver_rating_given":        driver_rating,
                    "customer_rating_given":      customer_rating,
                    "customer_complaint_flag":    False,
                    "customer_complaint_type":    None,

                    # Fraud labels — set by fraud.py
                    "is_fraud":                   False,
                    "fraud_type":                 None,
                    "fraud_recoverable_inr":      0.0,
                    "recoverable_amount_inr":      0.0,   # alias for model compat
                    # NOTE: fraud_confidence_score is REMOVED — model output, not input
                })
                progress.advance(task)

        return records

    console.rule("[cyan]Historical Window[/cyan]")
    hist_records = _generate_window(n_historical, hist_start, hist_end, "historical")
    console.rule("[cyan]Live Eval Window[/cyan]")
    eval_records = _generate_window(n_live_eval, eval_start, eval_end, "live_eval")

    df = pd.DataFrame(hist_records + eval_records)
    df["requested_at"] = pd.to_datetime(df["requested_at"])
    df = df.sort_values("requested_at").reset_index(drop=True)
    df["requested_at"] = df["requested_at"].astype(str)
    return df


if __name__ == "__main__":
    console.rule("[cyan]Trip Generator v2 — Validation[/cyan]")

    from generator.drivers   import generate_drivers
    from generator.customers import generate_customers

    drivers_df   = generate_drivers(n=2_000, city_filter="bangalore")
    customers_df = generate_customers(n=2_000, city_filter="bangalore")
    df = generate_trips(drivers_df, customers_df, n=5_000, city_filter="bangalore")

    # Physics check — this was the core bug
    completed = df[df["trip_status"] == "completed"].copy()
    completed["speed_check"] = (
        completed["declared_distance_km"]
        / (completed["actual_trip_duration_mins"] / 60)
    )
    max_speed = completed["speed_check"].max()
    assert max_speed < 120, f"Max speed {max_speed:.1f} km/hr is physically impossible"
    console.print(f"[green]✅ Physics fix: max speed = {max_speed:.1f} km/hr (was 1819)[/green]")

    # Schema checks
    assert "fraud_confidence_score" not in df.columns, \
        "fraud_confidence_score must NOT be in schema"
    assert "gps_ping_count" in df.columns, "gps_ping_count missing"
    assert "goods_category" in df.columns, "goods_category missing"
    assert "loading_time_mins" in df.columns, "loading_time_mins missing"
    assert "mock_location_flag" in df.columns, "mock_location_flag missing"
    console.print("[green]✅ Schema v2 validated — all new fields present[/green]")
    console.print("[green]✅ fraud_confidence_score correctly absent[/green]")

    # Avg speed sanity
    avg_speed_mean = completed["speed_check"].mean()
    assert 8 < avg_speed_mean < 45, f"Avg speed {avg_speed_mean:.1f} unrealistic"
    console.print(f"[green]✅ Avg speed: {avg_speed_mean:.1f} km/hr (realistic)[/green]")

    out = DATA_RAW / "trips_sample_5k.csv"
    df.to_csv(out, index=False)
    console.print(f"[green]✅ Saved → {out}[/green]")
    console.print("[green bold]✅ trips.py v2 — all checks passed[/green bold]")
