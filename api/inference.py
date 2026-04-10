"""
Porter Intelligence Platform — ML Inference Endpoints

All fraud scoring, demand forecasting, and KPI endpoints.
Registered as an APIRouter in api/main.py.
"""

import pandas as pd
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, HTTPException, Request

from api.limiting import limiter
from api.schemas import (
    TripScoreRequest, TripScoreResponse,
    HeatmapResponse, LiveFeedResponse,
    KPISummaryResponse, DriverRiskResponse,
    ZoneFraudRate, FraudFeedItem,
)
from api.state import app_state
from database.case_store import persist_flagged_case, should_enforce_actions
from security.settings import get_rate_limit

router = APIRouter(tags=["platform"])


@router.get(
    "/fraud/heatmap",
    response_model=HeatmapResponse,
)
async def fraud_heatmap():
    """
    Zone-level fraud rate heatmap for the live map.
    Returns fraud rate per zone with risk classification.
    """
    trips_df = app_state.get("trips_df", pd.DataFrame())
    zones    = app_state.get("zones", {})

    if trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Trip data not loaded",
        )

    zone_stats = (
        trips_df.groupby("pickup_zone_id")
        .agg(
            total_trips  = ("trip_id", "count"),
            fraud_count  = ("is_fraud", "sum"),
        )
        .reset_index()
    )
    zone_stats["fraud_rate"] = (
        zone_stats["fraud_count"] / zone_stats["total_trips"]
    )

    zone_items = []
    for _, row in zone_stats.iterrows():
        zid  = row["pickup_zone_id"]
        zone = zones.get(zid)
        if zone is None:
            continue

        rate = float(row["fraud_rate"])
        risk = (
            "CRITICAL" if rate > 0.12 else
            "HIGH"     if rate > 0.08 else
            "MEDIUM"   if rate > 0.04 else
            "LOW"
        )

        zone_items.append(ZoneFraudRate(
            zone_id     = zid,
            zone_name   = zone.name,
            city        = zone.city,
            lat         = zone.lat,
            lon         = zone.lon,
            fraud_rate  = round(rate, 4),
            fraud_count = int(row["fraud_count"]),
            risk_level  = risk,
        ))

    return HeatmapResponse(
        zones        = zone_items,
        total_trips  = int(trips_df.shape[0]),
        total_fraud  = int(trips_df["is_fraud"].sum()),
        generated_at = datetime.now().isoformat(),
    )


@router.get(
    "/fraud/live-feed",
    response_model=LiveFeedResponse,
)
async def fraud_live_feed(limit: int = 50):
    """
    Fraud-flagged trip feed.

    When the live simulator is running (ENABLE_SYNTHETIC_FEED=true), items are
    from the live stream and flagged_at timestamps are current.
    When the simulator is off, items are drawn from the benchmark CSV and
    is_benchmark=true is set on the response so the UI can label them correctly.
    """
    trips_df = app_state.get("trips_df", pd.DataFrame())
    synthetic_feed_enabled = app_state.get("synthetic_feed_enabled", False)

    if trips_df.empty:
        return LiveFeedResponse(
            items=[], total_shown=0,
            is_benchmark=not synthetic_feed_enabled,
        )

    fraud_df = trips_df[trips_df["is_fraud"] == True].copy()
    fraud_df = fraud_df.sort_values(
        "requested_at", ascending=False,
    ).head(limit)

    items = []
    for _, row in fraud_df.iterrows():
        items.append(FraudFeedItem(
            trip_id    = str(row["trip_id"]),
            driver_id  = str(row["driver_id"])[:8] + "...",
            zone_id    = str(row["pickup_zone_id"]),
            fraud_type = str(row["fraud_type"]),
            confidence = float(row.get(
                "fraud_confidence_score", 0.75,
            )),
            fare_inr       = float(row["fare_inr"]),
            recoverable    = float(row.get(
                "recoverable_amount_inr", 0,
            )),
            flagged_at = str(row["requested_at"]),
        ))

    return LiveFeedResponse(
        items           = items,
        total_shown     = len(items),
        is_benchmark    = not synthetic_feed_enabled,
    )


