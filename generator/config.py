"""
Porter Intelligence Platform — Master Configuration
All constants used across the entire project live here.
Import this module first in every other module.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List
from pathlib import Path

# ── Reproducibility ───────────────────────────────────────────
RANDOM_SEED: int = 42
np.random.seed(RANDOM_SEED)

# ── Scale constants ────────────────────────────────────────────
# Reference scale — sized to represent real Porter operations
NUM_DRIVERS:    int = 50_000    # represents 3 lakh real drivers
NUM_CUSTOMERS:  int = 100_000   # represents 20 lakh SME customers
NUM_TRIPS:      int = 500_000   # full generation run

# Evaluation windows used for model training and scored validation
HISTORICAL_DAYS: int = 45       # model trains on this window
LIVE_EVAL_DAYS:  int = 14       # simulated live evaluation window

# ── Cities ────────────────────────────────────────────────────
CITIES: List[str] = [
    "bangalore", "mumbai", "delhi",
    "hyderabad", "chennai", "pune", "kolkata"
]

PRIMARY_CITY: str = "bangalore"  # primary walkthrough city

# ── Vehicle types with Porter's exact pricing ─────────────────
# Source: Porter website public pricing as of 2024
@dataclass
class VehicleConfig:
    """Configuration for a Porter vehicle type."""

    name: str
    base_fare: float        # ₹
    per_km_rate: float      # ₹/km
    capacity_kg: int
    typical_trip_km: tuple  # (min, max)
    fraud_rate_multiplier: float  # some vehicles see more fraud


VEHICLE_TYPES: Dict[str, VehicleConfig] = {
    "two_wheeler": VehicleConfig(
        name="Two Wheeler",
        base_fare=30,
        per_km_rate=8,
        capacity_kg=20,
        typical_trip_km=(1, 15),
        fraud_rate_multiplier=1.4,  # highest fraud — easy fake trips
    ),
    "three_wheeler": VehicleConfig(
        name="Three Wheeler",
        base_fare=80,
        per_km_rate=12,
        capacity_kg=150,
        typical_trip_km=(2, 20),
        fraud_rate_multiplier=1.1,
    ),
    "mini_truck": VehicleConfig(
        name="Mini Truck (Tata Ace)",
        base_fare=200,
        per_km_rate=18,
        capacity_kg=750,
        typical_trip_km=(3, 30),
        fraud_rate_multiplier=1.0,
    ),
    "truck_14ft": VehicleConfig(
        name="14ft Truck",
        base_fare=600,
        per_km_rate=25,
        capacity_kg=4000,
        typical_trip_km=(5, 60),
        fraud_rate_multiplier=0.8,  # less frequent, harder to fake
    ),
    "truck_17ft": VehicleConfig(
        name="17ft Truck",
        base_fare=900,
        per_km_rate=30,
        capacity_kg=7000,
        typical_trip_km=(10, 80),
        fraud_rate_multiplier=0.6,
    ),
}

# Vehicle distribution across Porter's fleet (estimated from public data)
VEHICLE_DISTRIBUTION: Dict[str, float] = {
    "two_wheeler":   0.45,
    "three_wheeler": 0.20,
    "mini_truck":    0.22,
    "truck_14ft":    0.08,
    "truck_17ft":    0.05,
}

# ── Fraud configuration ────────────────────────────────────────
FRAUD_BASE_RATE: float = 0.047   # 4.7% — gig economy industry benchmark

FRAUD_TYPES: List[str] = [
    "fake_trip",          # GPS fraud — driver never moved
    "cash_extortion",     # driver demands cash above metered fare
    "route_deviation",    # detour to inflate distance/fare
    "fake_cancellation",  # accept and instantly cancel to game system
    "duplicate_trip",     # bill same trip twice
    "inflated_distance",  # declare more km than possible
]

# Fraud type distribution (must sum to 1.0)
FRAUD_TYPE_DISTRIBUTION: Dict[str, float] = {
    "fake_trip":          0.28,
    "cash_extortion":     0.22,
    "route_deviation":    0.20,
    "fake_cancellation":  0.15,
    "duplicate_trip":     0.08,
    "inflated_distance":  0.07,
}

# Night hours see 2x fraud rate (10PM-5AM)
NIGHT_FRAUD_MULTIPLIER: float = 2.0
NIGHT_HOURS: tuple = (22, 5)   # 10PM to 5AM

# ── Driver fraud propensity segments ──────────────────────────
FRAUD_PROPENSITY_SEGMENTS: Dict[str, dict] = {
    "honest":     {"pct": 0.91, "range": (0.00, 0.15)},
    "occasional": {"pct": 0.06, "range": (0.15, 0.50)},
    "chronic":    {"pct": 0.03, "range": (0.50, 1.00)},
}

# Additive fraud propensity correlations
FRAUD_PROPENSITY_ADJUSTMENTS: Dict[str, float] = {
    "cash_payment":        +0.30,
    "unverified_status":   +0.20,
    "new_driver":          +0.15,   # joined < 180 days ago
    "low_rating":          +0.25,   # rating < 3.8
    "high_cancellation":   +0.20,   # cancellation_rate > 0.20
}

# ── Performance criteria ──────────────────────────────────────
# These thresholds anchor the scored validation benchmark.
PILOT_SUCCESS_CRITERIA: Dict[str, float] = {
    "min_detection_improvement_pct": 25.0,   # beat baseline by 25%
    "max_false_positive_rate":        0.08,  # 8% ceiling
    "min_net_recoverable_per_trip":   0.50,  # ₹0.50/trip minimum
}

# Cost assumptions for KPI calculation
FALSE_POSITIVE_OPS_COST: float = 200.0   # ₹ cost per false flag raised
ANNUAL_EXTRAP_FACTOR: float = 365 / 14   # evaluation window -> annualised view
CONFIDENCE_HAIRCUT: float = 0.70         # conservative adj for real data

# ── Time patterns ─────────────────────────────────────────────
# Probability weights for trip hour (index 0 = midnight, 23 = 11PM)
WEEKDAY_HOUR_WEIGHTS: List[float] = [
    0.008, 0.005, 0.003, 0.002, 0.003, 0.010,  # midnight-5AM
    0.025, 0.045, 0.075, 0.072, 0.055, 0.058,  # 6AM-11AM
    0.065, 0.060, 0.052, 0.048, 0.045, 0.055,  # noon-5PM
    0.072, 0.080, 0.068, 0.052, 0.038, 0.020,  # 6PM-11PM
]

WEEKEND_HOUR_WEIGHTS: List[float] = [
    0.015, 0.010, 0.008, 0.005, 0.004, 0.008,  # midnight-5AM
    0.015, 0.025, 0.040, 0.052, 0.058, 0.062,  # 6AM-11AM
    0.068, 0.065, 0.060, 0.058, 0.055, 0.060,  # noon-5PM
    0.075, 0.088, 0.080, 0.065, 0.045, 0.028,  # 6PM-11PM
]

# Normalise weights to sum to 1.0
_wday_sum = sum(WEEKDAY_HOUR_WEIGHTS)
_wend_sum = sum(WEEKEND_HOUR_WEIGHTS)
WEEKDAY_HOUR_WEIGHTS = [w / _wday_sum for w in WEEKDAY_HOUR_WEIGHTS]
WEEKEND_HOUR_WEIGHTS = [w / _wend_sum for w in WEEKEND_HOUR_WEIGHTS]

# ── API config ────────────────────────────────────────────────
API_TITLE: str = "Porter Intelligence Platform"
API_VERSION: str = "1.0.0"
API_DESCRIPTION: str = (
    "ML-powered leakage control, fraud detection, and operational "
    "decision support for logistics operations."
)

# ── Paths ─────────────────────────────────────────────────────
ROOT_DIR        = Path(__file__).parent.parent
DATA_RAW        = ROOT_DIR / "data" / "raw"
DATA_MASKED     = ROOT_DIR / "data" / "masked"
DATA_BLIND_TEST = ROOT_DIR / "data" / "blind_test"
MODEL_WEIGHTS   = ROOT_DIR / "model" / "weights"

# Create dirs on import
for _dir in [DATA_RAW, DATA_MASKED, DATA_BLIND_TEST, MODEL_WEIGHTS]:
    _dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    console = Console()

    table = Table(title="Porter Config — Validation Check")
    table.add_column("Config Key", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Cities", str(len(CITIES)))
    table.add_row("Vehicle types", str(len(VEHICLE_TYPES)))
    table.add_row("Fraud types", str(len(FRAUD_TYPES)))
    table.add_row("Fraud base rate", f"{FRAUD_BASE_RATE*100:.1f}%")
    table.add_row("Historical window", f"{HISTORICAL_DAYS} days")
    table.add_row("Live eval window", f"{LIVE_EVAL_DAYS} days")
    table.add_row(
        "Vehicle dist sum",
        f"{sum(VEHICLE_DISTRIBUTION.values()):.2f} ✅"
    )
    table.add_row(
        "Fraud dist sum",
        f"{sum(FRAUD_TYPE_DISTRIBUTION.values()):.2f} ✅"
    )
    table.add_row(
        "Hour weights sum (weekday)",
        f"{sum(WEEKDAY_HOUR_WEIGHTS):.4f} ✅"
    )
    console.print(table)
    console.print("\n[green]✅ config.py — all checks passed[/green]")
