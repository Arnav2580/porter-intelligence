"""
Porter Intelligence Platform — Feature Engineering v2

Matches v2 trip schema exactly.
Adds 15 new features: GPS integrity, device signals, POD, loading anomaly,
timing integrity, OTP signals.
Fixes column name mismatches from v1 (status→trip_status, etc.).
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table

from generator.config import (
    RANDOM_SEED, VEHICLE_TYPES, PILOT_SUCCESS_CRITERIA,
    FRAUD_BASE_RATE, LOADING_TIME_NORMS_MIN,
)

console = Console()


# ── Feature definitions ───────────────────────────────────────

FEATURE_COLUMNS: List[str] = [

    # ── Trip-level features ──────────────────────────────────
    "declared_distance_km",
    "actual_trip_duration_mins",      # v2: was declared_duration_min
    "fare_inr",
    "surge_multiplier",
    "zone_demand_at_time",

    # ── Derived trip features ────────────────────────────────
    "fare_to_expected_ratio",         # key fraud signal
    "distance_time_ratio",
    "fare_per_km",
    "pickup_dropoff_haversine_km",
    "distance_vs_haversine_ratio",    # v2: gps_tracked/haversine

    # ── GPS integrity features (NEW v2) ──────────────────────
    "gps_ping_count",                 # low = spoofing signal
    "gps_accuracy_avg_m",             # perfect (<3m) = mock location
    "mock_location_flag",             # device-level spoof signal
    "gps_provider_encoded",           # 0=gps, 1=network, 2=mock
    "avg_speed_kmh",                  # >80 in city = impossible
    "max_speed_kmh",

    # ── Timing integrity features (NEW v2) ───────────────────
    "waiting_time_mins",              # 0 on fake trips
    "loading_time_mins",              # Porter-specific
    "loading_anomaly_score",          # loading_time vs p75 for goods_cat

    # ── POD integrity features (NEW v2) ──────────────────────
    "pod_photo_captured",
    "pod_location_match",             # False = partial delivery signal

    # ── OTP signals (NEW v2) ─────────────────────────────────
    "otp_verified",
    "otp_attempt_count",

    # ── Temporal features ────────────────────────────────────
    "hour_of_day",
    "day_of_week",
    "is_night",
    "is_peak_hour",
    "is_friday",
    "is_late_month",

    # ── Payment features ─────────────────────────────────────
    "payment_is_cash",
    "payment_is_credit",

    # ── Driver behavioural features ──────────────────────────
    "driver_cancellation_velocity_1hr",
    "driver_cancel_rate_rolling_7d",
    "driver_dispute_rate_rolling_14d",
    "driver_trips_last_24hr",
    "driver_cash_trip_ratio_7d",

    # ── Driver profile features ──────────────────────────────
    "driver_account_age_days",
    "driver_rating",
    "driver_lifetime_trips",
    "driver_verification_encoded",
    "driver_payment_type_encoded",

    # ── Geographic features ──────────────────────────────────
    "zone_fraud_rate_rolling_7d",
    "same_zone_trip",

    # ── Status features ──────────────────────────────────────
    "is_cancelled",

]

TARGET_COLUMN = "is_fraud"
WEIGHT_COLUMN = "sample_weight"


def _compute_loading_anomaly(row: pd.Series) -> float:
    """
    loading_time_mins vs p75 for goods_category.
    >1.0 = suspicious. 0 for 2W/3W (no loading charge).
    """
    cat = row.get("goods_category", "other")
    lt = float(row.get("loading_time_mins", 0.0) or 0.0)
    if lt <= 0:
        return 0.0
    norms = LOADING_TIME_NORMS_MIN.get(str(cat), (10.0, 22.0, 45.0))
    p75 = norms[1]
    return round(lt / max(p75, 0.1), 4)


def compute_trip_features(trips_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-trip derived features from v2 schema."""
    df = trips_df.copy()
    df["requested_at"] = pd.to_datetime(df["requested_at"], format="mixed")

    # ── Fare to expected ratio (surge-adjusted) ────────────
    def expected_fare(row: pd.Series) -> float:
        veh = VEHICLE_TYPES.get(row.get("vehicle_type", ""))
        if veh is None:
            return float(row.get("fare_inr", 100))
        return veh.base_fare + veh.per_km_rate * float(row.get("declared_distance_km", 1))

    df["expected_fare"] = df.apply(expected_fare, axis=1)
    surge = df.get("surge_multiplier", pd.Series(1.0, index=df.index)).clip(lower=1.0)
    df["fare_to_expected_ratio"] = (
        df["fare_inr"] / (df["expected_fare"].clip(lower=1.0) * surge)
    ).round(4)

    # ── Distance / time ratio ──────────────────────────────
    dur_col = "actual_trip_duration_mins"
    if dur_col not in df.columns and "declared_duration_min" in df.columns:
        df[dur_col] = df["declared_duration_min"]
    elif dur_col not in df.columns:
        df[dur_col] = 1.0
    df[dur_col] = pd.to_numeric(df[dur_col], errors="coerce").fillna(1.0)

    df["distance_time_ratio"] = (
        df["declared_distance_km"] / df[dur_col].clip(lower=0.1)
    ).round(4)

    # ── Fare per km ───────────────────────────────────────
    df["fare_per_km"] = (
        df["fare_inr"] / df["declared_distance_km"].clip(lower=0.1)
    ).round(2)

    # ── Haversine ─────────────────────────────────────────
    from generator.cities import haversine_km
    df["pickup_dropoff_haversine_km"] = df.apply(
        lambda r: haversine_km(
            r["pickup_lat"], r["pickup_lon"],
            r["dropoff_lat"], r["dropoff_lon"],
        ), axis=1,
    ).round(3)

    # ── distance_vs_haversine_ratio (GPS-tracked / haversine) ─
    if "gps_tracked_distance_km" in df.columns:
        df["distance_vs_haversine_ratio"] = (
            df["gps_tracked_distance_km"]
            / df["pickup_dropoff_haversine_km"].clip(lower=0.1)
        ).round(4)
    else:
        df["distance_vs_haversine_ratio"] = (
            df["declared_distance_km"]
            / df["pickup_dropoff_haversine_km"].clip(lower=0.1)
        ).round(4)

    # ── GPS features ──────────────────────────────────────
    for col, default in [
        ("gps_ping_count", 30),
        ("gps_accuracy_avg_m", 10.0),
        ("mock_location_flag", False),
        ("avg_speed_kmh", 0.0),
        ("max_speed_kmh", 0.0),
    ]:
        if col not in df.columns:
            df[col] = default
    df["gps_ping_count"]    = pd.to_numeric(df["gps_ping_count"], errors="coerce").fillna(30)
    df["gps_accuracy_avg_m"] = pd.to_numeric(df["gps_accuracy_avg_m"], errors="coerce").fillna(10.0)
    df["mock_location_flag"] = df["mock_location_flag"].astype(float)
    df["avg_speed_kmh"]     = pd.to_numeric(df["avg_speed_kmh"], errors="coerce").fillna(0.0)
    df["max_speed_kmh"]     = pd.to_numeric(df["max_speed_kmh"], errors="coerce").fillna(0.0)

    # GPS provider encoding: gps=0, network=1, mock=2
    if "gps_provider" in df.columns:
        prov_map = {"gps": 0, "network": 1, "mock": 2}
        df["gps_provider_encoded"] = df["gps_provider"].map(prov_map).fillna(0).astype(float)
    else:
        df["gps_provider_encoded"] = 0.0

    # ── Timing features ───────────────────────────────────
    for col, default in [
        ("waiting_time_mins", 0.0),
        ("loading_time_mins", 0.0),
    ]:
        if col not in df.columns:
            df[col] = default
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["loading_anomaly_score"] = df.apply(_compute_loading_anomaly, axis=1)

    # ── POD integrity ─────────────────────────────────────
    for col, default in [("pod_photo_captured", False), ("pod_location_match", True)]:
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].astype(float)

    # ── OTP signals ───────────────────────────────────────
    for col, default in [("otp_verified", True), ("otp_attempt_count", 1)]:
        if col not in df.columns:
            df[col] = default
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default).astype(float)

    # ── Temporal ──────────────────────────────────────────
    df["is_friday"]    = (df["day_of_week"] == 4).astype(int)
    df["is_late_month"] = (df["requested_at"].dt.day >= 25).astype(int)

    # ── Payment encoding ──────────────────────────────────
    df["payment_is_cash"]   = (df["payment_mode"] == "cash").astype(int)
    df["payment_is_credit"] = (df["payment_mode"] == "credit").astype(int)

    # ── Zone trip ─────────────────────────────────────────
    df["same_zone_trip"] = (df["pickup_zone_id"] == df["dropoff_zone_id"]).astype(int)

    # ── Cancellation flag — support both v1 (status) and v2 (trip_status) ──
    status_col = "trip_status" if "trip_status" in df.columns else "status"
    if status_col in df.columns:
        df["is_cancelled"] = df[status_col].isin(
            ["cancelled_by_driver", "cancelled_by_customer"]
        ).astype(int)
    else:
        df["is_cancelled"] = 0

    # ── Complaint flag ────────────────────────────────────
    df["has_complaint"] = df.get("customer_complaint_flag", pd.Series(False, index=df.index)).astype(int)

    return df