@router.get(
    "/fraud/driver/{driver_id}",
    response_model=DriverRiskResponse,
)
async def driver_risk(driver_id: str):
    """
    Risk profile for a specific driver.
    Used for drill-down in the dashboard.
    """
    trips_df   = app_state.get("trips_df", pd.DataFrame())
    drivers_df = app_state.get("drivers_df", pd.DataFrame())

    driver_trips = trips_df[
        trips_df["driver_id"] == driver_id
    ] if not trips_df.empty else pd.DataFrame()

    if driver_trips.empty:
        return DriverRiskResponse(
            driver_id         = driver_id,
            risk_score        = 0.0,
            risk_level        = "UNKNOWN",
            recent_fraud_rate = 0.0,
            cancel_velocity   = 0.0,
            ring_member       = False,
            recommendation    = "No data available for this driver.",
        )

    fraud_rate = float(driver_trips["is_fraud"].mean())
    cancel_rate = float(
        driver_trips["status"].isin([
            "cancelled_by_driver",
        ]).mean()
    )

    # Check ring membership
    ring_member = False
    if not drivers_df.empty:
        drv_row = drivers_df[
            drivers_df["driver_id"] == driver_id
        ]
        if not drv_row.empty and "fraud_ring_id" in drv_row.columns:
            ring_member = pd.notna(
                drv_row["fraud_ring_id"].iloc[0]
            )

    risk_score = min(1.0, fraud_rate * 10 + cancel_rate * 2)
    risk_level = (
        "CRITICAL" if risk_score > 0.7 else
        "HIGH"     if risk_score > 0.4 else
        "MEDIUM"   if risk_score > 0.2 else
        "LOW"
    )

    recommendation = (
        "Immediate suspension recommended."
        if risk_level == "CRITICAL" else
        "Flag for manual review."
        if risk_level == "HIGH" else
        "Monitor closely."
        if risk_level == "MEDIUM" else
        "No action required."
    )

    return DriverRiskResponse(
        driver_id         = driver_id,
        risk_score        = round(risk_score, 4),
        risk_level        = risk_level,
        recent_fraud_rate = round(fraud_rate, 4),
        cancel_velocity   = round(cancel_rate, 4),
        ring_member       = ring_member,
        recommendation    = recommendation,
    )


@router.get("/demand/forecast/{zone_id}")
async def demand_forecast(zone_id: str):
    """
    Next 24-hour demand forecast for a zone.
    Uses Prophet ML model if available, falls back to rule-based.
    """
    from generator.cities import ZONES, get_zone_demand_pattern
    from model.demand import forecast_zone
    import datetime as dt

    zone = ZONES.get(zone_id)
    if zone is None:
        raise HTTPException(
            status_code=404,
            detail=f"Zone {zone_id} not found",
        )

    demand_models = app_state.get("demand_models", {})

    # ML path — Prophet model available for this zone
    if zone_id in demand_models:
        forecast_df = forecast_zone(
            demand_models[zone_id], zone_id, hours_ahead=24,
        )
        forecast = []
        for _, row in forecast_df.iterrows():
            forecast.append({
                "hour":              int(row["hour"]),
                "hour_label":        row["hour_label"],
                "demand_multiplier": float(row["demand_multiplier"]),
                "expected_trips":    max(0, round(float(row["yhat"]))),
                "surge_expected":    bool(row["surge_expected"]),
                "yhat_lower":        float(row["yhat_lower"]),
                "yhat_upper":        float(row["yhat_upper"]),
                "confidence_pct":    float(row["confidence_pct"]),
            })

        return {
            "zone_id":      zone_id,
            "zone_name":    zone.name,
            "city":         zone.city,
            "forecast":     forecast,
            "model":        "prophet_ml",
            "generated_at": dt.datetime.now().isoformat(),
        }

    # Fallback — rule-based demand pattern
    now = dt.datetime.now()
    forecast = []
    for h in range(24):
        hour   = (now.hour + h) % 24
        dow    = now.weekday()
        demand = get_zone_demand_pattern(zone, hour, dow)
        forecast.append({
            "hour":              hour,
            "hour_label":        f"{hour:02d}:00",
            "demand_multiplier": round(demand, 3),
            "expected_trips":    int(demand * 45),
            "surge_expected":    demand > 1.8,
        })

    return {
        "zone_id":      zone_id,
        "zone_name":    zone.name,
        "city":         zone.city,
        "forecast":     forecast,
        "model":        "rule_based",
        "generated_at": now.isoformat(),
    }


