"""
Porter Intelligence Platform — Fraud Injection Engine

Takes clean trip records from trips.py and injects
realistic fraud patterns for model training.

Three fraud properties encoded:
  1. Temporal clustering (Friday + late-month spikes)
  2. Ring coordination signals (historical window)
  3. Window evolution (new patterns in live_eval only)

Fraud confidence scores are training weights, not metadata.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from generator.config import (
    RANDOM_SEED, FRAUD_BASE_RATE, FRAUD_TYPES,
    FRAUD_TYPE_DISTRIBUTION, NIGHT_FRAUD_MULTIPLIER,
    NIGHT_HOURS, VEHICLE_TYPES, DATA_RAW,
)

console = Console()
rng = np.random.default_rng(RANDOM_SEED + 3)


# ── Temporal fraud multipliers ────────────────────────────────

def get_temporal_fraud_multiplier(
    requested_at_str: str,
    data_split: str,
) -> float:
    """
    Returns fraud probability multiplier based on day of week
    and day of month.

    Friday + late-month is the highest risk combination.
    Weekend nights are also elevated.
    live_eval window gets a base uplift for pattern evolution.
    """
    dt = pd.to_datetime(requested_at_str)
    dow = dt.dayofweek   # 0=Mon, 6=Sun
    dom = dt.day         # 1-31

    is_friday     = dow == 4
    is_late_month = dom >= 25
    is_night_hour = dt.hour >= 22 or dt.hour < 5

    multiplier = 1.0

    # Friday uplift
    if is_friday:
        multiplier *= 1.35

    # Late month uplift
    if is_late_month:
        multiplier *= 1.28

    # Combined Friday + late month
    if is_friday and is_late_month:
        multiplier *= 1.10  # additional on top of both

    # Night hours
    if is_night_hour:
        multiplier *= NIGHT_FRAUD_MULTIPLIER

    # Non-peak days slightly below baseline
    if not is_friday and not is_late_month and not is_night_hour:
        multiplier *= 0.92

    # live_eval evolution uplift
    if data_split == "live_eval":
        multiplier *= 1.08

    return float(multiplier)


# ── Fraud type sampler ────────────────────────────────────────

def sample_fraud_type(
    vehicle_type: str,
    payment_mode: str,
    is_night: bool,
    data_split: str,
    rng: np.random.Generator,
) -> str:
    """
    Sample a fraud type with context-aware probability adjustments.

    Base distribution from FRAUD_TYPE_DISTRIBUTION.
    Adjustments:
      cash payment → cash_extortion more likely (+40%)
      two_wheeler  → fake_trip and fake_cancellation more likely
      truck        → inflated_distance more likely (less detectable)
      night        → fake_trip and duplicate_trip more likely
      live_eval    → inflated_distance gets 2x weight
                     (emerging pattern simulation)
    """
    weights = {ft: FRAUD_TYPE_DISTRIBUTION[ft] for ft in FRAUD_TYPES}

    # Context adjustments
    if payment_mode == "cash":
        weights["cash_extortion"] *= 1.4

    if vehicle_type == "two_wheeler":
        weights["fake_trip"]         *= 1.3
        weights["fake_cancellation"] *= 1.3

    if "truck" in vehicle_type:
        weights["inflated_distance"] *= 1.5
        weights["fake_trip"]         *= 0.5

    if is_night:
        weights["fake_trip"]      *= 1.4
        weights["duplicate_trip"] *= 1.3

    if data_split == "live_eval":
        weights["inflated_distance"] *= 2.0  # emerging pattern

    # Normalise
    total = sum(weights.values())
    types = list(weights.keys())
    probs = [weights[t] / total for t in types]

    return str(rng.choice(types, p=probs))


# ── Confidence score sampler ──────────────────────────────────

def sample_confidence_score(
    fraud_type: str,
    rng: np.random.Generator,
) -> float:
    """
    Sample a fraud confidence score for this fraud type.

    These ranges reflect how detectable each fraud type is.
    High confidence = clear signal in the features.
    Low confidence  = subtle, ambiguous, borderline.

    Ranges:
      fake_trip:          0.85 – 0.99  (GPS contradiction = clear)
      cash_extortion:     0.65 – 0.85  (needs complaint signal)
      route_deviation:    0.70 – 0.90  (distance ratio = moderate)
      fake_cancellation:  0.75 – 0.95  (timing cluster = clear)
      duplicate_trip:     0.90 – 0.99  (exact match = very clear)
      inflated_distance:  0.55 – 0.75  (subtle, borderline)
    """
    ranges = {
        "fake_trip":         (0.85, 0.99),
        "cash_extortion":    (0.65, 0.85),
        "route_deviation":   (0.70, 0.90),
        "fake_cancellation": (0.75, 0.95),
        "duplicate_trip":    (0.90, 0.99),
        "inflated_distance": (0.55, 0.75),
    }
    lo, hi = ranges[fraud_type]
    return float(rng.uniform(lo, hi))


# ── Per-type fraud field modifiers ────────────────────────────

def apply_fake_trip(
    row: dict,
    rng: np.random.Generator,
) -> dict:
    """
    Fake trip: driver claims completion but barely moved.

    Signals injected:
      - actual_distance very short (< 0.3km)
      - declared_distance remains as-is (the lie)
      - completed_at - started_at too short for declared_distance
      - pickup and dropoff coordinates nearly identical
    """
    # Driver stayed near pickup — tiny actual movement
    row["actual_distance_km"] = float(rng.uniform(0.05, 0.25))

    # Compress dropoff coordinates toward pickup
    lat_offset = rng.uniform(-0.001, 0.001)
    lon_offset = rng.uniform(-0.001, 0.001)
    row["dropoff_lat"] = round(row["pickup_lat"] + lat_offset, 6)
    row["dropoff_lon"] = round(row["pickup_lon"] + lon_offset, 6)

    # Duration artificially short (< 3 min for any distance)
    row["declared_duration_min"] = float(rng.uniform(0.5, 2.8))

    # Compress completed_at to match fake duration
    if row.get("started_at"):
        started = pd.to_datetime(row["started_at"])
        fake_duration_s = int(row["declared_duration_min"] * 60)
        row["completed_at"] = (
            started + timedelta(seconds=fake_duration_s)
        ).isoformat()

    # Full fare is recoverable
    row["recoverable_amount_inr"] = float(row["fare_inr"])

    return row


def apply_cash_extortion(
    row: dict,
    rng: np.random.Generator,
) -> dict:
    """
    Cash extortion: driver demands cash above metered fare.

    Signals injected:
      - payment_mode forced to cash
      - fare_inr inflated 1.4x-2.2x
      - customer_complaint_flag = True
      - driver_rating_given by customer = 1 or 2
    """
    veh = VEHICLE_TYPES[row["vehicle_type"]]
    expected_fare = veh.base_fare + veh.per_km_rate * row["declared_distance_km"]
    extortion_multiplier = float(rng.uniform(1.4, 2.2))
    inflated_fare = expected_fare * extortion_multiplier

    row["payment_mode"]            = "cash"
    row["fare_inr"]                = round(inflated_fare, 2)
    row["customer_complaint_flag"] = True
    row["driver_rating_given"]     = float(rng.choice([1, 2]))
    row["recoverable_amount_inr"]  = round(inflated_fare - expected_fare, 2)

    return row


def apply_route_deviation(
    row: dict,
    rng: np.random.Generator,
) -> dict:
    """
    Route deviation: driver takes longer route to inflate fare.

    Signals injected:
      - actual_distance 1.3x-1.8x declared
      - extra_km field added
      - duration inflated proportionally
    """
    deviation_factor = float(rng.uniform(1.3, 1.8))
    actual_dist = row["declared_distance_km"] * deviation_factor
    extra_km    = actual_dist - row["declared_distance_km"]

    row["actual_distance_km"]    = round(actual_dist, 3)
    row["extra_km"]              = round(extra_km, 3)
    row["declared_duration_min"] = round(
        row["declared_duration_min"] * deviation_factor, 2
    )

    veh = VEHICLE_TYPES[row["vehicle_type"]]
    row["recoverable_amount_inr"] = round(extra_km * veh.per_km_rate, 2)

    return row


def apply_fake_cancellation(
    row: dict,
    rng: np.random.Generator,
) -> dict:
    """
    Fake cancellation: accept then immediately cancel
    to game the allocation system.

    Signals injected:
      - status forced to cancelled_by_driver
      - cancelled_at within 45 seconds of accepted_at
      - completed_at and started_at set to None
    """
    row["status"] = "cancelled_by_driver"

    if row.get("accepted_at"):
        accepted = pd.to_datetime(row["accepted_at"])
        cancel_delay_s = int(rng.integers(5, 45))
        row["cancelled_at"] = (
            accepted + timedelta(seconds=cancel_delay_s)
        ).isoformat()

    row["started_at"]  = None
    row["completed_at"] = None

    # Cancellation penalty
    penalty_map = {
        "two_wheeler":   75.0,
        "three_wheeler": 100.0,
        "mini_truck":    150.0,
        "truck_14ft":    200.0,
        "truck_17ft":    200.0,
    }
    row["recoverable_amount_inr"] = penalty_map.get(
        row["vehicle_type"], 100.0
    )

    return row


def apply_duplicate_trip(
    row: dict,
    rng: np.random.Generator,
) -> dict:
    """
    Duplicate trip: same trip billed twice.

    Signals injected:
      - Mark this trip as the duplicate (second billing)
      - Shift requested_at forward by 5-15 minutes
        to simulate the second billing window
      - Full fare is recoverable
    """
    if row.get("requested_at"):
        orig = pd.to_datetime(row["requested_at"])
        shift_min = int(rng.integers(5, 15))
        row["requested_at"] = (
            orig + timedelta(minutes=shift_min)
        ).isoformat()

    row["recoverable_amount_inr"] = float(row["fare_inr"])

    return row


def apply_inflated_distance(
    row: dict,
    rng: np.random.Generator,
) -> dict:
    """
    Inflated distance: declare more km than physically possible.

    Signals injected:
      - declared_distance inflated 1.2x-1.5x
      - actual_distance remains at original (the truth)
      - fare recalculated from inflated distance

    Only applied when inflation makes the distance implausible:
      declared > haversine × 1.5 (generous road factor)
    Otherwise confidence is too low to be useful training data.
    """
    original_dist = row["declared_distance_km"]
    inflation     = float(rng.uniform(1.2, 1.5))
    inflated_dist = original_dist * inflation

    # Max plausible road distance
    from generator.cities import haversine_km
    straight_line = haversine_km(
        row["pickup_lat"], row["pickup_lon"],
        row["dropoff_lat"], row["dropoff_lon"],
    )
    max_plausible = straight_line * 1.5

    if inflated_dist <= max_plausible:
        # Not implausible enough — skip fraud injection
        return row

    row["declared_distance_km"] = round(inflated_dist, 3)
    row["actual_distance_km"]   = round(original_dist, 3)

    # Recalculate fare from inflated distance
    veh = VEHICLE_TYPES[row["vehicle_type"]]
    new_fare = (
        (veh.base_fare + veh.per_km_rate * inflated_dist)
        * row["surge_multiplier"]
    )
    if row.get("is_night"):
        new_fare *= 1.25
    row["fare_inr"] = round(new_fare, 2)

    row["recoverable_amount_inr"] = round(
        (inflated_dist - original_dist) * veh.per_km_rate, 2
    )

    return row


# ── Fraud type dispatcher ─────────────────────────────────────

FRAUD_APPLIERS = {
    "fake_trip":         apply_fake_trip,
    "cash_extortion":    apply_cash_extortion,
    "route_deviation":   apply_route_deviation,
    "fake_cancellation": apply_fake_cancellation,
    "duplicate_trip":    apply_duplicate_trip,
    "inflated_distance": apply_inflated_distance,
}


# ── Ring coordination injector ────────────────────────────────

def inject_ring_coordination(
    df: pd.DataFrame,
    drivers_df: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Inject coordinated fake_cancellation clusters for fraud rings.

    Ring members in the historical window generate fake
    cancellations in coordinated 3-minute sessions.
    Sessions: Tuesday-Thursday evenings, 7PM-10PM.
    Frequency: 2-4 sessions per week per ring.

    This creates the temporal clustering signal that the model
    must learn to detect as organised fraud rather than
    individual driver misbehaviour.

    Also injects RING_NEW_001 behaviour into live_eval window
    only — four solo drivers acting as an undetected new ring.
    """
    # Get ring members from drivers
    ring_drivers = drivers_df[
        drivers_df["fraud_ring_id"].notna()
    ][["driver_id", "fraud_ring_id", "zone_id", "ring_role"]]

    if len(ring_drivers) == 0:
        return df

    ring_ids = ring_drivers["fraud_ring_id"].unique()
    df = df.copy()

    coordinated_count = 0

    for ring_id in ring_ids:
        members = ring_drivers[ring_drivers["fraud_ring_id"] == ring_id]
        member_ids = members["driver_id"].values
        ring_zone  = members["zone_id"].iloc[0]

        # Find historical trips by ring members in their zone
        member_trips_mask = (
            df["driver_id"].isin(member_ids)
            & (df["pickup_zone_id"] == ring_zone)
            & (df["data_split"] == "historical")
        )
        member_trips = df[member_trips_mask].copy()

        if len(member_trips) == 0:
            continue

        # Convert to datetime for time filtering
        member_trips["_dt"] = pd.to_datetime(
            member_trips["requested_at"], format="mixed"
        )

        # Filter: Tuesday(1)-Thursday(3), 7PM-10PM
        session_trips = member_trips[
            member_trips["_dt"].dt.dayofweek.isin([1, 2, 3])
            & member_trips["_dt"].dt.hour.between(19, 22)
        ]

        if len(session_trips) < 3:
            continue

        # Sample 3-8 trips per session, 2-4 sessions
        n_sessions        = int(rng.integers(2, 5))
        trips_per_session = int(rng.integers(3, 9))

        n_to_inject = min(
            len(session_trips),
            n_sessions * trips_per_session,
        )
        inject_indices = rng.choice(
            session_trips.index.values,
            size=n_to_inject,
            replace=False,
        )

        for idx in inject_indices:
            if df.at[idx, "is_fraud"]:
                continue  # already flagged

            row_dict = df.loc[idx].to_dict()
            row_dict = apply_fake_cancellation(row_dict, rng)
            confidence = sample_confidence_score("fake_cancellation", rng)

            df.at[idx, "status"]                 = row_dict["status"]
            df.at[idx, "cancelled_at"]           = row_dict["cancelled_at"]
            df.at[idx, "started_at"]             = row_dict["started_at"]
            df.at[idx, "completed_at"]           = row_dict["completed_at"]
            df.at[idx, "is_fraud"]               = True
            df.at[idx, "fraud_type"]             = "fake_cancellation"
            df.at[idx, "fraud_confidence_score"] = confidence
            df.at[idx, "recoverable_amount_inr"] = row_dict["recoverable_amount_inr"]
            df.at[idx, "ring_coordination"]      = True

            coordinated_count += 1

    console.print(
        f"[cyan]Ring coordination: {coordinated_count} coordinated "
        f"cancellations injected across {len(ring_ids)} rings[/cyan]"
    )

    # ── RING_NEW_001 — live_eval only ─────────────────────────
    # Pick 4 solo chronic fraudsters from same zone
    # and create a new coordinated pattern
    solo_chronic = drivers_df[
        (drivers_df["ring_role"] == "solo")
        & (drivers_df["fraud_propensity"] > 0.50)
        & (drivers_df["city"] == "bangalore")
    ].head(4)

    if len(solo_chronic) >= 4:
        new_ring_ids  = solo_chronic["driver_id"].values
        new_ring_zone = solo_chronic["zone_id"].iloc[0]

        new_ring_mask = (
            df["driver_id"].isin(new_ring_ids)
            & (df["pickup_zone_id"] == new_ring_zone)
            & (df["data_split"] == "live_eval")
        )
        new_ring_trips = df[new_ring_mask]

        if len(new_ring_trips) >= 4:
            inject_count = min(len(new_ring_trips), 12)
            inject_idx = rng.choice(
                new_ring_trips.index.values,
                size=inject_count,
                replace=False,
            )
            new_ring_injected = 0
            for idx in inject_idx:
                if df.at[idx, "is_fraud"]:
                    continue
                row_dict = df.loc[idx].to_dict()
                row_dict = apply_fake_cancellation(row_dict, rng)
                df.at[idx, "status"]                 = row_dict["status"]
                df.at[idx, "cancelled_at"]           = row_dict["cancelled_at"]
                df.at[idx, "started_at"]             = row_dict["started_at"]
                df.at[idx, "completed_at"]           = row_dict["completed_at"]
                df.at[idx, "is_fraud"]               = True
                df.at[idx, "fraud_type"]             = "fake_cancellation"
                df.at[idx, "fraud_confidence_score"] = sample_confidence_score(
                    "fake_cancellation", rng
                )
                df.at[idx, "recoverable_amount_inr"] = row_dict["recoverable_amount_inr"]
                df.at[idx, "ring_coordination"]      = True
                new_ring_injected += 1

            if new_ring_injected > 0:
                console.print(
                    f"[yellow]RING_NEW_001 injected: {new_ring_injected} "
                    f"coordinated cancellations in live_eval window[/yellow]"
                )

    return df


