"""
Redis-backed feature store for real-time inference.

Precomputes driver behavioral features and stores
them in Redis with 1-hour TTL.
Inference reads features from Redis instead of
scanning the full trips DataFrame.

Keys:
  driver_features:{driver_id}  → JSON feature dict
  zone_features:{zone_id}      → JSON zone stats
  model_threshold              → float
  model_version                → string
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

DRIVER_FEATURE_TTL = 3600     # 1 hour
ZONE_FEATURE_TTL   = 1800     # 30 minutes
FEATURE_VERSION    = "v1"


async def precompute_driver_features(
    trips_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
) -> int:
    """
    Precompute behavioral features for all drivers.
    Store in Redis. Called at startup and hourly refresh.
    Returns count of drivers cached.
    """
    from database.redis_client import cache_set

    if trips_df.empty or drivers_df.empty:
        return 0

    # Pre-parse timestamps once for the whole DataFrame (not per-driver)
    trips_ts = trips_df.copy()
    trips_ts["requested_at"] = pd.to_datetime(
        trips_ts["requested_at"], format="mixed"
    )
    cutoff_14d = trips_ts["requested_at"].max() - pd.Timedelta(days=14)

    # Pre-index driver profile for O(1) lookups
    driver_profile = drivers_df.set_index("driver_id") \
        if "driver_id" in drivers_df.columns else pd.DataFrame()

    # Single groupby pass — O(n log n) instead of O(n × d)
    grouped = trips_ts.groupby("driver_id")

    count = 0
    for driver_id, driver_trips in grouped:
        try:
            total_trips  = len(driver_trips)
            if total_trips == 0:
                continue

            fraud_rate = float(driver_trips["is_fraud"].mean())
            cancel_rate = float(
                driver_trips["status"].isin(
                    ["cancelled_by_driver"]
                ).mean()
            )
            cash_ratio = float(
                (driver_trips["payment_mode"] == "cash").mean()
            )
            avg_fare     = float(driver_trips["fare_inr"].mean())
            dispute_rate = float(
                (driver_trips["status"] == "disputed").mean()
            )

            # Rolling 14-day dispute rate
            recent_trips = driver_trips[
                driver_trips["requested_at"] >= cutoff_14d
            ]
            dispute_rate_14d = float(
                (recent_trips["status"] == "disputed").mean()
            ) if len(recent_trips) > 0 else 0.0

            # Driver profile features (O(1) lookup via pre-indexed DataFrame)
            account_age = 180
            is_verified = 1
            if not driver_profile.empty and driver_id in driver_profile.index:
                row = driver_profile.loc[driver_id]
                account_age = int(
                    row.get("account_age_days", 180)
                    if hasattr(row, "get") else 180
                )
                is_verified = int(
                    row.get("is_verified", True)
                    if hasattr(row, "get") else True
                )

            features = {
                "driver_id":                       str(driver_id),
                "total_trips":                     total_trips,
                "fraud_rate":                      round(fraud_rate, 4),
                "cancel_rate":                     round(cancel_rate, 4),
                "cash_ratio":                      round(cash_ratio, 4),
                "avg_fare":                        round(avg_fare, 2),
                "dispute_rate":                    round(dispute_rate, 4),
                "driver_dispute_rate_rolling_14d": round(dispute_rate_14d, 4),
                "driver_account_age_days":         account_age,
                "driver_is_verified":              is_verified,
                "cached_at":                       datetime.utcnow().isoformat(),
                "version":                         FEATURE_VERSION,
            }

            await cache_set(
                f"driver_features:{driver_id}",
                features,
                ttl_seconds=DRIVER_FEATURE_TTL,
            )
            count += 1

        except Exception as e:
            logger.warning(
                f"Failed to cache features for {driver_id}: {e}"
            )
            continue

    logger.info(f"Precomputed features for {count} drivers")
    return count


async def precompute_zone_features(
    trips_df: pd.DataFrame,
) -> int:
    """Precompute fraud rate and demand stats per zone."""
    from database.redis_client import cache_set
    from generator.cities import ZONES

    if trips_df.empty:
        return 0

    count = 0
    for zone_id in trips_df["pickup_zone_id"].unique():
        try:
            zone_trips = trips_df[
                trips_df["pickup_zone_id"] == zone_id
            ]

            # Rolling 7-day fraud rate
            zone_trips_copy = zone_trips.copy()
            zone_trips_copy["requested_at"] = pd.to_datetime(
                zone_trips_copy["requested_at"], format='mixed'
            )
            recent = zone_trips_copy[
                zone_trips_copy["requested_at"]
                >= zone_trips_copy["requested_at"].max()
                   - pd.Timedelta(days=7)
            ]
            fraud_rate_7d = float(
                recent["is_fraud"].mean()
            ) if len(recent) > 0 else 0.0

            zone_obj = ZONES.get(zone_id)
            features = {
                "zone_id":                        zone_id,
                "zone_name":                      zone_obj.name
                                                  if zone_obj
                                                  else zone_id,
                "zone_fraud_rate_rolling_7d":     round(
                    fraud_rate_7d, 4
                ),
                "zone_total_trips":               len(zone_trips),
                "cached_at":  datetime.utcnow().isoformat(),
            }

            await cache_set(
                f"zone_features:{zone_id}",
                features,
                ttl_seconds=ZONE_FEATURE_TTL,
            )
            count += 1

        except Exception as e:
            logger.warning(
                f"Failed to cache zone {zone_id}: {e}"
            )

    return count


async def get_driver_features(
    driver_id: str,
) -> Dict:
    """
    Get precomputed driver features from Redis.
    Returns default features if not cached.
    """
    from database.redis_client import cache_get

    cached = await cache_get(f"driver_features:{driver_id}")
    if cached:
        return cached

    # Default features for unknown driver
    return {
        "driver_id":                       driver_id,
        "total_trips":                     0,
        "fraud_rate":                      0.0,
        "cancel_rate":                     0.0,
        "cash_ratio":                      0.5,
        "avg_fare":                        300.0,
        "dispute_rate":                    0.0,
        "driver_dispute_rate_rolling_14d": 0.0,
        "driver_account_age_days":         30,
        "driver_is_verified":              1,
    }


async def get_zone_features(zone_id: str) -> Dict:
    """Get precomputed zone features from Redis."""
    from database.redis_client import cache_get

    cached = await cache_get(f"zone_features:{zone_id}")
    if cached:
        return cached

    return {
        "zone_id":                    zone_id,
        "zone_fraud_rate_rolling_7d": 0.05,
        "zone_total_trips":           0,
    }