@router.get(
    "/kpi/summary",
    response_model=KPISummaryResponse,
)
async def kpi_summary():
    """
    Evaluation benchmark summary used by management and buyer review.
    """
    report = app_state.get("report", {})

    if not report:
        raise HTTPException(
            status_code=503,
            detail="Evaluation report not loaded. Run train.py.",
        )

    xgb      = report.get("xgboost", {})
    two_stage = report.get("two_stage", {})
    base     = report.get("baseline", {})
    annual   = report.get("annual_extrapolation", {})

    total_trips = int(
        xgb.get("total_trips", two_stage.get("total_trips", 0))
    )
    fraud_caught = int(
        xgb.get("fraud_caught", two_stage.get("action_tier_caught", 0))
    )
    net_per_trip = float(
        xgb.get(
            "net_recoverable_per_trip",
            two_stage.get("net_recoverable_per_trip", 0),
        )
    )
    net_rec = float(
        xgb.get(
            "net_recoverable_inr",
            two_stage.get("net_recoverable_inr", 0),
        )
    )
    if total_trips > 0 and net_per_trip > 0:
        reconciled = round(net_per_trip * total_trips, 2)
        if net_rec <= 0 or abs((net_rec / total_trips) - net_per_trip) >= 0.01:
            net_rec = reconciled

    annual_rec_crore = annual.get("net_recoverable_crore", 0)

    return KPISummaryResponse(
        evaluation_window_label = (
            "synthetic evaluation window (14-day scored benchmark)"
        ),
        total_trips      = total_trips,
        fraud_detected   = fraud_caught,
        fraud_rate_pct   = round(
            xgb.get("total_fraud", 0)
            / max(total_trips, 1) * 100, 2,
        ),
        baseline_caught  = base.get("fraud_caught", 0),
        xgboost_caught   = fraud_caught,
        improvement_pct  = report.get("improvement_pct", 0),
        net_recoverable_inr = net_rec,
        net_recoverable_per_trip = net_per_trip,
        fpr_pct          = round(xgb.get("fpr", 0) * 100, 2),
        projected_annual_recovery_crore = annual_rec_crore,
        performance_criteria = xgb.get("pilot_pass", {}),
    )


@router.get("/kpi/report")
async def kpi_report():
    """Sanitized evaluation report for buyer-safe inspection."""
    report = app_state.get("report", {})
    if not report:
        return {}

    def _sanitize(value):
        if isinstance(value, dict):
            sanitized = {}
            for key, item in value.items():
                if key == "royalty_at_4pct_crore":
                    continue
                mapped_key = {
                    "annual_extrapolation": "annual_impact_estimate",
                    "pilot_pass": "performance_criteria",
                    "pilot_ready": "performance_ready",
                }.get(key, key)
                sanitized[mapped_key] = _sanitize(item)
            return sanitized
        if isinstance(value, list):
            return [_sanitize(item) for item in value]
        return value

    return _sanitize(report)


# Human-readable labels and normalisation ranges for each feature.
# normalise_max: the value at which a feature is "at maximum concern".
_SIGNAL_META = {
    "driver_lifetime_trips":          ("New/unverified driver account",       50,    True),   # low = bad
    "fare_to_expected_ratio":         ("Fare inflated {v:.2f}×",              3.0,   False),
    "driver_cancellation_velocity_1hr": ("Cancellations this hour: {v:.0f}", 10.0,  False),
    "distance_vs_haversine_ratio":    ("Distance inflated {v:.2f}×",          3.0,   False),
    "driver_cancel_rate_rolling_7d":  ("Cancel rate {v:.0%} (7d)",            0.5,   False),
    "driver_dispute_rate_rolling_14d":("Dispute rate {v:.0%} (14d)",          0.3,   False),
    "driver_cash_trip_ratio_7d":      ("Cash ratio {v:.0%} (7d)",             1.0,   False),
    "zone_fraud_rate_rolling_7d":     ("Zone fraud rate {v:.1%}",             0.20,  False),
    "payment_is_cash":                ("Cash payment",                        1.0,   False),
    "is_night":                       ("Night-time trip",                     1.0,   False),
    "same_zone_trip":                 ("Pickup = dropoff zone",               1.0,   False),
    "distance_time_ratio":            ("Speed anomaly ({v:.2f} km/min)",       2.0,   False),
}


