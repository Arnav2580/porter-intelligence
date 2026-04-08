"""Schema mapper tests for flexible ingestion."""

from ingestion.schema_mapper import SchemaMapper


def test_schema_mapper_handles_porter_style_fields():
    mapper = SchemaMapper.from_file()
    row = {
        "trip_id": "PTR_001",
        "driver_id": "DRV_001",
        "vehicle_category": "TWO_WHEELER",
        "zone": "blr_koramangala",
        "dropoff_zone": "blr_whitefield",
        "pickup_latitude": "12.9352",
        "pickup_longitude": "77.6245",
        "dropoff_latitude": "12.9698",
        "dropoff_longitude": "77.7500",
        "fare": "640",
        "distance_km": "8.4",
        "duration_min": "28",
        "payment_type": "CASH",
        "completed_at": "2026-04-08T22:30:00",
        "complaint_flag": "false",
    }

    mapped = mapper.map_row(row)

    assert mapped["trip_id"] == "PTR_001"
    assert mapped["driver_id"] == "DRV_001"
    assert mapped["vehicle_type"] == "two_wheeler"
    assert mapped["payment_mode"] == "cash"
    assert mapped["pickup_zone_id"] == "blr_koramangala"
    assert mapped["dropoff_zone_id"] == "blr_whitefield"
    assert mapped["hour_of_day"] == 22
    assert mapped["is_night"] is True


def test_schema_mapper_handles_generic_field_names():
    mapper = SchemaMapper.from_file()
    row = {
        "booking_id": "GEN_100",
        "partner_id": "DRV_100",
        "vehicle": "mini",
        "pickup_cluster": "hyd_hitech_city",
        "destination_zone": "hyd_madhapur",
        "origin_lat": 17.4500,
        "origin_lon": 78.3800,
        "dest_lat": 17.4380,
        "dest_lon": 78.3920,
        "amount": 420,
        "trip_distance_km": 6.8,
        "trip_duration_min": 22,
        "payment_method": "UPI",
        "trip_time": "2026-04-08T10:05:00",
    }

    mapped = mapper.map_row(row)

    assert mapped["trip_id"] == "GEN_100"
    assert mapped["driver_id"] == "DRV_100"
    assert mapped["vehicle_type"] == "mini_truck"
    assert mapped["payment_mode"] == "upi"
    assert mapped["hour_of_day"] == 10
    assert mapped["day_of_week"] >= 0
