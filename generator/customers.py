"""
Porter Intelligence Platform — SME Customer Profile Generator
Generates 100,000 Porter SME customer profiles.
Business type drives order patterns, vehicle preferences,
and fraud exposure (some businesses more prone to disputes).
"""

import uuid
import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from generator.config import (
    RANDOM_SEED, NUM_CUSTOMERS, CITIES,
    VEHICLE_DISTRIBUTION, DATA_RAW,
)
from generator.cities import CITY_ZONES

console = Console()
rng = np.random.default_rng(RANDOM_SEED + 1)  # offset from drivers.py


# ── Business type configuration ───────────────────────────────

@dataclass
class BusinessTypeConfig:
    """Behavioural profile for a Porter SME business category."""

    name: str
    weight: float                           # sampling probability
    order_value_range: Tuple[float, float]  # ₹ min/max avg order
    monthly_volume_range: Tuple[int, int]   # trips/month min/max
    preferred_vehicles: List[str]           # vehicle type preferences
    peak_hours: List[int]                   # peak booking hours (0-23)
    peak_days: List[int]                    # 0=Mon … 6=Sun
    complaint_rate_base: float              # base complaint probability
    payment_mode_prefs: Dict[str, float]    # upi/credit/cash sampling weights


BUSINESS_CONFIGS: Dict[str, BusinessTypeConfig] = {
    "ecommerce_seller": BusinessTypeConfig(
        name="E-Commerce Seller",
        weight=0.25,
        order_value_range=(800, 5_000),
        monthly_volume_range=(20, 200),
        preferred_vehicles=["two_wheeler", "three_wheeler"],
        peak_hours=[9, 10, 11, 14, 15],
        peak_days=[0, 1, 2],
        complaint_rate_base=0.08,
        payment_mode_prefs={"upi": 0.70, "credit": 0.25, "cash": 0.05},
    ),
    "restaurant": BusinessTypeConfig(
        name="Restaurant / Cloud Kitchen",
        weight=0.20,
        order_value_range=(500, 3_000),
        monthly_volume_range=(30, 150),
        preferred_vehicles=["two_wheeler", "three_wheeler"],
        peak_hours=[10, 11, 12, 13, 18, 19, 20, 21],
        peak_days=[4, 5, 6],
        complaint_rate_base=0.12,  # perishable goods → more disputes
        payment_mode_prefs={"upi": 0.65, "credit": 0.20, "cash": 0.15},
    ),
    "retail_shop": BusinessTypeConfig(
        name="Retail Shop",
        weight=0.18,
        order_value_range=(1_000, 8_000),
        monthly_volume_range=(10, 80),
        preferred_vehicles=["three_wheeler", "mini_truck"],
        peak_hours=[9, 10, 11, 14, 15, 16],
        peak_days=[5, 6],
        complaint_rate_base=0.06,
        payment_mode_prefs={"upi": 0.55, "credit": 0.25, "cash": 0.20},
    ),
    "manufacturer": BusinessTypeConfig(
        name="Manufacturer / Factory",
        weight=0.12,
        order_value_range=(5_000, 50_000),
        monthly_volume_range=(5, 40),
        preferred_vehicles=["mini_truck", "truck_14ft", "truck_17ft"],
        peak_hours=[7, 8, 9, 10],
        peak_days=[0, 1, 2, 3, 4],
        complaint_rate_base=0.04,
        payment_mode_prefs={"credit": 0.60, "upi": 0.35, "cash": 0.05},
    ),
    "pharma_distributor": BusinessTypeConfig(
        name="Pharma Distributor",
        weight=0.08,
        order_value_range=(3_000, 25_000),
        monthly_volume_range=(8, 50),
        preferred_vehicles=["three_wheeler", "mini_truck"],
        peak_hours=[7, 8, 9],
        peak_days=[0, 1, 2, 3, 4],
        complaint_rate_base=0.03,  # regulated industry → careful
        payment_mode_prefs={"credit": 0.70, "upi": 0.28, "cash": 0.02},
    ),
    "textile": BusinessTypeConfig(
        name="Textile / Garment",
        weight=0.07,
        order_value_range=(2_000, 15_000),
        monthly_volume_range=(8, 60),
        preferred_vehicles=["mini_truck", "truck_14ft"],
        peak_hours=[9, 10, 11, 14, 15],
        peak_days=[0, 1, 2, 3, 4],
        complaint_rate_base=0.05,
        payment_mode_prefs={"credit": 0.50, "upi": 0.40, "cash": 0.10},
    ),
    "electronics": BusinessTypeConfig(
        name="Electronics Dealer",
        weight=0.05,
        order_value_range=(5_000, 40_000),
        monthly_volume_range=(3, 30),
        preferred_vehicles=["mini_truck", "truck_14ft"],
        peak_hours=[10, 11, 14, 15, 16],
        peak_days=[0, 1, 2, 3, 4],
        complaint_rate_base=0.07,  # high-value goods → more disputes
        payment_mode_prefs={"credit": 0.65, "upi": 0.30, "cash": 0.05},
    ),
    "other": BusinessTypeConfig(
        name="Other Business",
        weight=0.05,
        order_value_range=(800, 10_000),
        monthly_volume_range=(1, 40),
        preferred_vehicles=["two_wheeler", "three_wheeler", "mini_truck"],
        peak_hours=[9, 10, 11, 14, 15, 16],
        peak_days=[0, 1, 2, 3, 4, 5],
        complaint_rate_base=0.06,
        payment_mode_prefs={"upi": 0.60, "credit": 0.25, "cash": 0.15},
    ),
}