def _build_top_signals(
    feature_vals: dict,
    feature_names: list,
    model,
    fraud_prob: float,
    is_fraud: bool,
    n: int = 4,
) -> list:
    """
    Return up to *n* human-readable signal strings ranked by
    (feature_importance × normalised_feature_value).

    This is a lightweight SHAP substitute — no extra dependency,
    runs in microseconds, and is model-grounded.
    """
    importances: dict = {}
    try:
        raw = model.feature_importances_
        importances = {name: float(imp) for name, imp in zip(feature_names, raw)}
    except Exception:
        pass  # model may not expose feature_importances_

    scored: list = []
    for feat, (label_tmpl, norm_max, invert) in _SIGNAL_META.items():
        val = feature_vals.get(feat, 0.0)
        if val == 0.0 and not invert:
            continue  # zero contribution — skip

        # Normalise to [0, 1]
        if invert:
            normed = max(0.0, 1.0 - float(val) / max(norm_max, 1.0))
        else:
            normed = min(float(val) / max(norm_max, 1.0), 1.0)

        importance = importances.get(feat, 0.01)
        score = importance * normed

        if score > 0.001:
            try:
                label = label_tmpl.format(v=val)
            except (KeyError, ValueError):
                label = label_tmpl
            scored.append((score, label))

    scored.sort(key=lambda x: x[0], reverse=True)
    signals = [label for _, label in scored[:n]]

    if not signals:
        signals = [f"Fraud probability: {fraud_prob * 100:.1f}%"]

    return signals


