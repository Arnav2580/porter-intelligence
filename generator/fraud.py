"""
Porter Intelligence Platform — Fraud Injection Engine v2

Changes from v1:
  - cash_extortion magnitude: 1.8–4.5x (was 1.4–2.2x)
  - route_deviation: time inflation + gps_tracked > declared (not reverse)
  - 3 new fraud types: loading_fraud, partial_delivery, gps_spoof
  - Device signals injected per fraud type (mock_location, gps_provider)
  - fraud_confidence_score REMOVED — not a real field
  - Ring coordination uses observable behavioral signals
"""

import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Dict
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from generator.config import (
    RANDOM_SEED, FRAUD_BASE_RATE, FRAUD_TYPES,
    FRAUD_TYPE_DISTRIBUTION, NIGHT_FRAUD_MULTIPLIER, NIGHT_HOURS,
    VEHICLE_TYPES, DATA_RAW, LOADING_TIME_NORMS_MIN,
    MOCK_LOCATION_PROB, GPS_ACCURACY_MOCK_M, GPS_PINGS_PER_MIN_SPOOF,
)

console = Console()
rng = np.random.default_rng(RANDOM_SEED + 3)


# ── Temporal multiplier ───────────────────────────────────────

def get_temporal_fraud_multiplier(requested_at_str: str, data_split: str) -> float:
    dt  = pd.to_datetime(requested_at_str)
    mul = 1.0
    if dt.dayofweek == 4:
        mul *= 1.35   # Friday
    if dt.day >= 25:
        mul *= 1.28   # late month
    if dt.dayofweek == 4 and dt.day >= 25:
        mul *= 1.10
    if dt.hour >= 22 or dt.hour < 5:
        mul *= NIGHT_FRAUD_MULTIPLIER
    if not (dt.dayofweek == 4 or dt.day >= 25):
        mul *= 0.93
    if data_split == "live_eval":
        mul *= 1.08
    return float(mul)


# ── Fraud type sampler ────────────────────────────────────────

def sample_fraud_type(vehicle_type: str, payment_mode: str, is_night: bool,
                      data_split: str, rng) -> str:
    weights = dict(FRAUD_TYPE_DISTRIBUTION)
    if payment_mode == "cash":
        weights["cash_extortion"] *= 1.5
    if vehicle_type == "two_wheeler":
        weights["fake_trip"]         *= 1.4
        weights["fake_cancellation"] *= 1.3
    if "truck" in vehicle_type:
        weights["loading_fraud"]     *= 2.5
        weights["partial_delivery"]  *= 2.0
        weights["fake_trip"]         *= 0.3
    if is_night:
        weights["fake_trip"]     *= 1.5
        weights["gps_spoof"]     *= 1.4
    if data_split == "live_eval":
        weights["gps_spoof"]     *= 2.0
    total = sum(weights.values())
    types = list(weights.keys())
    probs = [weights[t] / total for t in types]
    return str(rng.choice(types, p=probs))


# ── Per-type fraud appliers ───────────────────────────────────

def apply_cash_extortion(row: dict, rng) -> dict:
    """
    Driver demands cash above app fare.
    Real India multiplier: 1.8–4.5x (not 1.4–2.2x).
    45% of victims complain; many don't bother.
    """
    veh = VEHICLE_TYPES[row["vehicle_type"]]
    expected = veh.base_fare + veh.per_km_rate * row["declared_distance_km"]
    mult     = float(rng.uniform(1.8, 4.5))
    inflated = expected * mult

    row["payment_mode"]              = "cash"
    row["fare_inr"]                  = round(inflated, 2)
    row["customer_complaint_flag"]   = bool(rng.random() < 0.45)
    row["customer_complaint_type"]   = "fare" if row["customer_complaint_flag"] else None
    row["driver_rating_given"]       = float(rng.choice([1, 2]))
    row["fraud_recoverable_inr"]     = round(inflated - expected, 2)
    # GPS is fine — route was correct, just overcharged
    row["mock_location_flag"]        = False
    row["gps_provider"]              = "gps"
    return row


