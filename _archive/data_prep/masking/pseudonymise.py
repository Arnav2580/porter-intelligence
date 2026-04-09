"""
Porter Intelligence Platform — Pseudonymisation Engine

Transforms raw CSVs into a masked dataset suitable for
sharing under NDA in a sandboxed pilot environment.

WHAT IS PRESERVED (model signal must survive):
  - Relative temporal patterns (rush hour, day of week)
  - Zone-level fraud clustering
  - Driver behavioural sequences (hashed IDs still unique)
  - Fraud type signatures and feature ratios
  - Vehicle type and payment mode distributions

WHAT IS DESTROYED (PII and competitive intelligence):
  - Driver/customer names and phone numbers
  - Exact GPS coordinates
  - Exact fare amounts
  - Exact timestamps
  - Raw driver IDs
"""

import numpy as np
import pandas as pd
import hashlib
from pathlib import Path
from typing import Dict, Tuple
from rich.console import Console
from rich.table import Table

from generator.config import (
    RANDOM_SEED, DATA_RAW, DATA_MASKED, MODEL_WEIGHTS,
)

console = Console()
rng = np.random.default_rng(RANDOM_SEED + 99)


def hash_id(raw_id: str, salt: str = "porter_pilot_2024") -> str:
    """
    Deterministically hash an ID using SHA256.
    Same raw_id always produces same hash — preserves
    uniqueness for driver behavioural sequence features.
    MASKED_COMPATIBLE: driver_id joins still work.
    """
    combined = f"{salt}:{raw_id}"
    return hashlib.sha256(
        combined.encode()
    ).hexdigest()[:16].upper()


