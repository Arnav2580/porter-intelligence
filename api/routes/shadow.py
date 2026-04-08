"""Shadow-mode status endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.case_store import get_case_storage_target, should_enforce_actions
from database.connection import get_db
from database.models import ShadowCase
from runtime_config import get_runtime_settings

router = APIRouter(prefix="/shadow", tags=["shadow"])


@router.get("/status")
async def shadow_status(db: AsyncSession = Depends(get_db)):
    """Expose shadow-mode safety state for buyer-facing demos."""
    runtime = get_runtime_settings()
    target = get_case_storage_target()
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    total_shadow_cases = await db.scalar(
        select(func.count(ShadowCase.id))
    ) or 0
    shadow_cases_24h = await db.scalar(
        select(func.count(ShadowCase.id)).where(
            ShadowCase.created_at >= cutoff_24h
        )
    ) or 0
    action_cases_24h = await db.scalar(
        select(func.count(ShadowCase.id)).where(
            and_(
                ShadowCase.created_at >= cutoff_24h,
                ShadowCase.tier == "action",
            )
        )
    ) or 0

    return {
        "shadow_mode": runtime.shadow_mode,
        "runtime_mode": runtime.mode.value,
        "case_write_target": target.table_name,
        "operational_writeback_enabled": False,
        "enforcement_enabled": should_enforce_actions(),
        "shadow_cases_total": total_shadow_cases,
        "shadow_cases_24h": shadow_cases_24h,
        "action_shadow_cases_24h": action_cases_24h,
        "note": (
            "When shadow mode is enabled, trips are scored normally but "
            "flagged cases are written only to shadow_cases and never trigger "
            "operational enforcement."
        ),
    }
