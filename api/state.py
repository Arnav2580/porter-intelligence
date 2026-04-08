"""
Porter Intelligence Platform — Application State

Global app_state dictionary and lifespan context manager.
Extracted from api/main.py to keep the entry point lean.
"""

import asyncio
import json
import os
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict

from generator.config import MODEL_WEIGHTS, DATA_RAW
from database.connection import init_db
from database.redis_client import cache_set
from logging_config import setup_logging
from runtime_config import get_runtime_settings
from security.settings import validate_security_configuration

# -- Global state (loaded at startup) --
app_state: Dict = {}


def console_log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


@asynccontextmanager
async def lifespan(app):
    """Load model and data at startup. Release at shutdown."""
    import xgboost as xgb
    from generator.cities import ZONES

    setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    runtime = get_runtime_settings()
    app_state["runtime_mode"] = runtime.mode.value
    app_state["synthetic_feed_enabled"] = (
        runtime.synthetic_feed_enabled
    )
    app_state["shadow_mode"] = runtime.shadow_mode
    security_validation = validate_security_configuration()
    app_state["security_validation"] = (
        security_validation.to_dict()
    )
    for warning in security_validation.warnings:
        console_log(f"⚠️  Security warning: {warning}")
    if security_validation.errors:
        for error in security_validation.errors:
            console_log(f"❌ Security config error: {error}")
        if runtime.is_prod:
            raise RuntimeError(
                "Security configuration invalid for prod runtime."
            )
    console_log("Loading Porter Intelligence Platform...")
    console_log(
        f"Runtime mode: {runtime.mode.value} | "
        f"synthetic_feed_enabled={runtime.synthetic_feed_enabled} | "
        f"shadow_mode={runtime.shadow_mode}"
    )

    # Load XGBoost model
    model_path = MODEL_WEIGHTS / "xgb_fraud_model.json"
    if not model_path.exists():
        console_log(
            "Warning: Model not found. Run python train.py first."
        )
        app_state["model"] = None
    else:
        model = xgb.XGBClassifier()
        model.load_model(str(model_path))
        app_state["model"] = model
        console_log("XGBoost model loaded")

    # Load threshold
    thresh_path = MODEL_WEIGHTS / "threshold.json"
    if thresh_path.exists():
        with open(thresh_path) as f:
            app_state["threshold"] = json.load(f)["threshold"]
    else:
        app_state["threshold"] = 0.45

    # Load feature names
    feat_path = MODEL_WEIGHTS / "feature_names.json"
    if feat_path.exists():
        with open(feat_path) as f:
            app_state["feature_names"] = json.load(f)
    else:
        from model.features import FEATURE_COLUMNS
        app_state["feature_names"] = FEATURE_COLUMNS

    # Load evaluation report
    report_path = DATA_RAW / "evaluation_report.json"
    if report_path.exists():
        with open(report_path) as f:
            app_state["report"] = json.load(f)
    else:
        app_state["report"] = {}

    # Load two-stage scoring config
    two_stage_path = MODEL_WEIGHTS / "two_stage_config.json"
    if two_stage_path.exists():
        with open(two_stage_path) as f:
            app_state["two_stage_config"] = json.load(f)
        console_log("Two-stage scoring config loaded")
    else:
        app_state["two_stage_config"] = None

    # Load trips — prefer full scale
    for path in [
        DATA_RAW / "trips_full_fraud.csv",
        DATA_RAW / "trips_with_fraud_10k.csv",
    ]:
        if path.exists():
            app_state["trips_df"] = pd.read_csv(path)
            console_log(
                f"{len(app_state['trips_df']):,} trips "
                f"<- {path.name}"
            )
            break
    else:
        app_state["trips_df"] = pd.DataFrame()
        console_log("No trip data found")

    # Load drivers — prefer full scale
    for path in [
        DATA_RAW / "drivers_full.csv",
        DATA_RAW / "drivers_sample_1000.csv",
    ]:
        if path.exists():
            app_state["drivers_df"] = pd.read_csv(path)
            console_log(
                f"{len(app_state['drivers_df']):,} drivers "
                f"<- {path.name}"
            )
            break
    else:
        app_state["drivers_df"] = pd.DataFrame()
        console_log("No driver data found")

    # Precompute Redis feature store
    try:
        from ml.feature_store import (
            precompute_driver_features,
            precompute_zone_features,
        )
        trips  = app_state.get("trips_df", pd.DataFrame())
        drivers= app_state.get("drivers_df", pd.DataFrame())
        if not trips.empty and not drivers.empty:
            n_drivers = await asyncio.wait_for(
                precompute_driver_features(trips, drivers),
                timeout=30.0,
            )
            n_zones = await asyncio.wait_for(
                precompute_zone_features(trips),
                timeout=20.0,
            )
            console_log(
                f"✅ Feature store ready: "
                f"{n_drivers} drivers, {n_zones} zones"
            )
    except asyncio.TimeoutError:
        console_log("⚠️  Feature store timeout — skipping cache warm")
    except Exception as e:
        console_log(f"⚠️  Feature store failed: {e}")

    app_state["zones"] = ZONES

    # Load demand models
    from model.demand import load_demand_models
    demand_models = load_demand_models()
    app_state["demand_models"] = demand_models
    if demand_models:
        console_log(
            f"{len(demand_models)} demand models loaded"
        )
    else:
        console_log(
            "No demand models found. "
            "Run python model/demand.py first."
        )

    # Preload query context
    from model.query import load_context
    app_state["query_context"] = load_context()
    console_log("Query context preloaded")

    # Initialise database tables
    try:
        await asyncio.wait_for(init_db(), timeout=10.0)
        console_log("✅ Database tables ready")
    except asyncio.TimeoutError:
        console_log("⚠️  Database timeout — running without DB")
    except Exception as e:
        console_log(f"⚠️  Database unavailable: {e}")
        console_log("   Running in CSV-only mode")

    # Precompute route efficiency cache
    if not app_state.get("trips_df", pd.DataFrame()).empty:
        try:
            from model.route_efficiency import (
                compute_dead_mile_rate,
                compute_hourly_utilisation,
                generate_reallocation_suggestions,
            )
            trips = app_state["trips_df"]

            def _build_efficiency_cache():
                dead_mile   = compute_dead_mile_rate(trips)
                utilisation = compute_hourly_utilisation(trips)
                suggestions = generate_reallocation_suggestions(
                    trips, dead_mile, utilisation
                )
                return dead_mile, utilisation, suggestions

            dead_mile, utilisation, suggestions = await asyncio.wait_for(
                asyncio.to_thread(_build_efficiency_cache),
                timeout=30.0,
            )
            app_state["efficiency_cache"] = {
                "dead_mile":   dead_mile,
                "utilisation": utilisation,
                "suggestions": suggestions,
            }
            await cache_set(
                "route-efficiency:bootstrap",
                app_state["efficiency_cache"],
                ttl_seconds=3600,
            )
            app_state["efficiency_cache_hour"] = datetime.now().hour
            console_log(
                f"Route efficiency cache ready "
                f"({len(suggestions)} suggestions)"
            )
        except asyncio.TimeoutError:
            console_log("⚠️  Efficiency cache timeout — skipping")
        except Exception as e:
            console_log(f"Efficiency cache failed: {e}")

    # Precompute top-risk driver rankings
    if not app_state.get("trips_df", pd.DataFrame()).empty:
        try:
            from api.routes.driver_intelligence import (
                _compute_top_risk
            )
            _trips   = app_state["trips_df"]
            _drivers = app_state["drivers_df"]
            app_state["top_risk_cache"] = await asyncio.wait_for(
                asyncio.to_thread(
                    _compute_top_risk, _trips, _drivers, 50
                ),
                timeout=20.0,
            )
            await cache_set(
                "driver-intelligence:bootstrap",
                app_state["top_risk_cache"],
                ttl_seconds=3600,
            )
            app_state["top_risk_cache_hour"] = datetime.now().hour
            console_log("Driver risk cache ready")
        except asyncio.TimeoutError:
            console_log("⚠️  Driver risk cache timeout — skipping")
        except Exception as e:
            console_log(f"Driver risk cache failed: {e}")

    # Start Redis Stream consumer (Phase B)
    _consumer_task = None
    try:
        from ingestion.streams import consume_loop
        _consumer_task = asyncio.create_task(consume_loop())
        console_log("✅ Stream consumer task started")
    except Exception as e:
        console_log(f"⚠️  Stream consumer failed to start: {e}")

    _simulator_task = None
    if runtime.synthetic_feed_enabled:
        try:
            from ingestion.live_simulator import (
                get_simulator_summary,
                run_live_simulator,
            )
            app_state["simulator_summary"] = (
                get_simulator_summary()
            )
            _simulator_task = asyncio.create_task(
                run_live_simulator()
            )
            console_log(
                "✅ Synthetic feed started "
                f"({app_state['simulator_summary']['effective_trips_per_min']:.1f} trips/min, "
                f"{app_state['simulator_summary']['city_count']} cities, "
                f"{app_state['simulator_summary']['base_fraud_rate_pct']:.1f}% base fraud)"
            )
        except Exception as e:
            console_log(f"⚠️  Synthetic feed failed to start: {e}")
    else:
        app_state["simulator_summary"] = None
        console_log(
            "Synthetic feed disabled for this runtime mode"
        )

    # Start APScheduler for drift detection + stream lag (Phase C)
    _scheduler = None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from monitoring.drift import run_drift_check, update_stream_lag_gauge
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            run_drift_check, "interval", minutes=60, id="drift_check"
        )
        _scheduler.add_job(
            update_stream_lag_gauge, "interval", seconds=30, id="stream_lag"
        )
        _scheduler.start()
        console_log("✅ APScheduler started (drift check 60m, stream lag 30s)")
    except Exception as e:
        console_log(f"⚠️  APScheduler failed to start: {e}")

    # Initialise model metadata in Prometheus
    try:
        from monitoring.metrics import MODEL_INFO
        MODEL_INFO.info({
            "version":         str(app_state.get("threshold", 0.45)),
            "threshold":       str(app_state.get("threshold", 0.45)),
            "feature_count":   str(len(app_state.get("feature_names", []))),
        })
    except Exception:
        pass

    console_log("Porter Intelligence Platform ready")

    yield

    # Cleanup
    if _simulator_task is not None:
        _simulator_task.cancel()
        try:
            await _simulator_task
        except asyncio.CancelledError:
            pass

    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)

    app_state.clear()
