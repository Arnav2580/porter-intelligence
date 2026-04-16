"""Buyer close packet — bundled PDF for the legal/commercial close."""

from __future__ import annotations

import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from auth.dependencies import require_permission

router = APIRouter(prefix="/legal", tags=["legal"])

_DOCS_ROOT = Path(__file__).resolve().parents[2]
_ACCEPTANCE_CRITERIA_MD = _DOCS_ROOT / "docs" / "handover" / "acceptance-criteria.md"
_SUPPORT_SCOPE_MD       = _DOCS_ROOT / "docs" / "handover" / "deployment-and-support-scope.md"
_REPO_HANDOVER_MD       = _DOCS_ROOT / "docs" / "handover" / "repo-access-and-handover.md"

_PORTER_BUYER          = "SmartShift Logistics Solutions Pvt Ltd (Porter)"
_PLATFORM_NAME         = "Porter Intelligence Platform"
_SUPPORT_DAYS          = 90
_SHADOW_EVAL_DAYS      = 60
_SHADOW_EVAL_FEE       = "₹40-50 lakh"
_ASSET_TRANSFER_FEE    = "₹1.5-2 crore"
_SELLER_ENTITY = {
    "name": "Porter Intelligence (Unregistered)",
    "address": "[Seller registered address — to be confirmed on execution]",
    "pan": "[Seller PAN — to be confirmed on execution]",
    "gstin": "[Seller GSTIN if applicable]",
    "email": "arnav2580goyal@gmail.com",
    "signatory": "Arnav Goyal, Founder",
}
_DRAFT_FOOTER_LINES = (
    "DRAFT — For discussion purposes only.",
    "Final terms subject to legal review. Not binding until executed by both parties.",
)


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=base["Heading1"],
                             fontSize=18, spaceAfter=10, textColor=colors.HexColor("#1a1a2e")),
        "h2": ParagraphStyle("h2", parent=base["Heading2"],
                             fontSize=13, spaceAfter=6, spaceBefore=14,
                             textColor=colors.HexColor("#16213e")),
        "h3": ParagraphStyle("h3", parent=base["Heading3"],
                             fontSize=11, spaceAfter=4, spaceBefore=10,
                             textColor=colors.HexColor("#0f3460")),
        "body": ParagraphStyle("body", parent=base["Normal"],
                               fontSize=9.5, leading=14, spaceAfter=6),
        "small": ParagraphStyle("small", parent=base["Normal"],
                                fontSize=8.5, leading=12, textColor=colors.HexColor("#444444")),
        "bold": ParagraphStyle("bold", parent=base["Normal"],
                               fontSize=9.5, leading=14, fontName="Helvetica-Bold"),
        "footer": ParagraphStyle("footer", parent=base["Normal"],
                                 fontSize=8, textColor=colors.HexColor("#888888"),
                                 alignment=1),
    }


def _table_style_default():
    return TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f5f5"), colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ])


def _draw_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.setFont("Helvetica", 8)
    y_pos = 20
    for line in _DRAFT_FOOTER_LINES:
        canvas.drawCentredString(A4[0] / 2, y_pos, line)
        y_pos += 9
    canvas.restoreState()


def _commercial_schedule_text() -> str:
    return f"""
Commercial Structure — {_PLATFORM_NAME}

Phase 1: Shadow Evaluation
- Duration: {_SHADOW_EVAL_DAYS} days
- Fee: {_SHADOW_EVAL_FEE} (exclusive evaluation)
- Deliverable: Validation report with Porter production-format data
- Risk to Porter: Zero operational risk — read-only shadow mode, no live enforcement writeback

Phase 2: Asset Transfer (on validation)
- Fee: {_ASSET_TRANSFER_FEE}
- Includes: Source code, model weights, deployment package, runbooks, analyst training
- Timeline: {_SUPPORT_DAYS}-day deployment program
- Payment: Milestone-based tranches tied to execution, deployment progress, and handover completion

Notes
- Device identity controls remain upstream with Incognia.
- This platform is the trip intelligence layer focused on in-trip behavioral leakage.
- Final commercial terms remain subject to legal review and execution.
""".strip()