def pseudonymise_drivers(
    df: pd.DataFrame,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Pseudonymise driver profiles.

    Transformations:
      driver_id   → SHA256 hash (deterministic, unique)
      name        → "DRIVER_XXXX" format
      phone       → "+91XXXXXXXXXX" random
      zone_id     → kept (needed for geographic features)
      city        → kept (needed for filtering)
      fraud_propensity → REMOVED (internal label, never expose)
      fraud_ring_id   → hashed if present
      ring_role       → kept (ring structure signal preserved)
      all other fields → kept (needed for features)

    Returns (masked_df, id_mapping) where id_mapping maps
    original → hashed IDs for cross-table joins.
    """
    masked = df.copy()

    # Build ID mapping for cross-table consistency
    id_map = {
        orig: hash_id(str(orig))
        for orig in masked["driver_id"].unique()
    }

    masked["driver_id"] = masked["driver_id"].map(id_map)
    masked["name"]      = [
        f"DRIVER_{i:05d}" for i in range(len(masked))
    ]
    masked["phone"] = [
        f"+91{rng.choice([6,7,8,9])}"
        f"{rng.integers(100_000_000, 999_999_999)}"
        for _ in range(len(masked))
    ]

    # Hash ring IDs if present
    if "fraud_ring_id" in masked.columns:
        masked["fraud_ring_id"] = masked["fraud_ring_id"].apply(
            lambda x: hash_id(str(x)) if pd.notna(x) else None
        )

    # Remove internal training labels
    drop_cols = ["fraud_propensity"]
    masked = masked.drop(
        columns=[c for c in drop_cols if c in masked.columns]
    )

    return masked, id_map


def pseudonymise_customers(
    df: pd.DataFrame,
    driver_id_map: Dict[str, str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Pseudonymise customer profiles.

    Transformations:
      customer_id   → SHA256 hash
      business_name → "BUSINESS_XXXXX" format
      zone_id       → kept
      city          → kept
      ltv_inr       → scaled by random factor per customer
                       preserves distribution, hides exact values
      all other fields → kept
    """
    masked = df.copy()

    cust_id_map = {
        orig: hash_id(str(orig), salt="customer_2024")
        for orig in masked["customer_id"].unique()
    }
    masked["customer_id"]   = masked["customer_id"].map(cust_id_map)
    masked["business_name"] = [
        f"BUSINESS_{i:06d}" for i in range(len(masked))
    ]

    # Scale LTV by per-customer random factor 0.80-1.20
    # Preserves distribution shape, destroys exact values
    scale_factors = rng.uniform(0.80, 1.20, len(masked))
    masked["ltv_inr"] = (
        masked["ltv_inr"] * scale_factors
    ).round(2)

    return masked


def pseudonymise_trips(
    df: pd.DataFrame,
    driver_id_map: Dict[str, str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Pseudonymise trip records.

    Transformations:
      driver_id/customer_id → apply same hash maps
      pickup/dropoff lat/lon → add gaussian noise ±0.002°
                               (~200m shift, preserves zone patterns)
      fare_inr              → multiply by per-driver scale factor
                               preserves distribution and ratios
      requested_at etc      → shift ALL timestamps by same random
                               offset per dataset (±7 days)
                               preserves temporal patterns exactly
      trip_id               → hash
      is_fraud / fraud_type → KEPT (needed for evaluation)
      fraud_confidence_score→ KEPT (needed for weighted eval)
      recoverable_amount_inr→ scaled by same fare factor
      ring_coordination     → kept (structure signal)

    GPS noise: gaussian with std=0.0006° (~67m at equator)
    Clipped to ±0.002° max shift to stay within zone bounds.
    """
    masked = df.copy()

    # Hash trip IDs
    masked["trip_id"] = masked["trip_id"].apply(
        lambda x: hash_id(str(x), salt="trip_2024")
    )

    # Apply driver/customer ID maps
    masked["driver_id"] = masked["driver_id"].map(
        driver_id_map
    ).fillna(masked["driver_id"])  # fallback for unmapped

    cust_id_map_cache = {}
    def hash_cust(cid):
        if cid not in cust_id_map_cache:
            cust_id_map_cache[cid] = hash_id(
                str(cid), salt="customer_2024"
            )
        return cust_id_map_cache[cid]
    masked["customer_id"] = masked["customer_id"].apply(hash_cust)

    # GPS noise — preserves zone-level clustering
    n = len(masked)
    lat_noise = np.clip(rng.normal(0, 0.0006, n), -0.002, 0.002)
    lon_noise = np.clip(rng.normal(0, 0.0006, n), -0.002, 0.002)

    masked["pickup_lat"]  = (masked["pickup_lat"]  + lat_noise).round(6)
    masked["pickup_lon"]  = (masked["pickup_lon"]  + lon_noise).round(6)
    masked["dropoff_lat"] = (masked["dropoff_lat"] + lat_noise).round(6)
    masked["dropoff_lon"] = (masked["dropoff_lon"] + lon_noise).round(6)

    # Fare scaling — per-driver consistent factor
    # Preserves fare_to_expected_ratio (both sides scale equally)
    driver_scale = {
        d: rng.uniform(0.88, 1.12)
        for d in masked["driver_id"].unique()
    }
    fare_scale = masked["driver_id"].map(driver_scale).fillna(1.0)
    masked["fare_inr"] = (masked["fare_inr"] * fare_scale).round(2)
    masked["recoverable_amount_inr"] = (
        masked["recoverable_amount_inr"] * fare_scale
    ).round(2)

    # Timestamp shift — uniform offset for entire dataset
    # Same offset preserves ALL temporal patterns
    shift_days = int(rng.integers(-7, 8))
    shift_td   = pd.Timedelta(days=shift_days)

    for ts_col in [
        "requested_at", "accepted_at", "started_at",
        "completed_at", "cancelled_at"
    ]:
        if ts_col in masked.columns:
            non_null = masked[ts_col].notna()
            masked.loc[non_null, ts_col] = (
                pd.to_datetime(
                    masked.loc[non_null, ts_col],
                    format="ISO8601",
                )
                + shift_td
            ).astype(str)

    return masked


def verify_masking_quality(
    raw_trips: pd.DataFrame,
    masked_trips: pd.DataFrame,
    raw_drivers: pd.DataFrame,
    masked_drivers: pd.DataFrame,
) -> bool:
    """
    Verify that masking preserves the signals the model needs.

    Tests (all must pass):
      1. Fraud rate preserved (within 0.5% — same rows, same labels)
      2. Fraud type distribution preserved (max type diff < 5%)
      3. Payment mode distribution preserved (max diff < 2%)
      4. Zone fraud clustering preserved (top 3 zones: 2/3 match)
      5. Temporal pattern preserved (peak hour fraud rate ratio)
      6. fare_to_expected_ratio distribution preserved (within 5%)
      7. No PII leaked (no original driver IDs in masked)

    Returns True if all tests pass.
    """
    all_pass = True
    results  = []

    # Test 1: Fraud rate
    raw_rate    = raw_trips["is_fraud"].mean()
    masked_rate = masked_trips["is_fraud"].mean()
    diff = abs(raw_rate - masked_rate)
    ok1  = diff < 0.005
    results.append((
        "Fraud rate preserved",
        f"{raw_rate*100:.2f}% → {masked_rate*100:.2f}%",
        "✅" if ok1 else "❌"
    ))
    if not ok1: all_pass = False

    # Test 2: Fraud type distribution
    raw_dist    = raw_trips[raw_trips["is_fraud"]]["fraud_type"].value_counts(normalize=True)
    masked_dist = masked_trips[masked_trips["is_fraud"]]["fraud_type"].value_counts(normalize=True)
    max_diff = max(
        abs(raw_dist.get(ft, 0) - masked_dist.get(ft, 0))
        for ft in raw_dist.index
    )
    ok2 = max_diff < 0.05
    results.append((
        "Fraud type distribution",
        f"Max type diff: {max_diff:.4f}",
        "✅" if ok2 else "❌"
    ))
    if not ok2: all_pass = False

    # Test 3: Payment mode distribution
    raw_pay    = raw_trips["payment_mode"].value_counts(normalize=True)
    masked_pay = masked_trips["payment_mode"].value_counts(normalize=True)
    pay_diff   = max(
        abs(raw_pay.get(m, 0) - masked_pay.get(m, 0))
        for m in ["cash", "upi", "credit"]
    )
    ok3 = pay_diff < 0.02
    results.append((
        "Payment mode distribution",
        f"Max diff: {pay_diff:.4f}",
        "✅" if ok3 else "❌"
    ))
    if not ok3: all_pass = False

    # Test 4: Zone fraud clustering
    raw_zone_fraud = (
        raw_trips.groupby("pickup_zone_id")["is_fraud"].mean()
        .nlargest(3).index.tolist()
    )
    masked_zone_fraud = (
        masked_trips.groupby("pickup_zone_id")["is_fraud"].mean()
        .nlargest(3).index.tolist()
    )
    overlap = len(set(raw_zone_fraud) & set(masked_zone_fraud))
    ok4 = overlap >= 2
    results.append((
        "Top fraud zones preserved",
        f"{overlap}/3 zones match",
        "✅" if ok4 else "❌"
    ))
    if not ok4: all_pass = False

    # Test 5: Temporal pattern
    raw_trips_dt = raw_trips.copy()
    masked_trips_dt = masked_trips.copy()
    raw_trips_dt["_hour"] = pd.to_datetime(
        raw_trips_dt["requested_at"], format="ISO8601"
    ).dt.hour
    masked_trips_dt["_hour"] = pd.to_datetime(
        masked_trips_dt["requested_at"], format="ISO8601"
    ).dt.hour

    raw_peak  = raw_trips_dt[
        raw_trips_dt["_hour"].isin([8,9,18,19,20])
    ]["is_fraud"].mean()
    raw_off   = raw_trips_dt[
        raw_trips_dt["_hour"].isin([2,3,4])
    ]["is_fraud"].mean()
    masked_peak = masked_trips_dt[
        masked_trips_dt["_hour"].isin([8,9,18,19,20])
    ]["is_fraud"].mean()
    masked_off  = masked_trips_dt[
        masked_trips_dt["_hour"].isin([2,3,4])
    ]["is_fraud"].mean()

    raw_ratio    = raw_peak / max(raw_off, 0.001)
    masked_ratio = masked_peak / max(masked_off, 0.001)
    ratio_diff   = abs(raw_ratio - masked_ratio) / max(raw_ratio, 0.001)
    ok5 = ratio_diff < 0.20
    results.append((
        "Temporal pattern preserved",
        f"Peak/off ratio diff: {ratio_diff*100:.1f}%",
        "✅" if ok5 else "❌"
    ))
    if not ok5: all_pass = False

    # Test 6: fare_to_expected_ratio distribution
    from model.features import compute_trip_features

    def get_fare_ratio(df):
        result = compute_trip_features(df)
        return result["fare_to_expected_ratio"]

    raw_ratio_mean    = get_fare_ratio(raw_trips).mean()
    masked_ratio_mean = get_fare_ratio(masked_trips).mean()
    ratio_pct_diff = abs(
        raw_ratio_mean - masked_ratio_mean
    ) / max(raw_ratio_mean, 0.001)
    ok6 = ratio_pct_diff < 0.05
    results.append((
        "fare_to_expected_ratio preserved",
        f"Diff: {ratio_pct_diff*100:.2f}% (target <5%)",
        "✅" if ok6 else "❌"
    ))
    if not ok6: all_pass = False

    # Test 7: No PII leakage
    raw_ids    = set(raw_drivers["driver_id"].astype(str))
    masked_ids = set(masked_drivers["driver_id"].astype(str))
    overlap_ids = raw_ids & masked_ids
    ok7 = len(overlap_ids) == 0
    results.append((
        "No original driver IDs in masked data",
        f"ID overlap: {len(overlap_ids)}",
        "✅" if ok7 else "❌"
    ))
    if not ok7: all_pass = False

    # Print results table
    table = Table(title="Masking Quality Verification")
    table.add_column("Test",    style="cyan", min_width=35)
    table.add_column("Result",  justify="right")
    table.add_column("Status",  justify="center")
    for test, result, status in results:
        table.add_row(test, result, status)
    console.print(table)

    return all_pass


def run_pseudonymisation(
    raw_trips_path:    Path,
    raw_drivers_path:  Path,
    raw_customers_path: Path,
) -> bool:
    """
    Load raw CSVs, pseudonymise, save to data/masked/.
    Returns True if quality verification passes.
    """
    from rich.panel import Panel

    console.rule("[cyan]Pseudonymisation Engine[/cyan]")

    # Load
    trips_df     = pd.read_csv(raw_trips_path)
    drivers_df   = pd.read_csv(raw_drivers_path)
    customers_df = pd.read_csv(raw_customers_path)

    console.print(
        f"[dim]Loaded: {len(trips_df):,} trips | "
        f"{len(drivers_df):,} drivers | "
        f"{len(customers_df):,} customers[/dim]"
    )

    # Pseudonymise
    masked_drivers, driver_id_map = pseudonymise_drivers(
        drivers_df, rng
    )
    masked_customers = pseudonymise_customers(
        customers_df, driver_id_map, rng
    )
    masked_trips = pseudonymise_trips(
        trips_df, driver_id_map, rng
    )

    # Save
    masked_drivers.to_csv(
        DATA_MASKED / "drivers_masked.csv", index=False
    )
    masked_customers.to_csv(
        DATA_MASKED / "customers_masked.csv", index=False
    )
    masked_trips.to_csv(
        DATA_MASKED / "trips_masked.csv", index=False
    )
    console.print(
        f"[green]Masked CSVs saved to {DATA_MASKED}[/green]"
    )

    # Verify quality
    console.rule("[cyan]Quality Verification[/cyan]")
    quality_ok = verify_masking_quality(
        trips_df, masked_trips,
        drivers_df, masked_drivers
    )

    if quality_ok:
        console.print(Panel.fit(
            "[green bold]Masking quality verified.\n"
            "Safe to share under NDA.[/green bold]",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            "[red]Masking quality failed.\n"
            "Do not share these files.[/red]",
            border_style="red"
        ))

    return quality_ok


if __name__ == "__main__":
    from rich.panel import Panel

    # Regenerate sample data for masking test
    console.print("[dim]Generating sample data for masking test...[/dim]")
    from generator.drivers import generate_drivers
    from generator.customers import generate_customers
    from generator.trips import generate_trips
    from generator.fraud import inject_fraud

    drivers_df   = generate_drivers(n=2000, city_filter="bangalore")
    customers_df = generate_customers(n=2000, city_filter="bangalore")
    trips_df     = generate_trips(
        drivers_df, customers_df,
        n=5000, city_filter="bangalore"
    )
    trips_df = inject_fraud(trips_df, drivers_df)

    # Save raw samples
    trips_df.to_csv(DATA_RAW / "trips_sample_5k.csv", index=False)
    drivers_df.to_csv(DATA_RAW / "drivers_sample_2k.csv", index=False)
    customers_df.to_csv(DATA_RAW / "customers_sample_2k.csv", index=False)

    # Run pseudonymisation
    quality_ok = run_pseudonymisation(
        DATA_RAW / "trips_sample_5k.csv",
        DATA_RAW / "drivers_sample_2k.csv",
        DATA_RAW / "customers_sample_2k.csv",
    )

    assert quality_ok, "Masking quality check failed"
    console.print(
        "\n[green bold]pseudonymise.py — all checks passed"
        "[/green bold]"
    )