# ── Main injection engine ─────────────────────────────────────

def inject_fraud(
    trips_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
    rng: np.random.Generator = rng,
) -> pd.DataFrame:
    """
    Main fraud injection function.

    Takes clean trips_df and drivers_df.
    Returns trips_df with fraud injected.

    Process:
      1. Add helper columns if missing
      2. For each trip, determine fraud probability
         using driver propensity × temporal multiplier
      3. Sample fraud type and apply field modifications
      4. Inject ring coordination patterns
      5. Return modified DataFrame
    """
    df = trips_df.copy()

    # ── Add missing columns ────────────────────────────────────
    if "extra_km" not in df.columns:
        df["extra_km"] = 0.0
    if "ring_coordination" not in df.columns:
        df["ring_coordination"] = False

    # ── Build driver propensity lookup ─────────────────────────
    propensity_map: Dict[str, float] = dict(
        zip(drivers_df["driver_id"], drivers_df["fraud_propensity"])
    )

    total_trips = len(df)
    fraud_count = 0
    skipped     = 0

    console.rule("[cyan]Injecting Fraud Patterns[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Injecting fraud..."),
        BarColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fraud injection", total=total_trips)

        for idx, row in df.iterrows():
            # Skip already-flagged (ring pre-injection runs after)
            if df.at[idx, "is_fraud"]:
                progress.advance(task)
                continue

            driver_id  = row["driver_id"]
            propensity = propensity_map.get(driver_id, 0.05)
            data_split = row["data_split"]

            # ── Temporal multiplier ────────────────────────────
            temporal_mult = get_temporal_fraud_multiplier(
                row["requested_at"], data_split
            )

            # ── Effective fraud probability ────────────────────
            # Base rate × driver propensity ratio × temporal
            propensity_ratio = propensity / 0.047  # normalise to base
            effective_prob = (
                FRAUD_BASE_RATE
                * propensity_ratio
                * temporal_mult
            )
            effective_prob = float(np.clip(effective_prob, 0.0, 0.85))

            # ── Roll for fraud ────────────────────────────────
            if rng.random() > effective_prob:
                progress.advance(task)
                continue

            # ── Sample fraud type ─────────────────────────────
            fraud_type = sample_fraud_type(
                vehicle_type=row["vehicle_type"],
                payment_mode=row["payment_mode"],
                is_night=bool(row.get("is_night", False)),
                data_split=data_split,
                rng=rng,
            )

            # ── Apply fraud modifications ─────────────────────
            row_dict = df.loc[idx].to_dict()
            applier  = FRAUD_APPLIERS[fraud_type]
            row_dict = applier(row_dict, rng)

            # Check if inflated_distance was skipped
            if (fraud_type == "inflated_distance"
                    and row_dict.get("recoverable_amount_inr", 0) == 0):
                skipped += 1
                progress.advance(task)
                continue

            # ── Write back modified fields ────────────────────
            confidence = sample_confidence_score(fraud_type, rng)

            for field in [
                "actual_distance_km", "declared_distance_km",
                "declared_duration_min", "fare_inr",
                "payment_mode", "status", "driver_rating_given",
                "dropoff_lat", "dropoff_lon",
                "started_at", "completed_at", "cancelled_at",
                "customer_complaint_flag", "extra_km",
                "recoverable_amount_inr", "requested_at",
            ]:
                if field in row_dict:
                    df.at[idx, field] = row_dict[field]

            df.at[idx, "is_fraud"]               = True
            df.at[idx, "fraud_type"]             = fraud_type
            df.at[idx, "fraud_confidence_score"] = confidence

            fraud_count += 1
            progress.advance(task)

    console.print(
        f"[green]Individual fraud: {fraud_count:,} trips flagged "
        f"({fraud_count / total_trips * 100:.2f}%) | "
        f"{skipped} inflated_distance attempts skipped[/green]"
    )

    # ── Ring coordination (runs after individual injection) ────
    df = inject_ring_coordination(df, drivers_df, rng)

    return df


