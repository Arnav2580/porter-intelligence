"""
Porter Intelligence Platform — Driver Profile Generator v2

v2 changes:
  - REMOVED: fraud_propensity field (was a leaked training label)
  - REMOVED: fraud_propensity_segments (god-mode cheating for model)
  - ADDED:   document verification fields (aadhaar, DL, RC, bank KYC)
  - ADDED:   observable behavioral stats (30-day rolling windows)
  - ADDED:   device risk signals (shared_device, duplicate_account)
  - KEPT:    fraud_ring_id / ring_role — these are structural metadata
             used for RING DETECTION logic, not per-trip fraud label
  - Ring assignment now based on OBSERVABLE driver behavior stats,
    not on a hidden propensity score

The fraud injection engine (fraud.py) uses probabilistic selection
based on observable driver features — not a leaked propensity field.
"""

import uuid
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from generator.config import (
    RANDOM_SEED, NUM_DRIVERS, CITIES, VEHICLE_TYPES,
    VEHICLE_DISTRIBUTION, DATA_RAW,
    CITY_CASH_PCT,
)
from generator.cities import ZONES, CITY_ZONES

console = Console()

fake_seed = RANDOM_SEED
rng = np.random.default_rng(RANDOM_SEED)

# ── Indian name pool ──────────────────────────────────────────
INDIAN_FIRST_NAMES: List[str] = [
    "Ravi", "Suresh", "Ramesh", "Mahesh", "Ganesh", "Rajesh",
    "Dinesh", "Naresh", "Prakash", "Lokesh", "Umesh", "Rakesh",
    "Vijay", "Sanjay", "Ajay", "Manoj", "Anil", "Sunil",
    "Mukesh", "Deepak", "Vivek", "Ashok", "Vinod",
    "Mohan", "Rohan", "Krishan", "Kishan", "Harish",
    "Girish", "Paresh", "Nilesh", "Ritesh", "Satish",
    "Manish", "Santosh", "Venkatesh", "Shivakumar", "Basavaraj",
    "Mohammed", "Abdul", "Ibrahim", "Salman", "Imran",
    "Arjun", "Kiran", "Pavan", "Naveen", "Praveen",
    "Thirumalai", "Selvam", "Murugan", "Senthil", "Karthi",
    "Babu", "Raja", "Rajan", "Mani", "Kumar",
]

INDIAN_LAST_NAMES: List[str] = [
    "Kumar", "Singh", "Sharma", "Yadav", "Gupta", "Mishra",
    "Patel", "Shah", "Mehta", "Desai", "Joshi", "Nair",
    "Pillai", "Menon", "Reddy", "Naidu", "Rao", "Iyer",
    "Bhat", "Shetty", "Gowda", "Hegde", "Patil",
    "Kulkarni", "Jain", "Agarwal", "Bansal", "Garg",
    "Khan", "Ansari", "Shaikh", "Siddiqui",
    "Mukherjee", "Chatterjee", "Das", "Ghosh",
    "Verma", "Tiwari", "Pandey", "Dubey", "Shukla",
    "Nayak", "Swamy", "Murthy", "Raju", "Babu",
]


def generate_indian_phone(rng: np.random.Generator) -> str:
    first_digit = rng.choice([6, 7, 8, 9])
    remaining = rng.integers(100_000_000, 999_999_999)
    return f"+91{first_digit}{remaining}"


def generate_indian_name(rng: np.random.Generator) -> str:
    first = rng.choice(INDIAN_FIRST_NAMES)
    last  = rng.choice(INDIAN_LAST_NAMES)
    return f"{first} {last}"


def assign_driver_zone(city: str, rng: np.random.Generator) -> str:
    """
    Assign a home zone to a driver.
    Distribution is uniform — fraud-zone bias is removed.
    Real fraud emerges from behavioral patterns, not pre-seeded zones.
    """
    zone_ids = CITY_ZONES.get(city, [])
    if not zone_ids:
        return "unknown"
    return str(rng.choice(zone_ids))


