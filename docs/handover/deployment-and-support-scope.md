# Deployment and Support Scope

[Handover Hub](./README.md) | [Acceptance Criteria](./acceptance-criteria.md)

This document defines the 90-day deployment and support engagement: what is included, what is excluded, who is responsible for what, and how issues are escalated.

---

## Engagement Overview

| Phase | Duration | Objective |
|-------|----------|-----------|
| Phase 1 — Setup and Shadow Activation | Day 1–30 | Environment live, shadow mode generating cases |
| Phase 2 — Validation and Acceptance | Day 31–60 | Acceptance criteria evaluated and confirmed |
| Phase 3 — Rollout and Handover | Day 61–90 | Live enforcement (if approved), full handover complete |

---

## Phase 1: Setup and Shadow Activation (Day 1–30)

### Deliverables

- Environment provisioning completed (AWS or Porter-provided infrastructure)
- PostgreSQL and Redis running, schema initialised, health endpoint returning `ok`
- Schema mapping adapter configured for Porter's trip event format
- Ingestion path verified (webhook or batch CSV)
- Shadow mode active: cases being scored and stored, no enforcement dispatch
- Initial analyst accounts created and access confirmed
- Two analyst training walkthroughs delivered (1 hour each, remote or on-site)
- Weekly written progress report (every Friday)

### Milestones

| Day | Milestone |
|-----|-----------|
| 3 | Environment provisioned and health endpoint returning `ok` |
| 7 | First Porter trip event successfully scored and stored in shadow |
| 14 | 100+ shadow cases in queue, analyst accounts active |
| 30 | Shadow mode stable, Criterion 1 and 2 verified |

### Responsibility Split

| Item | Seller | Porter |
|------|--------|--------|
| Platform source code and setup | Yes | |
| AWS/infrastructure provisioning | Guidance + templates | Final approval and cost |
| Porter trip event access (webhook or batch) | Integration support | Providing the data |
| Database and Redis credentials | Configuration | Hosting decision |
| Analyst training sessions | Delivery | Scheduling and attendance |
| Network firewall / VPN access | Requirements doc | Implementation |

---

## Phase 2: Validation and Acceptance (Day 31–60)

### Deliverables

- Shadow-mode case review with Porter's fraud/ops team underway
- Reviewed-case precision tracked and reported weekly
- Threshold tuning performed if Porter-specific fraud patterns differ from benchmark
- Criterion 3 (analyst workflow) confirmed at Day 30 evaluation
- Criterion 4 (reviewed-case precision) evaluated after 200+ reviewed cases
- One joint evaluation session with Porter's fraud lead (1.5 hours)

### Threshold Tuning

If Porter's live data distribution produces materially different precision numbers than the benchmark, the action threshold (default 0.94) can be recalibrated. This involves:

1. Exporting reviewed cases from the shadow period as labelled training data
2. Re-running the threshold grid search (`model/train.py:tune_threshold()`) against Porter-specific data
3. Updating `model/weights/threshold.json` and `two_stage_config.json`
4. Redeploying the updated model weights

One threshold tuning cycle is included at no additional cost.

### Acceptance Gate

Tranche 2 payment is triggered when all 5 acceptance criteria are met and confirmed in writing. See [Acceptance Criteria](./acceptance-criteria.md) for full detail.

---

## Phase 3: Rollout and Handover (Day 61–90)

### Deliverables

- Live enforcement mode activation (pending explicit Porter approval)
- Enforcement dispatch webhook configured against Porter's driver management system
- Full integration test: trip → score → case → analyst → enforcement dispatch
- Three knowledge transfer sessions (1.5 hours each, remote)
- Complete handover package reviewed and confirmed (Criterion 5)
- Source code repository access transferred
- Model weights and training data access confirmed

### Knowledge Transfer Sessions

| Session | Topic |
|---------|-------|
| KT-1 | Architecture walkthrough, codebase navigation, deployment |
| KT-2 | Model card, feature engineering, threshold tuning, retraining |
| KT-3 | Operations runbooks, secret rotation, monitoring, escalation path |

### Live Enforcement Activation

Enforcement dispatch is only activated with Porter's explicit written approval. The activation sequence:

1. Set `SHADOW_MODE=false` and `PORTER_DISPATCH_URL` to the production endpoint
2. Verify one test enforcement call (using a synthetic trip) before live activation
3. Monitor the dispatch log for the first 48 hours after activation

---

## What Is Included

- Environment setup support (guidance and troubleshooting, not hands-on cloud provisioning)
- Schema mapper configuration for Porter's trip event format
- Two analyst training walkthroughs (Phase 1)
- One joint evaluation session (Phase 2)
- Three knowledge transfer sessions (Phase 3)
- One threshold tuning cycle (Phase 2)
- Weekly progress reports (Phase 1 and 2)
- Bug fixes for defects that prevent the platform from meeting acceptance criteria
- All documentation included in the handover package

---

## What Is Not Included

- Ongoing support after Day 90 (unless separately agreed)
- Additional feature development beyond the platform as demonstrated
- Integration with Porter internal systems beyond the dispatch webhook and ingest webhook
- Compliance certifications (SOC 2, ISO 27001, etc.)
- Data migration from Porter's existing fraud tools
- Model retraining on Porter's historical data beyond the included single tuning cycle
- SLA-backed uptime guarantees (the platform is delivered as infrastructure for Porter to host)

---

## Communication and Escalation

### Primary Communication

- Weekly written status report via email (every Friday during Phases 1 and 2)
- Response to technical questions within 1 business day
- Critical issues (platform down, data loss risk): same-day response target

### Issue Classification

| Severity | Definition | Response Target |
|----------|------------|-----------------|
| P1 | Platform inaccessible, data loss, ingestion stopped | Same business day |
| P2 | Core feature broken (scoring, case review, reports) | 1 business day |
| P3 | Non-critical feature issue, cosmetic, edge case | Next weekly report |

### Escalation Path

1. Email to seller's primary contact with subject: `[PORTER-P1]` or `[PORTER-P2]`
2. If no response within the target window: escalate to the named secondary contact
3. Dispute resolution: per the Master Service Agreement dispute resolution clause

---

## Post Day 90

- No ongoing support obligation unless separately agreed in writing
- Source code and all documentation fully transferred to Porter
- Porter operates the platform independently
- Model retraining, feature extension, and integration work available at separately negotiated rates

---

## Infrastructure Requirements

Porter's team needs to provision and maintain:

| Component | Minimum Spec | Notes |
|-----------|-------------|-------|
| PostgreSQL 15 | 2 vCPU, 4GB RAM, 50GB storage | RDS `db.t3.medium` or equivalent |
| Redis 7 | 1 vCPU, 1GB RAM | ElastiCache `cache.t3.micro` or equivalent |
| API server | 2 vCPU, 4GB RAM | ECS Fargate or EC2 `t3.medium` |
| Load balancer | Optional | Required only if multi-AZ desired |

Infrastructure cost estimate (AWS): Rs 15,000–25,000 per month depending on region and volume.

Full AWS deployment templates are included in `infrastructure/aws/`.
