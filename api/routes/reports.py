"""Management reporting endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import require_permission
from database.connection import get_db
from database.models import FraudCase, FraudCaseStatus

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily-summary")
async def daily_summary(
    date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:reports")),
):
    target = datetime.fromisoformat(date) if date else datetime.utcnow()
    day_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    opened = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.created_at >= day_start,
                FraudCase.created_at < day_end,
            )
        )
    ) or 0

    confirmed = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.resolved_at >= day_start,
                FraudCase.resolved_at < day_end,
                FraudCase.status == FraudCaseStatus.CONFIRMED,
            )
        )
    ) or 0

    false_alarms = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.resolved_at >= day_start,
                FraudCase.resolved_at < day_end,
                FraudCase.status == FraudCaseStatus.FALSE_ALARM,
            )
        )
    ) or 0

    resolved = confirmed + false_alarms
    precision = confirmed / max(resolved, 1)

    recovered = await db.scalar(
        select(func.sum(FraudCase.recoverable_inr)).where(
            and_(
                FraudCase.resolved_at >= day_start,
                FraudCase.resolved_at < day_end,
                FraudCase.status == FraudCaseStatus.CONFIRMED,
            )
        )
    ) or 0.0

    return {
        "date": day_start.date().isoformat(),
        "cases_opened": opened,
        "cases_confirmed": confirmed,
        "cases_false_alarm": false_alarms,
        "unresolved": opened - resolved,
        "live_precision": round(precision, 4),
        "recovered_inr": round(float(recovered), 2),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/model-performance")
async def model_performance(
    days: int = Query(30, le=90),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:reports")),
):
    """Live model performance from analyst verdicts."""
    since = datetime.utcnow() - timedelta(days=days)

    total = await db.scalar(
        select(func.count(FraudCase.id)).where(FraudCase.created_at >= since)
    ) or 0

    confirmed = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.created_at >= since,
                FraudCase.status == FraudCaseStatus.CONFIRMED,
            )
        )
    ) or 0

    false_alarms = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.created_at >= since,
                FraudCase.status == FraudCaseStatus.FALSE_ALARM,
            )
        )
    ) or 0

    resolved = confirmed + false_alarms
    precision = confirmed / max(resolved, 1)

    recovered = await db.scalar(
        select(func.sum(FraudCase.recoverable_inr)).where(
            and_(
                FraudCase.created_at >= since,
                FraudCase.status == FraudCaseStatus.CONFIRMED,
            )
        )
    ) or 0.0

    return {
        "period_days": days,
        "total_cases": total,
        "confirmed_fraud": confirmed,
        "false_alarms": false_alarms,
        "unresolved": total - resolved,
        "live_precision": round(precision, 4),
        "total_recovered_inr": round(float(recovered), 2),
        "avg_per_confirmed": round(float(recovered) / max(confirmed, 1), 2),
        "note": (
            "Precision computed from analyst verdicts. "
            "Populate by reviewing cases in the analyst UI."
        ),
        "generated_at": datetime.utcnow().isoformat(),
    }
