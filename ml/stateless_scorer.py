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
    from generator.config import VEHICLE_TYPES

    # Trip-level features
    fare     = float(trip.get("fare_inr", 0))
    distance = float(trip.get("declared_distance_km", 1))
    duration = float(trip.get("declared_duration_min", 1))

    # Haversine distance
    import math
    lat1 = math.radians(float(trip.get("pickup_lat", 0)))
    lon1 = math.radians(float(trip.get("pickup_lon", 0)))
    lat2 = math.radians(float(trip.get("dropoff_lat", 0)))
    lon2 = math.radians(float(trip.get("dropoff_lon", 0)))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat/2)**2
         + math.cos(lat1) * math.cos(lat2)
         * math.sin(dlon/2)**2)
    haversine_km = 6371 * 2 * math.asin(math.sqrt(a))
    haversine_km = max(haversine_km, 0.1)

    # Expected fare from vehicle type
    vtype      = trip.get("vehicle_type", "two_wheeler")
    veh        = VEHICLE_TYPES.get(vtype)
    base_fare  = veh.base_fare if veh else 50
    per_km     = veh.per_km_rate if veh else 15
    expected   = base_fare + per_km * distance
    fare_ratio = fare / max(expected, 1.0)

    # Distance vs haversine ratio
    dist_ratio = distance / haversine_km

    # Speed
    speed = distance / max(duration / 60, 0.01)

    # Payment
    payment_is_cash = 1 if trip.get(
        "payment_mode", ""
    ) == "cash" else 0

    # Time features
    hour = int(trip.get("hour_of_day", 12))
    dow  = int(trip.get("day_of_week", 0))
    is_night     = int(trip.get("is_night", False))
    is_peak      = int(trip.get("is_peak_hour", False))
    surge        = float(trip.get("surge_multiplier", 1.0))
    zone_demand  = float(trip.get("zone_demand_at_time", 1.0))

    # Vehicle encoded
    vtypes_list  = list(VEHICLE_TYPES.keys())
    vehicle_enc  = vtypes_list.index(vtype) \
                   if vtype in vtypes_list else 0

    # Zone fraud rate
    zone_fraud   = float(
        zone_features.get("zone_fraud_rate_rolling_7d", 0.05)
    )

    # Driver features from Redis
    cancel_vel   = float(
        driver_features.get("cancel_rate", 0) * 5
    )
    dispute_rate = float(
        driver_features.get(
            "driver_dispute_rate_rolling_14d", 0
        )
    )
    acct_age     = float(
        driver_features.get("driver_account_age_days", 180)
    )
    is_verified  = float(
        driver_features.get("driver_is_verified", 1)
    )
    drv_cash     = float(
        driver_features.get("cash_ratio", 0.5)
    )
    drv_fare_avg = float(
        driver_features.get("avg_fare", 300)
    )

    # Is cancelled proxy
    is_cancelled = 1 if trip.get(
        "status", ""
    ) == "cancelled_by_driver" else 0

    # Build named feature dict
    feature_dict = {
        "fare_to_expected_ratio":              fare_ratio,
        "distance_vs_haversine_ratio":         dist_ratio,
        "speed_kmh":                           speed,
        "payment_is_cash":                     payment_is_cash,
        "is_night":                            is_night,
        "is_peak_hour":                        is_peak,
        "surge_multiplier":                    surge,
        "zone_demand_at_time":                 zone_demand,
        "hour_of_day":                         hour,
        "day_of_week":                         dow,
        "vehicle_type_encoded":                vehicle_enc,
        "fare_inr":                            fare,
        "declared_distance_km":                distance,
        "declared_duration_min":               duration,
        "haversine_distance_km":               haversine_km,
        "zone_fraud_rate_rolling_7d":          zone_fraud,
        "driver_cancellation_velocity_1hr":    cancel_vel,
        "driver_dispute_rate_rolling_14d":     dispute_rate,
        "driver_account_age_days":             acct_age,
        "driver_is_verified":                  is_verified,
        "driver_cash_trip_ratio":              drv_cash,
        "driver_avg_fare":                     drv_fare_avg,
        "is_cancelled":                        is_cancelled,
        "customer_complaint_flag":             int(
            trip.get("customer_complaint_flag", False)
        ),
        "pickup_lat":   float(trip.get("pickup_lat", 0)),
        "pickup_lon":   float(trip.get("pickup_lon", 0)),
        "dropoff_lat":  float(trip.get("dropoff_lat", 0)),
        "dropoff_lon":  float(trip.get("dropoff_lon", 0)),
        "recoverable_amount_inr": fare * 0.15,
        "fraud_confidence_score": 0.0,
    }

    # Build vector in exact feature_names order
    vector = []
    for fname in feature_names:
        vector.append(
            float(feature_dict.get(fname, 0.0))
        )

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
    }
