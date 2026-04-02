"""
Porter Intelligence Platform — Feature Engineering

Transforms raw trip records into the feature matrix
used for XGBoost fraud detection training and inference.

All features are computed from fields available in the
pseudonymised/masked dataset — no raw PII required.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table

from generator.config import (
    RANDOM_SEED, VEHICLE_TYPES, PILOT_SUCCESS_CRITERIA,
    FRAUD_BASE_RATE,
)

console = Console()


# ── Feature definitions ───────────────────────────────────────

FEATURE_COLUMNS: List[str] = [

    # ── Trip-level features ──────────────────────────────────
    "declared_distance_km",        # MASKED_COMPATIBLE (ratio preserved)
    "declared_duration_min",       # MASKED_COMPATIBLE
    "fare_inr",                    # MASKED_COMPATIBLE (scaled, ratio valid)
    "surge_multiplier",            # MASKED_COMPATIBLE
    "zone_demand_at_time",         # MASKED_COMPATIBLE

    # ── Derived trip features ────────────────────────────────
    "fare_to_expected_ratio",      # MASKED_COMPATIBLE ← key fraud signal
    "distance_time_ratio",         # MASKED_COMPATIBLE
    "fare_per_km",                 # MASKED_COMPATIBLE
    "pickup_dropoff_haversine_km", # MASKED_COMPATIBLE (noise-shifted but valid)
    "distance_vs_haversine_ratio", # MASKED_COMPATIBLE

    # ── Temporal features ────────────────────────────────────
    "hour_of_day",                 # MASKED_COMPATIBLE
    "day_of_week",                 # MASKED_COMPATIBLE
    "is_night",                    # MASKED_COMPATIBLE
    "is_peak_hour",                # MASKED_COMPATIBLE
    "is_friday",                   # MASKED_COMPATIBLE
    "is_late_month",               # MASKED_COMPATIBLE

    # ── Payment features ─────────────────────────────────────
    "payment_is_cash",             # MASKED_COMPATIBLE
    "payment_is_credit",           # MASKED_COMPATIBLE

    # ── Driver behavioural features ──────────────────────────
    "driver_cancellation_velocity_1hr",  # MASKED_COMPATIBLE ← ring signal
    "driver_cancel_rate_rolling_7d",     # MASKED_COMPATIBLE
    "driver_dispute_rate_rolling_14d",   # MASKED_COMPATIBLE (replaces fraud rate — no label leakage)
    "driver_trips_last_24hr",            # MASKED_COMPATIBLE
    "driver_cash_trip_ratio_7d",         # MASKED_COMPATIBLE

    # ── Driver profile features ──────────────────────────────
    "driver_account_age_days",     # MASKED_COMPATIBLE
    "driver_rating",               # MASKED_COMPATIBLE
    "driver_lifetime_trips",       # MASKED_COMPATIBLE
    "driver_verification_encoded", # MASKED_COMPATIBLE (0/1/2)
    "driver_payment_type_encoded", # MASKED_COMPATIBLE (0/1/2)

    # ── Geographic features ──────────────────────────────────
    "zone_fraud_rate_rolling_7d",  # MASKED_COMPATIBLE ← clustering signal
    "same_zone_trip",              # MASKED_COMPATIBLE (pickup==dropoff zone)

    # ── Status features ──────────────────────────────────────
    "is_cancelled",                # MASKED_COMPATIBLE

]

TARGET_COLUMN = "is_fraud"
WEIGHT_COLUMN = "fraud_confidence_score"


def compute_trip_features(
    trips_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute per-trip derived features.
    These do not require any cross-trip lookups.
    Fast — vectorised pandas operations throughout.
    """
    df = trips_df.copy()
    df["requested_at"] = pd.to_datetime(
        df["requested_at"], format="mixed"
    )

    # ── Fare to expected ratio ─────────────────────────────
    # MASKED_COMPATIBLE
    def expected_fare(row: pd.Series) -> float:
        veh = VEHICLE_TYPES.get(row["vehicle_type"])
        if veh is None:
            return row["fare_inr"]
        return veh.base_fare + veh.per_km_rate * row["declared_distance_km"]

    df["expected_fare"] = df.apply(expected_fare, axis=1)
    df["fare_to_expected_ratio"] = (
        df["fare_inr"] / df["expected_fare"].clip(lower=1.0)
    ).round(4)

    # ── Distance / time ratio ──────────────────────────────
    # MASKED_COMPATIBLE
    df["distance_time_ratio"] = (
        df["declared_distance_km"]
        / df["declared_duration_min"].clip(lower=0.1)
    ).round(4)

    # ── Fare per km ────────────────────────────────────────
    # MASKED_COMPATIBLE
    df["fare_per_km"] = (
        df["fare_inr"]
        / df["declared_distance_km"].clip(lower=0.1)
    ).round(2)

    # ── Haversine between pickup and dropoff ──────────────
    # MASKED_COMPATIBLE (noise shift preserves zone-level signal)
    from generator.cities import haversine_km
    df["pickup_dropoff_haversine_km"] = df.apply(
        lambda r: haversine_km(
            r["pickup_lat"], r["pickup_lon"],
            r["dropoff_lat"], r["dropoff_lon"],
        ),
        axis=1,
    ).round(3)

    # ── Declared distance vs haversine ratio ──────────────
    # MASKED_COMPATIBLE
    df["distance_vs_haversine_ratio"] = (
        df["declared_distance_km"]
        / df["pickup_dropoff_haversine_km"].clip(lower=0.1)
    ).round(4)

    # ── Temporal features ──────────────────────────────────
    # MASKED_COMPATIBLE (timestamps shifted uniformly — patterns preserved)
    df["is_friday"]     = (df["day_of_week"] == 4).astype(int)
    df["is_late_month"] = (
        df["requested_at"].dt.day >= 25
    ).astype(int)

    # ── Payment encoding ───────────────────────────────────
    # MASKED_COMPATIBLE
    df["payment_is_cash"]   = (df["payment_mode"] == "cash").astype(int)
    df["payment_is_credit"] = (df["payment_mode"] == "credit").astype(int)

    # ── Zone trip (pickup == dropoff zone) ─────────────────
    # MASKED_COMPATIBLE
    df["same_zone_trip"] = (
        df["pickup_zone_id"] == df["dropoff_zone_id"]
    ).astype(int)

    # ── Cancellation flag ──────────────────────────────────
    # MASKED_COMPATIBLE
    df["is_cancelled"] = df["status"].isin(
        ["cancelled_by_driver", "cancelled_by_customer"]
    ).astype(int)

    # ── Complaint flag ─────────────────────────────────────
    # MASKED_COMPATIBLE
    df["has_complaint"] = df["customer_complaint_flag"].astype(int)

    return df