@router.post(
    "/fraud/score",
    response_model=TripScoreResponse,
)
@limiter.limit(get_rate_limit("FRAUD_SCORE_RATE_LIMIT", "100/minute"))
async def score_trip(request: Request, body: TripScoreRequest):
    """
    Real-time fraud scoring for a single trip.
    Returns fraud probability, prediction, and top signals.
    """
    model     = app_state.get("model")
    threshold = app_state.get("threshold", 0.45)

    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Run the training pipeline first.",
        )

    import logging
    logger = logging.getLogger(__name__)

    trip_dict     = body.model_dump()
    feature_names = app_state.get("feature_names", [])
    two_stage     = app_state.get("two_stage_config", {})
    
    fraud_prob   = None
    feature_vals = {}
    is_fraud     = False

    # Try stateless scoring first (production path)
    try:
        from ml.stateless_scorer import score_trip_stateless
        from model.scoring import get_tier
        
        if model and feature_names:
            result = await score_trip_stateless(
                trip_dict, model,
                feature_names, two_stage
            )
            fraud_prob    = result["fraud_probability"]
            tier          = get_tier(fraud_prob)
            auto_escalate = tier.auto_escalate
            is_fraud      = fraud_prob >= threshold
            # Feature values returned directly — no second Redis round-trip
            feature_vals  = result.get("feature_vals", {})
            
    except Exception as e:
        logger.warning(
            f"Stateless scorer failed, "
            f"falling back to pandas: {e}"
        )

    if fraud_prob is None:
        # Pandas fallback — only reached when stateless scorer fails.
        # Wrapped in a 5s timeout so a stuck compute_trip_features call
        # doesn't block the request thread indefinitely.
        import asyncio

        def _pandas_score():
            from model.features import (
                compute_trip_features,
                compute_behavioural_sequence_features,
                FEATURE_COLUMNS,
                compute_driver_features,
            )
            trips_df  = pd.DataFrame([trip_dict])
            trips_df["is_fraud"] = False
            if "is_cancelled" not in trips_df:
                trips_df["is_cancelled"] = 0
            if "customer_complaint_flag" not in trips_df:
                trips_df["customer_complaint_flag"] = False
            if "data_split" not in trips_df:
                trips_df["data_split"] = "historical"
            drivers_df = app_state.get("drivers_df", pd.DataFrame())
            trips_df = compute_trip_features(trips_df)
            trips_df = compute_driver_features(trips_df, drivers_df)
            trips_df = compute_behavioural_sequence_features(trips_df)
            for col in FEATURE_COLUMNS:
                if col not in trips_df.columns:
                    trips_df[col] = 0.0
            X = trips_df[FEATURE_COLUMNS].fillna(0.0).astype(float)
            return float(model.predict_proba(X)[0, 1]), X.iloc[0].to_dict()

        try:
            loop = asyncio.get_event_loop()
            pandas_result = await asyncio.wait_for(
                loop.run_in_executor(None, _pandas_score),
                timeout=5.0,
            )
            fraud_prob, _fvals = pandas_result
            feature_vals = _fvals
        except asyncio.TimeoutError:
            logger.error("Pandas fallback timed out after 5s for trip %s", body.trip_id)
            raise HTTPException(status_code=503, detail="Scoring timed out")
        is_fraud = fraud_prob >= threshold

        # Two-stage tier assignment
        from model.scoring import get_tier
        tier = get_tier(fraud_prob)
        auto_escalate = tier.auto_escalate

    risk_level = (
        "CRITICAL" if fraud_prob > 0.85 else
        "HIGH"     if fraud_prob > 0.65 else
        "MEDIUM"   if fraud_prob > threshold else
        "LOW"
    )

    confidence_label = (
        "high"   if fraud_prob > 0.80 or fraud_prob < 0.20 else
        "medium" if fraud_prob > 0.60 or fraud_prob < 0.40 else
        "low"
    )

    # Top signals — ranked by (feature_importance × normalised_value)
    # Uses XGBoost's own feature_importances_ so signals reflect what
    # the model actually weighted, not hardcoded rule thresholds.
    top_signals = _build_top_signals(
        feature_vals, feature_names, model, fraud_prob, is_fraud
    )

    # Persist to database if action or watchlist
    if tier.name in ("action", "watchlist"):
        try:
            await persist_flagged_case(
                trip_id=str(body.trip_id),
                driver_id=str(body.driver_id),
                zone_id=body.pickup_zone_id,
                tier=tier.name,
                fraud_probability=fraud_prob,
                top_signals=top_signals,
                fare_inr=body.fare_inr,
                recoverable_inr=round(body.fare_inr * 0.15, 2),
                auto_escalated=auto_escalate,
                source_channel="api_score",
            )
        except Exception as exc:
            logger.error(
                "Failed to persist scored fraud case for %s: %s",
                body.trip_id,
                exc,
            )

    # Emit Prometheus counter
    try:
        from monitoring.metrics import TRIPS_SCORED
        TRIPS_SCORED.labels(tier=tier.name, path="stateless").inc()
    except Exception:
        pass

    # Fire enforcement webhook for action tier (non-blocking)
    if tier.name == "action" and should_enforce_actions():
        import asyncio
        from enforcement.dispatch import auto_enforce
        asyncio.create_task(
            auto_enforce(
                driver_id         = body.driver_id,
                trip_id           = body.trip_id,
                fraud_probability = fraud_prob,
                tier              = tier.name,
                top_signals       = top_signals,
            )
        )

    return TripScoreResponse(
        trip_id            = body.trip_id,
        fraud_probability  = round(fraud_prob, 4),
        tier               = tier.name,
        tier_label         = tier.label,
        tier_color         = tier.color,
        is_fraud_predicted = is_fraud,
        fraud_risk_level   = risk_level,
        action_required    = tier.action,
        auto_escalate      = auto_escalate,
        top_signals        = top_signals[:3],
        confidence         = confidence_label,
        scored_at          = datetime.now().isoformat(),
    )


@router.get("/fraud/tier-summary")
async def fraud_tier_summary():
    """
    Two-stage scoring tier summary.
    Returns per-tier metrics and combined system performance.
    """
    config = app_state.get("two_stage_config")
    report = app_state.get("report", {})
    two_stage = report.get("two_stage", {})

    if not config and not two_stage:
        raise HTTPException(
            status_code=503,
            detail="Two-stage config not loaded. "
                   "Run the scoring evaluation pipeline first.",
        )

    from model.scoring import TIERS

    tiers = []
    for tier_name, tier in TIERS.items():
        tiers.append({
            "name":           tier.name,
            "label":          tier.label,
            "threshold_low":  tier.threshold_low,
            "threshold_high": tier.threshold_high,
            "color":          tier.color,
            "action":         tier.action,
            "auto_escalate":  tier.auto_escalate,
        })

    evaluation = config.get("evaluation", {}) if config else {}
    performance_criteria = config.get("pilot_pass", {}) if config else {}

    return {
        "tiers":                tiers,
        "evaluation":           evaluation,
        "performance_criteria": performance_criteria,
        "two_stage":            two_stage,
        "generated_at":         datetime.now().isoformat(),
    }
