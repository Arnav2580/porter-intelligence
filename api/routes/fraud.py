"""Compatibility exports for fraud handlers defined in api/inference.py."""

from fastapi import APIRouter

from api.inference import (
    fraud_heatmap,
    fraud_live_feed,
    fraud_tier_summary,
    score_trip,
)

router = APIRouter(prefix="/fraud", tags=["fraud"])

__all__ = [
    "router",
    "fraud_heatmap",
    "fraud_live_feed",
    "fraud_tier_summary",
    "score_trip",
]
