"""PostgreSQL staging buffer for ingestion retry and replay."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from database.connection import AsyncSessionLocal
from database.models import (
    IngestionStagingRecord,
    IngestionStagingStatus,
)
from database.redis_client import ping_redis
from ingestion.streams import publish_trip


async def buffer_trip_payloads(
    payloads: list[dict],
    *,
    source: str,
    mapping_name: str,
    error_message: str | None = None,
) -> int:
    """Persist payloads to the staging table for later replay."""
    if not payloads:
        return 0

    async with AsyncSessionLocal() as db:
        db.add_all(
            [
                IngestionStagingRecord(
                    source=source,
                    mapping_name=mapping_name,
                    external_trip_id=payload.get("trip_id"),
                    payload=payload,
                    status=IngestionStagingStatus.PENDING,
                    error_message=error_message,
                    last_error_at=(
                        datetime.now(timezone.utc)
                        if error_message
                        else None
                    ),
                )
                for payload in payloads
            ]
        )
        await db.commit()
    return len(payloads)


async def drain_staged_trips(limit: int = 100) -> dict[str, int | bool]:
    """Replay pending/failed staged rows back onto Redis when available."""
    redis_available = await ping_redis()
    if not redis_available:
        return {
            "redis_available": False,
            "drained": 0,
            "failed": 0,
        }

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(IngestionStagingRecord)
            .where(
                IngestionStagingRecord.status.in_(
                    (
                        IngestionStagingStatus.PENDING,
                        IngestionStagingStatus.FAILED,
                    )
                )
            )
            .order_by(IngestionStagingRecord.created_at.asc())
            .limit(limit)
        )
        rows = result.scalars().all()

        drained = 0
        failed = 0
        now = datetime.now(timezone.utc)
        for row in rows:
            try:
                msg_id = await publish_trip(row.payload)
                row.status = IngestionStagingStatus.QUEUED
                row.stream_message_id = msg_id
                row.queued_at = now
                row.error_message = None
                drained += 1
            except Exception as exc:
                row.status = IngestionStagingStatus.FAILED
                row.retry_count += 1
                row.error_message = str(exc)[:500]
                row.last_error_at = now
                failed += 1
                break

        await db.commit()

    return {
        "redis_available": True,
        "drained": drained,
        "failed": failed,
    }


async def get_queue_status_summary(
    *,
    auto_drain: bool = True,
) -> dict[str, int | bool | dict]:
    """Return staging queue health and counts by status."""
    redis_available = await ping_redis()
    drain_result = {
        "redis_available": redis_available,
        "drained": 0,
        "failed": 0,
    }
    if auto_drain and redis_available:
        drain_result = await drain_staged_trips(limit=100)

    async with AsyncSessionLocal() as db:
        counts_result = await db.execute(
            select(
                IngestionStagingRecord.status,
                func.count(IngestionStagingRecord.id),
            ).group_by(IngestionStagingRecord.status)
        )
        counts = {
            status.value if status else "unknown": count
            for status, count in counts_result.all()
        }
        oldest_pending = await db.scalar(
            select(func.min(IngestionStagingRecord.created_at)).where(
                IngestionStagingRecord.status.in_(
                    (
                        IngestionStagingStatus.PENDING,
                        IngestionStagingStatus.FAILED,
                    )
                )
            )
        )

    return {
        "redis_available": redis_available,
        "counts": counts,
        "pending_rows": counts.get("pending", 0),
        "failed_rows": counts.get("failed", 0),
        "queued_rows": counts.get("queued", 0),
        "oldest_pending_at": (
            oldest_pending.isoformat() if oldest_pending else None
        ),
        "auto_drain_result": drain_result,
    }
