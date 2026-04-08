# Day 08 - Handover And Key Person Risk

[Index](./README.md) | [Prev](./day-07-cxo-talk-tracks.md) | [Next](./day-09-commercial-framing.md)

Objective:
- make post-purchase continuity feel credible and specific
- turn the "founder dependency" objection from a blocker into a strength of the deal structure

---

## 1. Answer To "What Happens After We Buy This?"

### The Short Answer (15 Seconds)

"You receive a complete operating asset: source code, deployment package, operator runbooks, architecture docs, model card, and a 90-day support and knowledge-transfer window. After Day 90, your team owns and operates independently."

### The Full Answer (60 Seconds)

"What you are buying is not a repo drop. Let me be specific about what the package includes:

First, source code and IP. Full Python backend, React frontend, ML models, ingestion pipeline, enforcement dispatch — everything you saw in the demo. Perpetual license, no recurring fees.

Second, deployment package. Docker Compose for local, AWS ECS Fargate for production, infrastructure scripts, environment configuration templates. Your team can deploy this to a fresh AWS account in under an hour.

Third, operator runbooks. Step-by-step procedures for the seven things an operator needs to do: add a city, retrain the model, rotate secrets, restore from backup, scale workers, configure ingestion, and troubleshoot scoring failures.

Fourth, documentation. Architecture overview, API reference, model card with training methodology and threshold justification, KPI definitions, and a security summary.

Fifth, a 90-day support window. Three phases: setup and shadow validation, analyst workflow and acceptance, and live rollout with knowledge transfer. Weekly check-ins. By Day 90, your internal team is the primary owner.

The operating knowledge is packaged with the system. Your team is not left reverse-engineering context from code comments."

### The Deliverable List (Say This Out Loud In The Room)

When Shruti or Pranav asks "what exactly do we get," list these:

1. Source code package (Python backend, React frontend, ML models, tests)
2. Deployment package (Docker, ECS task definitions, Prometheus/Grafana configs)
3. Infrastructure scripts (AWS setup, database provisioning, Redis configuration)
4. Operator runbooks (7 procedures — see Section 3 below)
5. Architecture documentation (module map, data flow, API reference)
6. Model card (training data, features, thresholds, known limitations)
7. KPI definition sheet (what each metric means, how it is calculated, what is buyer-safe)
8. Security summary (encryption, auth, RBAC, audit logging, rate limiting)
9. Board pack (executive summary, ROI, rollout plan — PDF ready to circulate)
10. 90-day support and knowledge-transfer program

---

## 2. Answer To "How Do We Reduce Founder/Key-Person Risk?"

### Why This Question Will Come Up

Pranav will think about this from a board governance perspective: "We are buying a system from one person. What if they disappear?"

Shruti will think about this from an engineering perspective: "Can my team maintain this without the builder?"

This is a legitimate concern. Do not dismiss it. Address it with specifics.

### The Honest Framing

"Founder dependency is a real risk when the product is undocumented, unstable, and held together by tacit knowledge. The entire handover package is designed to eliminate that condition. Let me show you specifically how."

### The Seven Runbooks That Prove Transferability

These are the seven things an operator would need to do without the founder. Each one has a step-by-step runbook:

| # | Runbook | What It Covers | Complexity |
|---|---|---|---|
| 1 | **Adding a city** | Zone configuration, demand baseline seeding, scoring threshold calibration, dashboard update | Low — config files and database seeds |
| 2 | **Retraining the model** | Data preparation, feature engineering, XGBoost training, threshold validation, model swap | Medium — requires ML familiarity |
| 3 | **Rotating secrets** | JWT secret key, encryption key, webhook secret, database password, Redis password | Low — environment variable updates + restart |
| 4 | **Restoring from backup** | PostgreSQL point-in-time recovery, Redis snapshot restore, model weight restore from S3 | Medium — standard database ops |
| 5 | **Scaling workers** | ECS task count adjustment, Uvicorn worker configuration, Redis consumer scaling | Low — infrastructure config |
| 6 | **Configuring ingestion** | Schema mapping for new data sources, webhook endpoint setup, batch CSV upload | Low — JSON config + API calls |
| 7 | **Troubleshooting scoring failures** | Model loading errors, feature computation failures, threshold configuration issues, queue backlog | Medium — log analysis and config checks |

### The Acid Test

Say this in the room:

"If I disappear after Day 90, your team should still be able to: start the system, deploy it to a new environment, add a city, retrain the model on new data, rotate every secret, restore from a backup, and diagnose why scoring stopped working. If they cannot, the handover failed. That is the standard I am building toward."

### What Porter's Team Needs To Staff

Be honest about what Porter needs on their side:

| Role | Responsibility | Estimated Effort |
|---|---|---|
| 1 DevOps / SRE engineer | Infrastructure, deployment, monitoring, scaling | 20% of time ongoing |
| 1 ML engineer (or data scientist) | Model retraining, threshold tuning, drift monitoring | 10-15% of time ongoing |
| 2-6 fraud/ops analysts | Daily case review, driver actions, quality feedback | Full-time during operational use |
| 1 engineering manager or tech lead | Owns the system post-handover, point of contact | 10% oversight |

If they already have a fraud team (likely), the analyst roles are covered. The engineering investment is fractional — one person spending 20% of their time on infra and one spending 10-15% on model tuning.

---

## 3. The 90-Day Handover Plan — Detailed

### Phase 1: Setup And Shadow Validation (Day 1-30)

**Week 1: Environment and Ingestion**
- Provision infrastructure (AWS ECS, RDS PostgreSQL, ElastiCache Redis) or use Porter's existing infra
- Deploy the platform to Porter's environment
- Configure schema mapper for Porter's trip event format
- Connect ingestion adapter to Porter's trip pipeline (webhook or batch)
- Verify first trip events are ingested and scored correctly