def compute_driver_features(trips_df: pd.DataFrame, drivers_df: pd.DataFrame) -> pd.DataFrame:
    """Join driver profile features onto trips. Supports v2 schema."""
    # Support both old column names and new v2 names
    rename_map = {}
    if "avg_rating_30d" in drivers_df.columns and "rating" not in drivers_df.columns:
        rename_map["avg_rating_30d"] = "rating"
    if "total_trips_lifetime" not in drivers_df.columns and "trips_last_30d" in drivers_df.columns:
        # fallback: use 30d trips * 12 as lifetime proxy
        drivers_df = drivers_df.copy()
        drivers_df["total_trips_lifetime"] = (drivers_df["trips_last_30d"] * 12).astype(int)
    if "kyc_status" in drivers_df.columns and "verification_status" not in drivers_df.columns:
        rename_map["kyc_status"] = "verification_status"

    drv = drivers_df.rename(columns=rename_map).copy()

    # Encode verification status
    verif_map = {"verified": 0, "pending": 1, "unverified": 2, "expired": 2}
    if "verification_status" in drv.columns:
        drv["driver_verification_encoded"] = drv["verification_status"].map(verif_map).fillna(1).astype(int)
    else:
        drv["driver_verification_encoded"] = 0

    # Encode payment preference
    pay_map = {"upi": 0, "bank": 1, "cash": 2}
    pay_col = "bank_account_type" if "bank_account_type" in drv.columns else None
    if pay_col:
        drv["driver_payment_type_encoded"] = drv[pay_col].map(pay_map).fillna(0).astype(int)
    else:
        drv["driver_payment_type_encoded"] = 0

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
    keep = [c for c in keep if c in drv.columns]

    df = trips_df.merge(drv[keep], on="driver_id", how="left")

    defaults = {
        "driver_account_age_days": 365,
        "driver_rating": 4.0,
        "driver_lifetime_trips": 100,
        "driver_verification_encoded": 0,
        "driver_payment_type_encoded": 0,
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val
        df[col] = pd.to_numeric(df[col].fillna(val), errors="coerce").fillna(val)

    return df


def compute_behavioural_sequence_features(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling behavioural features per driver. Time-ordered cross-trip lookups."""
    df = df.copy()
    df["requested_at"] = pd.to_datetime(df["requested_at"], format="mixed")
    df = df.sort_values("requested_at").reset_index(drop=True)

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

    df["_ts"] = df["requested_at"].astype(np.int64) // 10**9

    cancel_vel_list   = np.zeros(len(df))
    cancel_rate_list  = np.zeros(len(df))
    dispute_rate_list = np.zeros(len(df))
    trips_24hr_list   = np.zeros(len(df))
    cash_ratio_list   = np.zeros(len(df))

    # Status column: support both v1 and v2 schema
    status_col = "trip_status" if "trip_status" in df.columns else "status"

    driver_groups = df.groupby("driver_id", sort=False)
    for driver_id, group in driver_groups:
        indices    = group.index.values
        timestamps = group["_ts"].values

        if status_col in group.columns:
            is_cancelled_arr = group[status_col].isin(
                ["cancelled_by_driver", "cancelled_by_customer"]
            ).astype(int).values
            is_disputed_arr = (group[status_col] == "disputed").astype(int).values
        else:
            is_cancelled_arr = group.get("is_cancelled", pd.Series(0, index=group.index)).values
            is_disputed_arr  = np.zeros(len(group))

        is_cash_arr = (group["payment_mode"] == "cash").astype(int).values

        for i, (idx, ts) in enumerate(zip(indices, timestamps)):
            if i == 0:
                continue
            prior_ts      = timestamps[:i]
            prior_cancel  = is_cancelled_arr[:i]
            prior_dispute = is_disputed_arr[:i]
            prior_cash    = is_cash_arr[:i]

            recent_1hr = (ts - prior_ts) <= 3600
            cancel_vel_list[idx] = float(prior_cancel[recent_1hr].sum())

            recent_7d = (ts - prior_ts) <= 7 * 86400
            if recent_7d.sum() > 0:
                cancel_rate_list[idx] = float(prior_cancel[recent_7d].mean())
                cash_ratio_list[idx]  = float(prior_cash[recent_7d].mean())

            recent_14d = (ts - prior_ts) <= 14 * 86400
            if recent_14d.sum() > 0:
                dispute_rate_list[idx] = float(prior_dispute[recent_14d].mean())

            recent_24hr = (ts - prior_ts) <= 86400
            trips_24hr_list[idx] = float(recent_24hr.sum())

    df["driver_cancellation_velocity_1hr"] = cancel_vel_list
    df["driver_cancel_rate_rolling_7d"]    = cancel_rate_list
    df["driver_dispute_rate_rolling_14d"]  = dispute_rate_list
    df["driver_trips_last_24hr"]           = trips_24hr_list
    df["driver_cash_trip_ratio_7d"]        = cash_ratio_list

    # Zone fraud rate (from historical only — no leakage)
    hist_df = df[df["data_split"] == "historical"].copy() \
        if "data_split" in df.columns else df.copy()

    zone_fraud_map: Dict[str, float] = {}
    for zone_id in df["pickup_zone_id"].unique():
        zone_trips = hist_df[hist_df["pickup_zone_id"] == zone_id]
        zone_fraud_map[zone_id] = float(zone_trips["is_fraud"].mean()) \
            if len(zone_trips) > 0 else FRAUD_BASE_RATE

    df["zone_fraud_rate_rolling_7d"] = df["pickup_zone_id"].map(zone_fraud_map).fillna(FRAUD_BASE_RATE)

    df = df.drop(columns=["_ts"], errors="ignore")
    return df


def build_feature_matrix(
    trips_df:   pd.DataFrame,
    drivers_df: pd.DataFrame,
    fit_mode:   bool = True,
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Full pipeline: raw trips + drivers → feature matrix."""
    console.print("[dim]Building feature matrix v2...[/dim]")

    df = compute_trip_features(trips_df)
    df = compute_driver_features(df, drivers_df)
    df = compute_behavioural_sequence_features(df)

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            console.print(f"[yellow]⚠️  Missing feature '{col}' — filling 0[/yellow]")
            df[col] = 0.0

    X = df[FEATURE_COLUMNS].copy().fillna(0.0).astype(float)

    if not fit_mode:
        return X, pd.Series(dtype=int), pd.Series(dtype=float)

    y = df["is_fraud"].astype(int)

    # Sample weights: fraud trips weighted by confidence, clean trips = 1.0
    weights = pd.Series(1.0, index=df.index, dtype=float)
    fraud_mask = df["is_fraud"] == True
    # v2 schema has no fraud_confidence_score — use uniform 0.85 for fraud
    weights.loc[fraud_mask] = 0.85

    console.print(
        f"[green]Feature matrix v2: {X.shape[0]:,} rows × "
        f"{X.shape[1]} features | "
        f"Fraud: {y.sum():,} ({y.mean() * 100:.2f}%)[/green]"
    )
    return X, y, weights


if __name__ == "__main__":
    console.rule("[cyan]Feature Engineering v2 — Validation[/cyan]")

    from generator.drivers   import generate_drivers
    from generator.customers import generate_customers
    from generator.trips     import generate_trips
    from generator.fraud     import inject_fraud

    drivers_df   = generate_drivers(n=2000, city_filter="bangalore")
    customers_df = generate_customers(n=2000, city_filter="bangalore")
    trips_df     = generate_trips(drivers_df, customers_df, n=3000, city_filter="bangalore")
    trips_df     = inject_fraud(trips_df, drivers_df)

    X, y, weights = build_feature_matrix(trips_df, drivers_df)

    assert X.shape[1] == len(FEATURE_COLUMNS), \
        f"Expected {len(FEATURE_COLUMNS)} features, got {X.shape[1]}"
    assert X.isna().sum().sum() == 0, "Feature matrix has NaN"
    assert len(y) == len(X)

    table = Table(title="Feature Matrix v2 Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value",  style="green")
    table.add_row("Total features",   str(len(FEATURE_COLUMNS)))
    table.add_row("Total samples",    f"{len(X):,}")
    table.add_row("Fraud samples",    f"{y.sum():,} ({y.mean()*100:.2f}%)")
    table.add_row("GPS features",     "6 (ping, accuracy, mock, provider, speed×2)")
    table.add_row("Loading features", "2 (loading_time, loading_anomaly_score)")
    table.add_row("POD features",     "2 (pod_captured, pod_location_match)")
    table.add_row("OTP features",     "2 (otp_verified, otp_attempt_count)")
    console.print(table)
    console.print("[green bold]✅ features.py v2 — all checks passed[/green bold]")
