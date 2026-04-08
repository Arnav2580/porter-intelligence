"""
Porter-scale digital twin live simulator.

This generator feeds the real Redis Stream ingestion path with synthetic
trips shaped like a 22-city operating footprint. It is explicitly a demo /
validation tool and is disabled in production runtime mode.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from generator.config import VEHICLE_TYPES
from ingestion.city_profiles import (
    CITY_TWIN_PROFILES,
    CityTwinProfile,
    TwinZone,
    normalised_city_weights,
    zone_demand_multiplier,
)

logger = logging.getLogger(__name__)

_PAYMENT_MODES = ["upi", "cash", "credit"]
_PAYMENT_WEIGHTS = [0.62, 0.23, 0.15]
_SIMULATION_PATTERNS = (
    "clean_baseline",
    "fare_inflation",
    "route_abuse",
    "payout_spike",
    "cancellation_abuse",
    "cash_night_ring",
)


@dataclass(frozen=True)
class SimulatorSettings:
    active_cities: tuple[str, ...]
    base_trips_per_min: float
    scale_multiplier: float
    elapsed_days: int
    daily_growth_pct: float
    base_fraud_rate: float
    payout_anomaly_rate: float
    cancel_abuse_rate: float
    route_abuse_rate: float
    cash_ring_rate: float

    @property
    def effective_trips_per_min(self) -> float:
        growth_multiplier = (
            1 + max(self.daily_growth_pct, 0.0) / 100.0
        ) ** max(self.elapsed_days, 0)
        effective = (
            self.base_trips_per_min
            * max(self.scale_multiplier, 0.1)
            * growth_multiplier
        )
        return round(max(effective, 1.0), 2)

    @property
    def interval_seconds(self) -> float:
        return 60.0 / self.effective_trips_per_min

    @property
    def effective_trips_per_day(self) -> int:
        return int(round(self.effective_trips_per_min * 60 * 24))


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_active_cities(raw: str | None) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return tuple(CITY_TWIN_PROFILES.keys())

    selected: list[str] = []
    for token in raw.split(","):
        city_id = token.strip().lower()
        if city_id in CITY_TWIN_PROFILES and city_id not in selected:
            selected.append(city_id)

    return tuple(selected) or tuple(CITY_TWIN_PROFILES.keys())


def get_simulator_settings() -> SimulatorSettings:
    return SimulatorSettings(
        active_cities=_parse_active_cities(
            os.getenv("PORTER_TWIN_ACTIVE_CITIES")
        ),
        base_trips_per_min=_env_float(
            "PORTER_TWIN_TRIPS_PER_MIN",
            30.0,
        ),
        scale_multiplier=_env_float(
            "PORTER_TWIN_SCALE_MULTIPLIER",
            1.0,
        ),
        elapsed_days=_env_int(
            "PORTER_TWIN_ELAPSED_DAYS",
            0,
        ),
        daily_growth_pct=_env_float(
            "PORTER_TWIN_DAILY_GROWTH_PCT",
            0.0,
        ),
        base_fraud_rate=_env_float(
            "PORTER_TWIN_BASE_FRAUD_RATE",
            0.062,
        ),
        payout_anomaly_rate=_env_float(
            "PORTER_TWIN_PAYOUT_ANOMALY_RATE",
            0.018,
        ),
        cancel_abuse_rate=_env_float(
            "PORTER_TWIN_CANCEL_ABUSE_RATE",
            0.014,
        ),
        route_abuse_rate=_env_float(
            "PORTER_TWIN_ROUTE_ABUSE_RATE",
            0.021,
        ),
        cash_ring_rate=_env_float(
            "PORTER_TWIN_CASH_RING_RATE",
            0.013,
        ),
    )


def _top_city_mix(
    settings: SimulatorSettings,
    hour: int,
    day_of_week: int,
) -> list[dict]:
    weights = normalised_city_weights(
        hour,
        day_of_week,
        settings.active_cities,
    )
    top_items = sorted(
        weights.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    return [
        {
            "city": city_id,
            "label": CITY_TWIN_PROFILES[city_id].display_name,
            "share_pct": round(weight * 100, 1),
        }
        for city_id, weight in top_items
    ]


def get_simulator_summary() -> dict:
    now = datetime.now(timezone.utc)
    settings = get_simulator_settings()
    return {
        "city_count": len(settings.active_cities),
        "active_cities": list(settings.active_cities),
        "effective_trips_per_min": settings.effective_trips_per_min,
        "effective_trips_per_day": settings.effective_trips_per_day,
        "base_fraud_rate_pct": round(
            settings.base_fraud_rate * 100,
            2,
        ),
        "daily_growth_pct": round(
            settings.daily_growth_pct,
            2,
        ),
        "elapsed_days": settings.elapsed_days,
        "patterns": list(_SIMULATION_PATTERNS[1:]),
        "top_city_mix": _top_city_mix(
            settings,
            now.hour,
            now.weekday(),
        ),
    }


def format_simulator_summary() -> str:
    summary = get_simulator_summary()
    top_mix = ", ".join(
        f"{item['label']} {item['share_pct']:.0f}%"
        for item in summary["top_city_mix"][:3]
    )
    return (
        f"{summary['effective_trips_per_min']:.1f} trips/min, "
        f"{summary['base_fraud_rate_pct']:.1f}% base fraud, "
        f"{summary['city_count']} cities, "
        f"top mix: {top_mix}"
    )


def _weighted_choice(
    values: Iterable[tuple[object, float]],
):
    items = list(values)
    population = [item[0] for item in items]
    weights = [max(item[1], 0.001) for item in items]
    return random.choices(population, weights=weights, k=1)[0]


def _pick_city(
    settings: SimulatorSettings,
    hour: int,
    day_of_week: int,
) -> CityTwinProfile:
    weights = normalised_city_weights(
        hour,
        day_of_week,
        settings.active_cities,
    )
    city_id = _weighted_choice(weights.items())
    return CITY_TWIN_PROFILES[city_id]


def _pick_zone(
    profile: CityTwinProfile,
    hour: int,
    day_of_week: int,
    exclude_zone_id: str | None = None,
) -> TwinZone:
    candidates = [
        zone for zone in profile.zones
        if zone.zone_id != exclude_zone_id
    ]
    if not candidates:
        candidates = list(profile.zones)

    return _weighted_choice(
        (
            zone,
            zone_demand_multiplier(
                profile,
                zone,
                hour,
                day_of_week,
            ),
        )
        for zone in candidates
    )


def _haversine_km(
    pickup_zone: TwinZone,
    dropoff_zone: TwinZone,
) -> float:
    lat1 = math.radians(pickup_zone.lat)
    lon1 = math.radians(pickup_zone.lon)
    lat2 = math.radians(dropoff_zone.lat)
    lon2 = math.radians(dropoff_zone.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )
    return max(6371 * 2 * math.asin(math.sqrt(a)), 0.8)


def _pick_vehicle_type(profile: CityTwinProfile) -> str:
    return _weighted_choice(profile.vehicle_weights.items())


def _expected_trip_baseline(
    vehicle_type: str,
    pickup_zone: TwinZone,
    dropoff_zone: TwinZone,
) -> tuple[float, float]:
    vehicle = VEHICLE_TYPES[vehicle_type]
    haversine_km = _haversine_km(pickup_zone, dropoff_zone)
    typical_min, typical_max = vehicle.typical_trip_km
    declared_distance = max(
        haversine_km * random.uniform(1.05, 1.35),
        random.uniform(typical_min, min(typical_max, typical_min + 6)),
    )
    base_fare = (
        vehicle.base_fare
        + vehicle.per_km_rate * declared_distance
    )
    return round(declared_distance, 3), round(base_fare, 2)


def _pattern_weights(
    settings: SimulatorSettings,
    profile: CityTwinProfile,
    pickup_zone: TwinZone,
    hour: int,
) -> list[tuple[str, float]]:
    night_multiplier = 1.25 if hour >= 22 or hour < 5 else 1.0
    risk_multiplier = (
        profile.fraud_bias
        * pickup_zone.fraud_bias
        * night_multiplier
    )
    fare_inflation = settings.base_fraud_rate * risk_multiplier
    route_abuse = settings.route_abuse_rate * risk_multiplier
    payout_spike = settings.payout_anomaly_rate * risk_multiplier
    cancellation_abuse = settings.cancel_abuse_rate * risk_multiplier
    cash_night_ring = settings.cash_ring_rate * risk_multiplier
    fraud_total = min(
        fare_inflation
        + route_abuse
        + payout_spike
        + cancellation_abuse
        + cash_night_ring,
        0.75,
    )
    clean_weight = max(1.0 - fraud_total, 0.25)
    return [
        ("clean_baseline", clean_weight),
        ("fare_inflation", fare_inflation),
        ("route_abuse", route_abuse),
        ("payout_spike", payout_spike),
        ("cancellation_abuse", cancellation_abuse),
        ("cash_night_ring", cash_night_ring),
    ]


def _pick_driver_id(city_id: str, pattern: str) -> str:
    prefix = city_id.replace("_", "")[:4]
    if pattern in {"fare_inflation", "route_abuse", "cash_night_ring"}:
        return f"{prefix}_risk_{random.randint(1, 36):03d}"
    if pattern == "cancellation_abuse":
        return f"{prefix}_cancel_{random.randint(1, 24):03d}"
    return f"{prefix}_drv_{random.randint(1, 4000):05d}"


def _build_trip(
    profile: CityTwinProfile,
    pickup_zone: TwinZone,
    dropoff_zone: TwinZone,
    pattern: str,
    now: datetime,
) -> dict:
    hour = now.hour
    vehicle_type = _pick_vehicle_type(profile)
    declared_distance, expected_fare = _expected_trip_baseline(
        vehicle_type,
        pickup_zone,
        dropoff_zone,
    )
    zone_demand = zone_demand_multiplier(
        profile,
        pickup_zone,
        hour,
        now.weekday(),
    )
    base_payment = random.choices(
        _PAYMENT_MODES,
        weights=_PAYMENT_WEIGHTS,
        k=1,
    )[0]
    peak_multiplier = 1.0 + min(zone_demand - 1.0, 1.2) * 0.35
    fare_inr = expected_fare * random.uniform(0.94, 1.08) * peak_multiplier
    actual_distance_km = declared_distance * random.uniform(0.97, 1.04)
    duration_min = (
        declared_distance
        / random.uniform(18.0, 28.0)
        * 60.0
    )
    surge_multiplier = max(1.0, round(peak_multiplier, 3))
    payment_mode = base_payment
    status = "completed"
    customer_complaint_flag = False
    simulation_flags: list[str] = []
    is_night = hour >= 22 or hour < 5

    if pattern == "fare_inflation":
        fare_inr *= random.uniform(1.55, 2.25)
        declared_distance *= random.uniform(1.20, 1.55)
        actual_distance_km *= random.uniform(1.05, 1.18)
        duration_min *= random.uniform(0.90, 1.12)
        surge_multiplier = round(max(surge_multiplier, random.uniform(1.5, 2.4)), 3)
        payment_mode = "cash"
        is_night = True
        simulation_flags = ["fare_inflation", "cash_collection", "after_hours"]
    elif pattern == "route_abuse":
        declared_distance *= random.uniform(1.75, 2.45)
        actual_distance_km *= random.uniform(1.20, 1.50)
        fare_inr *= random.uniform(1.30, 1.75)
        duration_min *= random.uniform(1.10, 1.35)
        payment_mode = random.choice(["cash", "upi"])
        simulation_flags = ["route_abuse", "distance_hike"]
    elif pattern == "payout_spike":
        fare_inr *= random.uniform(1.45, 1.95)
        surge_multiplier = round(random.uniform(2.0, 3.2), 3)
        customer_complaint_flag = random.random() < 0.35
        payment_mode = random.choice(["cash", "credit"])
        simulation_flags = ["payout_spike", "surge_outlier"]
    elif pattern == "cancellation_abuse":
        status = "cancelled_by_driver"
        declared_distance *= random.uniform(1.05, 1.35)
        actual_distance_km *= random.uniform(0.80, 0.95)
        fare_inr *= random.uniform(1.15, 1.40)
        duration_min *= random.uniform(0.55, 0.85)
        payment_mode = random.choice(["cash", "upi"])
        customer_complaint_flag = True
        simulation_flags = ["driver_cancellation_abuse", "customer_complaint"]
    elif pattern == "cash_night_ring":
        fare_inr *= random.uniform(1.65, 2.35)
        declared_distance *= random.uniform(1.25, 1.80)
        actual_distance_km *= random.uniform(1.10, 1.25)
        duration_min *= random.uniform(0.85, 1.05)
        surge_multiplier = round(random.uniform(1.6, 2.6), 3)
        payment_mode = "cash"
        is_night = True
        simulation_flags = ["cash_ring", "after_hours", "repeat_driver_risk"]
    else:
        simulation_flags = ["baseline_clean"]

    if is_night and "after_hours" not in simulation_flags:
        simulation_flags.append("after_hours")

    return {
        "trip_id": str(uuid.uuid4()),
        "driver_id": _pick_driver_id(profile.city_id, pattern),
        "customer_id": f"cust_{uuid.uuid4().hex[:8]}",
        "city": profile.city_id,
        "city_label": profile.display_name,
        "pickup_zone_id": pickup_zone.zone_id,
        "dropoff_zone_id": dropoff_zone.zone_id,
        "pickup_lat": round(
            pickup_zone.lat + random.uniform(-0.008, 0.008),
            6,
        ),
        "pickup_lon": round(
            pickup_zone.lon + random.uniform(-0.008, 0.008),
            6,
        ),
        "dropoff_lat": round(
            dropoff_zone.lat + random.uniform(-0.008, 0.008),
            6,
        ),
        "dropoff_lon": round(
            dropoff_zone.lon + random.uniform(-0.008, 0.008),
            6,
        ),
        "fare_inr": round(fare_inr, 2),
        "declared_distance_km": round(declared_distance, 3),
        "actual_distance_km": round(actual_distance_km, 3),
        "declared_duration_min": round(max(duration_min, 2.0), 2),
        "payment_mode": payment_mode,
        "vehicle_type": vehicle_type,
        "surge_multiplier": surge_multiplier,
        "is_night": is_night,
        "hour_of_day": hour,
        "day_of_week": now.weekday(),
        "is_peak_hour": zone_demand >= 1.2,
        "zone_demand_at_time": zone_demand,
        "status": status,
        "requested_at": now.isoformat(),
        "customer_complaint_flag": customer_complaint_flag,
        "data_split": "live",
        "simulation_pattern": pattern,
        "simulation_flags": simulation_flags,
        "simulation_city_share": round(profile.base_trip_share, 4),
    }


def generate_live_trip(
    settings: SimulatorSettings | None = None,
    now: datetime | None = None,
) -> dict:
    """
    Generate a single digital-twin trip for stream ingestion.

    The output stays compatible with the stateless scorer while adding
    simulation metadata useful for audits and demos.
    """
    settings = settings or get_simulator_settings()
    now = now or datetime.now(timezone.utc)
    profile = _pick_city(settings, now.hour, now.weekday())
    pickup_zone = _pick_zone(profile, now.hour, now.weekday())
    dropoff_zone = _pick_zone(
        profile,
        now.hour,
        now.weekday(),
        exclude_zone_id=pickup_zone.zone_id,
    )
    pattern = _weighted_choice(
        _pattern_weights(
            settings,
            profile,
            pickup_zone,
            now.hour,
        )
    )
    return _build_trip(
        profile,
        pickup_zone,
        dropoff_zone,
        pattern,
        now,
    )


async def run_live_simulator() -> None:
    """
    Long-running asyncio task that publishes digital-twin trips into the
    Redis Stream ingestion pipeline.
    """
    from ingestion.streams import publish_trip

    logger.info(
        "Live simulator started — %s",
        format_simulator_summary(),
    )

    while True:
        settings = get_simulator_settings()
        try:
            trip = generate_live_trip(settings=settings)
            await publish_trip(trip)
        except asyncio.CancelledError:
            logger.info("Live simulator shutting down cleanly")
            break
        except Exception as exc:
            logger.warning("Live simulator publish error: %s", exc)

        try:
            await asyncio.sleep(settings.interval_seconds)
        except asyncio.CancelledError:
            logger.info("Live simulator shutting down cleanly")
            break
