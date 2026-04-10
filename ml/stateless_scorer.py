"""
Stateless inference engine.
Scores a single trip without pandas DataFrames.
Reads driver and zone features from Redis.
No CSV loading required at inference time.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def build_feature_vector(
    trip: Dict,
    driver_features: Dict,
    zone_features: Dict,
    feature_names: List[str],
) -> np.ndarray:
    """
    Build a feature vector from a trip dict +
    precomputed Redis features.
    No pandas. No DataFrame. Pure numpy.

    All features must match the training schema
    in model/features.py FEATURE_COLUMNS exactly.
    """
    import math
    from generator.config import VEHICLE_TYPES

    # Trip-level fields
    fare     = float(trip.get("fare_inr", 0))
    distance = max(float(trip.get("declared_distance_km", 1)), 0.01)
    duration = max(float(trip.get("declared_duration_min", 1)), 0.01)
    surge    = float(trip.get("surge_multiplier", 1.0))
    zone_demand = float(trip.get("zone_demand_at_time", 1.0))
    hour     = int(trip.get("hour_of_day", 12))
    dow      = int(trip.get("day_of_week", 0))
    is_night = int(trip.get("is_night", 0))
    is_peak  = int(trip.get("is_peak_hour", 0))

    # Derived temporal flags
    is_friday    = 1 if dow == 4 else 0
    is_late_month = int(trip.get("is_late_month", 0))
    if not is_late_month:
        # Infer from requested_at if available
        requested_at = trip.get("requested_at", "")
        try:
            from datetime import datetime as _dt
            ts = _dt.fromisoformat(str(requested_at).replace("Z", "+00:00"))
            is_late_month = 1 if ts.day >= 25 else 0
        except Exception:
            is_late_month = 0

    # Haversine distance
    lat1 = math.radians(float(trip.get("pickup_lat", 0)))
    lon1 = math.radians(float(trip.get("pickup_lon", 0)))
    lat2 = math.radians(float(trip.get("dropoff_lat", 0)))
    lon2 = math.radians(float(trip.get("dropoff_lon", 0)))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    haversine_km = max(6371 * 2 * math.asin(math.sqrt(min(a, 1.0))), 0.1)

    # Expected fare from vehicle type
    vtype    = trip.get("vehicle_type", "two_wheeler")
    veh      = VEHICLE_TYPES.get(vtype)
    base_fare = veh.base_fare if veh else 50
    per_km    = veh.per_km_rate if veh else 15
    expected  = base_fare + per_km * distance
    fare_ratio = fare / max(expected, 1.0)

    # Derived ratios matching FEATURE_COLUMNS names exactly
    distance_time_ratio   = distance / duration           # km/min
    fare_per_km           = fare / distance
    distance_vs_haversine = distance / haversine_km

    # Payment flags
    payment_mode    = trip.get("payment_mode", "").lower()
    payment_is_cash   = 1 if payment_mode == "cash" else 0
    payment_is_credit = 1 if payment_mode in ("credit", "card") else 0

    # Same-zone trip flag
    pickup_zone  = trip.get("pickup_zone_id", "")
    dropoff_zone = trip.get("dropoff_zone_id", "")
    same_zone_trip = 1 if pickup_zone and pickup_zone == dropoff_zone else 0

    # Cancelled flag
    is_cancelled = 1 if trip.get("status", "") == "cancelled_by_driver" else 0

    # Zone features from Redis
    zone_fraud_7d = float(zone_features.get("zone_fraud_rate_rolling_7d", 0.05))

    # Driver features from Redis — use exact FEATURE_COLUMNS key names.
    # IMPORTANT: defaults here are the population-median values from training data.
    # driver_lifetime_trips=0 is the strongest fraud predictor (new/unknown accounts).
    # When Redis is cold/empty use 500 (median established driver) to avoid every
    # trip scoring as action-tier before the feature store is warmed up.
    drv_cancel_vel     = float(driver_features.get("driver_cancellation_velocity_1hr",
                              driver_features.get("cancel_rate", 0.0) * 5))
    drv_cancel_7d      = float(driver_features.get("driver_cancel_rate_rolling_7d",
                              driver_features.get("cancel_rate", 0.05)))
    drv_dispute_14d    = float(driver_features.get("driver_dispute_rate_rolling_14d", 0.02))
    drv_trips_24h      = float(driver_features.get("driver_trips_last_24hr",
                              driver_features.get("total_trips", 8)))
    drv_cash_ratio_7d  = float(driver_features.get("driver_cash_trip_ratio_7d",
                              driver_features.get("cash_ratio", 0.25)))
    drv_acct_age       = float(driver_features.get("driver_account_age_days", 365))
    drv_rating         = float(driver_features.get("driver_rating",
                              driver_features.get("avg_rating", 4.3)))
    drv_lifetime_trips = float(driver_features.get("driver_lifetime_trips",
                              driver_features.get("total_trips", 500)))

    # Verification: feature_store stores driver_is_verified (0/1),
    # model expects driver_verification_encoded (0=verified, 1=pending, 2=unverified)
    is_verified_raw = driver_features.get("driver_is_verified", 1)
    drv_verification_enc = 0 if is_verified_raw else 2

    # Payment type: model expects driver_payment_type_encoded (0=upi, 1=bank, 2=cash)
    drv_payment_enc = int(driver_features.get("driver_payment_type_encoded", 0))

    # Build feature dict with exact FEATURE_COLUMNS names
    feature_dict = {
        "declared_distance_km":          distance,
        "declared_duration_min":         duration,
        "fare_inr":                      fare,
        "surge_multiplier":              surge,
        "zone_demand_at_time":           zone_demand,
        "fare_to_expected_ratio":        fare_ratio,
        "distance_time_ratio":           distance_time_ratio,
        "fare_per_km":                   fare_per_km,
        "pickup_dropoff_haversine_km":   haversine_km,
        "distance_vs_haversine_ratio":   distance_vs_haversine,
        "hour_of_day":                   float(hour),
        "day_of_week":                   float(dow),
        "is_night":                      float(is_night),
        "is_peak_hour":                  float(is_peak),
        "is_friday":                     float(is_friday),
        "is_late_month":                 float(is_late_month),
        "payment_is_cash":               float(payment_is_cash),
        "payment_is_credit":             float(payment_is_credit),
        "driver_cancellation_velocity_1hr": drv_cancel_vel,
        "driver_cancel_rate_rolling_7d": drv_cancel_7d,
        "driver_dispute_rate_rolling_14d": drv_dispute_14d,
        "driver_trips_last_24hr":        drv_trips_24h,
        "driver_cash_trip_ratio_7d":     drv_cash_ratio_7d,
        "driver_account_age_days":       drv_acct_age,
        "driver_rating":                 drv_rating,
        "driver_lifetime_trips":         drv_lifetime_trips,
        "driver_verification_encoded":   float(drv_verification_enc),
        "driver_payment_type_encoded":   float(drv_payment_enc),
        "zone_fraud_rate_rolling_7d":    zone_fraud_7d,
        "same_zone_trip":                float(same_zone_trip),
        "is_cancelled":                  float(is_cancelled),
    }

    # Build vector in exact feature_names order
    vector = [float(feature_dict.get(fname, 0.0)) for fname in feature_names]
    return np.array(vector, dtype=np.float32)


async def score_trip_stateless(
    trip: Dict,
    model,
    feature_names: List[str],
    two_stage_config: Dict,
) -> Dict:
    """
    Score a single trip with zero pandas dependency.
    Used by both the API endpoint and the ingestion pipeline.
    """
    from ml.feature_store import (
        get_driver_features, get_zone_features
    )
    from model.scoring import get_tier

    driver_id = trip.get("driver_id", "unknown")
    zone_id   = trip.get("pickup_zone_id", "unknown")

    # Fetch precomputed features from Redis
    driver_features = await get_driver_features(driver_id)
    zone_features   = await get_zone_features(zone_id)

    # Build feature vector
    X = build_feature_vector(
        trip, driver_features,
        zone_features, feature_names
    )

    # Score
    fraud_prob = float(
        model.predict_proba(X.reshape(1, -1))[0, 1]
    )
    tier = get_tier(fraud_prob)

    return {
        "fraud_probability": round(fraud_prob, 4),
        "tier":              tier.name,
        "tier_label":        tier.label,
        "tier_color":        tier.color,
        "action_required":   tier.action,
        "is_fraud_predicted":tier.name in (
            "action", "watchlist"
        ),
        # Return feature values so callers avoid a second Redis round-trip
        "feature_vals": dict(zip(feature_names, X.tolist())),
    }
