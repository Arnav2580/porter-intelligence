"""Compatibility exports for demand handlers defined in api/inference.py."""

from fastapi import APIRouter

from api.inference import demand_forecast

router = APIRouter(prefix="/demand", tags=["demand"])

__all__ = [
    "router",
    "demand_forecast",
]