**Week 2: Shadow Mode Activation**
- Enable shadow mode (`SHADOW_MODE=true`)
- Verify shadow cases are created in isolated storage
- Verify zero enforcement webhooks dispatched
- Onboard 2-3 analysts with a 1-hour training walkthrough
- Begin case review: analysts evaluate action-tier and watchlist cases against their own judgment

**Week 3-4: Shadow Validation**
- Accumulate reviewed cases (target: 500+ action-tier reviews)
- Measure reviewed-case precision (target: 70%+ for action tier)
- Measure false-alarm rate
- Identify any Porter-specific fraud patterns not covered by current features
- Weekly progress report to Porter's technical lead

**Deliverable at Day 30:**
- Shadow-mode validation report: precision, recall, false-alarm rate, case volume, analyst feedback
- Go/no-go recommendation for Phase 2

### Phase 2: Acceptance And Workflow Hardening (Day 31-60)

**Week 5-6: Threshold Tuning**
- Adjust scoring thresholds based on shadow validation results
- If precision is below target: tighten action-tier threshold, expand watchlist range
- If false-alarm rate is too high: analyze false-alarm patterns, add exclusion rules or new features
- Re-run shadow scoring on historical data to verify improvement

**Week 7-8: Workflow Integration**
- Expand analyst team to target size (4-6 analysts across key cities)
- Establish case review SLAs: action-tier cases reviewed within 4 hours
- Configure manager dashboard for city operations leadership
- Run acceptance criteria evaluation (see Day 12 for the 5 criteria)

**Deliverable at Day 60:**
- Acceptance criteria sign-off from Porter's CPTO or technical lead
- Tranche 2 payment triggered (Rs 1 crore)
- Go/no-go recommendation for live rollout

### Phase 3: Live Rollout And Knowledge Transfer (Day 61-90)

**Week 9-10: Enforcement Activation**
- Configure `PORTER_DISPATCH_URL` for webhook integration with Porter's driver management system
- Enable enforcement dispatch (driver suspend, flag, monitor actions)
- Run first live enforcement actions under close supervision
- Monitor for false positives in live enforcement (immediate review of every action for first week)

**Week 11: Knowledge Transfer**
- Session 1 (1.5 hours): Architecture walkthrough for Porter's engineering team — module structure, data flow, API contracts, deployment
- Session 2 (1.5 hours): ML walkthrough — model training, feature engineering, threshold tuning, retraining procedure
- Session 3 (1.5 hours): Operations walkthrough — runbooks, troubleshooting, monitoring, alerting, backup/restore

**Week 12: Closeout**
- Final documentation review and updates based on questions from knowledge transfer
- Handover sign-off: Porter's technical lead confirms ability to operate independently
- Tranche 3 payment triggered (Rs 1.25 crore)
- Support transition: founder available for email questions for 30 days post-handover (best-effort, not contractual)

---

## 4. Key-Person Risk Mitigation Matrix

| Risk | Mitigation | Evidence |
|---|---|---|
| Founder unavailable after purchase | Full documentation package + 90-day support window | Runbooks, architecture docs, model card |
| Code is incomprehensible | Clean module structure, type hints, comprehensive test suite | 17 test files, Pydantic schemas, async patterns |
| Model cannot be retrained | Retraining runbook with step-by-step procedure | Training script, feature list, threshold validation process |
| Secrets are lost | Secret rotation runbook, environment variable documentation | Config reference sheet, no hardcoded secrets |
| Infrastructure cannot be reproduced | Docker Compose + ECS task definitions + infra scripts | One-command local setup, documented AWS deployment |
| Team does not know how to use it | Analyst training (2 sessions) + knowledge transfer (3 sessions) | Training walkthrough, demo scenarios, workflow guide |
| Product breaks and no one can fix it | Troubleshooting runbook + Prometheus/Grafana monitoring + alert rules | 7 troubleshooting procedures, health check endpoint, metrics |

---

## 5. Forwardable Summary

If someone asks for the one-paragraph version to send in email or Slack:

> Porter Intelligence Platform is a transferable operating asset, not a founder-dependent prototype. The buyer receives: complete source code and IP, deployment package (Docker + AWS), operator runbooks (7 procedures covering city addition through disaster recovery), architecture documentation, model card, security summary, and a 90-day support program with three knowledge-transfer sessions. After handover, Porter operates the system independently with estimated 0.3 FTE engineering overhead and their existing fraud operations team.

---

## 6. What Pranav Wants To Hear (Board Governance Lens)

"The system is designed so that founder involvement decreases to zero by Day 90. The documentation, runbooks, and knowledge-transfer sessions exist specifically so that Porter's internal team becomes the primary owner. If the board asks 'what happens if the vendor disappears,' the answer is: the system is documented, deployable, and operable by your own team. That is the handover standard."

## 7. What Shruti Wants To Hear (Engineering Lens)

"Your team can read the code. It is Python with type hints, Pydantic schemas, and comprehensive tests. The architecture is modular: API routes, model scoring, ingestion, enforcement, security, and database are all separate modules. A senior Python engineer can understand the full system in 1-2 days. The runbooks cover every operational scenario. And if something genuinely confusing comes up during the 90-day window, I am available to explain it."

---

## 8. Day 08 Founder Output

By the end of Day 08, you should have:
- one 60-second handover explanation that names every deliverable
- one specific answer to "what if you disappear" that references runbooks, docs, and knowledge transfer
- a detailed 90-day handover plan (week-by-week, not vague phases)
- a staffing recommendation for Porter's side (honest about what they need to invest)
- a risk mitigation matrix that can be shown on screen or printed
- confidence that this is the strongest answer to the strongest objection
