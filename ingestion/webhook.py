"""
Real-time trip event ingestion.

Porter sends trip completion events to this endpoint.
We score immediately, persist case if flagged,
and return acknowledgement.

This endpoint is designed to support a future
live data connection once Porter or another
logistics operator shares a production schema.
The event model below is a reference contract
that can be remapped through the schema mapper.
"""

from fastapi import (
    APIRouter, BackgroundTasks,
    File, Form, HTTPException, Header, Request, UploadFile
)
import csv
import io
import json
from pydantic import BaseModel
from typing import Optional
import hmac
import hashlib
import logging
import os

from api.limiting import limiter
from security.settings import (
    get_rate_limit,
    get_required_secret,
    is_placeholder_value,
    require_webhook_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ingest",
    tags=["ingestion"],
)

class PorterTripEvent(BaseModel):
    """
    Porter trip completion event.

    This is a reference contract for live onboarding.
    Actual partner field names can be remapped through
    the schema-mapping layer without changing scoring logic.
    """
    trip_id:          str
    driver_id:        str
    pickup_lat:       float
    pickup_lon:       float
    dropoff_lat:      float
    dropoff_lon:      float
    fare:             float
    distance_km:      float
    duration_min:     float
    payment_type:     str
    vehicle_category: str
    completed_at:     str
    zone:             Optional[str] = None
    city:             Optional[str] = None


def _verify_signature(
    payload: bytes,
    signature: Optional[str],
    secret: str,
) -> bool:
    if not signature:
        return False
    try:
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        incoming = signature.replace("sha256=", "")
        return hmac.compare_digest(expected, incoming)
    except Exception:
        return False


def _normalise(event: PorterTripEvent) -> dict:
    """
    Map Porter field names to platform schema.
    Update this mapping when a partner-specific
    schema contract is confirmed.
    """
    payment_map = {
        "CASH":   "cash",
        "UPI":    "upi",
        "CARD":   "credit",
        "WALLET": "upi",
    }
    vehicle_map = {
        "TWO_WHEELER":   "two_wheeler",
        "MINI":          "mini_truck",
        "LOAD_14":       "truck_14ft",
        "LOAD_17":       "truck_17ft",
        "THREE_WHEELER": "three_wheeler",
    }
    return {
        "trip_id":               event.trip_id,
        "driver_id":             event.driver_id,
        "pickup_lat":            event.pickup_lat,
        "pickup_lon":            event.pickup_lon,
        "dropoff_lat":           event.dropoff_lat,
        "dropoff_lon":           event.dropoff_lon,
        "fare_inr":              event.fare,
        "declared_distance_km":  event.distance_km,
        "declared_duration_min": event.duration_min,
        "payment_mode":          payment_map.get(
            event.payment_type.upper(), "upi"
        ),
        "vehicle_type":          vehicle_map.get(
            event.vehicle_category.upper(), "mini_truck"
        ),
        "pickup_zone_id":        event.zone or "unknown",
        "completed_at":          event.completed_at,
    }


async def _publish_to_stream(normalised: dict) -> None:
    """
    Publish the normalised trip to the Redis Stream (Phase B primary path).
    The stream consumer handles stateless scoring + case persistence.
    Falls back to PostgreSQL staging if Redis is unavailable.
    """
    try:
        from ingestion.staging import drain_staged_trips
        from ingestion.streams import publish_trip
        msg_id = await publish_trip(normalised)
        await drain_staged_trips(limit=50)
        logger.info(
            f"Trip {normalised['trip_id']} queued "
            f"on stream (msg={msg_id})"
        )
    except Exception as e:
        from ingestion.staging import buffer_trip_payloads
        logger.warning(
            f"Stream unavailable ({e}), "
            f"buffering trip to staging"
        )
        await buffer_trip_payloads(
            [normalised],
            source="webhook",
            mapping_name="porter_event",
            error_message=str(e),
        )


async def _inline_score_and_persist(normalised: dict) -> None:
    """
    Fallback: score inline with stateless scorer (no pandas).
    Used when Redis Stream is unavailable.
    """
    try:
        from api.state import app_state
        from database.case_store import persist_flagged_case
        from model.scoring import get_tier

        model         = app_state.get("model")
        feature_names = app_state.get("feature_names", [])
        two_stage     = app_state.get("two_stage_config", {})

        if model is None:
            logger.warning("Model not loaded — skipping score")
            return

        from ml.stateless_scorer import score_trip_stateless
        result     = await score_trip_stateless(
            normalised, model, feature_names, two_stage
        )
        prob = result["fraud_probability"]
        tier = get_tier(prob)

        logger.info(
            f"[inline] trip={normalised['trip_id']} "
            f"prob={prob:.3f} tier={tier.name}"
        )

        if tier.name in ("action", "watchlist"):
            await persist_flagged_case(
                trip_id=normalised["trip_id"],
                driver_id=normalised["driver_id"],
                zone_id=normalised.get("pickup_zone_id", "unknown"),
                tier=tier.name,
                fraud_probability=prob,
                top_signals=[],
                fare_inr=normalised.get("fare_inr", 0),
                recoverable_inr=round(
                    normalised.get("fare_inr", 0) * 0.15,
                    2,
                ),
                auto_escalated=tier.auto_escalate,
                source_channel="inline_webhook",
            )
            logger.info(
                f"[inline] case persisted: "
                f"trip={normalised['trip_id']} tier={tier.name}"
            )

    except Exception as e:
        logger.error(
            f"Inline score/persist failed for "
            f"{normalised.get('trip_id', '?')}: {e}"
        )


