# Day 10 - Board Pack Leave-Behind

[Index](./README.md) | [Prev](./day-09-commercial-framing.md) | [Next](./day-11-demo-fail-safe.md)

Objective:
- produce a leave-behind packet that travels inside Porter without you present
- every page must stand alone: clear enough for someone who was not in the demo room

---

## 1. Board Pack Structure — 6 Pages

The board pack is the single most important document in the sale process. If the meeting goes well but they need board approval, this is what circulates. If the meeting goes sideways but they remember the problem, this is what brings them back.

Every page must answer one question. If a page does not clearly answer its question, it fails.

---

## 2. Page 1: Executive Summary — "What Is The Pain And Why Now?"

### Headline

**Porter Intelligence Platform: A Leakage-Control Operating System For Intra-City Logistics**

### Opening Paragraph

> Porter processes lakhs of trips daily across 35 cities with 3 lakh driver-partners. Industry estimates place fraud and operational leakage — fake trips, route manipulation, cash extortion, payout anomalies, cancellation abuse — at 2-4% of transaction volume.
>
> At Porter's FY25 revenue of Rs 4,306 crore, even a 2% leakage rate represents Rs 86 crore in annual loss. This leakage is currently addressed through manual investigation, which is reactive, unscalable, and inconsistent across cities.
>
> Porter Intelligence Platform is a purpose-built detection and intervention system that scores every trip in real time, routes high-risk cases to an analyst workflow, and enables enforcement actions through a structured, auditable process.

### Why Now

- FY25 was Porter's first profitable year (Rs 55 Cr net profit). Protecting margin is now the priority.
- Scaling from 35 to 50 cities will increase leakage proportionally unless a control layer is in place.
- Competitors who control leakage better will have structurally better unit economics.
- The platform is available now, deployable in 30 days, and validatable through shadow mode with zero operational risk.

### Category Clarification Box

| This IS | This IS NOT |
|---|---|
| A leakage-control operating system | A dashboard |
| A detection-to-action pipeline | A passive reporting layer |
| A shadow-safe validation environment | A system that touches operations immediately |
| A transferable enterprise asset | A founder-dependent prototype |

---

## 3. Page 2: System Architecture — "What Exists Today?"

### Architecture Overview

```
Trip Events (Porter Pipeline)
    |
    v
Ingestion Layer (webhook / CSV / API push)
    |
    v
Schema Mapper (configurable field translation)
    |
    v
Fraud Scoring Engine (XGBoost, 35 features, two-tier)
    |
    v
Case Creation (action tier / watchlist / clear)
    |
    v
Analyst Workflow (queue, evidence, decisions, audit trail)
    |
    v
Enforcement Dispatch (suspend / flag / monitor — shadow or live)
    |
    v
Manager Dashboard (KPIs, heatmap, case age, city comparison)
```

### Tech Stack Summary

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, async SQLAlchemy |
| ML Models | XGBoost (fraud), Prophet (demand forecasting) |
| Storage | PostgreSQL 15, Redis 7 |
| Frontend | React 19, Vite, Leaflet (heatmaps) |
| Security | AES-256-GCM (PII), JWT + RBAC, rate limiting, audit logs |
| Infrastructure | Docker, AWS ECS Fargate |
| Observability | Prometheus, Grafana |

### What Exists Today (Built And Demonstrable)

- 14 REST API endpoints across 9 routers
- Two-stage fraud scoring (88.3% benchmark precision at action tier, 0.53% FPR)
- Shadow-mode case isolation with zero enforcement writeback
- Full analyst workflow: case queue, evidence, decisions, driver actions, audit trail
- 22-city digital twin with configurable volume and fraud injection
- Schema mapper for Porter trip event integration
- Demand forecasting (per-zone, 24-hour horizon)
- Route efficiency analysis and reallocation engine
- ROI calculator with three scenarios
- Board pack PDF generation
- 17 test files covering scoring, auth, encryption, shadow mode, API contracts

### What Final Rollout Looks Like

- Connected to Porter's live trip pipeline via webhook
- Shadow mode validated on real data (30-60 days)
- Enforcement dispatch connected to Porter's driver management system
- Analyst team trained and operating on real cases
- Model retrained on Porter-specific patterns
- Full documentation and runbooks transferred to Porter's engineering team

