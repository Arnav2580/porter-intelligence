"""
Porter Intelligence Platform — Driver Profile Generator
Generates 50,000 synthetic Porter driver profiles.
Fraud propensity is the core training signal — encode it carefully.
"""

import uuid
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
from faker import Faker
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from generator.config import (
    RANDOM_SEED, NUM_DRIVERS, CITIES, VEHICLE_TYPES,
    VEHICLE_DISTRIBUTION, FRAUD_PROPENSITY_SEGMENTS,
    FRAUD_PROPENSITY_ADJUSTMENTS, DATA_RAW,
)
from generator.cities import ZONES, CITY_ZONES

console = Console()

# ── Faker setup ───────────────────────────────────────────────
fake = Faker("en_IN")
Faker.seed(RANDOM_SEED)
rng = np.random.default_rng(RANDOM_SEED)

# ── Indian name pool ──────────────────────────────────────────
INDIAN_FIRST_NAMES: List[str] = [
    "Ravi", "Suresh", "Ramesh", "Mahesh", "Ganesh", "Rajesh",
    "Dinesh", "Naresh", "Prakash", "Lokesh", "Umesh", "Rakesh",
    "Vijay", "Sanjay", "Ajay", "Manoj", "Anil", "Sunil",
    "Mukesh", "Deepak", "Vivek", "Ashok", "Vinod",
    "Mohan", "Rohan", "Sohan", "Krishan", "Kishan", "Harish",
    "Girish", "Paresh", "Nilesh", "Ritesh", "Hitesh", "Jitesh",
    "Satish", "Manish", "Danish", "Rupesh", "Brijesh", "Yogesh",
    "Santosh", "Ramakrishna", "Venkatesh", "Shivakumar", "Basavaraj",
    "Mohammed", "Abdul", "Ibrahim", "Salman", "Imran", "Wasim",
    "Arjun", "Kiran", "Pavan", "Naveen", "Praveen", "Sreeram",
    "Thirumalai", "Selvam", "Murugan", "Senthil", "Karthi",
    "Babu", "Thiru", "Raja", "Rajan", "Mani", "Kumar",
]

INDIAN_LAST_NAMES: List[str] = [
    "Kumar", "Singh", "Sharma", "Yadav", "Gupta", "Mishra",
    "Patel", "Shah", "Mehta", "Desai", "Joshi", "Nair",
    "Pillai", "Menon", "Reddy", "Naidu", "Rao", "Iyer",
    "Iyengar", "Bhat", "Shetty", "Gowda", "Hegde", "Patil",
    "Kulkarni", "Jain", "Agarwal", "Bansal", "Garg", "Mittal",
    "Khan", "Ansari", "Shaikh", "Siddiqui", "Qureshi",
    "Mukherjee", "Chatterjee", "Banerjee", "Das", "Ghosh",
    "Verma", "Tiwari", "Pandey", "Dubey", "Shukla", "Tripathi",
    "Nayak", "Swamy", "Murthy", "Raju", "Babu", "Prasad",
]


def generate_indian_phone(rng: np.random.Generator) -> str:
    """Generate a realistic Indian mobile number in +91XXXXXXXXXX format."""
    first_digit = rng.choice([6, 7, 8, 9])
    remaining = rng.integers(100_000_000, 999_999_999)
    return f"+91{first_digit}{remaining}"


def generate_indian_name(rng: np.random.Generator) -> str:
    """Generate a realistic Indian driver name from the curated pool."""
    first = rng.choice(INDIAN_FIRST_NAMES)
    last = rng.choice(INDIAN_LAST_NAMES)
    return f"{first} {last}"