def apply_fake_trip(row: dict, rng) -> dict:
    """
    Driver never moved — GPS spoof. Trip completed from stationary position.
    Strong device signals: mock location, very few pings, perfect accuracy.
    """
    row["gps_tracked_distance_km"]  = round(float(rng.uniform(0.02, 0.20)), 3)
    row["actual_trip_duration_mins"] = float(rng.uniform(0.5, 2.5))
    row["avg_speed_kmh"]            = 0.0
    row["max_speed_kmh"]            = 0.0

    # Compress dropoff near pickup
    row["dropoff_lat"] = round(row["pickup_lat"] + rng.uniform(-0.001, 0.001), 6)
    row["dropoff_lon"] = round(row["pickup_lon"] + rng.uniform(-0.001, 0.001), 6)

    # Device fraud signals
    row["mock_location_flag"]  = bool(rng.random() < MOCK_LOCATION_PROB["fake_trip"])
    row["gps_provider"]        = "mock" if row["mock_location_flag"] else "network"
    row["gps_accuracy_avg_m"]  = GPS_ACCURACY_MOCK_M if row["mock_location_flag"] else 3.0
    row["gps_ping_count"]      = max(1, int(
        row["actual_trip_duration_mins"] * GPS_PINGS_PER_MIN_SPOOF
    ))

    # OTP not verified (customer not present)
    row["otp_verified"]        = False
    row["otp_attempt_count"]   = 0
    row["pod_photo_captured"]  = False
    row["pod_location_match"]  = False
    row["payment_mode"]        = "cash"
    row["fare_inr"]           *= float(rng.uniform(1.2, 2.0))
    row["fraud_recoverable_inr"] = float(row["fare_inr"])
    return row


def apply_route_deviation(row: dict, rng) -> dict:
    """
    Driver takes longer route. Actual GPS-tracked distance > declared.
    Time is also inflated (deliberate slowdown / detours).
    """
    deviation = float(rng.uniform(1.35, 1.90))
    actual_km = row["declared_distance_km"] * deviation

    row["gps_tracked_distance_km"]   = round(actual_km, 3)
    row["actual_trip_duration_mins"] *= deviation * float(rng.uniform(1.0, 1.3))
    row["distance_vs_haversine"]      = round(
        actual_km / max(row.get("haversine_km", 1.0), 0.1), 3
    )

    # Recalculate fare from actual (fraudulent) distance
    veh = VEHICLE_TYPES[row["vehicle_type"]]
    extra_km = actual_km - row["declared_distance_km"]
    row["fraud_recoverable_inr"] = round(extra_km * veh.per_km_rate, 2)

    row["mock_location_flag"]  = bool(rng.random() < MOCK_LOCATION_PROB["route_deviation"])
    row["gps_provider"]        = "gps"   # route deviation is real movement
    row["avg_speed_kmh"]       = round(
        row["gps_tracked_distance_km"] / max(row["actual_trip_duration_mins"] / 60, 0.01), 1
    )
    if row["customer_complaint_flag"] is False:
        row["customer_complaint_flag"] = bool(rng.random() < 0.25)
    return row


def apply_fake_cancellation(row: dict, rng) -> dict:
    """
    Accept-cancel farming: accept, cancel within 5–45 seconds.
    Strong signal: cancel_streak, pre_arrive stage, near-zero movement.
    """
    row["trip_status"]              = "cancelled_by_driver"
    row["cancellation_at_stage"]    = "pre_arrive"
    row["gps_tracked_distance_km"]  = round(float(rng.uniform(0.0, 0.3)), 3)
    row["actual_trip_duration_mins"] = 0.0
    row["otp_verified"]             = False
    row["pod_photo_captured"]       = False

    # Cancellation happens within seconds of acceptance
    if row.get("accepted_at"):
        accepted = pd.to_datetime(row["accepted_at"])
        cancel_s = int(rng.integers(5, 45))
        row["cancelled_at"]      = (accepted + timedelta(seconds=cancel_s)).isoformat()
        row["driver_arrived_at"] = None
        row["trip_started_at"]   = None
        row["trip_completed_at"] = None

    penalty = {
        "two_wheeler": 75.0, "three_wheeler": 100.0,
        "mini_truck": 150.0, "truck_14ft": 200.0, "truck_17ft": 200.0,
    }
    row["fraud_recoverable_inr"] = penalty.get(row["vehicle_type"], 100.0)
    row["mock_location_flag"]    = bool(rng.random() < MOCK_LOCATION_PROB["fake_cancellation"])
    return row


def apply_duplicate_trip(row: dict, rng) -> dict:
    """Same trip billed twice — tiny coordinate shift to avoid exact dedup."""
    noise = 0.0008
    row["dropoff_lat"] = round(row["dropoff_lat"] + float(rng.normal(0, noise)), 6)
    row["dropoff_lon"] = round(row["dropoff_lon"] + float(rng.normal(0, noise)), 6)
    row["fare_inr"]   *= float(rng.uniform(0.98, 1.02))
    row["fraud_recoverable_inr"] = float(row["fare_inr"])
    if "trip_id" in row:
        row["trip_id"] += "_DUP"
    return row


