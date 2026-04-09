"""
Model drift detection — Phase C.

Uses Population Stability Index (PSI) to compare the current distribution
of fraud probability scores against the baseline captured at training time.

PSI < 0.1  → no significant drift
PSI < 0.2  → moderate drift (monitor)
PSI >= 0.2 → significant drift (retrain recommended)

Runs as an APScheduler job every hour, updates the DRIFT_PSI Prometheus gauge,
and logs a warning when drift crosses the threshold.
"""

import logging
import numpy as np
from typing import List, Optional

logger = logging.getLogger(__name__)

PSI_MODERATE  = 0.1
PSI_CRITICAL  = 0.2
N_BINS        = 10
BASELINE_KEY  = "model:baseline_prob_hist"
WINDOW_KEY    = "model:recent_prob_scores"
WINDOW_SIZE   = 5000   # keep last N scores in Redis list


def _compute_psi(
    expected: np.ndarray,
    actual: np.ndarray,
    bins: int = N_BINS,
) -> float:
    """
    Compute PSI between two 1-D arrays of fraud probabilities.
    Both arrays contain values in [0, 1].
    """
    breakpoints = np.linspace(0.0, 1.0, bins + 1)
    expected_pcts = np.histogram(expected, bins=breakpoints)[0]
    actual_pcts   = np.histogram(actual,   bins=breakpoints)[0]

    # Avoid division by zero — replace 0 counts with a small epsilon
    eps = 1e-6
    expected_pcts = np.where(expected_pcts == 0, eps, expected_pcts)
    actual_pcts   = np.where(actual_pcts   == 0, eps, actual_pcts)

    expected_pcts = expected_pcts / expected_pcts.sum()
    actual_pcts   = actual_pcts   / actual_pcts.sum()

    psi = float(
        np.sum((actual_pcts - expected_pcts) * np.log(actual_pcts / expected_pcts))
    )
    return round(psi, 4)


async def record_score(fraud_prob: float) -> None:
    """
    Append a fraud probability to the rolling Redis window.
    Called by the scoring path after each inference.
    Trims to the last WINDOW_SIZE entries.
    """
    try:
        from database.redis_client import get_redis
        redis = get_redis()
        await redis.rpush(WINDOW_KEY, str(round(fraud_prob, 4)))
        await redis.ltrim(WINDOW_KEY, -WINDOW_SIZE, -1)
    except Exception:
        pass   # non-critical — drift detection is best-effort


async def save_baseline(scores: List[float]) -> None:
    """
    Store the training-time fraud probability distribution as a baseline histogram.
    Called once at the end of training (or from train.py).
    """
    from database.redis_client import cache_set
    breakpoints = np.linspace(0.0, 1.0, N_BINS + 1)
    hist, _ = np.histogram(np.array(scores), bins=breakpoints)
    await cache_set(BASELINE_KEY, hist.tolist(), ttl_seconds=0)  # no expiry


async def run_drift_check() -> Optional[float]:
    """
    APScheduler job: compute PSI between baseline and recent scores.
    Updates DRIFT_PSI gauge and logs warnings on threshold breach.
    Returns computed PSI or None if insufficient data.
    """
    from database.redis_client import get_redis, cache_get
    from monitoring.metrics import DRIFT_PSI

    redis = get_redis()

    try:
        # Load baseline histogram
        baseline_hist = await cache_get(BASELINE_KEY)
        if baseline_hist is None:
            logger.debug("No baseline histogram found — skipping drift check")
            return None

        # Load recent scores
        recent_raw = await redis.lrange(WINDOW_KEY, 0, -1)
        if len(recent_raw) < 100:
            logger.debug(
                f"Only {len(recent_raw)} recent scores — need 100 for drift check"
            )
            return None

        recent_scores = np.array([float(x) for x in recent_raw])
        baseline_arr  = np.array(baseline_hist)

        # Reconstruct baseline probability array from histogram
        breakpoints    = np.linspace(0.0, 1.0, N_BINS + 1)
        bin_midpoints  = (breakpoints[:-1] + breakpoints[1:]) / 2
        baseline_probs = np.repeat(bin_midpoints, baseline_arr.astype(int))

        psi = _compute_psi(baseline_probs, recent_scores)
        DRIFT_PSI.set(psi)

        if psi >= PSI_CRITICAL:
            logger.warning(
                f"CRITICAL model drift detected: PSI={psi:.4f} "
                f"(threshold={PSI_CRITICAL}). Retrain recommended."
            )
        elif psi >= PSI_MODERATE:
            logger.warning(
                f"Moderate model drift: PSI={psi:.4f} "
                f"(threshold={PSI_MODERATE}). Monitor closely."
            )
        else:
            logger.info(f"Model drift check passed: PSI={psi:.4f}")

        return psi

    except Exception as e:
        logger.error(f"Drift check failed: {e}")
        return None


async def update_stream_lag_gauge() -> None:
    """Update the STREAM_LAG Prometheus gauge with current Redis Stream PEL count."""
    try:
        from ingestion.streams import get_stream_lag
        from monitoring.metrics import STREAM_LAG
        lag = await get_stream_lag()
        STREAM_LAG.set(lag)
    except Exception:
        pass
