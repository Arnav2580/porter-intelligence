"""Flexible schema mapper for CSV and webhook ingestion."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


DEFAULT_SCHEMA_MAP_PATH = (
    Path(__file__).with_name("schema_map.default.json")
)

_PAYMENT_MODE_MAP = {
    "cash": "cash",
    "upi": "upi",
    "wallet": "upi",
    "card": "credit",
    "credit": "credit",
    "credit_card": "credit",
}

_VEHICLE_TYPE_MAP = {
    "two_wheeler": "two_wheeler",
    "two wheeler": "two_wheeler",
    "bike": "two_wheeler",
    "mini": "mini_truck",
    "mini_truck": "mini_truck",
    "three_wheeler": "three_wheeler",
    "three wheeler": "three_wheeler",
    "truck_14ft": "truck_14ft",
    "14ft": "truck_14ft",
    "truck_17ft": "truck_17ft",
    "17ft": "truck_17ft",
}


def _normalise_key(value: str) -> str:
    return "".join(
        char.lower()
        for char in str(value).strip()
        if char.isalnum()
    )


def _as_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    return float(value)


def _as_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    return int(float(value))


def _as_bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_timestamp(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return datetime.utcnow()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw)


class SchemaMapper:
    """Map arbitrary source columns into TripScoreRequest-compatible payloads."""

    def __init__(self, alias_map: Mapping[str, list[str]], mapping_name: str):
        self.alias_map = {
            target: [_normalise_key(alias) for alias in aliases]
            for target, aliases in alias_map.items()
        }
        self.mapping_name = mapping_name

    @classmethod
    def from_file(
        cls,
        path: str | Path | None = None,
        *,
        mapping_name: str = "default",
    ) -> "SchemaMapper":
        resolved = Path(path) if path else DEFAULT_SCHEMA_MAP_PATH
        with resolved.open() as handle:
            alias_map = json.load(handle)
        return cls(alias_map, mapping_name=mapping_name)

    @classmethod
    def from_json_bytes(
        cls,
        raw: bytes,
        *,
        mapping_name: str = "uploaded",
    ) -> "SchemaMapper":
        alias_map = json.loads(raw.decode("utf-8"))
        return cls(alias_map, mapping_name=mapping_name)

    def _lookup(self, row: Mapping[str, Any], target: str) -> Any:
        normalised = {
            _normalise_key(key): value
            for key, value in row.items()
        }
        for alias in self.alias_map.get(target, []):
            if alias in normalised and normalised[alias] not in (None, ""):
                return normalised[alias]
        return None

    def map_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        requested_at = _parse_timestamp(
            self._lookup(row, "requested_at")
        )
        hour_of_day = _as_int(
            self._lookup(row, "hour_of_day"),
            requested_at.hour,
        )
        day_of_week = _as_int(
            self._lookup(row, "day_of_week"),
            requested_at.weekday(),
        )
        is_peak_hour = _as_bool(
            self._lookup(row, "is_peak_hour"),
            hour_of_day in {8, 9, 10, 18, 19, 20},
        )
        is_night = _as_bool(
            self._lookup(row, "is_night"),
            hour_of_day >= 22 or hour_of_day <= 5,
        )

        payment_mode = str(
            self._lookup(row, "payment_mode") or "upi"
        ).strip().lower()
        payment_mode = _PAYMENT_MODE_MAP.get(payment_mode, "upi")

        vehicle_type = str(
            self._lookup(row, "vehicle_type") or "mini_truck"
        ).strip().lower().replace("-", "_")
        vehicle_type = _VEHICLE_TYPE_MAP.get(
            vehicle_type,
            "mini_truck",
        )

        pickup_zone_id = str(
            self._lookup(row, "pickup_zone_id") or "unknown"
        ).strip()
        dropoff_zone_id = str(
            self._lookup(row, "dropoff_zone_id") or pickup_zone_id
        ).strip()

        return {
            "trip_id": str(self._lookup(row, "trip_id") or "").strip(),
            "driver_id": str(
                self._lookup(row, "driver_id") or ""
            ).strip(),
            "vehicle_type": vehicle_type,
            "pickup_zone_id": pickup_zone_id or "unknown",
            "dropoff_zone_id": dropoff_zone_id or "unknown",
            "pickup_lat": _as_float(self._lookup(row, "pickup_lat")),
            "pickup_lon": _as_float(self._lookup(row, "pickup_lon")),
            "dropoff_lat": _as_float(self._lookup(row, "dropoff_lat")),
            "dropoff_lon": _as_float(self._lookup(row, "dropoff_lon")),
            "declared_distance_km": _as_float(
                self._lookup(row, "declared_distance_km"),
                0.1,
            ),
            "declared_duration_min": _as_float(
                self._lookup(row, "declared_duration_min"),
                1.0,
            ),
            "fare_inr": _as_float(self._lookup(row, "fare_inr")),
            "payment_mode": payment_mode,
            "surge_multiplier": _as_float(
                self._lookup(row, "surge_multiplier"),
                1.0,
            ),
            "requested_at": requested_at.isoformat(),
            "is_night": is_night,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "is_peak_hour": is_peak_hour,
            "zone_demand_at_time": _as_float(
                self._lookup(row, "zone_demand_at_time"),
                1.0,
            ),
            "status": str(
                self._lookup(row, "status") or "completed"
            ).strip().lower(),
            "customer_complaint_flag": _as_bool(
                self._lookup(row, "customer_complaint_flag"),
                False,
            ),
        }
