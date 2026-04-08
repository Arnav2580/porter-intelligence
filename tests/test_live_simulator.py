"""Digital twin simulator tests."""

from datetime import datetime, timezone

from ingestion.city_profiles import CITY_TWIN_PROFILES
from ingestion.live_simulator import (
    generate_live_trip,
    get_simulator_settings,
    get_simulator_summary,
)


def test_porter_city_footprint_has_22_cities():
    assert len(CITY_TWIN_PROFILES) == 22


def test_simulator_settings_honor_env_controls(monkeypatch):
    monkeypatch.setenv(
        "PORTER_TWIN_ACTIVE_CITIES",
        "bangalore,hyderabad,invalid-city",
    )
    monkeypatch.setenv("PORTER_TWIN_TRIPS_PER_MIN", "45")
    monkeypatch.setenv("PORTER_TWIN_SCALE_MULTIPLIER", "1.5")
    monkeypatch.setenv("PORTER_TWIN_DAILY_GROWTH_PCT", "2.0")
    monkeypatch.setenv("PORTER_TWIN_ELAPSED_DAYS", "5")

    settings = get_simulator_settings()

    assert settings.active_cities == (
        "bangalore",
        "hyderabad",
    )
    assert settings.base_trips_per_min == 45.0
    assert settings.effective_trips_per_min > 45.0


def test_generate_live_trip_uses_active_city_subset(monkeypatch):
    monkeypatch.setenv("PORTER_TWIN_ACTIVE_CITIES", "hyderabad")

    trip = generate_live_trip(
        settings=get_simulator_settings(),
        now=datetime(2026, 4, 6, 22, 15, tzinfo=timezone.utc),
    )

    assert trip["city"] == "hyderabad"
    assert trip["pickup_zone_id"].startswith("hyd_")
    assert trip["dropoff_zone_id"].startswith("hyd_")
    assert trip["simulation_pattern"] in {
        "clean_baseline",
        "fare_inflation",
        "route_abuse",
        "payout_spike",
        "cancellation_abuse",
        "cash_night_ring",
    }
    assert trip["zone_demand_at_time"] >= 0.35


def test_simulator_summary_reports_top_city_mix(monkeypatch):
    monkeypatch.setenv(
        "PORTER_TWIN_ACTIVE_CITIES",
        "bangalore,mumbai,delhi_ncr",
    )
    monkeypatch.setenv("PORTER_TWIN_SCALE_MULTIPLIER", "2.0")

    summary = get_simulator_summary()

    assert summary["city_count"] == 3
    assert summary["effective_trips_per_min"] >= 60.0
    assert len(summary["top_city_mix"]) >= 1
