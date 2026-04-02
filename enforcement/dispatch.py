"""
Automated enforcement webhook.

When fraud score reaches action tier (>= 0.94),
fires HTTP payload to Porter's dispatch system.

Porter provides PORTER_DISPATCH_URL after pilot sign.
Until then: logs the action, no HTTP call made.
This allows testing the full flow without
requiring Porter's system to be connected.
"""

import os
import logging
import httpx
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

PORTER_DISPATCH_URL = os.getenv("PORTER_DISPATCH_URL", "")
ACTION_THRESHOLD    = 0.94
DISPATCH_TIMEOUT    = 5.0   # seconds


async def notify_dispatch(
    driver_id:         str,
    trip_id:           str,
    fraud_probability: float,
    tier:              str,
    top_signals:       List[str],
    action:            str = "flag",
) -> Dict:
    """
    Notify Porter's dispatch system of a fraud detection.
    Returns result dict including whether notification was sent.
    """
    payload = {
        "event_type":         "fraud_detection_alert",
        "driver_id":          driver_id,
        "trip_id":            trip_id,
        "fraud_probability":  fraud_probability,
        "confidence_tier":    tier,
        "recommended_action": action,
        "top_signals":        top_signals,
        "timestamp":          datetime.utcnow().isoformat(),
        "source":             "porter_intelligence_platform",
        "platform_version":   "1.0.0",
    }

    # Always log — creates audit trail even
    # before Porter connects their system
    logger.info(
        f"ENFORCEMENT: driver={driver_id} "
        f"trip={trip_id} prob={fraud_probability:.3f} "
        f"action={action} tier={tier}"
    )

    if not PORTER_DISPATCH_URL:
        # Log-only mode — Porter has not yet
        # provided their dispatch webhook URL
        logger.info(
            f"Dispatch URL not configured. "
            f"Action logged only: {action} on {driver_id}"
        )
        return {
            "sent":      False,
            "mode":      "log_only",
            "action":    action,
            "driver_id": driver_id,
            "logged_at": datetime.utcnow().isoformat(),
        }

    try:
        async with httpx.AsyncClient(
            timeout=DISPATCH_TIMEOUT
        ) as client:
            response = await client.post(
                PORTER_DISPATCH_URL,
                json=payload,
                headers={
                    "Content-Type":
                        "application/json",
                    "X-Porter-Intelligence-Source":
                        "fraud-detection",
                    "X-Porter-Event-Type":
                        "fraud_alert",
                }
            )
            response.raise_for_status()

            logger.info(
                f"Dispatch notified: {driver_id} "
                f"status={response.status_code}"
            )
            return {
                "sent":        True,
                "status_code": response.status_code,
                "driver_id":   driver_id,
                "action":      action,
                "sent_at":     datetime.utcnow().isoformat(),
            }

    except httpx.TimeoutException:
        logger.error(
            f"Dispatch timeout for {driver_id} "
            f"after {DISPATCH_TIMEOUT}s"
        )
        return {
            "sent":      False,
            "reason":    "timeout",
            "driver_id": driver_id,
        }

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Dispatch HTTP error for {driver_id}: "
            f"{e.response.status_code}"
        )
        return {
            "sent":        False,
            "reason":      "http_error",
            "status_code": e.response.status_code,
            "driver_id":   driver_id,
        }

    except Exception as e:
        logger.error(
            f"Dispatch failed for {driver_id}: {e}"
        )
        return {
            "sent":      False,
            "reason":    str(e),
            "driver_id": driver_id,
        }


async def auto_enforce(
    driver_id:         str,
    trip_id:           str,
    fraud_probability: float,
    tier:              str,
    top_signals:       List[str],
) -> Optional[Dict]:
    """
    Called after every fraud score.
    Only fires for action tier above threshold.
    Determines action severity from probability.
    """
    if tier != "action":
        return None

    if fraud_probability < ACTION_THRESHOLD:
        return None

    # Severity based on probability
    if fraud_probability >= 0.98:
        action = "suspend"   # Lock driver immediately
    elif fraud_probability >= 0.94:
        action = "flag"      # Flag in dispatch system
    else:
        action = "alert"     # Alert supervisor

    return await notify_dispatch(
        driver_id, trip_id,
        fraud_probability, tier,
        top_signals, action,
    )