# ── Test block ────────────────────────────────────────────────

if __name__ == "__main__":
    console.rule("[cyan]Fraud Injection Engine — Validation[/cyan]")

    # Load sample data
    console.print("[dim]Loading driver and customer samples...[/dim]")
    from generator.drivers import generate_drivers
    from generator.customers import generate_customers
    from generator.trips import generate_trips

    drivers_df   = generate_drivers(n=5000, city_filter="bangalore")
    customers_df = generate_customers(n=5000, city_filter="bangalore")

    console.print("[dim]Generating 10,000 clean trips...[/dim]")
    trips_df = generate_trips(
        drivers_df, customers_df,
        n=10_000, city_filter="bangalore",
    )

    console.print("[dim]Injecting fraud patterns...[/dim]")
    df = inject_fraud(trips_df, drivers_df)

    # ── Core assertions ────────────────────────────────────────
    total      = len(df)
    fraud_mask = df["is_fraud"] == True
    fraud_total = fraud_mask.sum()
    fraud_rate  = fraud_total / total * 100

    assert fraud_total > 0, "No fraud injected"
    assert 2.5 < fraud_rate < 9.0, \
        f"Fraud rate {fraud_rate:.2f}% outside expected 2.5-9%"
    assert df["fraud_confidence_score"].notna().sum() == fraud_total, \
        "Every fraud trip must have a confidence score"
    assert df.loc[fraud_mask, "recoverable_amount_inr"].gt(0).all(), \
        "All fraud trips must have recoverable_amount_inr > 0"
    assert df.loc[~fraud_mask, "recoverable_amount_inr"].eq(0).all(), \
        "Non-fraud trips must have recoverable_amount_inr = 0"

    # ── Overall fraud rate table ───────────────────────────────
    rate_table = Table(title="Overall Fraud Rate")
    rate_table.add_column("Metric",  style="cyan")
    rate_table.add_column("Value",   style="green")
    rate_table.add_column("Target",  justify="right")
    rate_table.add_column("Status",  justify="center")
    rate_table.add_row(
        "Total trips", f"{total:,}", "10,000", "✅"
    )
    rate_table.add_row(
        "Fraud trips", f"{fraud_total:,}",
        "250-900", "✅" if 250 < fraud_total < 900 else "❌"
    )
    rate_table.add_row(
        "Fraud rate", f"{fraud_rate:.2f}%",
        "2.5–9%", "✅" if 2.5 < fraud_rate < 9 else "❌"
    )
    console.print(rate_table)

    # ── Fraud type distribution ────────────────────────────────
    fraud_df  = df[fraud_mask]
    type_dist = fraud_df["fraud_type"].value_counts()
    type_table = Table(title="Fraud Type Distribution")
    type_table.add_column("Type",      style="cyan")
    type_table.add_column("Count",     justify="right")
    type_table.add_column("Pct",       justify="right")
    type_table.add_column("Conf avg",  justify="right")
    for ftype in FRAUD_TYPES:
        count = type_dist.get(ftype, 0)
        pct   = count / max(fraud_total, 1) * 100
        conf  = fraud_df[
            fraud_df["fraud_type"] == ftype
        ]["fraud_confidence_score"].mean()
        conf_str = f"{conf:.3f}" if not np.isnan(conf) else "—"
        type_table.add_row(ftype, str(count), f"{pct:.1f}%", conf_str)
    console.print(type_table)

    # ── Confidence score ranges per type ──────────────────────
    conf_table = Table(title="Confidence Score Validation")
    conf_table.add_column("Fraud Type",     style="cyan")
    conf_table.add_column("Min",            justify="right")
    conf_table.add_column("Avg",            justify="right")
    conf_table.add_column("Max",            justify="right")
    conf_table.add_column("Expected range", justify="right")
    conf_table.add_column("Status",         justify="center")
    expected_conf = {
        "fake_trip":         (0.85, 0.99),
        "cash_extortion":    (0.65, 0.85),
        "route_deviation":   (0.70, 0.90),
        "fake_cancellation": (0.75, 0.95),
        "duplicate_trip":    (0.90, 0.99),
        "inflated_distance": (0.55, 0.75),
    }
    all_conf_ok = True
    for ftype, (lo, hi) in expected_conf.items():
        sub = fraud_df[fraud_df["fraud_type"] == ftype][
            "fraud_confidence_score"
        ]
        if len(sub) == 0:
            continue
        ok = sub.min() >= lo * 0.95 and sub.max() <= hi * 1.05
        if not ok:
            all_conf_ok = False
        conf_table.add_row(
            ftype,
            f"{sub.min():.3f}", f"{sub.mean():.3f}",
            f"{sub.max():.3f}", f"{lo:.2f}–{hi:.2f}",
            "✅" if ok else "❌",
        )
    console.print(conf_table)
    assert all_conf_ok, "Confidence scores outside expected ranges"

    # ── Temporal clustering validation ────────────────────────
    df["_dt"]  = pd.to_datetime(df["requested_at"], format="mixed")
    df["_dow"] = df["_dt"].dt.dayofweek
    df["_dom"] = df["_dt"].dt.day

    friday_rate = df[df["_dow"] == 4]["is_fraud"].mean() * 100
    other_rate  = df[df["_dow"] != 4]["is_fraud"].mean() * 100
    late_rate   = df[df["_dom"] >= 25]["is_fraud"].mean() * 100
    early_rate  = df[df["_dom"] < 25]["is_fraud"].mean() * 100

    temp_table = Table(title="Temporal Clustering Validation")
    temp_table.add_column("Segment",    style="cyan")
    temp_table.add_column("Fraud rate", justify="right")
    temp_table.add_column("Status",     justify="center")
    temp_table.add_row(
        "Friday", f"{friday_rate:.2f}%",
        "✅" if friday_rate > other_rate else "❌"
    )
    temp_table.add_row("Other days", f"{other_rate:.2f}%", "—")
    temp_table.add_row(
        "Late month (day 25+)", f"{late_rate:.2f}%",
        "✅" if late_rate > early_rate else "❌"
    )
    temp_table.add_row("Early month", f"{early_rate:.2f}%", "—")
    console.print(temp_table)
    assert friday_rate > other_rate, \
        "Friday must have higher fraud rate than other days"
    assert late_rate > early_rate, \
        "Late month must have higher fraud rate than early month"

    # ── Window evolution validation ────────────────────────────
    hist_rate = df[
        df["data_split"] == "historical"
    ]["is_fraud"].mean() * 100
    eval_rate = df[
        df["data_split"] == "live_eval"
    ]["is_fraud"].mean() * 100

    # inflated_distance should be higher in live_eval
    hist_inf = df[
        (df["data_split"] == "historical")
        & (df["fraud_type"] == "inflated_distance")
    ].shape[0]
    eval_inf = df[
        (df["data_split"] == "live_eval")
        & (df["fraud_type"] == "inflated_distance")
    ].shape[0]
    hist_inf_rate = hist_inf / max(
        (df["data_split"] == "historical").sum(), 1
    ) * 100
    eval_inf_rate = eval_inf / max(
        (df["data_split"] == "live_eval").sum(), 1
    ) * 100

    evol_table = Table(title="Window Evolution Validation")
    evol_table.add_column("Metric",     style="cyan")
    evol_table.add_column("Historical", justify="right")
    evol_table.add_column("Live Eval",  justify="right")
    evol_table.add_column("Status",     justify="center")
    evol_table.add_row(
        "Overall fraud rate",
        f"{hist_rate:.2f}%", f"{eval_rate:.2f}%",
        "✅" if eval_rate > hist_rate else "⚠️"
    )
    evol_table.add_row(
        "inflated_distance rate",
        f"{hist_inf_rate:.2f}%", f"{eval_inf_rate:.2f}%",
        "✅" if eval_inf_rate > hist_inf_rate else "❌"
    )
    console.print(evol_table)
    assert eval_inf_rate > hist_inf_rate, \
        "inflated_distance must be higher in live_eval window"

    # ── Ring coordination check ────────────────────────────────
    ring_coord_count = df["ring_coordination"].sum()
    ring_table = Table(title="Ring Coordination Signals")
    ring_table.add_column("Metric",  style="cyan")
    ring_table.add_column("Value",   style="green")
    ring_table.add_column("Status",  justify="center")
    ring_table.add_row(
        "Coordinated cancellations",
        str(ring_coord_count),
        "✅" if ring_coord_count > 0 else "❌"
    )
    hist_ring = df[
        (df["ring_coordination"] == True)
        & (df["data_split"] == "historical")
    ].shape[0]
    eval_ring = df[
        (df["ring_coordination"] == True)
        & (df["data_split"] == "live_eval")
    ].shape[0]
    ring_table.add_row(
        "Historical ring signals", str(hist_ring), "—"
    )
    ring_table.add_row(
        "Live eval ring signals (RING_NEW_001)",
        str(eval_ring),
        "✅" if eval_ring > 0 else "⚠️"
    )
    console.print(ring_table)

    # ── Recoverable amount validation ─────────────────────────
    total_recoverable = fraud_df["recoverable_amount_inr"].sum()
    avg_recoverable   = fraud_df["recoverable_amount_inr"].mean()
    recov_table = Table(title="Recoverable Amount Summary")
    recov_table.add_column("Metric",  style="cyan")
    recov_table.add_column("Value",   style="green")
    recov_table.add_column("Status",  justify="center")
    recov_table.add_row(
        "Total recoverable (10K trips)",
        f"₹{total_recoverable:,.0f}",
        "✅" if total_recoverable > 50_000 else "❌"
    )
    recov_table.add_row(
        "Avg per fraud trip",
        f"₹{avg_recoverable:,.0f}",
        "✅" if avg_recoverable > 100 else "❌"
    )
    recov_per_trip = total_recoverable / total
    recov_table.add_row(
        "Recoverable per trip (all)",
        f"₹{recov_per_trip:.2f}",
        "✅" if recov_per_trip > 0.50 else "❌"
    )
    console.print(recov_table)

    assert total_recoverable > 50_000, \
        "Total recoverable too low for KPI calculation"
    assert avg_recoverable > 100, \
        "Avg recoverable per fraud trip below ₹100"
    assert recov_per_trip > 0.50, \
        "Recoverable per trip below ₹0.50 pilot KPI threshold"

    # ── Save ──────────────────────────────────────────────────
    out_path = DATA_RAW / "trips_with_fraud_10k.csv"
    df.drop(
        columns=["_dt", "_dow", "_dom"], errors="ignore"
    ).to_csv(out_path, index=False)
    console.print(f"\n[green]✅ Saved → {out_path}[/green]")

    # ── Final summary ──────────────────────────────────────────
    summary = Table(title="Fraud Injection — Day 4 Summary")
    summary.add_column("Metric",  style="cyan")
    summary.add_column("Value",   style="green")
    summary.add_row("Total trips",         f"{total:,}")
    summary.add_row("Fraud trips",         f"{fraud_total:,}")
    summary.add_row("Fraud rate",          f"{fraud_rate:.2f}%")
    summary.add_row("Fraud types active",  str(type_dist.shape[0]))
    summary.add_row("Ring coord signals",  str(ring_coord_count))
    summary.add_row("Total recoverable",   f"₹{total_recoverable:,.0f}")
    summary.add_row("Recoverable/trip",    f"₹{recov_per_trip:.2f}")
    summary.add_row("Conf scores valid",   "✅" if all_conf_ok else "❌")
    summary.add_row("Temporal clustering", "✅ Friday + late-month")
    summary.add_row("Window evolution",    "✅ live_eval drift encoded")
    console.print(summary)

    console.print(
        "\n[green bold]✅ fraud.py — all checks passed. "
        "Ready for Day 5 — model/features.py + train.py"
        "[/green bold]"
    )
