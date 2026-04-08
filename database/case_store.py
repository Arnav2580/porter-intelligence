"""Case persistence helpers for live and shadow modes."""

from __future__ import annotations

from dataclasses import dataclass

from database.connection import AsyncSessionLocal
from database.models import FraudCase, ShadowCase
from runtime_config import get_runtime_settings
from security.encryption import encrypt_pii


@dataclass(frozen=True)
class CasePersistenceResult:
    storage_mode: str
    table_name: str


def is_shadow_mode_enabled() -> bool:
    return get_runtime_settings().shadow_mode


def should_enforce_actions() -> bool:
    return not is_shadow_mode_enabled()


def get_case_storage_target() -> CasePersistenceResult:
    if is_shadow_mode_enabled():
        return CasePersistenceResult(
            storage_mode="shadow",
            table_name="shadow_cases",
        )
    return CasePersistenceResult(
        storage_mode="live",
        table_name="fraud_cases",
    )


async def persist_flagged_case(
    *,
    trip_id: str,
    driver_id: str,
    zone_id: str,
    tier: str,
    fraud_probability: float,
    top_signals: list[str] | None,
    fare_inr: float,
    recoverable_inr: float,
    auto_escalated: bool,
    source_channel: str,
) -> CasePersistenceResult:
    """Persist a flagged case to live or shadow storage."""
    target = get_case_storage_target()
    trip_id_stored = encrypt_pii(str(trip_id))
    driver_id_stored = encrypt_pii(str(driver_id))

    async with AsyncSessionLocal() as db:
        if target.storage_mode == "shadow":
            case = ShadowCase(
                trip_id=trip_id_stored,
                driver_id=driver_id_stored,
                zone_id=zone_id,
                tier=tier,
                fraud_probability=round(fraud_probability, 4),
                top_signals=top_signals or [],
                fare_inr=fare_inr,
                recoverable_inr=recoverable_inr,
                source_channel=source_channel,
                live_write_suppressed=True,
            )
        else:
            case = FraudCase(
                trip_id=trip_id_stored,
                driver_id=driver_id_stored,
                zone_id=zone_id,
                tier=tier,
                fraud_probability=round(fraud_probability, 4),
                top_signals=top_signals or [],
                fare_inr=fare_inr,
                recoverable_inr=recoverable_inr,
                auto_escalated=auto_escalated,
            )

        db.add(case)
        await db.commit()

    return target