def sample_base_fraud_propensity(rng: np.random.Generator) -> float:
    """
    Sample a base fraud propensity from the three-segment distribution.

    Segments mirror real gig-economy driver behaviour:
      91% honest     → beta(1.5, 12)  scaled to [0.00, 0.15]
      6%  occasional → beta(2.0, 3.0) scaled to [0.15, 0.50]
      3%  chronic    → beta(2.5, 1.5) scaled to [0.50, 1.00]
    """
    draw = rng.random()

    if draw < FRAUD_PROPENSITY_SEGMENTS["honest"]["pct"]:
        raw = rng.beta(1.5, 12.0)
        return float(raw * 0.15)

    elif draw < (FRAUD_PROPENSITY_SEGMENTS["honest"]["pct"]
                 + FRAUD_PROPENSITY_SEGMENTS["occasional"]["pct"]):
        raw = rng.beta(2.0, 3.0)
        return float(0.15 + raw * 0.35)

    else:
        raw = rng.beta(2.5, 1.5)
        return float(0.50 + raw * 0.50)


def compute_fraud_propensity(
    bank_account_type: str,
    verification_status: str,
    account_age_days: int,
    rating: float,
    cancellation_rate: float,
    base_propensity: float,
) -> float:
    """
    Apply risk-factor multipliers to base propensity score.

    Risk factors compound on existing propensity — a low-risk honest driver
    sees minimal absolute shift; a borderline driver shifts meaningfully.
    This preserves the 91/6/3 segment shape while encoding real correlations.

    The config adjustment values are used as additive multiplier components
    (e.g. cash_payment=0.30 → multiply by 1.30), not as raw additive shifts,
    so that the honest segment's narrow range [0, 0.15] is not blown out.

    CRITICAL: This field is a training label ONLY.
    It must NEVER appear in any API response or exported CSV
    intended for external sharing.

    Returns float clamped to [0.0, 1.0].
    """
    risk_multiplier = 1.0

    if bank_account_type == "cash":
        risk_multiplier += FRAUD_PROPENSITY_ADJUSTMENTS["cash_payment"]

    if verification_status == "unverified":
        risk_multiplier += FRAUD_PROPENSITY_ADJUSTMENTS["unverified_status"]

    if account_age_days < 180:
        risk_multiplier += FRAUD_PROPENSITY_ADJUSTMENTS["new_driver"]

    if rating < 3.8:
        risk_multiplier += FRAUD_PROPENSITY_ADJUSTMENTS["low_rating"]

    if cancellation_rate > 0.20:
        risk_multiplier += FRAUD_PROPENSITY_ADJUSTMENTS["high_cancellation"]

    return float(np.clip(base_propensity * risk_multiplier, 0.0, 1.0))


def assign_driver_zone(
    city: str,
    fraud_propensity: float,
    rng: np.random.Generator,
) -> str:
    """
    Assign a home zone to a driver.

    Chronic fraudsters (propensity > 0.50) are 3x more likely
    to operate in high-density commercial zones where trip volume
    hides fake trips more easily.
    """
    zone_ids = CITY_ZONES.get(city, [])
    if not zone_ids:
        return "unknown"

    if fraud_propensity <= 0.50:
        return str(rng.choice(zone_ids))

    # Chronic fraudsters — weight toward high fraud_rate_adj zones
    fraud_adjs = []
    for zid in zone_ids:
        zone = ZONES[zid]
        weight = 1.0 + (zone.fraud_rate_adj * 200)
        fraud_adjs.append(weight)

    total = sum(fraud_adjs)
    probs = [w / total for w in fraud_adjs]

    return str(rng.choice(zone_ids, p=probs))


