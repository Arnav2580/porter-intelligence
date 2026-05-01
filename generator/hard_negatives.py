"""
Porter Intelligence Platform — Hard Negative Feature Generator v2

Generates CLEAN feature vectors that look suspicious but are legitimate.
Column order matches model.features.FEATURE_COLUMNS exactly (46 features).

Hard negative categories:
  1. surge_pricing       — high fare ratio, but surge explains it
  2. airport_long        — long distance, high fare, UPI
  3. new_driver          — low account age, no behavioural red flags
  4. night_premium       — late hour, higher fare, UPI not cash
  5. heavy_cargo         — short distance, high fare + loading charge
  6. construction_detour — gps_tracked/haversine > 2.0, legitimate detour
  7. festival_surge      — extreme surge, mock_location=False
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List, Optional

from model.features import FEATURE_COLUMNS

rng = np.random.default_rng(99)

# FEATURE_COLUMNS order (46 total):
# 0  declared_distance_km
# 1  actual_trip_duration_mins
# 2  fare_inr
# 3  surge_multiplier
# 4  zone_demand_at_time
# 5  fare_to_expected_ratio
# 6  distance_time_ratio
# 7  fare_per_km
# 8  pickup_dropoff_haversine_km
# 9  distance_vs_haversine_ratio
# 10 gps_ping_count
# 11 gps_accuracy_avg_m
# 12 mock_location_flag
# 13 gps_provider_encoded
# 14 avg_speed_kmh
# 15 max_speed_kmh
# 16 waiting_time_mins
# 17 loading_time_mins
# 18 loading_anomaly_score
# 19 pod_photo_captured
# 20 pod_location_match
# 21 otp_verified
# 22 otp_attempt_count
# 23 hour_of_day
# 24 day_of_week
# 25 is_night
# 26 is_peak_hour
# 27 is_friday
# 28 is_late_month
# 29 payment_is_cash
# 30 payment_is_credit
# 31 driver_cancellation_velocity_1hr
# 32 driver_cancel_rate_rolling_7d
# 33 driver_dispute_rate_rolling_14d
# 34 driver_trips_last_24hr
# 35 driver_cash_trip_ratio_7d
# 36 driver_account_age_days
# 37 driver_rating
# 38 driver_lifetime_trips
# 39 driver_verification_encoded
# 40 driver_payment_type_encoded
# 41 zone_fraud_rate_rolling_7d
# 42 same_zone_trip
# 43 is_cancelled


def _surge_pricing(n: int) -> np.ndarray:
    """Legitimate surge trips. Surge-adjusted fare ratio ≈ 1.0."""
    surge    = rng.uniform(1.5, 4.5, n)
    distance = rng.uniform(8, 25, n)
    duration = distance / rng.uniform(18, 28, n) * 60
    fare     = (50 + 12 * distance) * surge * rng.uniform(0.95, 1.05, n)
    haversine = distance * rng.uniform(0.88, 0.97, n)
    surge_adj = np.clip(50 + 12 * distance, 1, None) * np.clip(surge, 1, None)
    fare_ratio = fare / surge_adj
    ping_count = (duration * 3).astype(int).clip(min=5)
    speed      = distance / (duration / 60)
    return np.column_stack([
        distance, duration, fare, surge,
        rng.uniform(3.0, 6.0, n),          # zone_demand
        fare_ratio,                          # ~1.0
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        distance / np.clip(haversine, 0.1, None),
        ping_count.astype(float),           # normal pings
        rng.uniform(4, 18, n),              # normal accuracy
        np.zeros(n),                         # mock_location=0
        np.zeros(n),                         # gps_provider=gps
        speed,                               # avg_speed
        speed * rng.uniform(1.2, 1.6, n),  # max_speed
        rng.uniform(0.5, 5.0, n),          # waiting_time
        np.zeros(n),                         # loading_time=0
        np.zeros(n),                         # loading_anomaly=0
        np.zeros(n),                         # pod_captured=0 (2W)
        np.zeros(n),                         # pod_location_match=0
        np.ones(n),                          # otp_verified=1
        np.ones(n),                          # otp_attempts=1
        rng.integers(8, 20, n).astype(float),
        rng.integers(0, 7, n).astype(float),
        np.zeros(n), np.ones(n),             # is_night=0, is_peak=1
        rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n), np.zeros(n),            # payment: UPI
        rng.uniform(0, 1, n),
        rng.uniform(0, 0.05, n),
        rng.uniform(0, 0.04, n),
        rng.uniform(4, 14, n),
        rng.uniform(0.05, 0.25, n),
        rng.uniform(365, 1500, n),
        rng.uniform(4.0, 5.0, n),
        rng.uniform(500, 3000, n),
        np.zeros(n), np.zeros(n),            # verified, upi
        rng.uniform(0.02, 0.07, n),
        np.zeros(n), np.zeros(n),            # same_zone=0, is_cancelled=0
    ])


def _airport_long_distance(n: int) -> np.ndarray:
    """Airport/intercity trips. Unusual distance (25-60km), UPI."""
    distance  = rng.uniform(25, 60, n)
    duration  = distance / rng.uniform(35, 55, n) * 60
    fare      = 200 + 18 * distance * rng.uniform(0.9, 1.1, n)
    haversine = distance * rng.uniform(0.88, 0.98, n)
    surge     = rng.uniform(1.0, 1.5, n)
    ping_count = (duration * 3).astype(int).clip(min=10)
    speed      = distance / (duration / 60)
    return np.column_stack([
        distance, duration, fare, surge,
        rng.uniform(0.5, 1.5, n),
        fare / np.clip(50 + 12 * distance, 1, None),
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        distance / np.clip(haversine, 0.1, None),
        ping_count.astype(float),
        rng.uniform(5, 15, n),
        np.zeros(n), np.zeros(n),
        speed, speed * rng.uniform(1.2, 1.5, n),
        rng.uniform(1.0, 8.0, n),
        np.zeros(n), np.zeros(n),
        rng.choice([0, 1], n, p=[0.3, 0.7]).astype(float),  # trucks have POD
        np.ones(n),
        np.ones(n), np.ones(n),
        rng.integers(3, 23, n).astype(float),
        rng.integers(0, 7, n).astype(float),
        rng.integers(0, 2, n).astype(float), np.zeros(n),
        rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),
        rng.choice([0, 1], n, p=[0.7, 0.3]).astype(float),  # credit more likely
        rng.uniform(0, 0.5, n),
        rng.uniform(0, 0.04, n),
        rng.uniform(0, 0.03, n),
        rng.uniform(2, 10, n),
        rng.uniform(0.05, 0.20, n),
        rng.uniform(180, 2000, n),
        rng.uniform(4.0, 5.0, n),
        rng.uniform(200, 4000, n),
        np.zeros(n), np.zeros(n),
        rng.uniform(0.02, 0.06, n),
        np.zeros(n), np.zeros(n),
    ])


def _new_driver_legitimate(n: int) -> np.ndarray:
    """New but legitimate drivers. Low age, no behavioural flags."""
    distance  = rng.uniform(3, 15, n)
    duration  = distance / rng.uniform(15, 25, n) * 60
    fare      = (50 + 12 * distance) * rng.uniform(0.95, 1.08, n)
    haversine = distance * rng.uniform(0.85, 0.98, n)
    ping_count = (duration * 3).astype(int).clip(min=5)
    speed      = distance / (duration / 60)
    return np.column_stack([
        distance, duration, fare,
        np.ones(n),                          # surge=1.0
        rng.uniform(0.5, 2.0, n),
        fare / np.clip(50 + 12 * distance, 1, None),
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        distance / np.clip(haversine, 0.1, None),
        ping_count.astype(float),
        rng.uniform(5, 15, n),
        np.zeros(n), np.zeros(n),
        speed, speed * rng.uniform(1.2, 1.5, n),
        rng.uniform(0.5, 4.0, n),
        np.zeros(n), np.zeros(n),
        np.zeros(n), np.zeros(n),
        np.ones(n), np.ones(n),
        rng.integers(9, 19, n).astype(float),
        rng.integers(0, 7, n).astype(float),
        np.zeros(n), rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),
        np.zeros(n), np.zeros(n),
        np.zeros(n), np.zeros(n), np.zeros(n),
        rng.uniform(1, 8, n),
        np.zeros(n),
        rng.uniform(7, 60, n),               # KEY: new driver age
        rng.uniform(3.8, 4.9, n),
        rng.uniform(5, 50, n),               # KEY: few trips
        np.zeros(n), np.zeros(n),
        rng.uniform(0.02, 0.05, n),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),
    ])


def _heavy_cargo_loading(n: int) -> np.ndarray:
    """Heavy cargo with real loading time. Short distance, high fare — legitimate."""
    distance     = rng.uniform(1.5, 5.0, n)
    loading_time = rng.uniform(30, 90, n)
    duration     = distance / rng.uniform(12, 18, n) * 60 + loading_time
    fare         = rng.uniform(400, 900, n)
    haversine    = distance * rng.uniform(0.88, 0.98, n)
    # loading_anomaly: loading_time / p75(boxes_mixed=22) → 1.4–4.0 = high but legit
    loading_anomaly = loading_time / 22.0
    ping_count   = (duration * 3).astype(int).clip(min=10)
    speed        = distance / (duration / 60)
    return np.column_stack([
        distance, duration, fare,
        np.ones(n),
        rng.uniform(0.5, 1.5, n),
        fare / np.clip(50 + 12 * distance, 1, None),   # high ratio — legit loading
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        distance / np.clip(haversine, 0.1, None),
        ping_count.astype(float),
        rng.uniform(5, 15, n),
        np.zeros(n), np.zeros(n),
        speed, speed * rng.uniform(1.1, 1.4, n),
        rng.uniform(5, 20, n),
        loading_time,
        loading_anomaly,
        np.ones(n),                          # POD captured (trucks)
        np.ones(n),                          # POD location match
        np.ones(n), np.ones(n),
        rng.integers(7, 17, n).astype(float),
        rng.integers(0, 5, n).astype(float),
        np.zeros(n), np.zeros(n),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n),
        np.zeros(n),
        rng.choice([0, 1], n, p=[0.6, 0.4]).astype(float),
        rng.uniform(0, 0.5, n),
        rng.uniform(0, 0.04, n),
        rng.uniform(0, 0.03, n),
        rng.uniform(3, 12, n),
        rng.uniform(0.05, 0.20, n),
        rng.uniform(180, 1500, n),
        rng.uniform(4.0, 5.0, n),
        rng.uniform(300, 3000, n),
        np.zeros(n), np.zeros(n),
        rng.uniform(0.02, 0.07, n),
        np.ones(n),                          # same_zone (short cargo)
        np.zeros(n),
    ])


def _night_premium_legitimate(n: int) -> np.ndarray:
    """Night premium trips. UPI not cash — legitimate."""
    distance      = rng.uniform(5, 20, n)
    duration      = distance / rng.uniform(20, 35, n) * 60
    night_premium = rng.uniform(1.15, 1.35, n)
    fare          = (50 + 12 * distance) * night_premium
    haversine     = distance * rng.uniform(0.88, 0.97, n)
    ping_count    = (duration * 3).astype(int).clip(min=5)
    speed         = distance / (duration / 60)
    return np.column_stack([
        distance, duration, fare,
        rng.uniform(1.0, 1.5, n),
        rng.uniform(0.5, 1.5, n),
        fare / np.clip(50 + 12 * distance, 1, None),
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        distance / np.clip(haversine, 0.1, None),
        ping_count.astype(float),
        rng.uniform(5, 18, n),
        np.zeros(n), np.zeros(n),
        speed, speed * rng.uniform(1.2, 1.6, n),
        rng.uniform(0.5, 5.0, n),
        np.zeros(n), np.zeros(n),
        np.zeros(n), np.zeros(n),
        np.ones(n), np.ones(n),
        rng.integers(22, 24, n).astype(float),
        rng.integers(0, 7, n).astype(float),
        np.ones(n), np.zeros(n),             # is_night=1, is_peak=0
        rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n), np.zeros(n),            # UPI, not cash
        rng.uniform(0, 0.5, n),
        rng.uniform(0, 0.05, n),
        rng.uniform(0, 0.04, n),
        rng.uniform(3, 12, n),
        rng.uniform(0.05, 0.25, n),
        rng.uniform(180, 1500, n),
        rng.uniform(3.8, 5.0, n),
        rng.uniform(200, 2500, n),
        np.zeros(n), np.zeros(n),
        rng.uniform(0.02, 0.08, n),
        np.zeros(n), np.zeros(n),
    ])


def _construction_detour(n: int) -> np.ndarray:
    """Legitimate detour due to road closure. High GPS/haversine ratio but real."""
    distance  = rng.uniform(5, 20, n)
    duration  = distance / rng.uniform(10, 18, n) * 60   # slow due to detour
    fare      = (50 + 12 * distance) * rng.uniform(0.95, 1.10, n)
    # haversine much shorter — detour makes GPS ratio high
    haversine = distance * rng.uniform(0.30, 0.50, n)
    gps_ratio = distance / np.clip(haversine, 0.1, None)  # 2.0–6.0 but legitimate
    ping_count = (duration * 3).astype(int).clip(min=10)
    speed      = distance / (duration / 60)
    return np.column_stack([
        distance, duration, fare,
        rng.uniform(1.0, 1.3, n),
        rng.uniform(0.5, 2.0, n),
        fare / np.clip(50 + 12 * distance, 1, None),
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        gps_ratio,                           # KEY: high but legitimate
        ping_count.astype(float),           # normal pings (real movement)
        rng.uniform(5, 15, n),              # normal accuracy (not mock)
        np.zeros(n), np.zeros(n),           # mock=0, provider=gps
        speed, speed * rng.uniform(1.2, 1.5, n),
        rng.uniform(0.5, 5.0, n),
        np.zeros(n), np.zeros(n),
        np.zeros(n), np.zeros(n),
        np.ones(n), np.ones(n),
        rng.integers(7, 20, n).astype(float),
        rng.integers(0, 7, n).astype(float),
        np.zeros(n), rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        rng.integers(0, 2, n).astype(float),
        np.zeros(n), np.zeros(n),
        rng.uniform(0, 1, n),
        rng.uniform(0, 0.06, n),
        rng.uniform(0, 0.05, n),
        rng.uniform(4, 14, n),
        rng.uniform(0.05, 0.30, n),
        rng.uniform(180, 1500, n),
        rng.uniform(3.8, 5.0, n),
        rng.uniform(100, 2000, n),
        np.zeros(n), np.zeros(n),
        rng.uniform(0.02, 0.08, n),
        np.zeros(n), np.zeros(n),
    ])


def _festival_surge(n: int) -> np.ndarray:
    """Extreme surge during festivals. Fare 3-5x but surge justifies it."""
    surge    = rng.uniform(3.0, 5.5, n)
    distance = rng.uniform(5, 18, n)
    duration = distance / rng.uniform(15, 22, n) * 60
    fare     = (50 + 12 * distance) * surge * rng.uniform(0.95, 1.05, n)
    haversine = distance * rng.uniform(0.88, 0.97, n)
    surge_adj = np.clip(50 + 12 * distance, 1, None) * np.clip(surge, 1, None)
    fare_ratio = fare / surge_adj  # ≈ 1.0 — surge explains it all
    ping_count = (duration * 3).astype(int).clip(min=5)
    speed      = distance / (duration / 60)
    return np.column_stack([
        distance, duration, fare, surge,
        rng.uniform(5.0, 10.0, n),           # very high demand
        fare_ratio,
        distance / np.clip(duration, 0.1, None),
        fare / np.clip(distance, 0.1, None),
        haversine,
        distance / np.clip(haversine, 0.1, None),
        ping_count.astype(float),
        rng.uniform(5, 15, n),
        np.zeros(n), np.zeros(n),
        speed, speed * rng.uniform(1.2, 1.5, n),
        rng.uniform(1.0, 10.0, n),
        np.zeros(n), np.zeros(n),
        np.zeros(n), np.zeros(n),
        np.ones(n), np.ones(n),
        rng.integers(18, 24, n).astype(float),
        rng.integers(4, 7, n).astype(float),  # weekend/friday
        rng.integers(0, 2, n).astype(float), np.ones(n),
        np.ones(n),                           # is_friday
        rng.integers(0, 2, n).astype(float),
        np.zeros(n), np.zeros(n),
        rng.uniform(0, 2, n),
        rng.uniform(0, 0.08, n),
        rng.uniform(0, 0.05, n),
        rng.uniform(5, 18, n),
        rng.uniform(0.05, 0.30, n),
        rng.uniform(180, 1500, n),
        rng.uniform(3.8, 5.0, n),
        rng.uniform(200, 3000, n),
        np.zeros(n), np.zeros(n),
        rng.uniform(0.03, 0.10, n),
        np.zeros(n), np.zeros(n),
    ])


_GENERATORS = {
    "surge_pricing":         _surge_pricing,
    "airport_long_distance": _airport_long_distance,
    "new_driver_legitimate": _new_driver_legitimate,
    "heavy_cargo_loading":   _heavy_cargo_loading,
    "night_premium":         _night_premium_legitimate,
    "construction_detour":   _construction_detour,
    "festival_surge":        _festival_surge,
}


def generate_hard_negatives(
    n_per_type: int = 500,
    types: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Generate hard negative feature vectors for model training.
    Returns DataFrame with FEATURE_COLUMNS + is_fraud=0 + sample_weight=1.0.
    """
    active = types if types else list(_GENERATORS.keys())
    frames = []

    for name in active:
        arr = _GENERATORS[name](n_per_type)
        assert arr.shape[1] == len(FEATURE_COLUMNS), \
            f"{name}: expected {len(FEATURE_COLUMNS)} cols, got {arr.shape[1]}"
        df         = pd.DataFrame(arr, columns=FEATURE_COLUMNS)
        df["_hn_type"] = name
        frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    result["is_fraud"]     = 0
    result["sample_weight"] = 1.0   # full weight — ground-truth clean

    print(f"Hard negatives generated: {len(result)} total ({len(active)} types × {n_per_type})")
    for name in active:
        count = (result["_hn_type"] == name).sum()
        print(f"  {name:<28} {count:>5}")

    return result


if __name__ == "__main__":
    df = generate_hard_negatives(n_per_type=500)
    out = "data/raw/hard_negatives.csv"
    df.drop(columns=["_hn_type"]).to_csv(out, index=False)
    print(f"\nSaved {len(df)} hard negatives → {out}")
