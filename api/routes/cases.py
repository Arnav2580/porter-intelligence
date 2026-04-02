"""Fraud case management.

Every scored trip creates a persistent case.
Analysts review and action cases here.
All changes are audit-logged.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import require_permission
from database.connection import get_db
from database.models import (
    AuditLog,
    DriverAction,
    DriverActionType,
    FraudCase,
    FraudCaseStatus,
)

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseUpdateRequest(BaseModel):
    status: FraudCaseStatus
    analyst_notes: Optional[str] = None
    override_reason: Optional[str] = None


class DriverActionRequest(BaseModel):
    action_type: DriverActionType
    reason: str
    case_id: Optional[str] = None


def _to_dict(case: FraudCase) -> dict:
    from security.encryption import decrypt_pii
    return {
        "id": str(case.id),
        "trip_id": decrypt_pii(case.trip_id) if case.trip_id else case.trip_id,
        "driver_id": decrypt_pii(case.driver_id) if case.driver_id else case.driver_id,
        "zone_id": case.zone_id,
        "fraud_type": case.fraud_type,
        "tier": case.tier,
        "fraud_probability": case.fraud_probability,
        "top_signals": case.top_signals,
        "fare_inr": case.fare_inr,
        "recoverable_inr": case.recoverable_inr,
        "status": case.status.value,
        "assigned_to": case.assigned_to,
        "analyst_notes": case.analyst_notes,
        "auto_escalated": case.auto_escalated,
        "created_at": case.created_at.isoformat()
        if case.created_at
        else None,
        "resolved_at": case.resolved_at.isoformat()
        if case.resolved_at
        else None,
    }


@router.get("/")
async def list_cases(
    status: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:cases")),
):
    query = select(FraudCase).order_by(FraudCase.created_at.desc())
    if status:
        query = query.where(FraudCase.status == status)
    if tier:
        query = query.where(FraudCase.tier == tier)
    if zone_id:
        query = query.where(FraudCase.zone_id == zone_id)
    if user["role"] == "ops_analyst":
        query = query.where(FraudCase.assigned_to == user["sub"])

    result = await db.execute(query.limit(limit).offset(offset))
    cases = result.scalars().all()
    return {
        "cases": [_to_dict(case) for case in cases],
        "total": len(cases),
        "offset": offset,
        "limit": limit,
    }


@router.get("/summary/counts")
async def case_counts(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:cases")),
):
    """Quick count by status for dashboard header."""
    counts = {}
    for status in FraudCaseStatus:
        n = await db.scalar(
            select(func.count(FraudCase.id)).where(FraudCase.status == status)
        )
        counts[status.value] = n or 0
    return counts


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:cases")),
):
    result = await db.execute(
        select(FraudCase).where(FraudCase.id == uuid.UUID(case_id))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    return _to_dict(case)


@router.patch("/{case_id}")
async def update_case(
    case_id: str,
    body: CaseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("write:case_status")),
):
    result = await db.execute(
        select(FraudCase).where(FraudCase.id == uuid.UUID(case_id))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")

    old_status = case.status
    case.status = body.status
    case.analyst_notes = body.analyst_notes
    case.override_reason = body.override_reason
    case.updated_at = datetime.utcnow()

    if body.status in (
        FraudCaseStatus.CONFIRMED,
        FraudCaseStatus.FALSE_ALARM,
    ):
        case.resolved_at = datetime.utcnow()

    db.add(
        AuditLog(
            user_id=user["sub"],
            action="case_status_change",
            resource="fraud_case",
            resource_id=case_id,
            details={
                "old_status": old_status.value,
                "new_status": body.status.value,
                "notes": body.analyst_notes,
            },
        )
    )

    await db.commit()
    return _to_dict(case)


@router.post("/{case_id}/driver-action")
async def take_driver_action(
    case_id: str,
    body: DriverActionRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("write:driver_actions")),
):
    result = await db.execute(
        select(FraudCase).where(FraudCase.id == uuid.UUID(case_id))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")

    db.add(
        DriverAction(
            driver_id=case.driver_id,
            action_type=body.action_type,
            reason=body.reason,
            performed_by=user["sub"],
            case_id=case_id,
        )
    )
    db.add(
        AuditLog(
            user_id=user["sub"],
            action=f"driver_{body.action_type.value}",
            resource="driver",
            resource_id=case.driver_id,
            details={
                "case_id": case_id,
                "reason": body.reason,
            },
        )
    )
    await db.commit()

    return {
        "driver_id": case.driver_id,
        "action": body.action_type.value,
        "performed_by": user["sub"],
        "case_id": case_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