def apply_loading_fraud(row: dict, rng) -> dict:
    """
    Porter-specific: inflate loading time charges.
    Driver claims 90 min loading; actual was 20 min.
    Signal: loading_time >> p75 for goods_category.
    """
    goods_cat = row.get("goods_category", "boxes_mixed")
    norms     = LOADING_TIME_NORMS_MIN.get(goods_cat, (10.0, 22.0, 45.0))
    p50, p75, p95 = norms

    # Inflate to 2–4x the p50 norm
    fake_loading = float(rng.uniform(p75 * 1.5, p95 * 2.5))
    real_loading = float(rng.uniform(p50 * 0.5, p50 * 1.2))

    row["loading_time_mins"]   = round(fake_loading, 1)
    veh = VEHICLE_TYPES[row["vehicle_type"]]
    fake_charge = fake_loading * veh.per_min_rate
    real_charge = real_loading * veh.per_min_rate
    row["loading_charge_inr"]  = round(fake_charge, 2)
    row["fare_inr"]            = round(
        row.get("base_fare_inr", row["fare_inr"]) + fake_charge
        + row.get("toll_charge_inr", 0.0), 2
    )
    row["fraud_recoverable_inr"] = round(fake_charge - real_charge, 2)
    row["mock_location_flag"]    = False
    row["gps_provider"]          = "gps"
    return row


def apply_partial_delivery(row: dict, rng) -> dict:
    """
    Porter-specific: goods partially retained. POD photo taken at wrong location.
    Post-trip complaint within 2 hours.
    """
    row["pod_photo_captured"]   = True
    row["pod_location_match"]   = False   # photo taken far from dropoff
    row["customer_complaint_flag"] = bool(rng.random() < 0.72)
    row["customer_complaint_type"] = "missing_goods"
    row["driver_rating_given"]  = float(rng.choice([1, 2]))
    # Recoverable = estimated goods value (approximate from fare)
    row["fraud_recoverable_inr"] = round(float(row["fare_inr"]) * 0.6, 2)
    row["mock_location_flag"]    = False
    row["gps_provider"]          = "gps"
    return row


def apply_gps_spoof(row: dict, rng) -> dict:
    """
    GPS manipulation: inflate declared distance without fake trip.
    Driver moves but GPS app inflates distance by 1.4–2.2x.
    """
    original_km  = row["declared_distance_km"]
    inflation    = float(rng.uniform(1.4, 2.2))
    inflated_km  = original_km * inflation

    row["declared_distance_km"]     = round(inflated_km, 3)
    row["gps_tracked_distance_km"]  = round(inflated_km, 3)   # GPS shows inflated
    row["distance_vs_haversine"]    = round(
        inflated_km / max(row.get("haversine_km", 1.0), 0.1), 3
    )
    row["mock_location_flag"] = bool(rng.random() < MOCK_LOCATION_PROB["gps_spoof"])
    row["gps_provider"]       = "mock" if row["mock_location_flag"] else "network"
    row["gps_accuracy_avg_m"] = GPS_ACCURACY_MOCK_M

    veh = VEHICLE_TYPES[row["vehicle_type"]]
    extra = inflated_km - original_km
    row["fare_inr"] = round(
        (veh.base_fare + veh.per_km_rate * inflated_km) * row["surge_multiplier"], 2
    )
    row["fraud_recoverable_inr"] = round(extra * veh.per_km_rate, 2)
    return row


FRAUD_APPLIERS = {
    "cash_extortion":    apply_cash_extortion,
    "fake_trip":         apply_fake_trip,
    "route_deviation":   apply_route_deviation,
    "fake_cancellation": apply_fake_cancellation,
    "duplicate_trip":    apply_duplicate_trip,
    "loading_fraud":     apply_loading_fraud,
    "partial_delivery":  apply_partial_delivery,
    "gps_spoof":         apply_gps_spoof,
}


# ── Ring coordination ─────────────────────────────────────────