@router.post("/trip-completed")
@limiter.limit(get_rate_limit("INGEST_RATE_LIMIT", "300/minute"))
async def ingest_trip(
    request:     Request,
    event:       PorterTripEvent,
    background:  BackgroundTasks,
    x_signature: Optional[str] = Header(
        None, alias="X-Porter-Signature"
    ),
):
    """
    Receive trip completion event from Porter.

    Verifies HMAC signature if provided.
    Scores and persists in background.
    Always returns 200 immediately — Porter's
    webhook sender should not wait on scoring.
    """
    # Verify signature if provided
    # In production this is required
    signature_required = require_webhook_signature()
    if signature_required or x_signature:
        secret = get_required_secret(
            "WEBHOOK_SECRET",
            "webhook signature verification",
        )
        body = await request.body()
        if not _verify_signature(body, x_signature, secret):
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )

    normalised = _normalise(event)
    background.add_task(_publish_to_stream, normalised)

    return {
        "received":  True,
        "trip_id":   event.trip_id,
        "queued_for":"scoring",
    }


async def _queue_csv_payloads(
    payloads: list[dict],
    *,
    source: str,
    mapping_name: str,
) -> dict:
    from database.redis_client import ping_redis
    from ingestion.staging import buffer_trip_payloads, drain_staged_trips
    from ingestion.streams import publish_trip

    if not payloads:
        return {
            "accepted": True,
            "rows": 0,
            "queued": False,
            "queue_mode": "empty",
            "staged_rows": 0,
            "published_rows": 0,
        }

    if not await ping_redis():
        staged = await buffer_trip_payloads(
            payloads,
            source=source,
            mapping_name=mapping_name,
            error_message="Redis unavailable during upload",
        )
        return {
            "accepted": True,
            "rows": len(payloads),
            "queued": True,
            "queue_mode": "postgres_staging",
            "staged_rows": staged,
            "published_rows": 0,
            "mapping_name": mapping_name,
        }

    published = 0
    for index, payload in enumerate(payloads):
        try:
            await publish_trip(payload)
            published += 1
        except Exception as exc:
            remaining = payloads[index:]
            staged = await buffer_trip_payloads(
                remaining,
                source=source,
                mapping_name=mapping_name,
                error_message=str(exc),
            )
            return {
                "accepted": True,
                "rows": len(payloads),
                "queued": True,
                "queue_mode": "redis_with_stage_fallback",
                "staged_rows": staged,
                "published_rows": published,
                "mapping_name": mapping_name,
            }

    drain_result = await drain_staged_trips(limit=100)
    return {
        "accepted": True,
        "rows": len(payloads),
        "queued": True,
        "queue_mode": "redis_stream",
        "staged_rows": 0,
        "published_rows": published,
        "mapping_name": mapping_name,
        "drain_result": drain_result,
    }


@router.post("/batch-csv")
@limiter.limit(get_rate_limit("INGEST_RATE_LIMIT", "300/minute"))
async def ingest_batch_csv(
    request: Request,
    file: UploadFile = File(...),
    mapping_file: Optional[UploadFile] = File(None),
    mapping_name: str = Form("default"),
):
    """Accept a CSV upload, map rows, and queue them for scoring."""
    from ingestion.schema_mapper import SchemaMapper

    raw_csv = await file.read()
    if not raw_csv:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty")

    if mapping_file is not None:
        mapper = SchemaMapper.from_json_bytes(
            await mapping_file.read(),
            mapping_name=mapping_name or "uploaded",
        )
    else:
        mapper = SchemaMapper.from_file(mapping_name=mapping_name)

    text = raw_csv.decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="CSV contains no data rows",
        )

    try:
        mapped_rows = [mapper.map_row(row) for row in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"CSV mapping failed: {exc}",
        ) from exc

    result = await _queue_csv_payloads(
        mapped_rows,
        source="batch_csv",
        mapping_name=mapper.mapping_name,
    )
    result["filename"] = file.filename
    return result


@router.get("/status")
async def ingestion_status():
    """
    Ingestion pipeline status.
    Shows whether the webhook is configured
    and ready to receive Porter events.
    """
    webhook_secret = (os.getenv("WEBHOOK_SECRET") or "").strip()
    from ingestion.staging import get_queue_status_summary
    queue_status = await get_queue_status_summary(auto_drain=True)
    return {
        "status":          "ready",
        "webhook_url":     "/ingest/trip-completed",
        "signature_check": require_webhook_signature(),
        "webhook_secret_configured": not is_placeholder_value(
            webhook_secret
        ),
        "queue_status": queue_status,
        "note": (
            "In prod mode a configured WEBHOOK_SECRET and signed requests "
            "are required before live ingestion should be enabled."
        ),
    }


@router.get("/schema-map/default")
async def default_schema_map():
    """Expose the default alias map so live mapping can be shown quickly."""
    from ingestion.schema_mapper import DEFAULT_SCHEMA_MAP_PATH

    with DEFAULT_SCHEMA_MAP_PATH.open() as handle:
        alias_map = json.load(handle)

    return {
        "mapping_name": "default",
        "field_count": len(alias_map),
        "aliases": alias_map,
        "sample_template": "/data/samples/porter_sample_10_trips.csv",
        "note": (
            "Use this mapping surface during onboarding to show exactly how "
            "external partner fields are normalized into the scoring schema."
        ),
    }