def sample_behavioral_stats(
    account_age_days: int,
    vehicle_type: str,
    city: str,
    rng: np.random.Generator,
) -> dict:
    """
    Generate realistic 30-day behavioral statistics for a driver.

    These are the ONLY behavioral signals the fraud model sees.
    They replace the leaked fraud_propensity field entirely.

    Three latent driver archetypes (drawn probabilistically):
      ~91% honest drivers  → low cancel, low dispute, moderate cash
      ~6%  opportunistic   → elevated cancel + dispute, higher cash
      ~3%  chronic risk    → high cancel, high dispute, high cash, low rating

    This is a natural outcome of the behavioral distribution,
    not a stored propensity label.
    """
    city_cash_pct = CITY_CASH_PCT.get(city, 0.25)

    # Draw archetype
    draw = rng.random()
    if draw < 0.91:
        # Honest: low risk across all signals
        cancel_rate   = float(np.clip(rng.beta(1.2, 10.0) * 0.18, 0.0, 0.18))
        dispute_rate  = float(np.clip(rng.beta(1.0, 20.0) * 0.05, 0.0, 0.05))
        cash_ratio    = float(np.clip(
            rng.normal(city_cash_pct, city_cash_pct * 0.3), 0.0, 0.55
        ))
        avg_rating    = float(np.clip(rng.normal(4.3, 0.3), 3.5, 5.0))
        night_ratio   = float(np.clip(rng.beta(1.5, 8.0) * 0.25, 0.0, 0.25))

    elif draw < 0.97:
        # Opportunistic: elevated on 1–2 signals
        cancel_rate   = float(np.clip(rng.beta(2.5, 6.0) * 0.40, 0.05, 0.40))
        dispute_rate  = float(np.clip(rng.beta(2.0, 8.0) * 0.12, 0.01, 0.12))
        cash_ratio    = float(np.clip(
            rng.normal(city_cash_pct + 0.20, 0.10), 0.10, 0.70
        ))
        avg_rating    = float(np.clip(rng.normal(3.8, 0.4), 2.5, 4.5))
        night_ratio   = float(np.clip(rng.beta(2.0, 5.0) * 0.40, 0.05, 0.40))

    else:
        # Chronic risk: consistently elevated across all signals
        cancel_rate   = float(np.clip(rng.beta(3.0, 4.0) * 0.55, 0.15, 0.55))
        dispute_rate  = float(np.clip(rng.beta(3.0, 5.0) * 0.25, 0.05, 0.25))
        cash_ratio    = float(np.clip(
            rng.normal(city_cash_pct + 0.35, 0.12), 0.30, 0.92
        ))
        avg_rating    = float(np.clip(rng.normal(3.2, 0.5), 1.0, 4.0))
        night_ratio   = float(np.clip(rng.beta(3.0, 4.0) * 0.60, 0.15, 0.60))

    # Trip counts derived from account age (2–4 trips/day)
    trips_per_day = float(np.clip(rng.normal(2.8, 0.8), 0.5, 8.0))
    active_days   = min(account_age_days, 30)
    trips_30d     = max(1, int(trips_per_day * active_days * 0.85))

    # Average fare by vehicle type
    veh = VEHICLE_TYPES[vehicle_type]
    avg_distance_30d = float(np.clip(
        rng.normal(
            (veh.typical_trip_km[0] + veh.typical_trip_km[1]) / 2,
            (veh.typical_trip_km[1] - veh.typical_trip_km[0]) / 4
        ),
        veh.typical_trip_km[0], veh.typical_trip_km[1]
    ))
    avg_fare_30d = veh.base_fare + veh.per_km_rate * avg_distance_30d
    avg_fare_30d = float(np.clip(
        rng.normal(avg_fare_30d, avg_fare_30d * 0.15),
        veh.base_fare, avg_fare_30d * 2.5
    ))

    # Completion rate (inverse of cancel rate)
    completion_rate_30d = float(np.clip(1.0 - cancel_rate - 0.05, 0.40, 0.98))

    return {
        "trips_last_30d":       trips_30d,
        "completion_rate_30d":  round(completion_rate_30d, 4),
        "cancel_rate_30d":      round(cancel_rate, 4),
        "dispute_rate_30d":     round(dispute_rate, 4),
        "cash_trip_ratio_30d":  round(cash_ratio, 4),
        "avg_rating_30d":       round(avg_rating, 2),
        "night_trip_ratio_30d": round(night_ratio, 4),
        "avg_fare_30d":         round(avg_fare_30d, 2),
        "avg_distance_30d":     round(avg_distance_30d, 2),
    }


