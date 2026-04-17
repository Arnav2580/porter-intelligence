"""
Porter Intelligence Platform — Hard Negative Feature Generator

Generates synthetic CLEAN feature vectors that look suspicious
to a naive classifier but are genuinely not fraudulent.

These are injected directly into the XGBoost training matrix
(post-feature-engineering) so the model learns to separate
real edge cases from fraud patterns.

Hard negative categories:
  1. surge_pricing       — high fare ratio, but surge explains it
  2. airport_long        — long distance, unusual fare, UPI payment
  3. new_driver          — low account age, but no behavioural red flags
  4. night_premium       — late hour, higher fare, UPI not cash
  5. heavy_cargo         — short distance, high fare, loading time

Column order matches model.features.FEATURE_COLUMNS exactly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List, Optional

from model.features import FEATURE_COLUMNS

rng = np.random.default_rng(99)   # separate seed from training data


# ---------------------------------------------------------------------------
# Feature-vector builders — one per hard-negative type
# Each returns an (n, 31) ndarray in FEATURE_COLUMNS order.
# ---------------------------------------------------------------------------

def _surge_pricing(n: int) -> np.ndarray:
    """
    Legitimate surge-pricing trips.

    Fraud signal present:  high fare_to_expected_ratio (2.5-4.0×)
    Why it's not fraud:    surge_multiplier matches and explains fare
                           UPI payment, verified driver, no cancellations
    """
    surge     = rng.uniform(2.5, 4.0, n)
    distance  = rng.uniform(8, 25, n)
    duration  = distance / rng.uniform(18, 28, n) * 60
    fare      = (50 + 12 * distance) * surge * rng.uniform(0.95, 1.05, n)
    fare_per_km = fare / np.clip(distance, 0.1, None)
    haversine = distance * rng.uniform(0.88, 0.97, n)

    rows = np.column_stack([
        distance,                           # declared_distance_km
        duration,                           # declared_duration_min
        fare,                               # fare_inr
        surge,                              # surge_multiplier
        rng.uniform(3.0, 6.0, n),          # zone_demand_at_time (high — explains surge)
        fare / np.clip(50 + 12 * distance, 1, None),  # fare_to_expected_ratio
        distance / np.clip(duration, 0.1, None),       # distance_time_ratio
        fare_per_km,                        # fare_per_km
        haversine,                          # pickup_dropoff_haversine_km
        distance / np.clip(haversine, 0.1, None),      # distance_vs_haversine_ratio
        rng.integers(8, 20, n).astype(float),  # hour_of_day (daytime)
        rng.integers(0, 7, n).astype(float),   # day_of_week
        np.zeros(n),                        # is_night = 0
        np.ones(n),                         # is_peak_hour = 1
        rng.integers(0, 2, n).astype(float),   # is_friday
        rng.integers(0, 2, n).astype(float),   # is_late_month
        np.zeros(n),                        # payment_is_cash = 0 (UPI)
        np.zeros(n),                        # payment_is_credit = 0
        rng.uniform(0, 1, n),              # driver_cancellation_velocity_1hr (low)
        rng.uniform(0, 0.05, n),           # driver_cancel_rate_rolling_7d
        rng.uniform(0, 0.04, n),           # driver_dispute_rate_rolling_14d
        rng.uniform(4, 14, n),             # driver_trips_last_24hr (normal)
        rng.uniform(0.05, 0.25, n),        # driver_cash_trip_ratio_7d (low)
        rng.uniform(365, 1500, n),         # driver_account_age_days (established)
        rng.uniform(4.0, 5.0, n),         # driver_rating (good)
        rng.uniform(500, 3000, n),         # driver_lifetime_trips (experienced)
        rng.integers(1, 3, n).astype(float),  # driver_verification_encoded (verified)
        rng.integers(0, 3, n).astype(float),  # driver_payment_type_encoded
        rng.uniform(0.02, 0.07, n),        # zone_fraud_rate_rolling_7d (normal)
        np.zeros(n),                        # same_zone_trip = 0
        np.zeros(n),                        # is_cancelled = 0
    ])
    return rows


def _airport_long_distance(n: int) -> np.ndarray:
    """
    Airport / intercity trips.

    Fraud signal present:  unusual distance (25-60km), high fare
    Why it's not fraud:    distance/haversine ratio is ~1.1 (straight line)
                           UPI or credit, no cancellations, verified driver
    """
    distance  = rng.uniform(25, 60, n)
    duration  = distance / rng.uniform(35, 55, n) * 60
    fare      = 200 + 18 * distance * rng.uniform(0.9, 1.1, n)
    haversine = distance * rng.uniform(0.88, 0.98, n)
    fare_per_km = fare / np.clip(distance, 0.1, None)
    surge     = rng.uniform(1.0, 1.5, n)

    rows = np.column_stack([
        distance,
        duration,
        fare,
        surge,
        rng.uniform(0.5, 1.5, n),          # zone_demand_at_time
        fare / np.clip(50 + 12 * distance, 1, None),  # fare_to_expected_ratio
        distance / np.clip(duration, 0.1, None),
        fare_per_km,
        haversine,
        distance / np.clip(haversine, 0.1, None),
        rng.integers(3, 23, n).astype(float),  # hour_of_day (any hour for airport)
        rng.integers(0, 7, n).astype(float),
        rng.integers(0, 2, n).astype(float),   # is_night (airport = any hour)
        np.zeros(n),                        # is_peak_hour = 0 (airport not peak)
        rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),                        # payment_is_cash = 0
        rng.choice([0, 1], n, p=[0.7, 0.3]).astype(float),  # credit more likely for airport
        rng.uniform(0, 0.5, n),            # driver_cancellation_velocity_1hr
        rng.uniform(0, 0.04, n),
        rng.uniform(0, 0.03, n),
        rng.uniform(2, 10, n),             # driver_trips_last_24hr (fewer for airport drivers)
        rng.uniform(0.05, 0.20, n),
        rng.uniform(180, 2000, n),
        rng.uniform(4.0, 5.0, n),
        rng.uniform(200, 4000, n),
        rng.integers(1, 3, n).astype(float),
        rng.integers(0, 3, n).astype(float),
        rng.uniform(0.02, 0.06, n),
        np.zeros(n),                        # same_zone_trip = 0 (airport always different)
        np.zeros(n),
    ])
    return rows


def _new_driver_legitimate(n: int) -> np.ndarray:
    """
    New but legitimate drivers.

    Fraud signal present:  low driver_account_age_days (7-60 days)
                           low driver_lifetime_trips (5-50)
    Why it's not fraud:    normal fare ratio (~1.0), UPI payment
                           no cancellation velocity, normal distance
    """
    distance  = rng.uniform(3, 15, n)
    duration  = distance / rng.uniform(15, 25, n) * 60
    fare      = (50 + 12 * distance) * rng.uniform(0.95, 1.08, n)
    haversine = distance * rng.uniform(0.85, 0.98, n)

    rows = np.column_stack([
        distance,
        duration,
        fare,
        np.ones(n),                         # surge_multiplier = 1.0 (no surge)
        rng.uniform(0.5, 2.0, n),
        fare / np.clip(50 + 12 * distance, 1, None),  # fare ratio ~1.0
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        distance / np.clip(haversine, 0.1, None),
        rng.integers(9, 19, n).astype(float),
        rng.integers(0, 7, n).astype(float),
        np.zeros(n),                        # is_night = 0
        rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),                        # is_late_month = 0
        np.zeros(n),                        # payment_is_cash = 0
        np.zeros(n),
        np.zeros(n),                        # cancellation_velocity = 0
        np.zeros(n),                        # cancel_rate = 0 (new, no history)
        np.zeros(n),                        # dispute_rate = 0
        rng.uniform(1, 8, n),              # driver_trips_last_24hr (few trips)
        np.zeros(n),                        # cash_trip_ratio = 0 (new → UPI)
        rng.uniform(7, 60, n),             # driver_account_age_days (KEY: new driver)
        rng.uniform(3.8, 4.9, n),         # driver_rating (decent for new)
        rng.uniform(5, 50, n),             # driver_lifetime_trips (KEY: new)
        np.zeros(n),                        # driver_verification_encoded = 0 (unverified but new)
        np.zeros(n),                        # driver_payment_type_encoded
        rng.uniform(0.02, 0.05, n),        # zone_fraud_rate (low zone risk)
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),
    ])
    return rows


def _heavy_cargo_loading(n: int) -> np.ndarray:
    """
    Heavy cargo/loading trips.

    Fraud signal present:  short distance (1-5km), very high fare (₹400-900)
                           → fare_to_expected_ratio looks extreme
    Why it's not fraud:    loading time is real, payment is UPI/credit
                           no cancellations, normal driver behaviour
    """
    distance  = rng.uniform(1.5, 5.0, n)
    duration  = rng.uniform(45, 120, n)    # long due to loading/unloading
    fare      = rng.uniform(400, 900, n)
    haversine = distance * rng.uniform(0.88, 0.98, n)

    rows = np.column_stack([
        distance,
        duration,
        fare,
        np.ones(n),                         # surge = 1.0
        rng.uniform(0.5, 1.5, n),
        fare / np.clip(50 + 12 * distance, 1, None),  # high fare ratio (loading)
        distance / np.clip(duration, 0.1, None),       # low speed (loading time)
        fare / np.clip(distance, 0.1, None),           # high per-km (short trip)
        haversine,
        distance / np.clip(haversine, 0.1, None),
        rng.integers(7, 17, n).astype(float),
        rng.integers(0, 5, n).astype(float),   # weekday
        np.zeros(n),                        # is_night = 0
        np.zeros(n),                        # is_peak_hour = 0
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),
        np.zeros(n),                        # payment_is_cash = 0
        rng.choice([0, 1], n, p=[0.6, 0.4]).astype(float),  # credit for cargo
        rng.uniform(0, 0.5, n),
        rng.uniform(0, 0.04, n),
        rng.uniform(0, 0.03, n),
        rng.uniform(3, 12, n),
        rng.uniform(0.05, 0.20, n),
        rng.uniform(180, 1500, n),
        rng.uniform(4.0, 5.0, n),
        rng.uniform(300, 3000, n),
        rng.integers(1, 3, n).astype(float),
        rng.integers(0, 3, n).astype(float),
        rng.uniform(0.02, 0.07, n),
        np.ones(n),                         # same_zone_trip = 1 (short cargo trips)
        np.zeros(n),
    ])
    return rows


def _night_premium_legitimate(n: int) -> np.ndarray:
    """
    Legitimate night-time premium trips.

    Fraud signal present:  is_night=1, slightly elevated fare ratio
    Why it's not fraud:    UPI payment (not cash), no cancellations
                           normal distance, established driver
    """
    distance  = rng.uniform(5, 20, n)
    duration  = distance / rng.uniform(20, 35, n) * 60
    night_premium = rng.uniform(1.15, 1.35, n)
    fare      = (50 + 12 * distance) * night_premium
    haversine = distance * rng.uniform(0.88, 0.97, n)

    rows = np.column_stack([
        distance,
        duration,
        fare,
        rng.uniform(1.0, 1.5, n),          # surge
        rng.uniform(0.5, 1.5, n),
        fare / np.clip(50 + 12 * distance, 1, None),  # fare ratio (slightly elevated)
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        distance / np.clip(haversine, 0.1, None),
        rng.integers(22, 24, n).astype(float),  # hour (late night)
        rng.integers(0, 7, n).astype(float),
        np.ones(n),                         # is_night = 1 (KEY: night trip)
        np.zeros(n),                        # is_peak_hour = 0
        rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),                        # payment_is_cash = 0 (KEY: UPI not cash)
        np.zeros(n),
        rng.uniform(0, 0.5, n),            # cancel velocity (low)
        rng.uniform(0, 0.05, n),
        rng.uniform(0, 0.04, n),
        rng.uniform(3, 12, n),
        rng.uniform(0.05, 0.25, n),
        rng.uniform(180, 1500, n),
        rng.uniform(3.8, 5.0, n),
        rng.uniform(200, 2500, n),
        rng.integers(1, 3, n).astype(float),
        rng.integers(0, 3, n).astype(float),
        rng.uniform(0.02, 0.08, n),
        np.zeros(n),                        # same_zone_trip = 0
        np.zeros(n),
    ])
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_GENERATORS = {
    "surge_pricing":         _surge_pricing,
    "airport_long_distance": _airport_long_distance,
    "new_driver_legitimate": _new_driver_legitimate,
    "heavy_cargo_loading":   _heavy_cargo_loading,
    "night_premium":         _night_premium_legitimate,
}


def generate_hard_negatives(
    n_per_type: int = 500,
    types: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Generate hard negative feature vectors for model training.

    Args:
        n_per_type: number of examples per hard-negative category
        types:      subset of categories to generate (default: all)

    Returns:
        DataFrame with FEATURE_COLUMNS + is_fraud=0 + fraud_confidence_score=1.0
        Ready to concatenate with X_train / y_train / weights.
    """
    active = types if types else list(_GENERATORS.keys())
    frames = []

    for name in active:
        gen_fn = _GENERATORS[name]
        arr    = gen_fn(n_per_type)
        df     = pd.DataFrame(arr, columns=FEATURE_COLUMNS)
        df["_hn_type"] = name
        frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    result["is_fraud"]               = 0
    result["fraud_confidence_score"] = 1.0   # full weight — these are ground-truth clean

    total = len(result)
    print(f"Hard negatives generated: {total} total")
    for name in active:
        count = (result["_hn_type"] == name).sum()
        print(f"  {name:<28} {count:>5}")

    return result


if __name__ == "__main__":
    df = generate_hard_negatives(n_per_type=500)
    out = "data/raw/hard_negatives.csv"
    df.drop(columns=["_hn_type"]).to_csv(out, index=False)
    print(f"\nSaved {len(df)} hard negatives → {out}")
