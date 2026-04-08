# Day 12 - Close Packet Preparation

[Index](./README.md) | [Prev](./day-11-demo-fail-safe.md) | [Next](./day-13-war-game.md)

Objective:
- remove every friction point from same-day signature
- make it easier to say yes than to defer

---

## 1. Documents To Prepare

### Core Deal Pack (Must Have On Day 14)

| Document | Purpose | Format |
|---|---|---|
| Non-Disclosure Agreement (NDA) | Mutual confidentiality for technical evaluation and source access | PDF + editable DOCX |
| Commercial Schedule | Asset description, payment tranches, milestones, acceptance criteria | PDF + editable DOCX |
| Master Service Agreement (MSA) | Legal framework: liability, IP transfer, warranty, dispute resolution | PDF + editable DOCX |
| Invoice (Tranche 1) | Rs 1 crore on signing — source access, deployment package, documentation | PDF |
| Acceptance Criteria Checklist | 5 measurable conditions that define "shadow-mode success" | PDF |
| Deployment and Support Scope | 90-day support window, responsibilities, escalation path | PDF |

### Payment and Compliance Details (Must Have Before Meeting)

| Item | Details To Prepare |
|---|---|
| Your entity name | Full legal name of selling entity |
| Your entity type | Pvt Ltd, LLP, or proprietorship |
| GST registration | GSTIN number and state |
| PAN | Entity PAN for TDS compliance |
| Bank details | Account number, IFSC, bank name, branch |
| Authorized signatory | Name, designation, and signing authority proof |
| HSN/SAC code | SAC 998314 (IT consulting and support) or SAC 997331 (licensing of software IP) |
| GST rate | 18% on software licensing and IT services |

---

## 2. NDA Template

### Key Terms

- Parties: [Your Entity] ("Discloser") and SmartShift Logistics Solutions Pvt Ltd (Porter) ("Recipient"), and vice versa (mutual NDA)
- Confidential information: source code, architecture, model weights, business terms, pricing, and technical documentation
- Exclusions: publicly available information, independently developed information, information received from third parties without obligation
- Term: 2 years from date of execution
- Permitted use: evaluation, shadow-mode validation, deployment, and operational use of the Porter Intelligence Platform
- Return/destruction: upon written request, within 30 days

### NDA Signature Block

```
For and on behalf of [Your Entity]:

Name: ____________________
Designation: ____________________
Date: ____________________
Signature: ____________________

For and on behalf of SmartShift Logistics Solutions Pvt Ltd:

Name: ____________________
Designation: ____________________
Date: ____________________
Signature: ____________________
```

Note: Porter's legal entity name is SmartShift Logistics Solutions Pvt Ltd. Confirm this before printing.

---

## 3. Commercial Schedule Template

### Section 1: Asset Description

The Porter Intelligence Platform asset package includes:

1. Source code: complete backend (Python/FastAPI), frontend (React), ML models (XGBoost, Prophet), ingestion pipeline, enforcement dispatch, security modules
2. Model weights: trained XGBoost fraud classifier, demand forecasting models
3. Documentation: architecture docs, API reference, runbooks, deployment guides, model card
4. Infrastructure templates: Docker Compose, AWS ECS Fargate task definitions, Prometheus/Grafana configs
5. Digital twin: 22-city simulation environment with configurable volume and fraud injection
6. Schema mapper: configurable field-mapping layer for Porter trip event integration
7. Board pack: executive-ready PDF with architecture, KPIs, ROI, and rollout plan

### Section 2: Payment Schedule

| Tranche | Amount | Trigger | Timeline |
|---|---|---|---|
| Tranche 1 | Rs 1,00,00,000 | Signing of this schedule | Day 0 |
| Tranche 2 | Rs 1,00,00,000 | Shadow-mode validation success (see acceptance criteria) | Day 30-60 |
| Tranche 3 | Rs 1,25,00,000 | Live rollout acceptance and handover completion | Day 60-90 |
| **Total** | **Rs 3,25,00,000** | | |

All amounts exclusive of GST (18% applicable).

### Section 3: Deployment And Support Scope

Phase 1 (Day 1-30): Setup and Shadow Validation
- Environment provisioning (AWS or Porter-provided infrastructure)
- Schema mapping and ingestion adapter configuration for Porter trip feed
- Shadow-mode activation and initial case generation
- Analyst training walkthrough (2 sessions, 1 hour each)
- Weekly progress reports

Phase 2 (Day 31-60): Validation and Acceptance
- Shadow-mode case review with Porter's fraud/ops team
- Reviewed-case precision measurement against agreed KPI targets
- Model threshold tuning based on Porter-specific patterns
- Acceptance criteria evaluation

Phase 3 (Day 61-90): Rollout and Handover
- Live enforcement mode activation (pending Porter approval)
- Enforcement dispatch webhook integration with Porter's driver systems
- Knowledge transfer sessions (3 sessions, 1.5 hours each)
- Documentation review and handover package delivery
- Support transition to Porter's internal team