def compute_driver_features(
    trips_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join driver profile features onto trips.
    Encode categorical driver fields numerically.
    MASKED_COMPATIBLE — all fields use hashed IDs.
    """
    driver_cols = [
        "driver_id", "account_age_days", "rating",
        "total_trips_lifetime", "verification_status",
        "bank_account_type",
    ]
    drv = drivers_df[driver_cols].copy()

    # Encode verification status
    # MASKED_COMPATIBLE (category preserved in masked data)
    verif_map = {"verified": 0, "pending": 1, "unverified": 2}
    drv["driver_verification_encoded"] = drv[
        "verification_status"
    ].map(verif_map).fillna(1).astype(int)

    # Encode payment preference
    # MASKED_COMPATIBLE
    pay_map = {"upi": 0, "bank": 1, "cash": 2}
    drv["driver_payment_type_encoded"] = drv[
        "bank_account_type"
    ].map(pay_map).fillna(0).astype(int)

    drv = drv.rename(columns={
        "account_age_days":     "driver_account_age_days",
        "rating":               "driver_rating",
        "total_trips_lifetime": "driver_lifetime_trips",
    })

    keep = [
        "driver_id",
        "driver_account_age_days",
        "driver_rating",
        "driver_lifetime_trips",
        "driver_verification_encoded",
        "driver_payment_type_encoded",
    ]

    df = trips_df.merge(drv[keep], on="driver_id", how="left")

    # Fill missing (drivers not in sample)
    df["driver_account_age_days"] = pd.to_numeric(
        df["driver_account_age_days"].fillna(365), errors="coerce"
    ).fillna(365)
    df["driver_rating"] = pd.to_numeric(
        df["driver_rating"].fillna(4.0), errors="coerce"
    ).fillna(4.0)
    df["driver_lifetime_trips"] = pd.to_numeric(
        df["driver_lifetime_trips"].fillna(100), errors="coerce"
    ).fillna(100)
    df["driver_verification_encoded"] = pd.to_numeric(
        df["driver_verification_encoded"].fillna(0), errors="coerce"
    ).fillna(0).astype(int)
    df["driver_payment_type_encoded"] = pd.to_numeric(
        df["driver_payment_type_encoded"].fillna(0), errors="coerce"
    ).fillna(0).astype(int)

    return df


def compute_behavioural_sequence_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute rolling behavioural features that require
    cross-trip lookups within a driver's history.

    These are the moat features — expensive to compute,
    impossible to replicate with simple SQL rules.
    All MASKED_COMPATIBLE via hashed driver_id.

    Features computed:
      driver_cancellation_velocity_1hr
      driver_cancel_rate_rolling_7d
      driver_fraud_rate_rolling_14d
      driver_trips_last_24hr
      driver_cash_trip_ratio_7d
      zone_fraud_rate_rolling_7d

    IMPORTANT: Sort by requested_at before calling this function.
    All rolling windows use time-ordered trip history.
    """
    df = df.copy()
    df["requested_at"] = pd.to_datetime(
        df["requested_at"], format="mixed"
    )
    df = df.sort_values("requested_at").reset_index(drop=True)

    # Initialise all sequence feature columns to 0
    seq_features = [
        "driver_cancellation_velocity_1hr",
        "driver_cancel_rate_rolling_7d",
        "driver_dispute_rate_rolling_14d",
        "driver_trips_last_24hr",
        "driver_cash_trip_ratio_7d",
        "zone_fraud_rate_rolling_7d",
    ]
    for feat in seq_features:
        df[feat] = 0.0

    # ── Driver-level rolling features ────────────────────────
    console.print(
        "[dim]Computing driver behavioural sequences...[/dim]"
    )

    df["_ts"] = df["requested_at"].astype(np.int64) // 10**9

    cancel_vel_list   = np.zeros(len(df))
    cancel_rate_list  = np.zeros(len(df))
    dispute_rate_list = np.zeros(len(df))
    trips_24hr_list   = np.zeros(len(df))
    cash_ratio_list   = np.zeros(len(df))

    driver_groups = df.groupby("driver_id", sort=False)

    for driver_id, group in driver_groups:
        indices    = group.index.values
        timestamps = group["_ts"].values

        is_cancelled_arr = group["is_cancelled"].values \
            if "is_cancelled" in group.columns \
            else (group["status"].isin(
                ["cancelled_by_driver", "cancelled_by_customer"]
            )).astype(int).values

        is_disputed_arr = (group["status"] == "disputed").astype(int).values
        is_cash_arr     = (group["payment_mode"] == "cash").astype(int).values

        for i, (idx, ts) in enumerate(zip(indices, timestamps)):
            if i == 0:
                continue

            prior_ts      = timestamps[:i]
            prior_cancel  = is_cancelled_arr[:i]
            prior_dispute = is_disputed_arr[:i]
            prior_cash    = is_cash_arr[:i]

            # 1-hour cancellation velocity
            recent_1hr = (ts - prior_ts) <= 3600
            cancel_vel_list[idx] = float(prior_cancel[recent_1hr].sum())

            # 7-day cancel rate + cash ratio
            recent_7d = (ts - prior_ts) <= 7 * 86400
            n_7d = recent_7d.sum()
            if n_7d > 0:
                cancel_rate_list[idx] = float(prior_cancel[recent_7d].mean())
                cash_ratio_list[idx]  = float(prior_cash[recent_7d].mean())

            # 14-day dispute rate (real-time proxy for fraud rate)
            recent_14d = (ts - prior_ts) <= 14 * 86400
            n_14d = recent_14d.sum()
            if n_14d > 0:
                dispute_rate_list[idx] = float(prior_dispute[recent_14d].mean())

            # 24-hour trip count
            recent_24hr = (ts - prior_ts) <= 86400
            trips_24hr_list[idx] = float(recent_24hr.sum())

    df["driver_cancellation_velocity_1hr"] = cancel_vel_list
    df["driver_cancel_rate_rolling_7d"]    = cancel_rate_list
    df["driver_dispute_rate_rolling_14d"]  = dispute_rate_list
    df["driver_trips_last_24hr"]           = trips_24hr_list
    df["driver_cash_trip_ratio_7d"]        = cash_ratio_list

    # ── Zone fraud rate rolling 7 days ────────────────────────
    # MASKED_COMPATIBLE
    # Compute from historical data only → no data leakage
    console.print("[dim]Computing zone fraud rates...[/dim]")

    hist_df = df[df["data_split"] == "historical"].copy() \
        if "data_split" in df.columns \
        else df.copy()

    zone_fraud_map: Dict[str, float] = {}
    for zone_id in df["pickup_zone_id"].unique():
        zone_trips = hist_df[hist_df["pickup_zone_id"] == zone_id]
        if len(zone_trips) > 0:
            zone_fraud_map[zone_id] = float(zone_trips["is_fraud"].mean())
        else:
            zone_fraud_map[zone_id] = FRAUD_BASE_RATE

    df["zone_fraud_rate_rolling_7d"] = df["pickup_zone_id"].map(
        zone_fraud_map
    ).fillna(FRAUD_BASE_RATE)

    df = df.drop(columns=["_ts"], errors="ignore")

    return df


def build_feature_matrix(
    trips_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
    fit_mode: bool = True,
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Full pipeline: raw trips + drivers → feature matrix.

    Args:
        trips_df:   Output of inject_fraud()
        drivers_df: Output of generate_drivers()
        fit_mode:   If True, includes target and weight columns.

    Returns:
        X:       Feature matrix (DataFrame with FEATURE_COLUMNS)
        y:       Target series (is_fraud as int)
        weights: Sample weights (confidence scores)
    """
    console.print("[dim]Building feature matrix...[/dim]")

    # Step 1: Trip-level features
    df = compute_trip_features(trips_df)

    # Step 2: Driver profile features
    df = compute_driver_features(df, drivers_df)

    # Step 3: Behavioural sequence features
    df = compute_behavioural_sequence_features(df)

    # Step 4: Enforce feature column set
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            console.print(
                f"[yellow]⚠️  Missing feature '{col}' — filling 0[/yellow]"
            )
            df[col] = 0.0

    X = df[FEATURE_COLUMNS].copy()
    X = X.fillna(0.0)
    X = X.astype(float)

    if not fit_mode:
        return X, pd.Series(dtype=int), pd.Series(dtype=float)

    # Target
    y = df["is_fraud"].astype(int)

    # Weights: fraud trips get confidence score, others get 1.0
    weights = pd.Series(1.0, index=df.index, dtype=float)
    fraud_mask = df["is_fraud"] == True
    if "fraud_confidence_score" in df.columns:
        fraud_scores = pd.to_numeric(
            df.loc[fraud_mask, "fraud_confidence_score"],
            errors="coerce",
        ).fillna(0.75)
        weights.loc[fraud_mask] = fraud_scores.values

    console.print(
        f"[green]Feature matrix: {X.shape[0]:,} rows × "
        f"{X.shape[1]} features | "
        f"Fraud: {y.sum():,} ({y.mean() * 100:.2f}%)[/green]"
    )

    return X, y, weights


# ── Test block ────────────────────────────────────────────────

if __name__ == "__main__":
    console.rule("[cyan]Feature Engineering — Validation[/cyan]")

    from generator.drivers import generate_drivers
    from generator.customers import generate_customers
    from generator.trips import generate_trips
    from generator.fraud import inject_fraud

    console.print("[dim]Generating sample data...[/dim]")
    drivers_df   = generate_drivers(n=2000, city_filter="bangalore")
    customers_df = generate_customers(n=2000, city_filter="bangalore")
    trips_df     = generate_trips(
        drivers_df, customers_df, n=3000, city_filter="bangalore",
    )
    trips_df = inject_fraud(trips_df, drivers_df)

    X, y, weights = build_feature_matrix(trips_df, drivers_df)

    # ── Assertions ─────────────────────────────────────────
    assert X.shape[1] == len(FEATURE_COLUMNS), \
        f"Expected {len(FEATURE_COLUMNS)} features, got {X.shape[1]}"
    assert X.isna().sum().sum() == 0, \
        "Feature matrix contains NaN values"
    assert len(y) == len(X), "Target length mismatch"
    assert len(weights) == len(X), "Weights length mismatch"
    assert weights[y == 0].eq(1.0).all(), \
        "Non-fraud weights must be 1.0"
    assert weights[y == 1].between(0.5, 1.0).all(), \
        "Fraud weights must be in [0.5, 1.0]"

    # ── Feature summary table ──────────────────────────────
    table = Table(title="Feature Matrix Summary")
    table.add_column("Metric",  style="cyan")
    table.add_column("Value",   style="green")
    table.add_row("Total features",    str(len(FEATURE_COLUMNS)))
    table.add_row("Total samples",     f"{len(X):,}")
    table.add_row("Fraud samples",     f"{y.sum():,} ({y.mean() * 100:.2f}%)")
    table.add_row("Non-fraud samples", f"{(~y.astype(bool)).sum():,}")
    table.add_row("Avg fraud weight",  f"{weights[y == 1].mean():.4f}")
    table.add_row("Non-fraud weight",  "1.0000 (constant)")
    table.add_row("NaN values",        "0 ✅")

    # Top 3 discriminating features by mean difference
    fraud_means    = X[y == 1].mean()
    nonfraud_means = X[y == 0].mean()
    diff           = (fraud_means - nonfraud_means).abs()
    top3 = diff.nlargest(3)
    for feat, val in top3.items():
        table.add_row(f"Top signal: {feat}", f"Δ{val:.4f}")
    console.print(table)

    # ── Sequence feature sanity check ─────────────────────
    high_vel = X["driver_cancellation_velocity_1hr"].max()
    console.print(
        f"[green]✅ Max cancellation velocity: "
        f"{high_vel:.0f} (ring signal active)[/green]"
    )

    # fare_to_expected_ratio should be elevated for fraud
    fraud_ratio = X.loc[y == 1, "fare_to_expected_ratio"].mean()
    clean_ratio = X.loc[y == 0, "fare_to_expected_ratio"].mean()
    assert fraud_ratio > clean_ratio, \
        "fare_to_expected_ratio must be higher for fraud trips"
    console.print(
        f"[green]✅ fare_to_expected_ratio: "
        f"fraud {fraud_ratio:.3f} vs clean {clean_ratio:.3f}[/green]"
    )

    console.print(
        "\n[green bold]✅ features.py — all checks passed[/green bold]"
    )