assert abs(sum(c.weight for c in BUSINESS_CONFIGS.values()) - 1.0) < 0.001, \
    "Business type weights must sum to 1.0"

# ── Business name generation ──────────────────────────────────

_BUSINESS_NAME_TEMPLATES: Dict[str, List[str]] = {
    "ecommerce_seller": [
        "{last} Traders", "{last} Enterprises", "Quick{last} Commerce",
        "{last} Online Store", "ShopFast {last}", "{last} E-Retail",
    ],
    "restaurant": [
        "Hotel {last}", "{last} Kitchen", "{last} Dhaba",
        "{last} Tiffins", "Sri {last} Foods", "{last} Cloud Kitchen",
    ],
    "retail_shop": [
        "{last} General Stores", "{last} Provisions",
        "New {last} Traders", "{last} & Sons", "{last} Super Store",
    ],
    "manufacturer": [
        "{last} Industries", "{last} Manufacturing",
        "{last} Fabricators", "{last} Works", "Shree {last} Mfg",
    ],
    "pharma_distributor": [
        "{last} Pharma", "{last} Medical Distributors",
        "{last} Healthcare", "Life{last} Pharma",
    ],
    "textile": [
        "{last} Textiles", "{last} Garments", "{last} Fabrics",
        "New {last} Cloth House", "{last} Fashion",
    ],
    "electronics": [
        "{last} Electronics", "{last} Digital", "{last} Tech Hub",
        "New {last} Electronics",
    ],
    "other": [
        "{last} Trading Co.", "{last} Services",
        "{last} Logistics", "{last} Supplies",
    ],
}

_BUSINESS_LAST_NAMES: List[str] = [
    "Kumar", "Singh", "Sharma", "Patel", "Gupta", "Rao",
    "Reddy", "Nair", "Mehta", "Shah", "Jain", "Agarwal",
    "Bansal", "Garg", "Shetty", "Gowda", "Pillai", "Menon",
    "Iyer", "Patil", "Kulkarni", "Hegde", "Bhat", "Desai",
]


def generate_business_name(
    business_type: str,
    rng: np.random.Generator,
) -> str:
    """Generate a realistic Indian SME business name for the given type."""
    templates = _BUSINESS_NAME_TEMPLATES.get(
        business_type, _BUSINESS_NAME_TEMPLATES["other"]
    )
    template = str(rng.choice(templates))
    last = str(rng.choice(_BUSINESS_LAST_NAMES))
    return template.format(last=last)