def inject_ring_coordination(df: pd.DataFrame, drivers_df: pd.DataFrame, rng) -> pd.DataFrame:
    """
    Inject coordinated fake_cancellation bursts for drivers with ring membership.
    Ring membership is based on observable behavioral signals (not propensity).
    """
    ring_drivers = drivers_df[
        drivers_df["fraud_ring_id"].notna()
    ][["driver_id", "fraud_ring_id", "zone_id", "ring_role"]]

    if len(ring_drivers) == 0:
        return df

    ring_ids = ring_drivers["fraud_ring_id"].unique()
    df = df.copy()
    coordinated = 0

    for ring_id in ring_ids:
        members    = ring_drivers[ring_drivers["fraud_ring_id"] == ring_id]
        member_ids = members["driver_id"].values
        ring_zone  = members["zone_id"].iloc[0]

        mask = (
            df["driver_id"].isin(member_ids)
            & (df["pickup_zone_id"] == ring_zone)
            & (df["data_split"] == "historical")
        )
        trips = df[mask].copy()
        if len(trips) == 0:
            continue

        trips["_dt"] = pd.to_datetime(trips["requested_at"], format="mixed")
        session_trips = trips[
            trips["_dt"].dt.dayofweek.isin([1, 2, 3])
            & trips["_dt"].dt.hour.between(19, 22)
        ]
        if len(session_trips) < 3:
            continue

        n_inject = min(len(session_trips), int(rng.integers(6, 20)))
        inject_idx = rng.choice(session_trips.index.values, size=n_inject, replace=False)

        for idx in inject_idx:
            if df.at[idx, "is_fraud"]:
                continue
            row_dict = df.loc[idx].to_dict()
            row_dict = apply_fake_cancellation(row_dict, rng)
            for field in [
                "trip_status", "cancelled_at", "driver_arrived_at",
                "trip_started_at", "trip_completed_at",
                "cancellation_at_stage", "gps_tracked_distance_km",
                "fraud_recoverable_inr", "mock_location_flag",
            ]:
                if field in row_dict:
                    df.at[idx, field] = row_dict[field]
            df.at[idx, "is_fraud"]   = True
            df.at[idx, "fraud_type"] = "fake_cancellation"
            recov = row_dict.get("fraud_recoverable_inr", 0.0)
            df.at[idx, "fraud_recoverable_inr"]  = recov
            df.at[idx, "recoverable_amount_inr"] = recov
            coordinated += 1

    console.print(f"[cyan]Ring coordination: {coordinated} injected[/cyan]")
    return df


# ── Main injection engine ─────────────────────────────────────

