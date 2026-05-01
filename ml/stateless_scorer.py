"""
Stateless inference engine — v2 schema.
Scores a single trip without pandas DataFrames.
Reads driver and zone features from Redis.
No CSV loading required at inference time.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
import math

logger = logging.getLogger(__name__)


def build_feature_vector(
    trip: Dict,
    driver_features: Dict,
    zone_features: Dict,
    feature_names: List[str],
) -> np.ndarray:
    """
    Build a feature vector from a trip dict + precomputed Redis features.
    Matches FEATURE_COLUMNS in model/features.py exactly (v2, 44 features).
    """
    from generator.config import VEHICLE_TYPES, LOADING_TIME_NORMS_MIN

    # ── Trip-level ────────────────────────────────────────────
    fare     = float(trip.get("fare_inr", trip.get("fare", 0)))
    distance = max(float(trip.get("declared_distance_km", trip.get("distance_km", 1))), 0.01)
    duration = max(float(trip.get("actual_trip_duration_mins",
                                   trip.get("declared_duration_min", 1))), 0.01)
    surge    = float(trip.get("surge_multiplier", 1.0))
    zone_demand = float(trip.get("zone_demand_at_time", 1.0))
    hour     = int(trip.get("hour_of_day", 12))
    dow      = int(trip.get("day_of_week", 0))
    is_night = int(bool(trip.get("is_night", False)))
    is_peak  = int(bool(trip.get("is_peak_hour", False)))

    is_friday    = 1 if dow == 4 else 0
    is_late_month = int(trip.get("is_late_month", 0))
    if not is_late_month:
        try:
            from datetime import datetime as _dt
            ts = _dt.fromisoformat(str(trip.get("requested_at", "")).replace("Z", "+00:00"))
            is_late_month = 1 if ts.day >= 25 else 0
        except Exception:
            is_late_month = 0

    # ── Haversine ─────────────────────────────────────────────
    lat1 = math.radians(float(trip.get("pickup_lat", 0)))
    lon1 = math.radians(float(trip.get("pickup_lon", 0)))
    lat2 = math.radians(float(trip.get("dropoff_lat", 0)))
    lon2 = math.radians(float(trip.get("dropoff_lon", 0)))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    haversine_km = max(6371 * 2 * math.asin(math.sqrt(min(a, 1.0))), 0.1)

    # ── Expected fare ─────────────────────────────────────────
    vtype = trip.get("vehicle_type", "two_wheeler")
    veh   = VEHICLE_TYPES.get(vtype)
    base_fare = veh.base_fare if veh else 50
    per_km    = veh.per_km_rate if veh else 15
    expected  = base_fare + per_km * distance
    surge_adj_expected = max(expected, 1.0) * max(surge, 1.0)
    fare_ratio = fare / max(surge_adj_expected, 1.0)

    # ── Derived ratios ────────────────────────────────────────
    distance_time_ratio   = distance / duration
    fare_per_km           = fare / distance

    # GPS-tracked vs haversine
    gps_tracked = float(trip.get("gps_tracked_distance_km", distance))
    distance_vs_haversine = gps_tracked / haversine_km

    # ── GPS integrity ─────────────────────────────────────────
    gps_ping_count    = float(trip.get("gps_ping_count", int(duration * 3)))
    gps_accuracy_avg  = float(trip.get("gps_accuracy_avg_m", 10.0))
    mock_location     = float(bool(trip.get("mock_location_flag", False)))
    gps_provider_raw  = str(trip.get("gps_provider", "gps")).lower()
    gps_provider_enc  = {"gps": 0.0, "network": 1.0, "mock": 2.0}.get(gps_provider_raw, 0.0)
    avg_speed         = float(trip.get("avg_speed_kmh", distance / (duration / 60)))
    max_speed         = float(trip.get("max_speed_kmh", avg_speed * 1.4))

    # ── Timing ────────────────────────────────────────────────
    waiting_time  = float(trip.get("waiting_time_mins", 0.0))
    loading_time  = float(trip.get("loading_time_mins", 0.0))
    goods_cat     = str(trip.get("goods_category", "other"))
    norms         = LOADING_TIME_NORMS_MIN.get(goods_cat, (10.0, 22.0, 45.0))
    loading_anomaly = loading_time / max(norms[1], 0.1) if loading_time > 0 else 0.0

    # ── POD ───────────────────────────────────────────────────
    pod_captured      = float(bool(trip.get("pod_photo_captured", False)))
    pod_location_match = float(bool(trip.get("pod_location_match", True)))

    # ── OTP ───────────────────────────────────────────────────
    otp_verified  = float(bool(trip.get("otp_verified", True)))
    otp_attempts  = float(trip.get("otp_attempt_count", 1))

    # ── Payment ───────────────────────────────────────────────
    payment_mode = str(trip.get("payment_mode", trip.get("payment_type", ""))).lower()
    payment_is_cash   = 1.0 if payment_mode in ("cash",) else 0.0
    payment_is_credit = 1.0 if payment_mode in ("credit", "card") else 0.0

    # ── Geographic ───────────────────────────────────────────
    pickup_zone  = trip.get("pickup_zone_id", trip.get("zone", ""))
    dropoff_zone = trip.get("dropoff_zone_id", "")
    same_zone_trip = 1.0 if pickup_zone and pickup_zone == dropoff_zone else 0.0

    # ── Cancellation ─────────────────────────────────────────
    status_val = str(trip.get("trip_status", trip.get("status", ""))).lower()
    is_cancelled = 1.0 if status_val in ("cancelled_by_driver", "cancelled_by_customer") else 0.0

    # ── Zone features from Redis ──────────────────────────────
    zone_fraud_7d = float(zone_features.get("zone_fraud_rate_rolling_7d", 0.05))

    # ── Driver features from Redis ────────────────────────────
    drv_cancel_vel    = float(driver_features.get("driver_cancellation_velocity_1hr",
                              driver_features.get("cancel_rate", 0.0) * 5))
    drv_cancel_7d     = float(driver_features.get("driver_cancel_rate_rolling_7d",
                              driver_features.get("cancel_rate", 0.05)))
    drv_dispute_14d   = float(driver_features.get("driver_dispute_rate_rolling_14d", 0.02))
    drv_trips_24h     = float(driver_features.get("driver_trips_last_24hr",
                              driver_features.get("total_trips", 8)))
    drv_cash_ratio    = float(driver_features.get("driver_cash_trip_ratio_7d",
                              driver_features.get("cash_ratio", 0.25)))
    drv_acct_age      = float(driver_features.get("driver_account_age_days", 365))
    drv_rating        = float(driver_features.get("driver_rating",
                              driver_features.get("avg_rating", 4.3)))
    drv_lifetime      = float(driver_features.get("driver_lifetime_trips",
                              driver_features.get("total_trips", 500)))
    is_verified_raw   = driver_features.get("driver_is_verified", 1)
    drv_verif_enc     = 0.0 if is_verified_raw else 2.0
    drv_payment_enc   = float(driver_features.get("driver_payment_type_encoded", 0))

    # ── Assemble in FEATURE_COLUMNS order ────────────────────
    feature_dict = {
        "declared_distance_km":          distance,
        "actual_trip_duration_mins":     duration,
        "fare_inr":                      fare,
        "surge_multiplier":              surge,
        "zone_demand_at_time":           zone_demand,
        "fare_to_expected_ratio":        fare_ratio,
        "distance_time_ratio":           distance_time_ratio,
        "fare_per_km":                   fare_per_km,
        "pickup_dropoff_haversine_km":   haversine_km,
        "distance_vs_haversine_ratio":   distance_vs_haversine,
        "gps_ping_count":                gps_ping_count,
        "gps_accuracy_avg_m":            gps_accuracy_avg,
        "mock_location_flag":            mock_location,
        "gps_provider_encoded":          gps_provider_enc,
        "avg_speed_kmh":                 avg_speed,
        "max_speed_kmh":                 max_speed,
        "waiting_time_mins":             waiting_time,
        "loading_time_mins":             loading_time,
        "loading_anomaly_score":         loading_anomaly,
        "pod_photo_captured":            pod_captured,
        "pod_location_match":            pod_location_match,
        "otp_verified":                  otp_verified,
        "otp_attempt_count":             otp_attempts,
        "hour_of_day":                   float(hour),
        "day_of_week":                   float(dow),
        "is_night":                      float(is_night),
        "is_peak_hour":                  float(is_peak),
        "is_friday":                     float(is_friday),
        "is_late_month":                 float(is_late_month),
        "payment_is_cash":               payment_is_cash,
        "payment_is_credit":             payment_is_credit,
        "driver_cancellation_velocity_1hr": drv_cancel_vel,
        "driver_cancel_rate_rolling_7d": drv_cancel_7d,
        "driver_dispute_rate_rolling_14d": drv_dispute_14d,
        "driver_trips_last_24hr":        drv_trips_24h,
        "driver_cash_trip_ratio_7d":     drv_cash_ratio,
        "driver_account_age_days":       drv_acct_age,
        "driver_rating":                 drv_rating,
        "driver_lifetime_trips":         drv_lifetime,
        "driver_verification_encoded":   drv_verif_enc,
        "driver_payment_type_encoded":   drv_payment_enc,
        "zone_fraud_rate_rolling_7d":    zone_fraud_7d,
        "same_zone_trip":                same_zone_trip,
        "is_cancelled":                  is_cancelled,
    }

    vector = [float(feature_dict.get(fname, 0.0)) for fname in feature_names]
    return np.array(vector, dtype=np.float32)


async def score_trip_stateless(
    trip: Dict,
    model,
    feature_names: List[str],
    two_stage_config: Dict,
) -> Dict:
    """Score a single trip. Zero pandas dependency."""
    from ml.feature_store import get_driver_features, get_zone_features
    from model.scoring import get_tier

    driver_id = trip.get("driver_id", "unknown")
    zone_id   = trip.get("pickup_zone_id", trip.get("zone", "unknown"))

    driver_features = await get_driver_features(driver_id)
    zone_features   = await get_zone_features(zone_id)

    X = build_feature_vector(trip, driver_features, zone_features, feature_names)

    fraud_prob = float(model.predict_proba(X.reshape(1, -1))[0, 1])
    tier = get_tier(fraud_prob)

    return {
        "fraud_probability": round(fraud_prob, 4),
        "tier":              tier.name,
        "tier_label":        tier.label,
        "tier_color":        tier.color,
        "action_required":   tier.action,
        "is_fraud_predicted": tier.name in ("action", "watchlist"),
        "feature_vals": dict(zip(feature_names, X.tolist())),
    }
