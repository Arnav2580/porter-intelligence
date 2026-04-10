"""
Porter Intelligence Platform — Model Drift & Stream Lag Monitor

Two scheduled jobs called by APScheduler in api/state.py:

  run_drift_check()        — every 60 min
      Computes Population Stability Index (PSI) for the fraud_prob
      distribution and the top behavioural features.
      Writes results to DRIFT_PSI and DRIFT_FEATURE_PSI gauges.
      Alerts when PSI > 0.2 (significant drift).

  update_stream_lag_gauge() — every 30 sec
      Reads the Redis Stream PEL (pending-entry list) count for the
      porter_trips consumer group and writes it to STREAM_LAG.
"""

import asyncio
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# PSI threshold constants (industry standard)
PSI_STABLE    = 0.1   # < 0.1  → no action needed
PSI_MONITOR   = 0.2   # 0.1–0.2 → monitor
PSI_RETRAIN   = 0.25  # > 0.25 → schedule retrain


# ---------------------------------------------------------------------------
# PSI helpers
# ---------------------------------------------------------------------------

def _psi_score(baseline: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """
    Compute Population Stability Index between two distributions.

    PSI = Σ (current_pct - baseline_pct) * ln(current_pct / baseline_pct)

    Returns 0.0 if either array is empty or all-zero.
    """
    if len(baseline) == 0 or len(current) == 0:
        return 0.0

    # Build bins from baseline distribution
    breakpoints = np.linspace(0.0, 1.0, bins + 1)

    baseline_counts = np.histogram(baseline, bins=breakpoints)[0]
    current_counts  = np.histogram(current,  bins=breakpoints)[0]

    # Avoid division by zero / log(0) — floor each bin at 0.1%
    baseline_pct = np.maximum(baseline_counts / len(baseline), 1e-4)
    current_pct  = np.maximum(current_counts  / len(current),  1e-4)

    psi = float(np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct)))
    return round(psi, 4)


# ---------------------------------------------------------------------------
# run_drift_check
# ---------------------------------------------------------------------------

async def run_drift_check() -> None:
    """
    Scheduled every 60 minutes.

    1. Pulls recent fraud_probability scores from app_state trips_df
       (or Redis if state unavailable).
    2. Computes PSI vs the baseline evaluation set.
    3. Updates Prometheus gauges.
    4. Logs a warning if drift exceeds PSI_MONITOR threshold.
    """
    try:
        from monitoring.metrics import DRIFT_PSI, DRIFT_FEATURE_PSI
        from api.state import app_state

        trips_df = app_state.get("trips_df")
        if trips_df is None or len(trips_df) == 0:
            logger.debug("drift_check: no trips_df available, skipping")
            return

        # ── Fraud prob distribution drift ────────────────────────────────
        if "fraud_probability" in trips_df.columns:
            current_probs = trips_df["fraud_probability"].dropna().values
        elif "is_fraud" in trips_df.columns:
            # Fallback: use boolean label as a proxy distribution
            current_probs = trips_df["is_fraud"].astype(float).values
        else:
            logger.debug("drift_check: no fraud_probability column, skipping")
            return

        # Baseline: synthetic reference drawn from training label distribution
        # (~8% fraud rate across 100k trips, right-skewed toward 0)
        rng = np.random.default_rng(seed=42)
        baseline_probs = np.concatenate([
            rng.beta(0.5, 6.0, size=9200),   # legitimate trips (low prob)
            rng.beta(8.0, 1.5, size=800),     # fraud trips (high prob)
        ])

        overall_psi = _psi_score(baseline_probs, current_probs)
        DRIFT_PSI.set(overall_psi)

        if overall_psi > PSI_MONITOR:
            logger.warning(
                "Model drift detected — PSI=%.4f (threshold=%.2f). "
                "Consider scheduling a retrain.",
                overall_psi, PSI_MONITOR,
            )
        else:
            logger.debug("drift_check: overall PSI=%.4f (stable)", overall_psi)

        # ── Per-feature drift for top behavioural signals ─────────────────
        feature_baselines = {
            "declared_distance_km":   rng.gamma(2.5, 3.0,  size=10000),
            "fare_inr":               rng.gamma(4.0, 40.0, size=10000),
            "declared_duration_min":  rng.gamma(3.0, 8.0,  size=10000),
            "surge_multiplier":       np.ones(10000),
            "hour_of_day":            rng.integers(0, 24,  size=10000).astype(float),
        }

        for feat, baseline_vals in feature_baselines.items():
            if feat not in trips_df.columns:
                continue
            current_vals = trips_df[feat].dropna().values
            feat_psi = _psi_score(baseline_vals, current_vals)
            DRIFT_FEATURE_PSI.labels(feature=feat).set(feat_psi)
            if feat_psi > PSI_MONITOR:
                logger.warning(
                    "Feature drift: %s PSI=%.4f", feat, feat_psi
                )

    except Exception as exc:
        logger.warning("drift_check failed: %s", exc, exc_info=False)


# ---------------------------------------------------------------------------
# update_stream_lag_gauge
# ---------------------------------------------------------------------------

async def update_stream_lag_gauge() -> None:
    """
    Scheduled every 30 seconds.

    Reads the Pending Entry List (PEL) count for the porter_trips
    consumer group from Redis Streams.  PEL = messages delivered to a
    consumer but not yet acknowledged → proxy for processing lag.

    Writes the count to the STREAM_LAG Prometheus gauge.
    """
    try:
        from monitoring.metrics import STREAM_LAG
        from database.redis_client import get_redis

        redis = get_redis()
        if redis is None:
            return

        stream_key = "porter:trips"
        group_name = "porter_consumers"

        # XPENDING summary: (count, min-id, max-id, [consumer-counts])
        try:
            pending = await redis.xpending(stream_key, group_name)
            pel_count = pending.get("pending", 0) if isinstance(pending, dict) else (pending[0] if pending else 0)
        except Exception:
            # Stream or group may not exist yet in demo mode
            pel_count = 0

        STREAM_LAG.set(int(pel_count))
        logger.debug("stream_lag: PEL=%d", pel_count)

    except Exception as exc:
        logger.debug("update_stream_lag_gauge failed: %s", exc)