def assign_fraud_rings(
    df: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Assign fraud ring membership to chronic fraudsters.

    Ring structure mirrors real gig fraud networks:
    - ~60% of chronic fraudsters belong to a ring
    - Ring size: 3-6 drivers
    - Rings are zone-specific (drivers in same zone)
    - ~40% of chronic fraudsters are solo operators

    fraud_ring_id: string like "RING_BLR_001" or None
    ring_role: "leader" | "member" | "solo" | None
    """
    df["fraud_ring_id"] = None
    df["ring_role"] = None

    chronic_mask = df["fraud_propensity"] > 0.50
    chronic_drivers = df[chronic_mask].copy()

    if len(chronic_drivers) == 0:
        return df

    # 60% join rings, 40% solo
    join_ring = rng.random(len(chronic_drivers)) < 0.60
    ring_candidates = chronic_drivers[join_ring]

    ring_counter = 1
    processed_ids: set = set()

    for (city, zone), group in ring_candidates.groupby(["city", "zone_id"]):
        group_ids = list(group.index)
        rng.shuffle(group_ids)

        i = 0
        while i < len(group_ids):
            ring_size = int(rng.integers(3, 7))
            ring_members = group_ids[i:i + ring_size]

            if len(ring_members) < 2:
                for idx in ring_members:
                    df.at[idx, "ring_role"] = "solo"
                i += ring_size
                continue

            ring_id = f"RING_{city[:3].upper()}_{ring_counter:03d}"
            ring_counter += 1

            leader_idx = max(
                ring_members,
                key=lambda idx: df.at[idx, "fraud_propensity"],
            )

            for idx in ring_members:
                df.at[idx, "fraud_ring_id"] = ring_id
                df.at[idx, "ring_role"] = (
                    "leader" if idx == leader_idx else "member"
                )
                processed_ids.add(idx)

            i += ring_size

    # Mark remaining chronic fraudsters as solo
    for idx in chronic_drivers.index:
        if idx not in processed_ids:
            df.at[idx, "ring_role"] = "solo"

    return df


def generate_drivers(
    n: int = NUM_DRIVERS,
    city_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generate n Porter driver profiles as a DataFrame.

    Args:
        n:           Number of driver profiles to generate.
        city_filter: If set, all drivers belong to this city.
                     If None, distributed across bangalore/mumbai/delhi.

    Returns:
        DataFrame with all driver fields. fraud_propensity is included
        for internal model training — never expose externally.
    """
    today = datetime.now().date()
    records = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating driver profiles...", total=n)

        for _ in range(n):
            # ── Identity ──────────────────────────────────────
            driver_id = str(uuid.uuid4())
            name      = generate_indian_name(rng)
            phone     = generate_indian_phone(rng)

            # ── City ──────────────────────────────────────────
            city = city_filter if city_filter else rng.choice(CITIES[:3])

            # ── Vehicle type ──────────────────────────────────
            vehicle_type = str(rng.choice(
                list(VEHICLE_DISTRIBUTION.keys()),
                p=list(VEHICLE_DISTRIBUTION.values()),
            ))

            # ── Joining date ──────────────────────────────────
            if rng.random() < 0.60:
                days_ago = int(rng.integers(365 * 2, 365 * 6))   # experienced
            else:
                days_ago = int(rng.integers(30, 365 * 2))         # newer
            joining_date     = today - timedelta(days=days_ago)
            account_age_days = days_ago

            # ── Verification and payment ──────────────────────
            verification_status = str(rng.choice(
                ["verified", "unverified", "pending"],
                p=[0.75, 0.15, 0.10],
            ))
            bank_account_type = str(rng.choice(
                ["upi", "bank", "cash"],
                p=[0.65, 0.25, 0.10],
            ))

            # ── Rating and cancellation ───────────────────────
            rating            = float(np.clip(rng.normal(4.2, 0.4), 1.0, 5.0))
            cancellation_rate = float(np.clip(rng.beta(1.5, 8.0) * 0.35, 0.0, 0.35))

            # ── Fraud propensity (computed early for zone bias) ──
            base_propensity  = sample_base_fraud_propensity(rng)
            fraud_propensity = compute_fraud_propensity(
                bank_account_type   = bank_account_type,
                verification_status = verification_status,
                account_age_days    = account_age_days,
                rating              = rating,
                cancellation_rate   = cancellation_rate,
                base_propensity     = base_propensity,
            )

            # ── Zone assignment (chronic fraudsters → commercial) ──
            zone_id = assign_driver_zone(city, fraud_propensity, rng)

            # ── Trip and earnings history ─────────────────────
            base_trips            = account_age_days * rng.normal(2.5, 0.8)
            total_trips_lifetime  = max(0, int(base_trips))

            veh             = VEHICLE_TYPES[vehicle_type]
            avg_fare        = veh.base_fare + veh.per_km_rate * 8
            trips_per_month = max(1, int(total_trips_lifetime / max(1, account_age_days / 30)))
            # Porter takes ~20% commission; add earnings variance
            monthly_earnings_avg = float(
                trips_per_month * avg_fare * 0.80 * rng.normal(1.0, 0.15)
            )

            # ── Activity and churn ────────────────────────────
            is_active = bool(rng.random() < 0.95)

            churn_base = 0.10
            if account_age_days < 90:
                churn_base += 0.20
            if monthly_earnings_avg < 8_000:
                churn_base += 0.15
            if rating < 3.8:
                churn_base += 0.20
            churn_risk = float(np.clip(churn_base + rng.normal(0, 0.05), 0.0, 1.0))

            records.append({
                "driver_id":             driver_id,
                "name":                  name,
                "phone":                 phone,
                "city":                  city,
                "zone_id":               zone_id,
                "vehicle_type":          vehicle_type,
                "joining_date":          str(joining_date),
                "account_age_days":      account_age_days,
                "verification_status":   verification_status,
                "bank_account_type":     bank_account_type,
                "rating":                round(rating, 2),
                "cancellation_rate":     round(cancellation_rate, 4),
                "total_trips_lifetime":  total_trips_lifetime,
                "monthly_earnings_avg":  round(monthly_earnings_avg, 2),
                "is_active":             is_active,
                "churn_risk":            round(churn_risk, 4),
                "fraud_propensity":      round(fraud_propensity, 4),
                # ⚠️  INTERNAL LABEL — never expose via API
            })

            progress.advance(task)

    df = pd.DataFrame(records)
    df = assign_fraud_rings(df, rng)
    return df


if __name__ == "__main__":
    console.rule("[cyan]Driver Generator — Validation[/cyan]")

    df = generate_drivers(n=1_000, city_filter="bangalore")

    # ── Assertion checks ──────────────────────────────────────
    assert len(df) == 1_000,                              "Row count mismatch"
    assert df["driver_id"].nunique() == 1_000,            "Duplicate IDs found"
    assert df["phone"].str.match(r"^\+91[6-9]\d{9}$").all(), \
        "Invalid phone numbers"
    assert df["rating"].between(1.0, 5.0).all(),          "Rating out of range"
    assert df["cancellation_rate"].between(0.0, 0.35).all(), \
        "Cancellation rate out of range"
    assert df["fraud_propensity"].between(0.0, 1.0).all(), \
        "Fraud propensity out of range"

    # ── Fraud propensity distribution ─────────────────────────
    honest     = (df["fraud_propensity"] <= 0.15).mean()
    occasional = df["fraud_propensity"].between(0.15, 0.50).mean()
    chronic    = (df["fraud_propensity"] >  0.50).mean()

    table1 = Table(title="Fraud Propensity Distribution (n=1,000)")
    table1.add_column("Segment",  style="cyan")
    table1.add_column("Expected", justify="right")
    table1.add_column("Actual",   justify="right")
    table1.add_column("Status",   justify="center")
    table1.add_row("Honest (≤0.15)",       "~91%",
                   f"{honest * 100:.1f}%",
                   "✅" if 85 < honest * 100 < 97 else "❌")
    table1.add_row("Occasional (0.15-0.5)", "~6%",
                   f"{occasional * 100:.1f}%",
                   "✅" if 2 < occasional * 100 < 12 else "❌")
    table1.add_row("Chronic (>0.50)",       "~3%",
                   f"{chronic * 100:.1f}%",
                   "✅" if 0.5 < chronic * 100 < 8 else "❌")
    console.print(table1)

    # ── Correlation checks ────────────────────────────────────
    cash_fraud    = df[df["bank_account_type"] == "cash"]["fraud_propensity"].mean()
    upi_fraud     = df[df["bank_account_type"] == "upi"]["fraud_propensity"].mean()
    assert cash_fraud > upi_fraud, \
        f"Cash fraud {cash_fraud:.4f} must exceed UPI fraud {upi_fraud:.4f}"

    unverif_fraud  = df[df["verification_status"] == "unverified"]["fraud_propensity"].mean()
    verified_fraud = df[df["verification_status"] == "verified"]["fraud_propensity"].mean()
    assert unverif_fraud > verified_fraud, \
        "Unverified drivers must be riskier than verified"

    # ── Summary stats ─────────────────────────────────────────
    table2 = Table(title="Driver Profile Summary (n=1,000)")
    table2.add_column("Metric", style="cyan")
    table2.add_column("Value",  style="green")
    table2.add_row("Avg rating",           f"{df['rating'].mean():.2f}")
    table2.add_row("Avg cancellation",     f"{df['cancellation_rate'].mean():.3f}")
    table2.add_row("Avg fraud propensity", f"{df['fraud_propensity'].mean():.4f}")
    table2.add_row("Cash pref fraud avg",  f"{cash_fraud:.4f}")
    table2.add_row("UPI pref fraud avg",   f"{upi_fraud:.4f}")
    table2.add_row("Unverified fraud avg", f"{unverif_fraud:.4f}")
    table2.add_row("Verified fraud avg",   f"{verified_fraud:.4f}")
    table2.add_row("Active drivers",
                   f"{df['is_active'].sum()} ({df['is_active'].mean() * 100:.1f}%)")
    table2.add_row("Unique zones",         str(df["zone_id"].nunique()))
    console.print(table2)

    # ── Fix 1 validation — zone bias for chronic fraudsters ────
    chronic_drivers = df[df["fraud_propensity"] > 0.50]
    if len(chronic_drivers) > 5:
        chronic_zones = chronic_drivers["zone_id"].value_counts()
        honest_drivers = df[df["fraud_propensity"] <= 0.15]
        honest_zones = honest_drivers["zone_id"].value_counts()

        top_chronic_zone = chronic_zones.index[0]
        top_honest_zone  = honest_zones.index[0]

        console.print(f"\n[cyan]Zone bias check:[/cyan]")
        console.print(f"  Top chronic zone: {top_chronic_zone} "
                      f"(fraud_adj: "
                      f"{ZONES[top_chronic_zone].fraud_rate_adj:.3f})")
        console.print(f"  Top honest zone:  {top_honest_zone} "
                      f"(fraud_adj: "
                      f"{ZONES[top_honest_zone].fraud_rate_adj:.3f})")

    # ── Fix 2 validation — fraud rings ────────────────────────
    ring_table = Table(title="Fraud Ring Structure")
    ring_table.add_column("Metric", style="cyan")
    ring_table.add_column("Value",  style="green")

    chronic_total = (df["fraud_propensity"] > 0.50).sum()
    ring_members  = df["fraud_ring_id"].notna().sum()
    solo_count    = (df["ring_role"] == "solo").sum()
    ring_count    = df["fraud_ring_id"].dropna().nunique()

    ring_table.add_row("Chronic fraudsters", str(chronic_total))
    ring_table.add_row("In rings",           str(ring_members))
    ring_table.add_row("Solo operators",      str(solo_count))
    ring_table.add_row("Total rings",         str(ring_count))

    if chronic_total > 0:
        ring_pct = ring_members / chronic_total * 100
        ring_table.add_row(
            "Ring participation rate",
            f"{ring_pct:.1f}% (target ~60%)",
        )

    console.print(ring_table)

    if ring_count > 0:
        # Each ring must have exactly one leader
        leaders = df[df["ring_role"] == "leader"]
        ring_leader_counts = leaders["fraud_ring_id"].value_counts()
        assert (ring_leader_counts == 1).all(), \
            "Each ring must have exactly one leader"
        console.print("[green]✅ Ring leadership structure valid[/green]")

        # Ring members must share the same zone
        for ring_id in df[df["fraud_ring_id"].notna()]["fraud_ring_id"].unique():
            ring = df[df["fraud_ring_id"] == ring_id]
            assert ring["zone_id"].nunique() == 1, \
                f"Ring {ring_id} spans multiple zones — invalid"
        console.print("[green]✅ All rings are zone-contained[/green]")

    # ── Save sample ───────────────────────────────────────────
    sample_path = DATA_RAW / "drivers_sample_1000.csv"
    df.to_csv(sample_path, index=False)
    console.print(f"\n[green]✅ Sample saved to {sample_path}[/green]")
    console.print("[green bold]✅ drivers.py — all checks passed[/green bold]")
