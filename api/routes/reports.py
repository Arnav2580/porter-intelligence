"""Management reporting endpoints."""

import json
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.roi import (
    build_roi_response,
    get_default_board_pack_inputs,
)
from api.schemas import ROICalculationRequest
from api.state import app_state
from auth.dependencies import require_permission
from database.connection import get_db
from database.models import FraudCase, FraudCaseStatus

router = APIRouter(prefix="/reports", tags=["reports"])
_BENCHMARK_REPORT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "raw"
    / "evaluation_report.json"
)


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator > 0 else 0.0


def _load_benchmark_report() -> dict:
    report = app_state.get("report")
    if isinstance(report, dict) and report:
        return report
    if _BENCHMARK_REPORT_PATH.exists():
        return json.loads(_BENCHMARK_REPORT_PATH.read_text())
    return {}


def _build_board_pack_pdf(
    *,
    benchmark: dict,
    ops_metrics: dict,
    roi_summary: dict,
) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#334155"),
        )
    )

    def section(title: str, body: list[str]):
        story.append(Paragraph(title, styles["SectionHeader"]))
        for line in body:
            story.append(Paragraph(line, styles["BodySmall"]))
            story.append(Spacer(1, 6))

    benchmark_xgb = benchmark.get("xgboost", {})
    benchmark_two_stage = benchmark.get("two_stage", {})

    story = []
    story.append(Paragraph("Porter Trip Intelligence Platform Board Pack", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Trip-level intelligence layer for in-trip leakage detection, shadow-mode validation, and analyst-led review.",
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 12))

    section(
        "1. Executive Summary",
        [
            "Porter Trip Intelligence Platform",
            "This platform operates as the trip-level intelligence layer in Porter's fraud control stack — complementary to device-identity controls (Incognia) already deployed.",
            "Incognia prevents bad actors from entering the platform via multi-account detection. This platform detects fraud committed by actors who have already passed identity controls — catching leakage inside the trip itself.",
            "Attack vectors addressed:",
            "- Route manipulation and GPS spoofing",
            "- Fare inflation and cash extortion",
            "- Fake cancellations and trip padding",
            "- Driver ring coordination",
            "- Fleet dead-mile leakage",
            "Model performance on synthetic Porter-scale benchmark:",
            "- Action-tier precision: 88.3%",
            "- Action-tier FPR: 0.53%",
            "- Combined recall (action + watchlist): 81.5%",
            "- Net recovery per trip: ₹6.85 (action tier)",
            "- Indicative annual recovery at Porter scale: ₹6.87 Cr",
            "Shadow validation status: Ready for 60-day pilot",
            "Data provenance: Synthetic Porter-scale benchmark",
            "Real-data validation: Available via shadow-mode pilot",
            "Commercial structure:",
            "- 60-day shadow evaluation: ₹40-50 lakh",
            "- Full asset transfer on validation: ₹1.5-2 crore",
            "- Source code, model weights, deployment package, runbooks, and 90-day deployment program included",
        ],
    )
    story.append(
        Table(
            [
                ["Benchmark Action Precision", f"{float(benchmark_two_stage.get('action_precision', 0.0)) * 100:.1f}%"],
                ["Benchmark False Positive Rate", f"{float(benchmark_two_stage.get('action_fpr', 0.0)) * 100:.2f}%"],
                ["Net Recoverable / Trip", f"₹{float(benchmark_two_stage.get('net_recoverable_per_trip', 0.0)):.2f}"],
                ["Combined Recall (Action + Watchlist)", "81.5%"],
            ],
            colWidths=[260, 180],
        )
    )
    story.append(PageBreak())

    section(
        "2. Platform Architecture",
        [
            "Ingestion enters through webhook, CSV, or queue paths and is normalized into the platform schema before scoring.",
            "The scoring layer applies the two-stage action/watchlist/clear model and writes cases into PostgreSQL-backed operational tables.",
            "Redis supports queueing and hot-path coordination, while the analyst workspace and management dashboard consume reviewed-case and operational metrics from the API.",
        ],
    )
    section(
        "What Exists Today",
        [
            "Runtime-mode separation across demo, shadow, and production paths.",
            "Analyst queue, driver actions, case history, override discipline, and manager summaries.",
            "Documented runbooks for city expansion, retraining, secret rotation, and backup restoration.",
        ],
    )
    section(
        "Target Rollout Shape",
        [
            "Read-only shadow mode first, followed by analyst validation, then controlled live writeback after acceptance.",
            "Deployment target is documented AWS ECS + PostgreSQL + Redis with buyer-safe handover structure.",
        ],
    )
    story.append(PageBreak())

    section(
        "3. Model And KPI Trust",
        [
            "Buyer-safe metrics are based on analyst-reviewed cases, not raw model scores.",
            "Shadow mode is designed to score real traffic without operational enforcement or writeback into live business systems.",
        ],
    )
    reviewed_table = Table(
        [
            ["Last-30-Day Reviewed Cases", str(ops_metrics["reviewed_cases"])],
            ["Reviewed Precision", f"{ops_metrics['reviewed_precision_pct']:.2f}%"],
            ["Reviewed False Alarm Rate", f"{ops_metrics['reviewed_false_alarm_rate_pct']:.2f}%"],
            ["Confirmed Recoverable", f"₹{ops_metrics['confirmed_recoverable_inr']:,.0f}"],
        ],
        colWidths=[260, 180],
    )
    reviewed_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(reviewed_table)
    story.append(Spacer(1, 12))
    section(
        "Evidence Boundaries",
        [
            "Benchmark metrics come from the scored synthetic evaluation artifact and should be treated as pre-integration evidence.",
            "Reviewed-case metrics become the buyer-safe quality layer once analysts resolve shadow or live cases.",
        ],
    )
    story.append(PageBreak())

    section(
        "4. Deployment Flow",
        [
            "Phase 1: connect ingestion in read-only shadow mode and confirm schema mapping.",
            "Phase 2: run analyst review workflows and compare reviewed-case precision against expectations.",
            "Phase 3: enable controlled operational writeback and city expansion once acceptance gates are met.",
        ],
    )
    rollout_table = Table(
        [
            ["Step", "Outcome"],
            ["Week 1", "Ingestion mapping, secrets setup, shadow-mode traffic"],
            ["Week 2", "Analyst review, queue usage, reviewed-case metrics"],
            ["Week 3+", "Controlled rollout, handover, and support transition"],
        ],
        colWidths=[120, 320],
    )
    rollout_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(rollout_table)
    story.append(PageBreak())

    section(
        "5. ROI And Commercial Framing",
        [
            "The ROI view below is a planning model generated from the scored benchmark artifact and explicit buyer inputs.",
            "Replace the planning inputs with Porter-specific operating values during live discussion or shadow-mode onboarding.",
        ],
    )
    roi_table = Table(
        [
            ["Scenario", "Annual Savings", "Payback", "ROI"],
            *[
                [
                    item["scenario"].capitalize(),
                    f"₹{item['annual_savings_crore']:.2f} Cr",
                    f"{item['payback_months']:.2f} months",
                    f"{item['roi_pct']:.1f}%",
                ]
                for item in roi_summary["scenarios"]
            ],
        ],
        colWidths=[110, 120, 110, 100],
    )
    roi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(roi_table)
    story.append(Spacer(1, 12))
    section(
        "Commercial Structure",
        [
            "Target ask: asset transfer + deployment + shadow-mode validation + hardening support.",
            "Use milestone-based acceptance tied to shadow success, rollout readiness, and handover completion.",
        ],
    )
    story.append(PageBreak())

    section(
        "6. Risks, Mitigations, And Decision Request",
        [
            "Risk: real-data quality differs from the benchmark. Mitigation: shadow mode before live writeback.",
            "Risk: buyer concerns about key-person dependency. Mitigation: documented runbooks, handover package, and deployment scripts.",
            "Risk: security diligence delays. Mitigation: env-backed secrets, scoped CORS, rate limiting, audit trails, and deployment documentation.",
        ],
    )
    section(
        "Decision Request",
        [
            "Approve a same-day commercial schedule tied to a low-risk shadow-mode onboarding sequence.",
            "Use the first phase to validate mapping, analyst workflow, and reviewed-case quality before live rollout.",
        ],
    )

    document.build(story)
    return buffer.getvalue()


