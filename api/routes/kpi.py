"""Compatibility exports for KPI handlers defined in api/inference.py."""

from fastapi import APIRouter

from api.inference import kpi_report, kpi_summary

router = APIRouter(prefix="/kpi", tags=["kpi"])

__all__ = [
    "router",
    "kpi_summary",
    "kpi_report",
]