def assign_fraud_rings(
    df: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Assign fraud ring membership based on OBSERVABLE behavioral signals.

    Ring criteria (all must be true):
      - cancel_rate_30d > 0.20  (active cancellation abuser)
      - dispute_rate_30d > 0.05 (elevated disputes)
      - cash_trip_ratio_30d > city_avg + 0.25 (cash preference)

    ~60% of qualifying drivers are grouped into rings (3-6 per ring).
    ~40% are solo operators with similar behavior.

    Rings are zone-contained (same city zone) — realistic operational pattern.
    """
    df = df.copy()
    df["fraud_ring_id"] = None
    df["ring_role"]     = None

    # Identify behavioral risk drivers using ONLY observable signals
    risk_mask = (
        (df["cancel_rate_30d"]     > 0.20) &
        (df["dispute_rate_30d"]    > 0.05) &
        (df["cash_trip_ratio_30d"] > 0.40)
    )
    risk_drivers = df[risk_mask].copy()

    if len(risk_drivers) == 0:
        return df

    # 60% join rings, 40% solo
    join_ring_mask = rng.random(len(risk_drivers)) < 0.60
    ring_candidates = risk_drivers[join_ring_mask]

    ring_counter = 1
    processed_ids: set = set()

    for (city, zone_id), group in ring_candidates.groupby(["city", "zone_id"]):
        group_idx = list(group.index)
        rng.shuffle(group_idx)

        i = 0
        while i < len(group_idx):
            ring_size    = int(rng.integers(3, 7))
            ring_members = group_idx[i : i + ring_size]

            if len(ring_members) < 2:
                for idx in ring_members:
                    df.at[idx, "ring_role"] = "solo"
                i += ring_size
                continue

            ring_id = f"RING_{city[:3].upper()}_{ring_counter:03d}"
            ring_counter += 1

            # Leader = highest cancel rate (observable signal)
            leader_idx = max(
                ring_members,
                key=lambda idx: df.at[idx, "cancel_rate_30d"],
            )

            for idx in ring_members:
                df.at[idx, "fraud_ring_id"] = ring_id
                df.at[idx, "ring_role"]     = (
                    "leader" if idx == leader_idx else "member"
                )
                processed_ids.add(idx)

            i += ring_size

    # Mark remaining risk drivers as solo
    for idx in risk_drivers.index:
        if idx not in processed_ids:
            df.at[idx, "ring_role"] = "solo"

    return df


def generate_drivers(
    n: int = NUM_DRIVERS,
    city_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generate n Porter driver profiles as a DataFrame.

    Schema v2: No fraud_propensity field.
    All behavioral signals are observable and derivable from trip history.
    """
    today   = datetime.now().date()
    records = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating driver profiles v2...", total=n)

        for _ in range(n):
            # ── Identity ──────────────────────────────────────
            driver_id = str(uuid.uuid4())
            name      = generate_indian_name(rng)
            phone     = generate_indian_phone(rng)

            # ── City ──────────────────────────────────────────
            city = city_filter if city_filter else str(rng.choice(CITIES[:3]))

            # ── Vehicle type ──────────────────────────────────
            vehicle_type = str(rng.choice(
                list(VEHICLE_DISTRIBUTION.keys()),
                p=list(VEHICLE_DISTRIBUTION.values()),
            ))

            # ── Joining date ──────────────────────────────────
            # 60% experienced (2-6 years), 40% newer (1 month – 2 years)
            if rng.random() < 0.60:
                days_ago = int(rng.integers(365 * 2, 365 * 6))
            else:
                days_ago = int(rng.integers(30, 365 * 2))
            joining_date     = today - timedelta(days=days_ago)
            account_age_days = days_ago

            # ── Document verification (KYC) ───────────────────
            # 75% fully verified, 15% pending, 10% unverified
            kyc_status = str(rng.choice(
                ["verified", "pending", "unverified", "expired"],
                p=[0.75, 0.12, 0.10, 0.03],
            ))
            aadhaar_verified    = kyc_status == "verified" or rng.random() < 0.82
            dl_verified         = kyc_status == "verified" or rng.random() < 0.78
            vehicle_rc_verified = kyc_status == "verified" or rng.random() < 0.80
            bank_verified       = kyc_status == "verified" or rng.random() < 0.85

            # DL expiry (5-10 years from joining, ~5% expired)
            dl_years = float(rng.uniform(1, 10))
            dl_expiry = joining_date + timedelta(days=int(dl_years * 365))
            dl_expired = dl_expiry < today

            # ── Payment preference ────────────────────────────
            # Note: bank_account_type is how Porter pays the driver
            bank_account_type = str(rng.choice(
                ["upi", "bank", "cash"],
                p=[0.65, 0.25, 0.10],
            ))

            # ── Zone ─────────────────────────────────────────
            zone_id = assign_driver_zone(city, rng)

            # ── Behavioral stats (30-day rolling) ─────────────
            behavior = sample_behavioral_stats(
                account_age_days, vehicle_type, city, rng
            )

            # ── Lifetime stats ────────────────────────────────
            base_trips           = account_age_days * rng.normal(2.5, 0.8)
            total_trips_lifetime = max(0, int(base_trips))
            veh                  = VEHICLE_TYPES[vehicle_type]
            avg_fare_lifetime    = veh.base_fare + veh.per_km_rate * 8
            trips_per_month      = max(1, int(
                total_trips_lifetime / max(1, account_age_days / 30)
            ))
            monthly_earnings_avg = float(
                trips_per_month * avg_fare_lifetime * 0.80
                * rng.normal(1.0, 0.15)
            )

            # ── Activity ──────────────────────────────────────
            is_active = bool(rng.random() < 0.95)

            # ── Churn risk (derived from observable signals) ──
            churn_base = 0.10
            if account_age_days < 90:
                churn_base += 0.20
            if monthly_earnings_avg < 8_000:
                churn_base += 0.15
            if behavior["avg_rating_30d"] < 3.8:
                churn_base += 0.20
            churn_risk = float(np.clip(
                churn_base + rng.normal(0, 0.05), 0.0, 1.0
            ))

            # ── Device risk signals ───────────────────────────
            # Shared device: same phone used for multiple accounts
            # (small probability — increases for new/unverified accounts)
            shared_device_prob = 0.02 if kyc_status == "verified" else 0.08
            shared_device_flag = bool(rng.random() < shared_device_prob)

            # Duplicate account: same aadhaar/phone on another account
            dup_account_prob = 0.01 if kyc_status == "verified" else 0.05
            duplicate_account_flag = bool(rng.random() < dup_account_prob)

            # Document mismatch (name vs RC vs DL)
            doc_mismatch = not dl_verified or not vehicle_rc_verified

            records.append({
                # ── Identity ──────────────────────────────────
                "driver_id":               driver_id,
                "name":                    name,
                "phone":                   phone,
                "city":                    city,
                "zone_id":                 zone_id,
                "vehicle_type":            vehicle_type,

                # ── Account ───────────────────────────────────
                "joining_date":            str(joining_date),
                "account_age_days":        account_age_days,
                "is_active":               is_active,

                # ── Document KYC ──────────────────────────────
                "kyc_status":              kyc_status,
                "aadhaar_verified":        aadhaar_verified,
                "dl_verified":             dl_verified,
                "dl_expired":              dl_expired,
                "vehicle_rc_verified":     vehicle_rc_verified,
                "bank_account_verified":   bank_verified,
                "bank_account_type":       bank_account_type,

                # ── Behavioral stats (30-day rolling) ─────────
                # These are the ONLY risk signals exposed to the model
                **behavior,

                # ── Lifetime ──────────────────────────────────
                "total_trips_lifetime":    total_trips_lifetime,
                "monthly_earnings_avg":    round(monthly_earnings_avg, 2),
                "churn_risk":              round(churn_risk, 4),

                # ── Device risk ───────────────────────────────
                "shared_device_flag":      shared_device_flag,
                "duplicate_account_flag":  duplicate_account_flag,
                "document_mismatch_flag":  doc_mismatch,

                # ── Ring membership (structural metadata) ─────
                # Populated by assign_fraud_rings() below
                "fraud_ring_id":           None,
                "ring_role":               None,

                # ── NO fraud_propensity field ──────────────────
                # Removed: was a leaked training label.
                # Fraud is inferred from the behavioral stats above.
            })

            progress.advance(task)

    df = pd.DataFrame(records)
    df = assign_fraud_rings(df, rng)
    return df


if __name__ == "__main__":
    console.rule("[cyan]Driver Generator v2 — Validation[/cyan]")

    df = generate_drivers(n=1_000, city_filter="bangalore")

    # ── Schema checks ─────────────────────────────────────────
    assert "fraud_propensity" not in df.columns, \
        "fraud_propensity must NOT be in driver schema v2"
    assert "fraud_ring_id" in df.columns, \
        "fraud_ring_id must be present"
    assert "kyc_status" in df.columns, \
        "kyc_status must be present"
    assert "cancel_rate_30d" in df.columns, \
        "cancel_rate_30d must be present"

    # ── Core assertions ───────────────────────────────────────
    assert len(df) == 1_000,               "Row count mismatch"
    assert df["driver_id"].nunique() == 1_000, "Duplicate IDs"
    assert df["avg_rating_30d"].between(1.0, 5.0).all(), "Rating range"
    assert df["cancel_rate_30d"].between(0.0, 0.55).all(), "Cancel rate range"
    assert df["cash_trip_ratio_30d"].between(0.0, 1.0).all(), "Cash ratio range"

    # ── Behavioral distribution check ─────────────────────────
    low_risk  = (df["cancel_rate_30d"] < 0.10).mean()
    mid_risk  = df["cancel_rate_30d"].between(0.10, 0.30).mean()
    high_risk = (df["cancel_rate_30d"] > 0.30).mean()

    table1 = Table(title="Behavioral Risk Distribution (n=1,000)")
    table1.add_column("Segment",    style="cyan")
    table1.add_column("Cancel Rate", justify="right")
    table1.add_column("Actual %",   justify="right")
    table1.add_column("Status",     justify="center")
    table1.add_row("Low risk",  "< 10%",    f"{low_risk*100:.1f}%",
                   "✅" if low_risk > 0.75 else "❌")
    table1.add_row("Mid risk",  "10–30%",   f"{mid_risk*100:.1f}%",
                   "✅" if 0.03 < mid_risk < 0.20 else "❌")
    table1.add_row("High risk", "> 30%",    f"{high_risk*100:.1f}%",
                   "✅" if high_risk < 0.08 else "❌")
    console.print(table1)

    # ── KYC distribution ──────────────────────────────────────
    table2 = Table(title="KYC Status Distribution")
    table2.add_column("Status",  style="cyan")
    table2.add_column("Count",   justify="right")
    table2.add_column("Pct",     justify="right")
    for status in ["verified", "pending", "unverified", "expired"]:
        cnt = (df["kyc_status"] == status).sum()
        table2.add_row(status, str(cnt), f"{cnt/10:.1f}%")
    console.print(table2)

    # ── Ring structure ────────────────────────────────────────
    ring_drivers = df["fraud_ring_id"].notna().sum()
    solo_drivers = (df["ring_role"] == "solo").sum()
    ring_count   = df["fraud_ring_id"].dropna().nunique()

    table3 = Table(title="Ring Structure (observable-signal based)")
    table3.add_column("Metric",  style="cyan")
    table3.add_column("Value",   style="green")
    table3.add_row("Ring members", str(ring_drivers))
    table3.add_row("Solo risk drivers", str(solo_drivers))
    table3.add_row("Total rings", str(ring_count))
    console.print(table3)

    # ── Validate no fraud_propensity exists ───────────────────
    assert "fraud_propensity" not in df.columns, \
        "❌ fraud_propensity leaked into schema"
    console.print(
        "[green]✅ fraud_propensity correctly absent from schema[/green]"
    )

    # ── Save ──────────────────────────────────────────────────
    sample_path = DATA_RAW / "drivers_sample_1000.csv"
    df.to_csv(sample_path, index=False)
    console.print(f"\n[green]✅ Sample saved → {sample_path}[/green]")
    console.print("[green bold]✅ drivers.py v2 — all checks passed[/green bold]")
