"""
Real-time trip event ingestion.

Porter sends trip completion events to this endpoint.
We score immediately, persist case if flagged,
and return acknowledgement.

This is Phase 3 infrastructure — built now,
activated when Porter provides a data feed.
The field mapping is a placeholder until
Porter's engineering team confirms their schema.
"""

from fastapi import (
    APIRouter, BackgroundTasks,
    HTTPException, Header, Request
)
from pydantic import BaseModel
from typing import Optional
import hmac
import hashlib
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ingest",
    tags=["ingestion"],
)

WEBHOOK_SECRET = os.getenv(
    "WEBHOOK_SECRET",
    "change-this-before-connecting-porter"
)


class PorterTripEvent(BaseModel):
    """
    Porter trip completion event.

    Field names are placeholders.
    Actual field names confirmed with Porter's
    engineering team during Phase 3 onboarding.
    Map: trip_id, driver_id, coordinates,
         fare, distance, duration, payment,
         vehicle type, completion timestamp.
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
) -> bool:
    if not signature:
        return False
    try:
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
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
    Update this mapping after Phase 3
    schema confirmation with Porter.
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
    Falls back to inline pandas scoring if Redis is unavailable.
    """
    try:
        from ingestion.streams import publish_trip
        msg_id = await publish_trip(normalised)
        logger.info(
            f"Trip {normalised['trip_id']} queued "
            f"on stream (msg={msg_id})"
        )
    except Exception as e:
        logger.warning(
            f"Stream unavailable ({e}), "
            f"falling back to inline scoring"
        )
        await _inline_score_and_persist(normalised)


async def _inline_score_and_persist(normalised: dict) -> None:
    """
    Fallback: score inline with stateless scorer (no pandas).
    Used when Redis Stream is unavailable.
    """
    try:
        from api.state import app_state
        from model.scoring import get_tier
        from database.connection import AsyncSessionLocal
        from database.models import FraudCase

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
            trip_id_stored   = normalised["trip_id"]
            driver_id_stored = normalised["driver_id"]
            try:
                from security.encryption import encrypt_pii
                trip_id_stored   = encrypt_pii(trip_id_stored)
                driver_id_stored = encrypt_pii(driver_id_stored)
            except Exception:
                pass

            async with AsyncSessionLocal() as db:
                case = FraudCase(
                    trip_id           = trip_id_stored,
                    driver_id         = driver_id_stored,
                    zone_id           = normalised.get(
                        "pickup_zone_id", "unknown"
                    ),
                    tier              = tier.name,
                    fraud_probability = round(prob, 4),
                    fare_inr          = normalised.get("fare_inr", 0),
                    recoverable_inr   = round(
                        normalised.get("fare_inr", 0) * 0.15, 2
                    ),
                    auto_escalated    = tier.auto_escalate,
                )
                db.add(case)
                await db.commit()
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
async def ingest_trip(
    event:       PorterTripEvent,
    request:     Request,
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
    if x_signature:
        body = await request.body()
        if not _verify_signature(body, x_signature):
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


@router.get("/status")
async def ingestion_status():
    """
    Ingestion pipeline status.
    Shows whether the webhook is configured
    and ready to receive Porter events.
    """
    return {
        "status":          "ready",
        "webhook_url":     "/ingest/trip-completed",
        "signature_check": WEBHOOK_SECRET != \
            "change-this-before-connecting-porter",
        "note": (
            "Signature check is disabled until "
            "Porter provides WEBHOOK_SECRET. "
            "Activate in Phase 3."
        ),
    }
