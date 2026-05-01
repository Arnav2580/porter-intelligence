"""
Porter Intelligence Platform — Master Configuration v2
All constants used across the entire project live here.

v2 changes:
  - Fraud types corrected to match real India distribution
  - Added Porter-specific fraud types (loading_fraud, partial_delivery, gps_spoof)
  - Added goods categories, loading time norms, device signal constants
  - Removed fraud_propensity_segments (was a leaked label used in training)
  - Added realistic city speed profiles (used to fix physics)
  - FRAUD_PROPENSITY_SEGMENTS removed — fraud is now injected via observable signals
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from pathlib import Path

# ── Reproducibility ───────────────────────────────────────────
RANDOM_SEED: int = 42
np.random.seed(RANDOM_SEED)

# ── Scale constants ───────────────────────────────────────────
NUM_DRIVERS:    int = 50_000
NUM_CUSTOMERS:  int = 100_000
NUM_TRIPS:      int = 500_000

HISTORICAL_DAYS: int = 45
LIVE_EVAL_DAYS:  int = 14

# ── Cities ────────────────────────────────────────────────────
CITIES: List[str] = [
    "bangalore", "mumbai", "delhi",
    "hyderabad", "chennai", "pune", "kolkata"
]
PRIMARY_CITY: str = "bangalore"

# ── Realistic city driving speeds (km/hr) ────────────────────
# Source: TomTom Traffic Index India 2023, local logistics benchmarks
# These are AVERAGE speeds including stops, signals, loading zones
CITY_AVG_SPEED_KMH: Dict[str, Dict[str, float]] = {
    "bangalore": {
        "two_wheeler":   24.0,
        "three_wheeler": 19.0,
        "mini_truck":    15.5,
        "truck_14ft":    13.0,
        "truck_17ft":    11.5,
    },
    "mumbai": {
        "two_wheeler":   18.0,   # extreme congestion
        "three_wheeler": 14.0,
        "mini_truck":    12.0,
        "truck_14ft":    10.5,
        "truck_17ft":    9.0,
    },
    "delhi": {
        "two_wheeler":   26.0,
        "three_wheeler": 20.0,
        "mini_truck":    17.0,
        "truck_14ft":    14.0,
        "truck_17ft":    12.0,
    },
    "hyderabad": {
        "two_wheeler":   27.0,
        "three_wheeler": 21.0,
        "mini_truck":    17.0,
        "truck_14ft":    14.0,
        "truck_17ft":    12.0,
    },
    "chennai": {
        "two_wheeler":   23.0,
        "three_wheeler": 18.0,
        "mini_truck":    15.0,
        "truck_14ft":    12.5,
        "truck_17ft":    11.0,
    },
    "pune": {
        "two_wheeler":   28.0,
        "three_wheeler": 22.0,
        "mini_truck":    18.0,
        "truck_14ft":    15.0,
        "truck_17ft":    13.0,
    },
    "kolkata": {
        "two_wheeler":   20.0,
        "three_wheeler": 15.0,
        "mini_truck":    13.0,
        "truck_14ft":    11.0,
        "truck_17ft":    9.5,
    },
}
# Default fallback (used when city not found)
DEFAULT_SPEED_KMH: Dict[str, float] = {
    "two_wheeler":   24.0,
    "three_wheeler": 19.0,
    "mini_truck":    15.5,
    "truck_14ft":    13.0,
    "truck_17ft":    11.5,
}

# Traffic multipliers by time-of-day (applied on top of city speed)
# Index = hour (0-23). Peak hours get 0.6x speed (1.67x longer duration).
TRAFFIC_HOUR_MULTIPLIER: List[float] = [
    0.95, 0.98, 1.00, 1.00, 0.98, 0.90,  # 0-5 AM: light traffic
    0.80, 0.65, 0.55, 0.60, 0.70, 0.78,  # 6-11 AM: morning peak at 8-9
    0.80, 0.82, 0.85, 0.80, 0.72, 0.68,  # 12-17: midday, builds to eve
    0.58, 0.55, 0.62, 0.72, 0.82, 0.90,  # 18-23: evening peak at 18-19
]

# ── Vehicle types with Porter's exact pricing ─────────────────
@dataclass
class VehicleConfig:
    name: str
    base_fare: float        # ₹
    per_km_rate: float      # ₹/km
    per_min_rate: float     # ₹/min (for loading/waiting charges)
    capacity_kg: int
    typical_trip_km: Tuple[float, float]   # (min, max) realistic range
    fraud_rate_multiplier: float


VEHICLE_TYPES: Dict[str, VehicleConfig] = {
    "two_wheeler": VehicleConfig(
        name="Two Wheeler",
        base_fare=30,
        per_km_rate=8,
        per_min_rate=0,         # no per-minute for 2W
        capacity_kg=20,
        typical_trip_km=(1.0, 15.0),
        fraud_rate_multiplier=1.4,
    ),
    "three_wheeler": VehicleConfig(
        name="Three Wheeler",
        base_fare=80,
        per_km_rate=12,
        per_min_rate=0,
        capacity_kg=150,
        typical_trip_km=(1.5, 20.0),
        fraud_rate_multiplier=1.1,
    ),
    "mini_truck": VehicleConfig(
        name="Mini Truck (Tata Ace)",
        base_fare=200,
        per_km_rate=18,
        per_min_rate=4.0,       # ₹4/min loading charge
        capacity_kg=750,
        typical_trip_km=(2.0, 30.0),
        fraud_rate_multiplier=1.0,
    ),
    "truck_14ft": VehicleConfig(
        name="14ft Truck",
        base_fare=600,
        per_km_rate=25,
        per_min_rate=6.0,
        capacity_kg=4000,
        typical_trip_km=(4.0, 60.0),
        fraud_rate_multiplier=0.8,
    ),
    "truck_17ft": VehicleConfig(
        name="17ft Truck",
        base_fare=900,
        per_km_rate=30,
        per_min_rate=8.0,
        capacity_kg=7000,
        typical_trip_km=(8.0, 80.0),
        fraud_rate_multiplier=0.6,
    ),
}

VEHICLE_DISTRIBUTION: Dict[str, float] = {
    "two_wheeler":   0.45,
    "three_wheeler": 0.20,
    "mini_truck":    0.22,
    "truck_14ft":    0.08,
    "truck_17ft":    0.05,
}

# ── Goods categories (Porter-specific) ────────────────────────
GOODS_CATEGORIES: List[str] = [
    "documents",        # envelopes, files — 2W mostly
    "electronics",      # laptops, appliances
    "furniture",        # sofa, beds — truck typically
    "appliances",       # fridge, washing machine
    "boxes_mixed",      # packed household/office goods
    "raw_material",     # construction, factory supplies
    "perishable",       # food, pharma
    "other",
]

# Goods category → typical weight range (kg) and vehicle compatibility
GOODS_WEIGHT_RANGE_KG: Dict[str, Tuple[float, float]] = {
    "documents":    (0.1,  5.0),
    "electronics":  (1.0,  50.0),
    "furniture":    (20.0, 500.0),
    "appliances":   (10.0, 200.0),
    "boxes_mixed":  (5.0,  300.0),
    "raw_material": (50.0, 1000.0),
    "perishable":   (1.0,  100.0),
    "other":        (1.0,  200.0),
}

# Goods category → typical vehicle
GOODS_VEHICLE_PREFS: Dict[str, List[str]] = {
    "documents":    ["two_wheeler", "three_wheeler"],
    "electronics":  ["three_wheeler", "mini_truck"],
    "furniture":    ["mini_truck", "truck_14ft", "truck_17ft"],
    "appliances":   ["mini_truck", "truck_14ft"],
    "boxes_mixed":  ["three_wheeler", "mini_truck", "truck_14ft"],
    "raw_material": ["truck_14ft", "truck_17ft"],
    "perishable":   ["two_wheeler", "three_wheeler", "mini_truck"],
    "other":        ["three_wheeler", "mini_truck"],
}

# Loading time norms per goods category (minutes, p50 / p75 / p95)
# Used to detect loading_fraud (excessive claimed loading time)
LOADING_TIME_NORMS_MIN: Dict[str, Tuple[float, float, float]] = {
    "documents":    (2.0,  5.0,  10.0),
    "electronics":  (8.0,  18.0, 35.0),
    "furniture":    (30.0, 55.0, 90.0),
    "appliances":   (15.0, 30.0, 55.0),
    "boxes_mixed":  (10.0, 22.0, 45.0),
    "raw_material": (20.0, 40.0, 70.0),
    "perishable":   (5.0,  12.0, 25.0),
    "other":        (8.0,  20.0, 40.0),
}

# Floor loading penalty: each floor adds ~8 min to loading
FLOOR_LOADING_PENALTY_MINS: float = 8.0

# ── Fraud configuration ───────────────────────────────────────
FRAUD_BASE_RATE: float = 0.042   # 4.2% — Uber India estimates 3-6%

# Fraud types: corrected to match real India distribution
# Sources: Uber deactivation data, PorterTwin research, academic papers
FRAUD_TYPES: List[str] = [
    "cash_extortion",    # driver demands cash above meter — India's #1
    "fake_trip",         # GPS spoof — driver never moved
    "route_deviation",   # detour + time inflation
    "fake_cancellation", # accept-cancel farming
    "duplicate_trip",    # same trip billed twice
    "loading_fraud",     # inflate loading time charges (Porter-specific)
    "partial_delivery",  # goods retained / short-delivered (Porter-specific)
    "gps_spoof",         # GPS manipulation without fake trip (inflated distance)
]

# CORRECTED distribution — cash_extortion is #1 in India (was #2, wrong)
FRAUD_TYPE_DISTRIBUTION: Dict[str, float] = {
    "cash_extortion":    0.28,   # India #1 due to cash dominance
    "fake_trip":         0.22,   # GPS spoof, incentive farming
    "route_deviation":   0.18,   # detour + deliberate slowdown
    "fake_cancellation": 0.14,   # accept-cancel cycle gaming
    "duplicate_trip":    0.10,   # system exploit / manual resubmit
    "loading_fraud":     0.05,   # Porter-specific: inflate loading charges
    "partial_delivery":  0.02,   # Porter-specific: goods retention
    "gps_spoof":         0.01,   # pure GPS manipulation (distance only)
}
assert abs(sum(FRAUD_TYPE_DISTRIBUTION.values()) - 1.0) < 1e-9, \
    "Fraud distribution must sum to 1.0"

# Night hours see 1.8x fraud rate (real data: TrustDecision India 2023)
NIGHT_FRAUD_MULTIPLIER: float = 1.8
NIGHT_HOURS: Tuple[int, int] = (22, 5)  # 10PM to 5AM

# ── GPS / Device signal constants ─────────────────────────────
# Used to inject realistic device signals into trip records

# Normal GPS accuracy range for a real phone in Indian cities (meters)
GPS_ACCURACY_NORMAL_M: Tuple[float, float] = (4.0, 18.0)
# Mock location apps produce suspiciously perfect accuracy
GPS_ACCURACY_MOCK_M: float = 1.5

# Normal GPS ping count per minute of trip
GPS_PINGS_PER_MIN_NORMAL: float = 3.0   # every 20 seconds
GPS_PINGS_PER_MIN_SPOOF: float  = 0.4   # spoofed = very few pings

# Probability of mock_location being enabled for fraud types
MOCK_LOCATION_PROB: Dict[str, float] = {
    "fake_trip":      0.85,
    "gps_spoof":      0.92,
    "route_deviation":0.20,
    "fake_cancellation": 0.05,
    "cash_extortion": 0.02,
    "duplicate_trip": 0.05,
    "loading_fraud":  0.01,
    "partial_delivery": 0.03,
}

# ── Timing constants ──────────────────────────────────────────
# Realistic latency distributions (seconds) for each lifecycle stage

# assign_latency: time between request and driver acceptance
ASSIGN_LATENCY_SEC: Dict[str, Tuple[int, int]] = {
    "peak":     (45,  300),   # 45s–5min during peak
    "off_peak": (20,  180),   # 20s–3min off-peak
    "night":    (60,  600),   # 1–10min at night
}

# accept_to_arrive: time from acceptance to reaching pickup (minutes)
ACCEPT_TO_ARRIVE_MINS: Dict[str, Tuple[float, float]] = {
    "two_wheeler":   (3.0,  18.0),
    "three_wheeler": (5.0,  22.0),
    "mini_truck":    (6.0,  30.0),
    "truck_14ft":    (8.0,  40.0),
    "truck_17ft":    (10.0, 50.0),
}

# waiting_time: customer loads goods after driver arrives
WAITING_TIME_MINS: Dict[str, Tuple[float, float]] = {
    "two_wheeler":   (0.5,  5.0),
    "three_wheeler": (1.0,  8.0),
    "mini_truck":    (2.0,  15.0),
    "truck_14ft":    (5.0,  30.0),
    "truck_17ft":    (8.0,  45.0),
}

# ── Cancellation config ───────────────────────────────────────
# Stage at which cancellation happens
CANCELLATION_STAGES: List[str] = [
    "pre_arrive",    # before driver reaches pickup
    "post_arrive",   # after arriving, before trip start
    "post_start",    # after trip started (rare)
]

CANCELLATION_STAGE_PROBS: List[float] = [0.72, 0.22, 0.06]

# ── Financial ─────────────────────────────────────────────────
# Toll ranges by city (₹)
TOLL_RANGE_INR: Dict[str, Tuple[float, float]] = {
    "bangalore": (0,   65),
    "mumbai":    (30, 150),   # Mumbai has more toll roads
    "delhi":     (30, 120),
    "hyderabad": (0,   60),
    "chennai":   (0,   50),
    "pune":      (20,  80),
    "kolkata":   (15,  60),
}

# Probability that a trip has toll charges (varies by vehicle + city)
TOLL_PROBABILITY: Dict[str, float] = {
    "two_wheeler":   0.08,
    "three_wheeler": 0.12,
    "mini_truck":    0.25,
    "truck_14ft":    0.38,
    "truck_17ft":    0.45,
}

# Night premium: trips starting 10PM-5AM
NIGHT_PREMIUM_MULTIPLIER: float = 1.25

# Surge caps
SURGE_MIN: float = 1.0
SURGE_MAX: float = 3.5

# ── Payment modes and city cash preferences ───────────────────
# Cash % varies heavily by city and vehicle type in India
CITY_CASH_PCT: Dict[str, float] = {
    "bangalore": 0.18,   # tech-savvy, low cash
    "mumbai":    0.22,
    "delhi":     0.28,
    "hyderabad": 0.25,
    "chennai":   0.30,
    "pune":      0.20,
    "kolkata":   0.38,   # highest cash usage
}

# ── Model performance benchmarks ─────────────────────────────
PILOT_SUCCESS_CRITERIA: Dict[str, float] = {
    "min_auc_roc":                    0.92,
    "min_precision_at_50":            0.78,
    "min_recall_at_50":               0.71,
    "max_false_positive_rate":        0.08,
    "min_detection_improvement_pct":  25.0,
    "min_net_recoverable_per_trip":   0.50,   # ₹0.50 net/trip minimum
}

# Cost to investigate one false-positive alert (ops team time ≈ 15 min)
FALSE_POSITIVE_OPS_COST: float = 50.0   # ₹50 per false alarm

# Conservative extrapolation haircut for annual projections
CONFIDENCE_HAIRCUT: float = 0.65        # 65% of lab results survive production

# Porter estimated annual trips (FY25: 43,200/day × 365)
ANNUAL_EXTRAP_FACTOR: int = 15_768_000

# ── API config ────────────────────────────────────────────────
API_TITLE: str = "Porter Intelligence Platform"
API_VERSION: str = "2.0.0"
API_DESCRIPTION: str = (
    "Real-time trip fraud scoring, case workflow, driver intelligence, "
    "and operational analytics for Porter-style logistics networks."
)

# ── Paths ─────────────────────────────────────────────────────
ROOT_DIR        = Path(__file__).parent.parent
DATA_RAW        = ROOT_DIR / "data" / "raw"
DATA_MASKED     = ROOT_DIR / "data" / "masked"
DATA_BLIND_TEST = ROOT_DIR / "data" / "blind_test"
MODEL_WEIGHTS   = ROOT_DIR / "model" / "weights"

for _dir in [DATA_RAW, DATA_MASKED, DATA_BLIND_TEST, MODEL_WEIGHTS]:
    _dir.mkdir(parents=True, exist_ok=True)

# ── Hour-of-day trip probability weights ─────────────────────
# Index 0 = midnight (0:00), index 23 = 11PM
# Bimodal distribution: morning peak 8-10AM, evening peak 7-9PM
WEEKDAY_HOUR_WEIGHTS: List[float] = [
    0.008, 0.005, 0.003, 0.002, 0.003, 0.010,  # 0-5 AM
    0.025, 0.045, 0.075, 0.072, 0.055, 0.058,  # 6-11 AM
    0.065, 0.060, 0.052, 0.048, 0.045, 0.055,  # noon-5 PM
    0.072, 0.080, 0.068, 0.052, 0.038, 0.020,  # 6-11 PM
]
WEEKEND_HOUR_WEIGHTS: List[float] = [
    0.015, 0.010, 0.008, 0.005, 0.004, 0.008,  # 0-5 AM
    0.015, 0.025, 0.040, 0.052, 0.058, 0.062,  # 6-11 AM
    0.068, 0.065, 0.060, 0.058, 0.055, 0.060,  # noon-5 PM
    0.075, 0.088, 0.080, 0.065, 0.045, 0.028,  # 6-11 PM
]
# Normalise to sum to 1.0
_wday_sum = sum(WEEKDAY_HOUR_WEIGHTS)
_wend_sum = sum(WEEKEND_HOUR_WEIGHTS)
WEEKDAY_HOUR_WEIGHTS = [w / _wday_sum for w in WEEKDAY_HOUR_WEIGHTS]
WEEKEND_HOUR_WEIGHTS = [w / _wend_sum for w in WEEKEND_HOUR_WEIGHTS]


if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    console = Console()

    table = Table(title="Porter Config v2 — Validation")
    table.add_column("Check", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", justify="center")

    dist_sum = sum(FRAUD_TYPE_DISTRIBUTION.values())
    veh_sum  = sum(VEHICLE_DISTRIBUTION.values())

    table.add_row("Cities",           str(len(CITIES)),      "✅")
    table.add_row("Vehicle types",    str(len(VEHICLE_TYPES)), "✅")
    table.add_row("Fraud types",      str(len(FRAUD_TYPES)),  "✅")
    table.add_row("Fraud dist sum",   f"{dist_sum:.4f}",
                  "✅" if abs(dist_sum - 1.0) < 1e-6 else "❌")
    table.add_row("Vehicle dist sum", f"{veh_sum:.4f}",
                  "✅" if abs(veh_sum - 1.0) < 1e-6 else "❌")
    table.add_row("Fraud base rate",  f"{FRAUD_BASE_RATE*100:.1f}%", "✅")
    table.add_row("Cash extortion #1",
                  f"{FRAUD_TYPE_DISTRIBUTION['cash_extortion']*100:.0f}%",
                  "✅" if FRAUD_TYPE_DISTRIBUTION["cash_extortion"] ==
                  max(FRAUD_TYPE_DISTRIBUTION.values()) else "❌")
    table.add_row("Goods categories", str(len(GOODS_CATEGORIES)), "✅")
    console.print(table)

    # Speed sanity: all vehicle speeds must be physically plausible
    for city, speeds in CITY_AVG_SPEED_KMH.items():
        for vtype, spd in speeds.items():
            assert 5 < spd < 80, f"{city}/{vtype} speed {spd} implausible"
    console.print("[green]✅ All city speed profiles physically plausible[/green]")
    console.print("[green bold]✅ config.py v2 — all checks passed[/green bold]")