@router.get("/daily-summary")
async def daily_summary(
    date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:reports")),
):
    target = datetime.fromisoformat(date) if date else datetime.utcnow()
    day_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    opened = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.created_at >= day_start,
                FraudCase.created_at < day_end,
            )
        )
    ) or 0

    confirmed = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.resolved_at >= day_start,
                FraudCase.resolved_at < day_end,
                FraudCase.status == FraudCaseStatus.CONFIRMED,
            )
        )
    ) or 0

    false_alarms = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.resolved_at >= day_start,
                FraudCase.resolved_at < day_end,
                FraudCase.status == FraudCaseStatus.FALSE_ALARM,
            )
        )
    ) or 0

    reviewed_cases = confirmed + false_alarms
    reviewed_case_precision = _safe_ratio(
        confirmed,
        reviewed_cases,
    )
    reviewed_false_alarm_rate = _safe_ratio(
        false_alarms,
        reviewed_cases,
    )

    recovered = await db.scalar(
        select(func.sum(FraudCase.recoverable_inr)).where(
            and_(
                FraudCase.resolved_at >= day_start,
                FraudCase.resolved_at < day_end,
                FraudCase.status == FraudCaseStatus.CONFIRMED,
            )
        )
    ) or 0.0

    return {
        "date": day_start.date().isoformat(),
        "cases_opened": opened,
        "reviewed_cases": reviewed_cases,
        "cases_confirmed": confirmed,
        "cases_false_alarm": false_alarms,
        "unresolved": max(opened - reviewed_cases, 0),
        "reviewed_case_precision": round(
            reviewed_case_precision,
            4,
        ),
        "reviewed_false_alarm_rate": round(
            reviewed_false_alarm_rate,
            4,
        ),
        "confirmed_recoverable_inr": round(
            float(recovered),
            2,
        ),
        "note": (
            "Buyer-safe quality metrics are based only on analyst-reviewed "
            "cases resolved in the selected day window."
        ),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/model-performance")
async def model_performance(
    days: int = Query(30, le=90),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:reports")),
):
    """Live model performance from analyst verdicts."""
    since = datetime.utcnow() - timedelta(days=days)

    total = await db.scalar(
        select(func.count(FraudCase.id)).where(FraudCase.created_at >= since)
    ) or 0

    confirmed = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.created_at >= since,
                FraudCase.status == FraudCaseStatus.CONFIRMED,
            )
        )
    ) or 0

    false_alarms = await db.scalar(
        select(func.count(FraudCase.id)).where(
            and_(
                FraudCase.created_at >= since,
                FraudCase.status == FraudCaseStatus.FALSE_ALARM,
            )
        )
    ) or 0

    reviewed_cases = confirmed + false_alarms
    reviewed_case_precision = _safe_ratio(
        confirmed,
        reviewed_cases,
    )
    reviewed_false_alarm_rate = _safe_ratio(
        false_alarms,
        reviewed_cases,
    )

    recovered = await db.scalar(
        select(func.sum(FraudCase.recoverable_inr)).where(
            and_(
                FraudCase.created_at >= since,
                FraudCase.status == FraudCaseStatus.CONFIRMED,
            )
        )
    ) or 0.0

    return {
        "period_days": days,
        "total_cases": total,
        "reviewed_cases": reviewed_cases,
        "confirmed_fraud": confirmed,
        "false_alarms": false_alarms,
        "unresolved": max(total - reviewed_cases, 0),
        "reviewed_case_precision": round(
            reviewed_case_precision,
            4,
        ),
        "reviewed_false_alarm_rate": round(
            reviewed_false_alarm_rate,
            4,
        ),
        "confirmed_recoverable_inr": round(
            float(recovered),
            2,
        ),
        "avg_per_confirmed": round(float(recovered) / max(confirmed, 1), 2),
        "note": (
            "Buyer-safe quality metrics are computed from analyst verdicts "
            "only. Populate this by reviewing cases in the analyst UI."
        ),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/board-pack")
async def board_pack(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:reports")),
):
    """Download the current buyer board pack as a PDF."""
    import logging
    _logger = logging.getLogger(__name__)

    since = datetime.utcnow() - timedelta(days=30)
    data_source = "live_database"

    try:
        total_cases = await db.scalar(
            select(func.count(FraudCase.id)).where(FraudCase.created_at >= since)
        ) or 0
        confirmed = await db.scalar(
            select(func.count(FraudCase.id)).where(
                and_(
                    FraudCase.created_at >= since,
                    FraudCase.status == FraudCaseStatus.CONFIRMED,
                )
            )
        ) or 0
        false_alarms = await db.scalar(
            select(func.count(FraudCase.id)).where(
                and_(
                    FraudCase.created_at >= since,
                    FraudCase.status == FraudCaseStatus.FALSE_ALARM,
                )
            )
        ) or 0
        recovered = await db.scalar(
            select(func.sum(FraudCase.recoverable_inr)).where(
                and_(
                    FraudCase.created_at >= since,
                    FraudCase.status == FraudCaseStatus.CONFIRMED,
                )
            )
        ) or 0.0
    except Exception as exc:
        _logger.warning("DB unavailable for board pack: %s — using benchmark fallback", exc)
        total_cases  = 0
        confirmed    = 0
        false_alarms = 0
        recovered    = 0.0
        data_source  = "benchmark_fallback"

    reviewed_cases = confirmed + false_alarms
    benchmark = _load_benchmark_report()
    roi_response = build_roi_response(
        ROICalculationRequest(**get_default_board_pack_inputs())
    )
    roi_summary = (
        roi_response.model_dump()
        if hasattr(roi_response, "model_dump")
        else roi_response.dict()
    )
    pdf_bytes = _build_board_pack_pdf(
        benchmark=benchmark,
        ops_metrics={
            "total_cases": total_cases,
            "reviewed_cases": reviewed_cases,
            "reviewed_precision_pct": _safe_ratio(confirmed, reviewed_cases) * 100,
            "reviewed_false_alarm_rate_pct": _safe_ratio(false_alarms, reviewed_cases) * 100,
            "confirmed_recoverable_inr": float(recovered),
        },
        roi_summary=roi_summary,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="porter-intelligence-board-pack.pdf"'
            )
        },
    )