# ── Main generator ────────────────────────────────────────────

def generate_customers(
    n: int = NUM_CUSTOMERS,
    city_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generate n Porter SME customer profiles as a DataFrame.

    Args:
        n:           Number of customer profiles to generate.
        city_filter: Restrict all records to one city if set.

    Returns:
        DataFrame with all customer fields.
    """
    today    = datetime.now().date()
    biz_types   = list(BUSINESS_CONFIGS.keys())
    biz_weights = [BUSINESS_CONFIGS[b].weight for b in biz_types]

    records: List[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating customer profiles...", total=n)

        for _ in range(n):
            # ── Identity ──────────────────────────────────────
            customer_id = str(uuid.uuid4())

            # ── Business type ─────────────────────────────────
            biz_type      = str(rng.choice(biz_types, p=biz_weights))
            cfg           = BUSINESS_CONFIGS[biz_type]
            business_name = generate_business_name(biz_type, rng)

            # ── City and zone ─────────────────────────────────
            city     = city_filter if city_filter else str(
                rng.choice(["bangalore", "mumbai", "delhi"])
            )
            zone_ids = CITY_ZONES.get(city, [])
            zone_id  = str(rng.choice(zone_ids)) if zone_ids else "unknown"

            # ── Account age ───────────────────────────────────
            account_age_days = int(rng.integers(30, 1800))
            joining_date     = today - timedelta(days=account_age_days)

            # ── Order patterns ────────────────────────────────
            vol_min, vol_max = cfg.monthly_volume_range
            vol_mean = (vol_min + vol_max) / 2.0
            monthly_order_volume = int(np.clip(
                rng.lognormal(np.log(max(vol_mean, 1)), 0.5),
                vol_min, vol_max,
            ))

            val_min, val_max    = cfg.order_value_range
            avg_order_value_inr = float(rng.uniform(val_min, val_max))

            # ── Vehicle preference ────────────────────────────
            preferred_vehicle_type = str(rng.choice(cfg.preferred_vehicles))

            # ── Payment mode ──────────────────────────────────
            payment_modes = list(cfg.payment_mode_prefs.keys())
            payment_probs = list(cfg.payment_mode_prefs.values())
            payment_mode  = str(rng.choice(payment_modes, p=payment_probs))

            # ── Complaint rate ────────────────────────────────
            complaint_rate = float(np.clip(
                rng.beta(1.5, 10.0) * cfg.complaint_rate_base * 10,
                0.0, 0.30,
            ))

            # ── Churn risk ────────────────────────────────────
            churn = 0.10
            if account_age_days < 90:
                churn += 0.25
            if monthly_order_volume < 5:
                churn += 0.15
            if complaint_rate > 0.15:
                churn += 0.20
            churn_risk_score = float(np.clip(
                churn + rng.normal(0, 0.05), 0.0, 1.0
            ))

            # ── Lifetime value estimate ───────────────────────
            account_months = max(1, account_age_days / 30)
            ltv_inr = float(
                monthly_order_volume
                * avg_order_value_inr
                * account_months
                * (1 - churn_risk_score)
                * 0.85  # Porter's ~15% margin on customer spend
            )

            records.append({
                "customer_id":            customer_id,
                "business_name":          business_name,
                "business_type":          biz_type,
                "city":                   city,
                "zone_id":                zone_id,
                "account_age_days":       account_age_days,
                "joining_date":           str(joining_date),
                "monthly_order_volume":   monthly_order_volume,
                "avg_order_value_inr":    round(avg_order_value_inr, 2),
                "preferred_vehicle_type": preferred_vehicle_type,
                "payment_mode":           payment_mode,
                "complaint_rate":         round(complaint_rate, 4),
                "churn_risk_score":       round(churn_risk_score, 4),
                "ltv_inr":                round(ltv_inr, 2),
                "peak_hours":             "|".join(map(str, cfg.peak_hours)),
                "peak_days":              "|".join(map(str, cfg.peak_days)),
            })

            progress.advance(task)

    return pd.DataFrame(records)


if __name__ == "__main__":
    console.rule("[cyan]Customer Generator — Validation[/cyan]")

    df = generate_customers(n=1_000, city_filter="bangalore")

    # ── Assertions ────────────────────────────────────────────
    assert len(df) == 1_000,                                  "Row count mismatch"
    assert df["customer_id"].nunique() == 1_000,              "Duplicate IDs"
    assert df["monthly_order_volume"].gt(0).all(),            "Zero orders found"
    assert df["avg_order_value_inr"].between(500, 55_000).all(), \
        "Order value out of range"
    assert df["complaint_rate"].between(0, 0.30).all(),       "Complaint rate out of range"
    assert df["churn_risk_score"].between(0, 1.0).all(),      "Churn score out of range"

    # ── Business type distribution ────────────────────────────
    dist = df["business_type"].value_counts(normalize=True)
    table1 = Table(title="Business Type Distribution (n=1,000)")
    table1.add_column("Business Type", style="cyan")
    table1.add_column("Expected",      justify="right")
    table1.add_column("Actual",        justify="right")
    table1.add_column("Status",        justify="center")
    for btype, cfg in BUSINESS_CONFIGS.items():
        actual_pct = dist.get(btype, 0) * 100
        exp_pct    = cfg.weight * 100
        ok = abs(actual_pct - exp_pct) < (exp_pct * 0.5 + 3)
        table1.add_row(
            cfg.name,
            f"{exp_pct:.0f}%",
            f"{actual_pct:.1f}%",
            "✅" if ok else "⚠️",
        )
    console.print(table1)

    # ── Order value by business type ──────────────────────────
    table2 = Table(title="Avg Order Value by Business Type")
    table2.add_column("Type",  style="cyan")
    table2.add_column("Avg ₹",  justify="right", style="green")
    table2.add_column("Min ₹",  justify="right")
    table2.add_column("Max ₹",  justify="right")
    for btype in BUSINESS_CONFIGS:
        subset = df[df["business_type"] == btype]["avg_order_value_inr"]
        if len(subset) > 0:
            table2.add_row(
                btype,
                f"₹{subset.mean():,.0f}",
                f"₹{subset.min():,.0f}",
                f"₹{subset.max():,.0f}",
            )
    console.print(table2)

    # ── Complaint rate correlation check ──────────────────────
    restaurant_complaint = df[
        df["business_type"] == "restaurant"
    ]["complaint_rate"].mean()
    pharma_complaint = df[
        df["business_type"] == "pharma_distributor"
    ]["complaint_rate"].mean()
    assert restaurant_complaint > pharma_complaint, (
        f"Restaurants ({restaurant_complaint:.4f}) must have higher "
        f"complaint rate than pharma ({pharma_complaint:.4f})"
    )
    console.print(
        f"[green]✅ Restaurant complaint ({restaurant_complaint:.4f}) "
        f"> Pharma ({pharma_complaint:.4f})[/green]"
    )

    # ── LTV validation ────────────────────────────────────────
    assert df["ltv_inr"].gt(0).all(), "LTV must be positive"
    high_ltv = df.nlargest(5, "ltv_inr")[
        ["business_name", "business_type", "ltv_inr"]
    ]
    console.print("\n[cyan]Top 5 customers by LTV:[/cyan]")
    for _, row in high_ltv.iterrows():
        console.print(
            f"  {row['business_name']} ({row['business_type']}): "
            f"₹{row['ltv_inr']:,.0f}"
        )

    # ── Save sample ───────────────────────────────────────────
    out = DATA_RAW / "customers_sample_1000.csv"
    df.to_csv(out, index=False)
    console.print(f"\n[green]✅ Sample saved to {out}[/green]")
    console.print("[green bold]✅ customers.py — all checks passed[/green bold]")
