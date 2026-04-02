"""Case management tests."""

import pytest
import json


def test_case_status_enum():
    from database.models import FraudCaseStatus
    assert FraudCaseStatus.OPEN.value         == "open"
    assert FraudCaseStatus.CONFIRMED.value    == "confirmed_fraud"
    assert FraudCaseStatus.FALSE_ALARM.value  == "false_alarm"


def test_driver_action_enum():
    from database.models import DriverActionType
    assert DriverActionType.SUSPEND.value     == "suspend"
    assert DriverActionType.FLAG_REVIEW.value == "flag_review"


def test_webhook_normalise():
    from ingestion.webhook import (
        _normalise, PorterTripEvent
    )
    event = PorterTripEvent(
        trip_id          = "T001",
        driver_id        = "D001",
        pickup_lat       = 12.93,
        pickup_lon       = 77.62,
        dropoff_lat      = 12.97,
        dropoff_lon      = 77.75,
        fare             = 450.0,
        distance_km      = 8.5,
        duration_min     = 22.0,
        payment_type     = "CASH",
        vehicle_category = "TWO_WHEELER",
        completed_at     = "2024-01-05T22:30:00",
    )
    result = _normalise(event)
    assert result["payment_mode"]   == "cash"
    assert result["vehicle_type"]   == "two_wheeler"
    assert result["fare_inr"]       == 450.0
    assert result["trip_id"]        == "T001"


def test_webhook_payment_mapping():
    from ingestion.webhook import (
        _normalise, PorterTripEvent
    )
    for porter_type, expected in [
        ("CASH",   "cash"),
        ("UPI",    "upi"),
        ("CARD",   "credit"),
        ("WALLET", "upi"),
    ]:
        event = PorterTripEvent(
            trip_id="T", driver_id="D",
            pickup_lat=12.9, pickup_lon=77.6,
            dropoff_lat=12.9, dropoff_lon=77.7,
            fare=100, distance_km=5, duration_min=15,
            payment_type=porter_type,
            vehicle_category="MINI",
            completed_at="2024-01-05T10:00:00",
        )
        assert _normalise(event)["payment_mode"] == expected
