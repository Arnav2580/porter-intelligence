"""
api/routes/live_kpi.py

Live KPI endpoint backed by PostgreSQL fraud_cases in real time.

Buyer-facing rule:
- reviewed-case metrics are primary
- operational signal metrics are supplementary
- proxy metrics must never be presented as final fraud precision/FPR

Registered as GET /kpi/live in api/main.py.
No auth required — same as /kpi/summary (read-only aggregate, no PII).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.state import app_state
from database.connection import get_db
from database.models import FraudCase, FraudCaseStatus
from runtime_config import describe_data_provenance

router = APIRouter(tags=["kpi"])

# Trips/day assumption for per-trip recovery calculation.
# Live simulator: 30 trips/min × 60 min × 24 h = 43 200 trips/day.
_TRIPS_PER_DAY = 30 * 60 * 24
_PENDING_STATUSES = (
    FraudCaseStatus.OPEN,
    FraudCaseStatus.UNDER_REVIEW,
    FraudCaseStatus.ESCALATED,
)


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator > 0 else 0.0


def get_review_confidence(reviewed_cases: int) -> dict[str, str]:
    """
    Map reviewed sample size to a trust note for buyers.

    This is not a statistical guarantee. It is a product-truth signal so the
    dashboard stays honest about whether the review sample is still too small.
    """
    if reviewed_cases <= 0:
        return {
            "status": "awaiting_reviews",
            "label": "Awaiting Analyst Reviews",
            "note": (
                "No analyst-reviewed cases in the selected window yet. "
                "Use operational signal metrics only as directional context."
            ),
        }
    if reviewed_cases < 10:
        return {
            "status": "early_signal",
            "label": "Early Signal",
            "note": (
                "Reviewed-case metrics are now live, but the sample is still "
                "small and should not be treated as finance-grade evidence."
            ),
        }
    if reviewed_cases < 25:
        return {
            "status": "growing_sample",
            "label": "Growing Review Sample",
            "note": (
                "Reviewed-case metrics are becoming more useful for fraud and "
                "ops review, but the sample is still limited."
            ),
        }
    return {
        "status": "decision_support",
        "label": "Decision Support Ready",
        "note": (
            "Reviewed-case metrics have enough analyst verdicts to support "
            "buyer-safe fraud and operations discussions."
        ),
    }


@router.get("/kpi/live")
async def kpi_live(db: AsyncSession = Depends(get_db)):
    """
    Live KPI numbers computed from PostgreSQL fraud_cases in real time.

    Window: last 24 hours (rolling).
    Fields:
      reviewed_cases_24h                — reviewed cases resolved in the last 24h
      reviewed_case_precision           — confirmed fraud / reviewed cases
      reviewed_false_alarm_rate         — false alarms / reviewed cases
      confirmed_recoverable_inr_24h     — recoverable value on confirmed cases
      pending_review_cases              — current unresolved flagged case queue
      action_tier_24h                   — cases flagged for immediate action
      watchlist_tier_24h                — cases flagged for monitoring
      action_score_avg                  — avg model score on action-tier cases
      estimated_recoverable_inr         — estimated recoverable on flagged action cases
      runtime_mode                      — demo / prod
      synthetic_feed_enabled            — whether the demo feeder is active
      data_provenance                   — human-readable source note
      generated_at                      — ISO timestamp of this response
    """
    now        = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    runtime_mode = app_state.get("runtime_mode", "prod")
    synthetic_feed_enabled = app_state.get(
        "synthetic_feed_enabled",
        False,
    )
    shadow_mode = app_state.get("shadow_mode", False)

    # ── 24h case counts by tier ───────────────────────────────────
    action_24h = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.tier == "action",
                FraudCase.created_at >= cutoff_24h,
            )
        )
    ) or 0

    watchlist_24h = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.tier == "watchlist",
                FraudCase.created_at >= cutoff_24h,
            )
        )
    ) or 0

    # ── Reviewed-case metrics: defensible for fraud / finance review ───────
    confirmed_fraud_24h = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.status == FraudCaseStatus.CONFIRMED,
                FraudCase.resolved_at >= cutoff_24h,
            )
        )
    ) or 0

    false_alarm_reviews_24h = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.status == FraudCaseStatus.FALSE_ALARM,
                FraudCase.resolved_at >= cutoff_24h,
            )
        )
    ) or 0

    reviewed_cases_24h = (
        confirmed_fraud_24h + false_alarm_reviews_24h
    )
    reviewed_case_precision = _safe_ratio(
        confirmed_fraud_24h,
        reviewed_cases_24h,
    )
    reviewed_false_alarm_rate = _safe_ratio(
        false_alarm_reviews_24h,
        reviewed_cases_24h,
    )
    review_confidence = get_review_confidence(reviewed_cases_24h)

    confirmed_rec = await db.scalar(
        select(func.sum(FraudCase.recoverable_inr)).where(
            and_(
                FraudCase.status == FraudCaseStatus.CONFIRMED,
                FraudCase.resolved_at >= cutoff_24h,
            )
        )
    )
    confirmed_recoverable_inr_24h = (
        float(confirmed_rec) if confirmed_rec is not None else 0.0
    )

    pending_review_cases = await db.scalar(
        select(func.count(FraudCase.id)).where(
            FraudCase.status.in_(_PENDING_STATUSES)
        )
    ) or 0

    # ── Operational proxy metrics: useful, but not final truth ─────────────
    avg_prob = await db.scalar(
        select(func.avg(FraudCase.fraud_probability)).where(
            and_(
                FraudCase.tier == "action",
                FraudCase.created_at >= cutoff_24h,
            )
        )
    )
    action_score_avg = float(avg_prob) if avg_prob is not None else 0.0

    total_flagged_24h = action_24h + watchlist_24h
    false_alarm_share = _safe_ratio(
        false_alarm_reviews_24h,
        total_flagged_24h,
    )

    # ── Estimated recoverable — action tier only ────────────────────────────
    net_rec = await db.scalar(
        select(func.sum(FraudCase.recoverable_inr)).where(
            and_(
                FraudCase.tier == "action",
                FraudCase.created_at >= cutoff_24h,
            )
        )
    )
    estimated_recoverable_inr = (
        float(net_rec) if net_rec is not None else 0.0
    )

    # ── Per-trip and annual figures ───────────────────────────────
    estimated_recoverable_per_trip = (
        estimated_recoverable_inr / _TRIPS_PER_DAY
    )
    indicative_annual_recovery_crore = (
        estimated_recoverable_inr * 365
    ) / 10_000_000

    # ── All-time totals ───────────────────────────────────────────
    all_time_cases = await db.scalar(
        select(func.count(FraudCase.id))
    ) or 0

    cases_today = await db.scalar(
        select(func.count(FraudCase.id)).where(
            FraudCase.created_at >= today_start
        )
    ) or 0

    metric_status = (
        "reviewed_case_metrics_primary"
        if reviewed_cases_24h > 0
        else "awaiting_reviewed_case_metrics"
    )

    return {
        "window": "last_24h",
        "generated_at": now.isoformat(),
        "runtime_mode": runtime_mode,
        "synthetic_feed_enabled": synthetic_feed_enabled,
        "shadow_mode": shadow_mode,
        "data_provenance": describe_data_provenance(
            runtime_mode,
            synthetic_feed_enabled,
            shadow_mode,
        ),
        "metric_status": metric_status,
        "review_basis": (
            "Analyst verdicts on resolved cases in the last 24 hours."
        ),
        "review_confidence_status": review_confidence["status"],
        "review_confidence_label": review_confidence["label"],
        "review_confidence_note": review_confidence["note"],
        "metric_notes": {
            "reviewed_case_precision": (
                "Confirmed fraud divided by reviewed cases with analyst "
                "verdicts in the selected window."
            ),
            "reviewed_false_alarm_rate": (
                "False alarms divided by reviewed cases with analyst "
                "verdicts in the selected window."
            ),
            "confirmed_recoverable": (
                "Recoverable value attached to confirmed fraud cases "
                "resolved in the selected window."
            ),
            "action_score_avg": (
                "Average model score on action-tier cases, "
                "not analyst-confirmed precision."
            ),
            "false_alarm_share": (
                "False alarms divided by all flagged cases, "
                "not population-level false positive rate."
            ),
            "estimated_recoverable": (
                "Estimated recoverable value from flagged "
                "action-tier cases."
            ),
        },
        "reviewed_cases_24h": reviewed_cases_24h,
        "confirmed_fraud_24h": confirmed_fraud_24h,
        "false_alarm_reviews_24h": false_alarm_reviews_24h,
        "reviewed_case_precision": round(
            reviewed_case_precision,
            4,
        ),
        "reviewed_case_precision_pct": round(
            reviewed_case_precision * 100,
            2,
        ),
        "reviewed_false_alarm_rate": round(
            reviewed_false_alarm_rate,
            4,
        ),
        "reviewed_false_alarm_rate_pct": round(
            reviewed_false_alarm_rate * 100,
            2,
        ),
        "confirmed_recoverable_inr_24h": round(
            confirmed_recoverable_inr_24h,
            2,
        ),
        "pending_review_cases": pending_review_cases,
        "action_tier_24h": action_24h,
        "watchlist_tier_24h": watchlist_24h,
        "total_flagged_24h": total_flagged_24h,
        "action_score_avg": round(action_score_avg, 4),
        "action_score_avg_pct": round(action_score_avg * 100, 2),
        "false_alarm_share": round(false_alarm_share, 4),
        "false_alarm_share_pct": round(
            false_alarm_share * 100,
            2,
        ),
        "estimated_recoverable_inr": round(
            estimated_recoverable_inr,
            2,
        ),
        "estimated_recoverable_per_trip": round(
            estimated_recoverable_per_trip,
            4,
        ),
        "indicative_annual_recovery_crore": round(
            indicative_annual_recovery_crore,
            3,
        ),
        "all_time_cases": all_time_cases,
        "cases_today": cases_today,
    }