Post Day 90:
- No ongoing support obligation unless separately agreed
- Source code and all documentation fully transferred
- Porter operates independently

### Section 4: Intellectual Property

- Upon full payment, Porter receives a perpetual, irrevocable, non-exclusive license to use, modify, and deploy the platform
- For exclusive license (Porter is the only licensee), add Rs 50 lakh to the total
- Source code is provided under no open-source obligation
- Model weights and training methodology are included
- Porter may modify, extend, and integrate the platform into their systems without restriction

### Section 5: Warranty

- The platform is delivered "as demonstrated during evaluation"
- The seller warrants that the platform performs materially as described in the technical documentation for 90 days from signing
- The seller does not warrant specific fraud detection rates on Porter's live data (this is the purpose of shadow-mode validation)
- Defects reported during the 90-day support window will be addressed with reasonable effort

---

## 4. Acceptance Criteria Checklist

Keep it short, measurable, and achievable. Maximum 5 items.

| # | Criterion | Measurement | Target |
|---|---|---|---|
| 1 | Ingestion path works | Porter trip events are successfully ingested, mapped, and scored | 95%+ ingestion success rate |
| 2 | Shadow mode operates without writeback | Zero enforcement actions dispatched during shadow period | 0 outbound webhooks |
| 3 | Analyst workflow is functional | Analysts can review, decide, and record cases with audit trail | 3+ analysts actively reviewing |
| 4 | Reviewed-case precision is acceptable | Action-tier cases confirmed as fraud by Porter analysts | 70%+ precision (action tier) |
| 5 | Deployment and documentation are delivered | Handover package, runbooks, and architecture docs reviewed by Porter | Porter technical lead sign-off |

### How Acceptance Is Determined

- Criteria 1-3 are binary (pass/fail)
- Criterion 4 is measured over a minimum of 200 reviewed action-tier cases
- Criterion 5 requires written confirmation from Porter's CPTO or designated technical lead
- All 5 criteria must be met for Tranche 2 payment to be triggered
- If criteria are not met within 60 days, both parties agree on a 30-day extension or scope adjustment

---

## 5. Same-Day Signature Workflow

### What To Bring To The Meeting

- 2 printed copies of each document (NDA, commercial schedule, MSA)
- 1 PDF version on a USB drive or ready to email
- 1 editable DOCX version on laptop (for live term adjustments)
- Invoice for Tranche 1 (pre-filled with your bank details)
- Your entity's rubber stamp and authorized signatory present (if required)
- Aadhaar/PAN of authorized signatory (for KYC if Porter's procurement requires it)

### If They Want To Sign On The Spot

1. Walk through the commercial schedule together on screen (5 minutes)
2. Confirm the acceptance criteria are acceptable (2 minutes)
3. Sign the NDA first (mutual protection)
4. Sign the commercial schedule
5. Issue Tranche 1 invoice
6. Agree on Day 1 kickoff date (ideally within 1 week)

### If They Need Internal Approval

1. Leave the printed packet with the decision-maker
2. Get the named approver (by name: "Who needs to approve this?")
3. Get the decision date (by date: "When will they review it?")
4. Offer to present to the approver directly if it helps
5. Send a follow-up email within 2 hours with the PDF packet and a one-paragraph summary

### If They Want To Negotiate Terms

Common negotiation points and prepared responses:

| Their Ask | Your Response |
|---|---|
| Lower total price | Move to fallback structure (Rs 3 Cr milestone-gated) or floor (Rs 1.75 Cr reduced scope) |
| Longer shadow validation | Accept 90 days instead of 60 if they commit to signing today |
| Exclusive license | Add Rs 50 lakh for exclusivity; or offer exclusivity for 12 months only |
| More support days | Accept up to 120 days if they move to the primary ask (Rs 3.25 Cr) |
| Remove one tranche (lump sum) | Accept if they pay Rs 2.5 Cr+ upfront |
| Add penalty clause | Accept reasonable penalty (e.g., refund Tranche 1 if Criterion 1 fails within 30 days) |

---

## 6. GST And Invoicing Notes

- SAC Code: 998314 (IT consulting and support services) or 997331 (licensing of rights to use computer software)
- GST Rate: 18%
- If Porter and your entity are in the same state: CGST 9% + SGST 9%
- If inter-state: IGST 18%
- TDS: Porter will likely deduct TDS at 10% (Section 194J for technical services) or 2% (Section 194C for contracts). Clarify with their finance team.
- Invoice format: must include GSTIN, SAC code, taxable value, GST breakdown, and your bank details

---

## 7. Day 12 Founder Output

By the end of Day 12, you should have:
- one NDA ready to print (mutual, 2-year term)
- one commercial schedule ready to print (asset description, 3 tranches, acceptance criteria, IP terms)
- one invoice template for Tranche 1 (Rs 1 crore + GST)
- your entity details, bank details, and GST registration confirmed
- same-day signature workflow rehearsed
- negotiation response table memorized
- zero administrative reasons for the buyer to say "we need to take this back and process it"