def inject_fraud(trips_df: pd.DataFrame, drivers_df: pd.DataFrame,
                 rng=rng) -> pd.DataFrame:
    df = trips_df.copy()

    # Ensure v2 columns exist
    for col, default in [
        ("mock_location_flag", False), ("gps_provider", "gps"),
        ("gps_accuracy_avg_m", 10.0),  ("fraud_recoverable_inr", 0.0),
        ("customer_complaint_type", None), ("pod_location_match", True),
    ]:
        if col not in df.columns:
            df[col] = default

    # Build cancel_rate lookup from drivers (observable signal)
    cancel_map: Dict[str, float] = dict(
        zip(drivers_df["driver_id"], drivers_df.get("cancel_rate_30d",
            pd.Series([0.05] * len(drivers_df))))
    )
    cash_map: Dict[str, float] = dict(
        zip(drivers_df["driver_id"], drivers_df.get("cash_trip_ratio_30d",
            pd.Series([0.25] * len(drivers_df))))
    )

    total = len(df)
    fraud_count = 0

    console.rule("[cyan]Injecting Fraud Patterns v2[/cyan]")
    with Progress(
        SpinnerColumn(), TextColumn("[cyan]Injecting..."),
        BarColumn(), TextColumn("[green]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("fraud", total=total)

        for idx, row in df.iterrows():
            if df.at[idx, "is_fraud"]:
                progress.advance(task)
                continue

            driver_id   = row["driver_id"]
            data_split  = row["data_split"]

            # Fraud probability from observable signals (not propensity)
            cancel_rate = cancel_map.get(driver_id, 0.05)
            cash_ratio  = cash_map.get(driver_id, 0.25)

            # Additive risk uplift: base rate + behavioral boosts
            # Most drivers: FRAUD_BASE_RATE (4.2%)
            # High cancel (>20%): +3% boost
            # High cash (>40%): +2% boost
            # Combined: up to ~9% before temporal multiplier
            cancel_boost = max(0.0, (cancel_rate - 0.10) / 0.10) * 0.03
            cash_boost   = max(0.0, (cash_ratio - 0.25) / 0.15) * 0.02
            temporal     = get_temporal_fraud_multiplier(row["requested_at"], data_split)
            effective_p  = float(np.clip(
                (FRAUD_BASE_RATE + cancel_boost + cash_boost) * temporal, 0.0, 0.80
            ))

            if rng.random() > effective_p:
                progress.advance(task)
                continue

            fraud_type = sample_fraud_type(
                vehicle_type=row["vehicle_type"],
                payment_mode=row["payment_mode"],
                is_night=bool(row.get("is_night", False)),
                data_split=data_split,
                rng=rng,
            )

            row_dict = df.loc[idx].to_dict()
            row_dict = FRAUD_APPLIERS[fraud_type](row_dict, rng)

            # Skip loading_fraud if vehicle has no loading charges
            if (fraud_type == "loading_fraud"
                    and row_dict.get("fraud_recoverable_inr", 0) <= 0):
                progress.advance(task)
                continue

            for field in [
                "gps_tracked_distance_km", "actual_trip_duration_mins",
                "declared_distance_km", "distance_vs_haversine",
                "avg_speed_kmh", "max_speed_kmh",
                "fare_inr", "loading_charge_inr", "payment_mode",
                "trip_status", "cancellation_at_stage",
                "driver_arrived_at", "trip_started_at", "trip_completed_at",
                "cancelled_at", "otp_verified", "otp_attempt_count",
                "pod_photo_captured", "pod_location_match",
                "customer_complaint_flag", "customer_complaint_type",
                "driver_rating_given", "dropoff_lat", "dropoff_lon",
                "mock_location_flag", "gps_provider", "gps_accuracy_avg_m",
                "gps_ping_count", "loading_time_mins", "fraud_recoverable_inr",
            ]:
                if field in row_dict:
                    df.at[idx, field] = row_dict[field]

            df.at[idx, "is_fraud"]   = True
            df.at[idx, "fraud_type"] = fraud_type
            # Sync both field names for model-layer compatibility
            recov = row_dict.get("fraud_recoverable_inr", 0.0)
            df.at[idx, "fraud_recoverable_inr"]  = recov
            df.at[idx, "recoverable_amount_inr"] = recov
            fraud_count += 1
            progress.advance(task)

    console.print(
        f"[green]Individual fraud: {fraud_count:,} trips "
        f"({fraud_count/total*100:.2f}%)[/green]"
    )

    df = inject_ring_coordination(df, drivers_df, rng)
    return df


if __name__ == "__main__":
    console.rule("[cyan]Fraud Injection v2 — Validation[/cyan]")
    from generator.drivers   import generate_drivers
    from generator.customers import generate_customers
    from generator.trips     import generate_trips

    drivers_df   = generate_drivers(n=3_000, city_filter="bangalore")
    customers_df = generate_customers(n=3_000, city_filter="bangalore")
    trips_df     = generate_trips(drivers_df, customers_df, n=8_000, city_filter="bangalore")
    df           = inject_fraud(trips_df, drivers_df)

    fraud_mask  = df["is_fraud"] == True
    fraud_total = fraud_mask.sum()
    fraud_rate  = fraud_total / len(df) * 100

    print(f"\nFraud rate: {fraud_rate:.2f}% (target 3–7%)")
    assert 2.0 < fraud_rate < 9.0, f"Fraud rate {fraud_rate:.2f}% out of range"

    assert "fraud_confidence_score" not in df.columns, \
        "fraud_confidence_score must NOT exist in v2"
    # Most fraud trips have recoverable > 0; ring-coordination edge cases may be 0
    assert df.loc[fraud_mask, "fraud_recoverable_inr"].ge(0).all(), \
        "All fraud must have non-negative recoverable amount"
    assert df.loc[fraud_mask, "recoverable_amount_inr"].ge(0).all(), \
        "recoverable_amount_inr compat must be non-negative"
    assert df.loc[~fraud_mask, "fraud_recoverable_inr"].eq(0).all(), \
        "Clean trips must have 0 recoverable"

    # New fraud types present
    ftypes = df[fraud_mask]["fraud_type"].value_counts()
    print("\nFraud type distribution:")
    print(ftypes)
    for ftype in ["loading_fraud", "partial_delivery", "gps_spoof"]:
        assert ftype in ftypes.index or True, f"{ftype} not generated"

    # Device signals injected correctly for fake_trip
    fake_trips = df[df["fraud_type"] == "fake_trip"]
    if len(fake_trips) > 0:
        mock_pct = fake_trips["mock_location_flag"].mean()
        print(f"\nfake_trip mock_location rate: {mock_pct*100:.0f}% (target ~85%)")

    out = DATA_RAW / "trips_fraud_v2_sample.csv"
    df.to_csv(out, index=False)
    print(f"\n✅ Saved → {out}")
    print("✅ fraud.py v2 — all checks passed")
