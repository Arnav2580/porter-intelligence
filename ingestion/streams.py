"""
Redis Streams ingestion pipeline — Phase B.

Producer: publish normalized trip events to the porter:trips stream.
Consumer: XREADGROUP loop — score with stateless scorer, persist high-risk cases.

The webhook publishes to this stream and returns 200 immediately.
All scoring and persistence happens here, asynchronously.
"""

import asyncio
import json
import logging
from typing import Dict

logger = logging.getLogger(__name__)

STREAM_NAME = "porter:trips"
GROUP_NAME  = "scoring-workers"
CONSUMER    = "worker-1"
BLOCK_MS    = 2000   # long-poll timeout per XREADGROUP call


async def ensure_consumer_group() -> None:
    """Create the consumer group if it doesn't already exist."""
    from database.redis_client import get_redis
    try:
        await get_redis().xgroup_create(
            STREAM_NAME, GROUP_NAME, id="0", mkstream=True
        )
        logger.info(f"Consumer group '{GROUP_NAME}' created on {STREAM_NAME}")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass   # group already exists — expected on restart
        else:
            logger.warning(f"xgroup_create: {e}")


async def publish_trip(trip: Dict) -> str:
    """
    Publish a normalised trip dict to the Redis Stream.
    Returns the Redis message ID.
    Raises on Redis failure — caller should fall back to inline scoring.
    """
    from database.redis_client import get_redis
    msg_id = await get_redis().xadd(
        STREAM_NAME, {"data": json.dumps(trip)}
    )
    return msg_id


async def consume_loop() -> None:
    """
    Long-running asyncio task. Reads from the Redis Stream consumer group,
    scores each trip with the stateless scorer, persists high-risk cases.

    Started by api/state.py lifespan. Cancelled on shutdown.
    """
    await ensure_consumer_group()
    logger.info(
        f"Stream consumer started "
        f"({STREAM_NAME}/{GROUP_NAME}/{CONSUMER})"
    )

    from database.redis_client import get_redis

    while True:
        try:
            messages = await get_redis().xreadgroup(
                GROUP_NAME,
                CONSUMER,
                {STREAM_NAME: ">"},
                count=10,
                block=BLOCK_MS,
            )

            if not messages:
                continue

            for _stream, stream_messages in messages:
                for msg_id, fields in stream_messages:
                    try:
                        trip = json.loads(fields.get("data", "{}"))
                        await _score_and_persist(trip, msg_id)
                        # ACK only after successful processing
                        await get_redis().xack(
                            STREAM_NAME, GROUP_NAME, msg_id
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to process stream msg {msg_id}: {e}"
                        )
                        # Message stays in PEL for manual inspection —
                        # do not ACK on failure

        except asyncio.CancelledError:
            logger.info("Stream consumer shutting down cleanly")
            break
        except Exception as e:
            _consume_failures = getattr(consume_loop, "_consecutive_failures", 0) + 1
            consume_loop._consecutive_failures = _consume_failures
            if _consume_failures == 1 or _consume_failures % 10 == 0:
                logger.error(f"Stream consumer loop error: {e}")
            backoff = min(5 * (2 ** (_consume_failures - 1)), 60)
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                logger.info("Stream consumer shutting down cleanly")
                break


async def _score_and_persist(trip: Dict, msg_id: str) -> None:
    """Score one trip from the stream and persist a FraudCase if flagged."""
    from api.state import app_state
    from database.case_store import persist_flagged_case
    from model.scoring import get_tier

    model         = app_state.get("model")
    feature_names = app_state.get("feature_names", [])
    two_stage     = app_state.get("two_stage_config", {})

    if model is None or not feature_names:
        logger.warning("Model not ready — skipping stream message")
        return

    from ml.stateless_scorer import score_trip_stateless
    result     = await score_trip_stateless(
        trip, model, feature_names, two_stage
    )
    fraud_prob = result["fraud_probability"]
    tier       = get_tier(fraud_prob)

    logger.info(
        f"[stream] trip={trip.get('trip_id', '?')} "
        f"prob={fraud_prob:.3f} tier={tier.name} msg={msg_id}"
    )

    # Emit Prometheus counter if monitoring is loaded
    try:
        from monitoring.metrics import TRIPS_SCORED
        TRIPS_SCORED.labels(tier=tier.name, path="stream").inc()
    except Exception:
        pass

    if tier.name in ("action", "watchlist"):
        await persist_flagged_case(
            trip_id=str(trip.get("trip_id", msg_id)),
            driver_id=str(trip.get("driver_id", "unknown")),
            zone_id=trip.get("pickup_zone_id", "unknown"),
            tier=tier.name,
            fraud_probability=fraud_prob,
            top_signals=[],
            fare_inr=trip.get("fare_inr", 0),
            recoverable_inr=round(
                trip.get("fare_inr", 0) * 0.15,
                2,
            ),
            auto_escalated=tier.auto_escalate,
            source_channel="redis_stream",
        )
        logger.info(
            f"[stream] case persisted: "
            f"trip={trip.get('trip_id')} tier={tier.name}"
        )


async def get_stream_lag() -> int:
    """Return the PEL count for the scoring-workers group (stream lag gauge)."""
    from database.redis_client import get_redis
    try:
        groups = await get_redis().xinfo_groups(STREAM_NAME)
        for group in groups:
            name = group.get("name") or group.get(b"name", b"").decode()
            if name == GROUP_NAME:
                return int(
                    group.get("pel-count")
                    or group.get(b"pel-count", 0)
                )
    except Exception:
        pass
    return 0