---

## 4. Page 3: Model And KPI Trust — "Why Should We Believe The Numbers?"

### The Honesty Framework

The platform makes two categories of claims:

**Benchmark claims (synthetic data):**
- These show that the model works on simulated trip data at Porter-like scale
- 88.3% action-tier precision, 0.53% false-positive rate, 25%+ detection improvement
- These are pre-integration evidence — they demonstrate capability, not final proof

**Reviewed-case claims (real data via shadow mode):**
- These show that the model works on Porter's actual data as judged by Porter's own analysts
- Reviewed-case precision = % of action-tier cases that Porter analysts confirm as real fraud
- This is the buyer-safe truth layer — it validates on Porter's data, judged by Porter's people

### The Trust Path

```
Step 1: Benchmark evidence (today)
    "The model catches fraud patterns in synthetic data."
    
Step 2: Shadow-mode validation (Day 1-60)
    "The model catches fraud patterns in Porter's real data."
    "Porter's analysts confirm this by reviewing cases."
    
Step 3: Live enforcement (Day 60-90)
    "The model catches fraud and Porter's team acts on it."
    "Recoverable value is measurable."
```

### KPI Definitions (Finance-Safe)

| KPI | Definition | Why It Matters |
|---|---|---|
| Reviewed-case precision (action tier) | % of action-tier cases confirmed as fraud by analyst review | This is the real accuracy metric — not model confidence, but human-validated truth |
| False-alarm rate | % of action-tier cases dismissed as false alarm by analysts | Must stay below 30% for analyst trust; benchmark is 0.53% FPR |
| Recovery rate | % of confirmed fraud cases where enforcement action prevents future leakage | Measures actual operational impact, not just detection |
| Analyst throughput | Cases reviewed per analyst per day | Measures workflow efficiency and team capacity |
| Case age (action tier) | Average time from case creation to analyst decision | Must stay below 4 hours for operational relevance |

### What To Say About Synthetic Data

"The benchmark numbers are real, but they are pre-integration evidence. We do not claim that synthetic precision equals production precision. The shadow-mode validation path exists specifically to replace benchmark claims with reviewed-case truth on Porter's own data."

---

## 5. Page 4: Deployment And Rollout Plan — "How Does This Get Into Our Systems Safely?"

### The 90-Day Roadmap

| Phase | Timeline | What Happens | Risk Level |
|---|---|---|---|
| **Phase 1: Setup** | Day 1-7 | Infrastructure provisioning, schema mapping, ingestion adapter configuration | Zero — no connection to live ops |
| **Phase 2: Shadow Mode** | Day 8-60 | Real trip data scored, cases created, analysts review, precision measured | Zero — no operational writeback |
| **Phase 3: Acceptance** | Day 45-60 | Acceptance criteria evaluated, threshold tuning, analyst team expanded | Zero — still shadow mode |
| **Phase 4: Live Rollout** | Day 61-90 | Enforcement dispatch enabled, driver actions taken, live KPIs monitored | Controlled — supervised enforcement |
| **Phase 5: Handover** | Day 75-90 | Knowledge transfer, documentation review, ownership transition to Porter | N/A |

### The Safety Guarantee

- Shadow mode ensures zero operational impact during validation
- Live rollout only begins after Porter's CPTO signs off on acceptance criteria
- First week of live enforcement is supervised: every action reviewed in real time
- Rollback is a configuration change (set `SHADOW_MODE=true`), not a code change

### What Porter Needs To Provide

| Item | When | Effort |
|---|---|---|
| AWS account or infrastructure access | Day 1 | DevOps — 2 hours |
| Trip event feed (webhook or batch) | Day 3-7 | Data engineering — 4-8 hours |
| 2-3 fraud/ops analysts for shadow review | Day 8 | Existing team reallocation |
| CPTO or tech lead for acceptance sign-off | Day 45-60 | 1 review meeting |
| Driver management webhook URL (for enforcement) | Day 61 | Engineering — 2-4 hours |

---

## 6. Page 5: ROI And Commercial Structure — "What Does This Cost And What Does It Return?"

### The ROI Table

