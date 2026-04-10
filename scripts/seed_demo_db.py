"""
scripts/seed_demo_db.py — Pre-seed the demo database with reviewed fraud cases.

Inserts a realistic mix of confirmed/false-alarm cases so the KPI Panel shows
non-zero metrics during investor/client demos instead of "Awaiting Analyst Reviews".

Safe to run multiple times (idempotent via trip_id check).

Usage:
    python scripts/seed_demo_db.py
"""

import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add repo root to path so imports work from any cwd
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from database.connection import AsyncSessionLocal
from database.models import FraudCase, FraudCaseStatus
from security.encryption import encrypt_pii
from sqlalchemy import select

SEED_TRIP_PREFIX = "SEED_DEMO_"

ZONES = [
    "blr_koramangala", "blr_whitefield", "blr_indiranagar",
    "blr_hsr", "blr_marathahalli", "mum_andheri", "del_cp",
]

SIGNAL_SETS = [
    ["Fare inflated 2.45×", "Cash payment", "New/unverified driver account"],
    ["Cancellations this hour: 6", "Night-time trip", "Cancel rate 42% (7d)"],
    ["Distance inflated 2.81×", "Cash payment", "Dispute rate 28% (14d)"],
    ["Cash ratio 91% (7d)", "Zone fraud rate 14.2%", "New/unverified driver account"],
    ["Speed anomaly (2.31 km/min)", "Pickup = dropoff zone", "Cash payment"],
]

# 30 seed cases: ~73% confirmed fraud (matches benchmark precision), rest false alarms
SEED_CASES = []
now = datetime.now(timezone.utc)

random.seed(42)
for i in range(30):
    days_ago   = random.randint(1, 14)
    created_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))

    # 73% confirmed, 27% false alarm
    if i < 22:
        status         = FraudCaseStatus.CONFIRMED
        fraud_prob     = round(random.uniform(0.72, 0.99), 4)
        fare           = round(random.uniform(120, 420), 2)
        recoverable    = round(fare * random.uniform(0.12, 0.18), 2)
        tier           = "action" if fraud_prob >= 0.94 else "watchlist"
    else:
        status         = FraudCaseStatus.FALSE_ALARM
        fraud_prob     = round(random.uniform(0.45, 0.71), 4)
        fare           = round(random.uniform(60, 180), 2)
        recoverable    = 0.0
        tier           = "watchlist"

    SEED_CASES.append({
        "trip_id":          f"{SEED_TRIP_PREFIX}{i:04d}",
        "driver_id":        f"DEMO_DRV_{i:04d}",
        "zone_id":          random.choice(ZONES),
        "tier":             tier,
        "fraud_probability":fraud_prob,
        "top_signals":      random.choice(SIGNAL_SETS),
        "fare_inr":         fare,
        "recoverable_inr":  recoverable,
        "status":           status,
        "auto_escalated":   tier == "action",
        "created_at":       created_at,
    })


async def seed():
    async with AsyncSessionLocal() as db:
        # Check which seeds already exist
        result = await db.execute(
            select(FraudCase.trip_id).where(
                FraudCase.trip_id.like(f"%{SEED_TRIP_PREFIX}%")
            )
        )
        existing_raw = {row[0] for row in result.fetchall()}

        inserted = 0
        for c in SEED_CASES:
            case = FraudCase(
                trip_id            = encrypt_pii(c["trip_id"]),
                driver_id          = encrypt_pii(c["driver_id"]),
                zone_id            = c["zone_id"],
                fraud_type         = "demo_seed",   # marker for idempotency check
                tier               = c["tier"],
                fraud_probability  = c["fraud_probability"],
                top_signals        = c["top_signals"],
                fare_inr           = c["fare_inr"],
                recoverable_inr    = c["recoverable_inr"],
                status             = c["status"],
                auto_escalated     = c["auto_escalated"],
                created_at         = c["created_at"],
            )
            db.add(case)
            inserted += 1

        await db.commit()
        print(f"[seed_demo_db] Inserted {inserted} demo cases")
        return inserted


async def check_existing_count():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import func as sqlfunc
        result = await db.execute(
            select(sqlfunc.count()).select_from(FraudCase).where(
                FraudCase.fraud_type == "demo_seed"
            )
        )
        return result.scalar() or 0


async def main():
    existing = await check_existing_count()
    if existing >= len(SEED_CASES):
        print(f"[seed_demo_db] {existing} seed cases already present — skipping")
        return
    await seed()
    print("[seed_demo_db] Done. KPI panel will now show reviewed-case metrics.")


if __name__ == "__main__":
    asyncio.run(main())