def _sig_block(
    entity: str,
    signatory: str | None = None,
    designation: str | None = None,
) -> list:
    S = _styles()
    return [
        Spacer(1, 14),
        Paragraph(f"For and on behalf of <b>{entity}</b>:", S["body"]),
        Spacer(1, 8),
        Paragraph(
            f"Name: {signatory or '_________________________________'}",
            S["body"],
        ),
        Paragraph(
            f"Designation: {designation or '___________________________'}",
            S["body"],
        ),
        Paragraph("Date: __________________________________", S["body"]),
        Paragraph("Signature: _____________________________", S["body"]),
        Spacer(1, 6),
    ]


# ---------------------------------------------------------------------------
# Individual PDF builders
# ---------------------------------------------------------------------------

def _build_nda_pdf() -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=50, bottomMargin=50,
                            leftMargin=60, rightMargin=60)
    S = _styles()
    today = datetime.utcnow().strftime("%d %B %Y")
    story = [
        Paragraph("NON-DISCLOSURE AGREEMENT", S["h1"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a1a2e")),
        Spacer(1, 8),
        Paragraph(f"Date: {today}", S["small"]),
        Spacer(1, 14),

        Paragraph("PARTIES", S["h2"]),
        Paragraph(
            'This Mutual Non-Disclosure Agreement ("Agreement") is entered into between '
            f'<b>{_SELLER_ENTITY["name"]}</b> ("Discloser"), '
            f'with correspondence address {_SELLER_ENTITY["address"]}, '
            f'PAN {_SELLER_ENTITY["pan"]}, GSTIN {_SELLER_ENTITY["gstin"]}, '
            f'and email {_SELLER_ENTITY["email"]}, and '
            f'<b>{_PORTER_BUYER}</b> ("Recipient"), and vice versa \u2014 each party may '
            "disclose and receive Confidential Information under this Agreement.",
            S["body"],
        ),

        Paragraph("DEFINITION OF CONFIDENTIAL INFORMATION", S["h2"]),
        Paragraph(
            '"Confidential Information" means all non-public technical and business '
            "information disclosed by either party, including but not limited to: source "
            "code, model weights, architecture documentation, pricing, business terms, "
            "customer data, and any information marked as confidential or that a reasonable "
            "person would understand to be confidential given the context of disclosure.",
            S["body"],
        ),
        Paragraph(
            "Confidential Information does not include information that: (a) is or becomes "
            "publicly available through no breach of this Agreement; (b) was rightfully known "
            "to the Recipient before disclosure; (c) is independently developed by the Recipient "
            "without use of Confidential Information; or (d) is received from a third party "
            "without obligation of confidentiality.",
            S["body"],
        ),

        Paragraph("OBLIGATIONS", S["h2"]),
        Paragraph(
            "Each party agrees to: (a) hold the other party's Confidential Information in strict "
            "confidence using at least the same degree of care it uses for its own confidential "
            "information (but no less than reasonable care); (b) not disclose Confidential "
            "Information to any third party without prior written consent; (c) use Confidential "
            "Information solely for the Permitted Use defined below.",
            S["body"],
        ),

        Paragraph("PERMITTED USE", S["h2"]),
        Paragraph(
            f"Confidential Information disclosed under this Agreement may be used solely for: "
            f"Phase 1 shadow-mode evaluation, validation, deployment planning, and operational "
            f"use of the {_PLATFORM_NAME} if a Phase 2 asset-transfer agreement is executed.",
            S["body"],
        ),

        Paragraph("TERM", S["h2"]),
        Paragraph(
            "This Agreement remains in effect for <b>two (2) years</b> from the date of execution. "
            "Obligations of confidentiality survive termination of this Agreement.",
            S["body"],
        ),

        Paragraph("RETURN AND DESTRUCTION", S["h2"]),
        Paragraph(
            "Upon written request by either party, all Confidential Information (including copies) "
            "shall be returned or destroyed within 30 days. This obligation does not apply to "
            "Confidential Information that Porter has legitimately incorporated into its production "
            "systems under a commercial schedule.",
            S["body"],
        ),

        Paragraph("GOVERNING LAW", S["h2"]),
        Paragraph(
            "This Agreement shall be governed by and construed in accordance with the laws of India. "
            "Disputes shall be subject to the exclusive jurisdiction of courts in Bengaluru, Karnataka.",
            S["body"],
        ),

        Spacer(1, 20),
        Paragraph("SIGNATURES", S["h2"]),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")),
    ]
    story += _sig_block(
        _SELLER_ENTITY["name"],
        signatory=_SELLER_ENTITY["signatory"],
        designation="Founder",
    )
    story += _sig_block(_PORTER_BUYER)
    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()


def _build_commercial_schedule_pdf() -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=50, bottomMargin=50,
                            leftMargin=60, rightMargin=60)
    S = _styles()
    today = datetime.utcnow().strftime("%d %B %Y")
    story = [
        Paragraph("COMMERCIAL SCHEDULE", S["h1"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a1a2e")),
        Spacer(1, 6),
        Paragraph(
            f"Platform: {_PLATFORM_NAME} &nbsp;&nbsp; | &nbsp;&nbsp; "
            f"Buyer: {_PORTER_BUYER} &nbsp;&nbsp; | &nbsp;&nbsp; Date: {today}",
            S["small"],
        ),
        Spacer(1, 14),

        Paragraph("1. Asset Description", S["h2"]),
        Paragraph("The transfer package includes:", S["body"]),
        Table(
            [
                ["Component", "Description"],
                ["Source code", "Backend (Python/FastAPI), frontend (React), ML pipeline"],
                ["Model weights", "XGBoost fraud classifier, Prophet demand models, evaluation artifacts"],
                ["Documentation", "Architecture docs, API reference, runbooks, logic documentation"],
                ["Infrastructure", "Docker Compose, AWS ECS templates, Prometheus/Grafana configs"],
                ["Digital twin", "22-city simulation with configurable volume and fraud injection"],
                ["Schema mapper", "Field-mapping layer for Porter trip event integration"],
                ["Validation suite", "Comprehensive pytest validation covering major platform paths"],
            ],
            colWidths=[150, 310],
        ).setStyle(_table_style_default()),
        Spacer(1, 12),

        Paragraph("2. Payment Schedule", S["h2"]),
        Table(
            [
                ["Phase", "Fee (excl. GST)", "Deliverable", "Commercial Trigger"],
                [
                    "Phase 1 — Shadow Evaluation",
                    _SHADOW_EVAL_FEE,
                    "Read-only shadow run plus Porter validation report",
                    "Executed evaluation order / NDA",
                ],
                [
                    "Phase 2 — Asset Transfer",
                    _ASSET_TRANSFER_FEE,
                    "Source code, model weights, deployment package, runbooks, training",
                    "Validation success and signed asset-transfer agreement",
                ],
                [
                    "Phase 2 payment structure",
                    "Milestone-based tranches",
                    f"{_SUPPORT_DAYS}-day deployment program and handover completion",
                    "Deployment milestones and final sign-off",
                ],
            ],
            colWidths=[125, 110, 160, 115],
        ).setStyle(_table_style_default()),
        Spacer(1, 8),
        Paragraph(
            "All amounts are exclusive of GST. GST at 18% is applicable. "
            "Phase 1 is an exclusive evaluation engagement. Phase 2 proceeds only after validation success.",
            S["small"],
        ),
        Spacer(1, 12),

        Paragraph("3. Acceptance Criteria", S["h2"]),
        Paragraph(
            "Progression from Phase 1 shadow evaluation into Phase 2 asset transfer requires the five criteria below "
            "to be confirmed in writing. See the Acceptance Criteria Checklist document for full measurement detail.",
            S["body"],
        ),
        Table(
            [
                ["#", "Criterion", "Target"],
                ["1", "Ingestion path works", "95%+ ingestion success rate"],
                ["2", "Shadow mode without writeback", "0 outbound enforcement webhooks"],
                ["3", "Analyst workflow functional", "3+ analysts actively reviewing"],
                ["4", "Reviewed-case precision", "70%+ on action-tier (min 200 cases)"],
                ["5", "Handover package delivered", "Porter technical lead written sign-off"],
            ],
            colWidths=[20, 230, 210],
        ).setStyle(_table_style_default()),
        Spacer(1, 12),

        Paragraph("4. Intellectual Property", S["h2"]),
        Paragraph(
            "Phase 1 grants Porter an exclusive evaluation right for the shadow-validation period only. "
            "Upon completion of Phase 2 payment obligations, Porter receives a <b>perpetual, irrevocable "
            "licence</b> to use, modify, and deploy the platform internally. Source code is provided without "
            "open-source obligation. Porter may modify and integrate the platform without restriction.",
            S["body"],
        ),

        Paragraph("5. Warranty", S["h2"]),
        Paragraph(
            f"The platform is delivered as demonstrated during evaluation. The seller warrants "
            f"that the platform performs materially as described in technical documentation for "
            f"<b>{_SUPPORT_DAYS} days</b> from Phase 2 execution. The seller does not warrant specific fraud "
            "detection rates on Porter's live data before validation — this is the purpose of the Phase 1 "
            "shadow-mode evaluation. "
            "Defects reported during the 90-day support window will be addressed with reasonable effort.",
            S["body"],
        ),

        Paragraph("6. Deployment and Support Scope", S["h2"]),
        Paragraph(
            f"A {_SUPPORT_DAYS}-day deployment and support engagement is included after Phase 2 execution. "
            "See the Deployment and Support Scope document for full deployment workstream breakdown, "
            "responsibility split, and escalation path.",
            S["body"],
        ),

        PageBreak(),

        Paragraph("SIGNATURES", S["h2"]),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")),
    ]
    story += _sig_block(
        _SELLER_ENTITY["name"],
        signatory=_SELLER_ENTITY["signatory"],
        designation="Founder",
    )
    story += _sig_block(_PORTER_BUYER)
    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()


def _build_acceptance_criteria_pdf() -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=50, bottomMargin=50,
                            leftMargin=60, rightMargin=60)
    S = _styles()
    today = datetime.utcnow().strftime("%d %B %Y")
    story = [
        Paragraph("ACCEPTANCE CRITERIA CHECKLIST", S["h1"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a1a2e")),
        Spacer(1, 6),
        Paragraph(
            f"Platform: {_PLATFORM_NAME} &nbsp;&nbsp; | &nbsp;&nbsp; "
            f"Buyer: {_PORTER_BUYER} &nbsp;&nbsp; | &nbsp;&nbsp; Date: {today}",
            S["small"],
        ),
        Spacer(1, 14),

        Paragraph("Overview", S["h2"]),
        Paragraph(
            "This checklist defines five measurable conditions that constitute shadow-mode success "
            "and trigger progression from Phase 1 evaluation into Phase 2 asset transfer. All five must be satisfied. "
            "Criteria 1–3 are evaluated at Day 30. Criterion 4 requires a minimum of 200 reviewed "
            "action-tier cases. Criterion 5 requires written confirmation from Porter's technical lead.",
            S["body"],
        ),
        Spacer(1, 8),

        Table(
            [
                ["#", "Criterion", "Target", "Evaluation Point"],
                ["1", "Ingestion path works", "95%+ success rate", "Day 7"],
                ["2", "Shadow mode without writeback", "0 enforcement webhooks", "Day 30"],
                ["3", "Analyst workflow functional", "3+ analysts reviewing", "Day 30"],
                ["4", "Reviewed-case precision", "≥70% (min 200 cases)", "Day 45–60"],
                ["5", "Handover package delivered", "Technical lead sign-off", "Day 60"],
            ],
            colWidths=[20, 180, 155, 100],
        ).setStyle(_table_style_default()),
        Spacer(1, 12),

        Paragraph("Criterion 1: Ingestion Path Works", S["h2"]),
        Paragraph(
            "Porter trip events are successfully received, schema-mapped, scored, and either "
            "persisted (action/watchlist) or acknowledged (clear tier). "
            "<b>Verify via:</b> <font name='Courier'>GET /ingest/status</font> — "
            "pending_messages near 0, staged_trips = 0.",
            S["body"],
        ),

        Paragraph("Criterion 2: Shadow Mode Without Writeback", S["h2"]),
        Paragraph(
            "No HTTP calls made to PORTER_DISPATCH_URL during the shadow period. "
            "<b>Verify via:</b> <font name='Courier'>GET /shadow/status</font> — "
            "shadow_mode_active: true. Every shadow case carries live_write_suppressed: true "
            "in the database, verifiable by Porter's DBA at any time.",
            S["body"],
        ),

        Paragraph("Criterion 3: Analyst Workflow Functional", S["h2"]),
        Paragraph(
            "Minimum 3 Porter ops analysts can log in, see their case queue, review cases, "
            "record decisions, and view audit trails. Each analyst must have reviewed at least "
            "5 cases with recorded outcomes.",
            S["body"],
        ),

        Paragraph("Criterion 4: Reviewed-Case Precision", S["h2"]),
        Paragraph(
            "Of all action-tier cases reviewed and closed by Porter analysts, ≥70% confirmed as fraud. "
            "<b>Formula:</b> confirmed / (confirmed + false_alarms). "
            "<b>Verify via:</b> <font name='Courier'>GET /cases/summary/dashboard</font> — "
            "reviewed_case_precision field. Not binding until 200+ cases reviewed.",
            S["body"],
        ),

        Paragraph("Criterion 5: Handover Package Delivered", S["h2"]),
        Paragraph(
            "Porter's CPTO, CTO, or designated technical lead provides written confirmation "
            "(email or signed document) that the handover package is complete and adequate for "
            "independent operation.",
            S["body"],
        ),

        Spacer(1, 20),
        Paragraph("ACCEPTANCE SIGN-OFF", S["h2"]),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")),
        Spacer(1, 10),
        Paragraph(
            "We confirm that all five acceptance criteria have been met as described above and "
            "authorise progression into the Phase 2 asset-transfer and deployment program.",
            S["body"],
        ),
    ]
    story += _sig_block(
        _SELLER_ENTITY["name"],
        signatory=_SELLER_ENTITY["signatory"],
        designation="Founder",
    )
    story += _sig_block(_PORTER_BUYER)
    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()


def _build_support_scope_pdf() -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=50, bottomMargin=50,
                            leftMargin=60, rightMargin=60)
    S = _styles()
    today = datetime.utcnow().strftime("%d %B %Y")
    story = [
        Paragraph("DEPLOYMENT AND SUPPORT SCOPE", S["h1"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a1a2e")),
        Spacer(1, 6),
        Paragraph(
            f"Platform: {_PLATFORM_NAME} &nbsp;&nbsp; | &nbsp;&nbsp; "
            f"Buyer: {_PORTER_BUYER} &nbsp;&nbsp; | &nbsp;&nbsp; Date: {today}",
            S["small"],
        ),
        Spacer(1, 14),
        Paragraph(
            "This scope applies after successful completion of the Phase 1 shadow evaluation and execution of the Phase 2 asset-transfer agreement.",
            S["body"],
        ),

        Paragraph("Engagement Overview", S["h2"]),
        Table(
            [
                ["Phase", "Duration", "Objective"],
                ["Deployment Workstream 1 — Environment Setup", "Day 1–30", "Production environment live and integration-ready"],
                ["Deployment Workstream 2 — Productionisation", "Day 31–60", "Analyst rollout, calibration, and monitored operations"],
                ["Deployment Workstream 3 — Handover", "Day 61–90", "Training, documentation transfer, and stabilisation"],
            ],
            colWidths=[220, 80, 160],
        ).setStyle(_table_style_default()),
        Spacer(1, 12),

        Paragraph("Deployment Workstream 1 Deliverables (Day 1–30)", S["h2"]),
        Paragraph(
            "Environment provisioned and health endpoint returning ok. "
            "Schema mapping adapter configured for Porter's trip event format. "
            "Shadow validation learnings incorporated into the production baseline. "
            "Two analyst training walkthroughs (1 hour each). "
            "Weekly written progress report every Friday.",
            S["body"],
        ),

        Paragraph("Deployment Workstream 2 Deliverables (Day 31–60)", S["h2"]),
        Paragraph(
            "Trip anomaly review with Porter's fraud/ops team. "
            "Reviewed-case precision tracked and reported weekly. "
            "One threshold tuning cycle included if Porter data distribution differs materially. "
            "One joint evaluation session with Porter's fraud lead (1.5 hours).",
            S["body"],
        ),

        Paragraph("Deployment Workstream 3 Deliverables (Day 61–90)", S["h2"]),
        Paragraph(
            "Live enforcement mode activation (pending Porter written approval). "
            "Enforcement dispatch webhook integrated with Porter's driver management system. "
            "Three knowledge transfer sessions (1.5 hours each). "
            "Complete handover package reviewed and signed off.",
            S["body"],
        ),

        Paragraph("What Is Included", S["h2"]),
        Table(
            [
                ["Item", "Included"],
                ["Environment setup guidance and troubleshooting", "Yes"],
                ["Schema mapper configuration", "Yes"],
                ["Analyst training (2 sessions, Phase 1)", "Yes"],
                ["Joint evaluation session (Phase 2)", "Yes"],
                ["Knowledge transfer (3 sessions, Phase 3)", "Yes"],
                ["One threshold tuning cycle", "Yes"],
                ["Weekly progress reports (Phase 1 and 2)", "Yes"],
                ["Bug fixes blocking acceptance criteria", "Yes"],
                ["All documentation in handover package", "Yes"],
            ],
            colWidths=[360, 100],
        ).setStyle(_table_style_default()),
        Spacer(1, 10),

        Paragraph("What Is Not Included", S["h2"]),
        Table(
            [
                ["Item", "Excluded"],
                ["Ongoing support after Day 90", "Not included unless agreed separately"],
                ["Additional feature development", "Not included"],
                ["Compliance certifications (SOC 2, ISO 27001)", "Not included"],
                ["Data migration from Porter's existing fraud tools", "Not included"],
                ["Model retraining beyond the included cycle", "Not included"],
                ["SLA-backed uptime guarantees", "Not included"],
            ],
            colWidths=[280, 180],
        ).setStyle(_table_style_default()),
        Spacer(1, 10),

        Paragraph("Issue Response Targets", S["h2"]),
        Table(
            [
                ["Severity", "Definition", "Response Target"],
                ["P1", "Platform inaccessible, data loss, ingestion stopped", "Same business day"],
                ["P2", "Core feature broken (scoring, cases, reports)", "1 business day"],
                ["P3", "Non-critical issue, cosmetic, edge case", "Next weekly report"],
            ],
            colWidths=[50, 280, 130],
        ).setStyle(_table_style_default()),
        Spacer(1, 20),

        Paragraph("SIGNATURES", S["h2"]),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")),
    ]
    story += _sig_block(
        _SELLER_ENTITY["name"],
        signatory=_SELLER_ENTITY["signatory"],
        designation="Founder",
    )
    story += _sig_block(_PORTER_BUYER)
    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/download",
    summary="Download buyer close packet as ZIP",
    response_class=Response,
)
async def download_close_packet(
    user=Depends(require_permission("read:all")),
):
    """
    Generate and stream the complete buyer close packet as a ZIP archive.

    Contents:
    - NDA.pdf — Mutual non-disclosure agreement
    - Commercial-Schedule.pdf — Asset description, payment tranches, IP terms
    - Acceptance-Criteria.pdf — Five shadow-mode acceptance conditions
    - Deployment-and-Support-Scope.pdf — 90-day phase plan and responsibilities

    Requires admin role.
    """
    nda_pdf        = _build_nda_pdf()
    schedule_pdf   = _build_commercial_schedule_pdf()
    acceptance_pdf = _build_acceptance_criteria_pdf()
    scope_pdf      = _build_support_scope_pdf()

    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("NDA.pdf",                          nda_pdf)
        zf.writestr("Commercial-Schedule.pdf",          schedule_pdf)
        zf.writestr("Acceptance-Criteria.pdf",          acceptance_pdf)
        zf.writestr("Deployment-and-Support-Scope.pdf", scope_pdf)
    zip_buf.seek(0)

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"porter-intelligence-close-packet-{date_str}.zip"

    return Response(
        content=zip_buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/download/nda",
    summary="Download NDA PDF",
    response_class=Response,
)
async def download_nda(
    user=Depends(require_permission("read:all")),
):
    """Download the NDA as a standalone PDF."""
    pdf = _build_nda_pdf()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="NDA.pdf"'},
    )


@router.get(
    "/download/commercial-schedule",
    summary="Download Commercial Schedule PDF",
    response_class=Response,
)
async def download_commercial_schedule(
    user=Depends(require_permission("read:all")),
):
    """Download the commercial schedule as a standalone PDF."""
    pdf = _build_commercial_schedule_pdf()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Commercial-Schedule.pdf"'},
    )


@router.get(
    "/commercial-schedule",
    summary="Commercial schedule summary",
    response_class=PlainTextResponse,
)
async def commercial_schedule_summary(
    user=Depends(require_permission("read:all")),
):
    """Return the phased commercial structure as plain text."""
    return PlainTextResponse(_commercial_schedule_text())


@router.get(
    "/download/acceptance-criteria",
    summary="Download Acceptance Criteria PDF",
    response_class=Response,
)
async def download_acceptance_criteria(
    user=Depends(require_permission("read:all")),
):
    """Download the acceptance criteria checklist as a standalone PDF."""
    pdf = _build_acceptance_criteria_pdf()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Acceptance-Criteria.pdf"'},
    )


@router.get(
    "/download/support-scope",
    summary="Download Deployment and Support Scope PDF",
    response_class=Response,
)
async def download_support_scope(
    user=Depends(require_permission("read:all")),
):
    """Download the deployment and support scope as a standalone PDF."""
    pdf = _build_support_scope_pdf()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Deployment-and-Support-Scope.pdf"'},
    )