| | Conservative | Realistic | Aggressive |
|---|---|---|---|
| Assumed leakage rate | 2% | 3% | 4% |
| Annual leakage (Rs Cr) | 86 | 129 | 172 |
| Recoverable value (Rs Cr/yr) | 10.3 | 31.9 | 61.5 |
| **Payback period** | **3.8 months** | **5.9 weeks** | **2.7 weeks** |
| Year 1 ROI | 217% | 881% | 1,792% |

### The Commercial Structure

| Tranche | Amount | Trigger |
|---|---|---|
| Signing | Rs 1.00 Cr | Source access + deployment + documentation |
| Shadow validation | Rs 1.00 Cr | Acceptance criteria met (60 days) |
| Live rollout + handover | Rs 1.25 Cr | Enforcement live + knowledge transfer (90 days) |
| **Total** | **Rs 3.25 Cr** | + 18% GST |

### The One-Line Price Defense

"The platform costs less than one week of recoverable leakage under the realistic scenario."

### What Porter Gets For Rs 3.25 Crore

- Complete source code and IP (perpetual license)
- Deployment package (Docker + AWS ECS Fargate)
- 22-city digital twin
- Ingestion adapters and schema mapper
- Shadow-mode integration
- Analyst workflow and enforcement dispatch
- Operator runbooks (7 procedures)
- Architecture docs, model card, API reference
- 3 knowledge-transfer sessions
- 90-day support window
- Board pack and ROI calculator

---

## 7. Page 6: Risks, Mitigations, And Decision Request

### Known Risks (Honest)

| Risk | Mitigation |
|---|---|
| Model trained on synthetic data | Shadow-mode validation on real Porter data before live enforcement |
| Founder/key-person dependency | Full documentation, runbooks, 90-day handover, 3 knowledge-transfer sessions |
| Integration complexity | Schema mapper handles field differences; ingestion tested on sample data |
| False alarms affect driver trust | Two-tier scoring limits action-tier flags; shadow mode measures FPR before enforcement |
| Organizational adoption | Shadow mode gives 30-60 day trial; analyst workflow learnable in 30 minutes |
| Price not justified | Milestone-gated payments; full amount due only after proven value |

### The Decision Request

> We are asking Porter to approve a same-day commercial schedule:
>
> - Rs 3.25 crore, milestone-gated across signing, shadow validation, and live rollout
> - Begin shadow-mode setup within 1 week of signing
> - Validate on Porter's real data for 30-60 days
> - Move to live enforcement only after CPTO sign-off on acceptance criteria
> - Full knowledge transfer and handover by Day 90
>
> The risk is minimal: shadow mode ensures zero operational impact during validation, and the milestone structure ensures Porter pays the full amount only after proven value.
>
> The cost of delay is real: every month without a structured leakage intervention system is Rs 7-11 crore in uncontrolled loss (at 2-3% leakage).

### Next Steps (Printed On The Page)

- Week 1: Schema mapping and shadow-mode setup
- Week 2-4: Analyst review and precision measurement
- Week 5-8: Threshold tuning and acceptance evaluation
- Week 9-12: Live enforcement, knowledge transfer, and handover

---

## 8. Leave-Behind Rules

### The Forwarding Test

If the board pack is forwarded to someone who was not in the meeting, they should understand within 5 minutes:
- the pain (leakage at scale)
- the product category (control layer, not dashboard)
- the trust path (benchmark → shadow → live)
- the commercial structure (Rs 3.25 Cr, milestone-gated)
- the ask (same-day commercial approval)

### The Circulation Instruction

Say this when leaving the packet:

"This is designed to circulate internally without me. If someone reviews it and has questions, I am available to present directly or answer in writing. The board pack covers: the problem, the system, the trust layer, the rollout plan, the ROI, and the decision request."

### Print Format

- 6 pages, single-sided, stapled
- Include a cover page with the headline: "Porter Intelligence Platform: Leakage-Control Operating System"
- Include your contact details on the last page
- Attach the finance memo as a separate sheet for the CFO

---

## 9. Day 10 Founder Output

By the end of Day 10, you should have:
- a complete 6-page board pack with actual content on every page (not just outlines)
- first page headline and opening paragraph finalized
- last page decision request specific and askable
- every page answering one clear question
- the pack tested: can someone who was not in the room understand the story in 5 minutes?
- the pack printed and ready for Day 14
