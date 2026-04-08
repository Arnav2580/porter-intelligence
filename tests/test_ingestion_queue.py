"""Queue-first ingestion tests."""

import pytest

from ingestion.webhook import _queue_csv_payloads


@pytest.mark.asyncio
async def test_queue_csv_payloads_stages_when_redis_unavailable(monkeypatch):
    async def fake_ping_redis():
        return False

    async def fake_buffer(payloads, **kwargs):
        return len(payloads)

    monkeypatch.setattr(
        "database.redis_client.ping_redis",
        fake_ping_redis,
    )
    monkeypatch.setattr(
        "ingestion.staging.buffer_trip_payloads",
        fake_buffer,
    )

    result = await _queue_csv_payloads(
        [{"trip_id": "CSV_001", "driver_id": "DRV_1"}],
        source="batch_csv",
        mapping_name="default",
    )

    assert result["accepted"] is True
    assert result["queue_mode"] == "postgres_staging"
    assert result["staged_rows"] == 1


@pytest.mark.asyncio
async def test_queue_csv_payloads_publish_to_redis_when_available(monkeypatch):
    published = []

    async def fake_ping_redis():
        return True

    async def fake_publish_trip(payload):
        published.append(payload["trip_id"])
        return "1-0"

    async def fake_drain(limit=100):
        return {"redis_available": True, "drained": 0, "failed": 0}

    monkeypatch.setattr(
        "database.redis_client.ping_redis",
        fake_ping_redis,
    )
    monkeypatch.setattr(
        "ingestion.streams.publish_trip",
        fake_publish_trip,
    )
    monkeypatch.setattr(
        "ingestion.staging.drain_staged_trips",
        fake_drain,
    )

    result = await _queue_csv_payloads(
        [
            {"trip_id": "CSV_001", "driver_id": "DRV_1"},
            {"trip_id": "CSV_002", "driver_id": "DRV_2"},
        ],
        source="batch_csv",
        mapping_name="default",
    )

    assert published == ["CSV_001", "CSV_002"]
    assert result["accepted"] is True
    assert result["queue_mode"] == "redis_stream"
    assert result["published_rows"] == 2
