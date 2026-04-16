"""Shadow-mode status endpoints."""

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.state import app_state
from auth.dependencies import require_permission
from database.case_store import get_case_storage_target, should_enforce_actions
from database.connection import get_db
from database.models import ShadowCase
from runtime_config import get_runtime_settings

router = APIRouter(prefix="/shadow", tags=["shadow"])


def _set_shadow_mode(enabled: bool) -> None:
    os.environ["SHADOW_MODE"] = "true" if enabled else "false"
    app_state["shadow_mode"] = enabled


@router.get("/status")
async def shadow_status(
    db: AsyncSession = Depends(get_db),
):
    """Expose shadow-mode safety state for buyer-facing demos."""
    runtime = get_runtime_settings()
    target = get_case_storage_target()
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
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
    except Exception:
        return {
            "shadow_mode": runtime.shadow_mode,
            "runtime_mode": runtime.mode.value,
            "case_write_target": "unavailable",
            "operational_writeback_enabled": False,
            "enforcement_enabled": False,
            "shadow_cases_total": 0,
            "shadow_cases_24h": 0,
            "action_shadow_cases_24h": 0,
            "status": "infrastructure_unavailable",
            "note": "Database unreachable — shadow-mode case counts unavailable.",
        }

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


@router.post("/activate")
async def activate_shadow_mode(
    user: dict = Depends(require_permission("write:all")),
):
    """Enable read-only shadow scoring mode."""
    _set_shadow_mode(True)
    activated_at = datetime.now(timezone.utc).isoformat()
    return {
        "shadow_mode": True,
        "activated_at": activated_at,
        "message": (
            "Shadow mode activated. Scoring runs read-only. "
            "No operational writeback."
        ),
        "enforcement_disabled": True,
    }


@router.post("/deactivate")
async def deactivate_shadow_mode(
    user: dict = Depends(require_permission("write:all")),
):
    """Disable shadow mode and restore live enforcement."""
    _set_shadow_mode(False)
    deactivated_at = datetime.now(timezone.utc).isoformat()
    return {
        "shadow_mode": False,
        "deactivated_at": deactivated_at,
        "message": "Shadow mode deactivated. Live enforcement resumed.",
    }
