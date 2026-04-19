"""API-level ingestion tests."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from ingestion.webhook import router as ingest_router


async def _fake_admin_user():
    return {"sub": "tester", "role": "admin", "name": "Test Admin"}


def test_batch_csv_endpoint_accepts_sample(monkeypatch):
    async def fake_queue(payloads, *, source, mapping_name):
        assert source == "batch_csv"
        assert mapping_name == "default"
        assert len(payloads) == 10
        return {
            "accepted": True,
            "rows": len(payloads),
            "queued": True,
            "queue_mode": "redis_stream",
            "staged_rows": 0,
            "published_rows": len(payloads),
            "mapping_name": mapping_name,
        }

    monkeypatch.setattr(
        "ingestion.webhook._queue_csv_payloads",
        fake_queue,
    )

    sample_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "samples"
        / "porter_sample_10_trips.csv"
    )

    app = FastAPI()
    app.include_router(ingest_router)
    app.dependency_overrides[get_current_user] = _fake_admin_user

    with TestClient(app) as client:
        with sample_path.open("rb") as handle:
            response = client.post(
                "/ingest/batch-csv",
                files={
                    "file": (
                        "porter_sample_10_trips.csv",
                        handle,
                        "text/csv",
                    )
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["rows"] == 10
    assert payload["queued"] is True


def test_default_schema_map_endpoint_exposes_aliases():
    app = FastAPI()
    app.include_router(ingest_router)
    app.dependency_overrides[get_current_user] = _fake_admin_user

    with TestClient(app) as client:
        response = client.get("/ingest/schema-map/default")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mapping_name"] == "default"
    assert payload["field_count"] > 0
    assert "trip_id" in payload["aliases"]
