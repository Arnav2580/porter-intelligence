# Day 01 - Commercial Framing

[Index](./README.md) | [Next](./day-02-cfo-note-and-roi.md)

Objective:
- establish the sale framing before any buyer conversation begins

Day-one founder output:
- pricing ladder with justification
- named stakeholder map with individual priorities
- positioning statement
- opening script

---

## 1. Pricing Ladder

### Primary Ask: Rs 3.25 Crore

Structure: enterprise asset and deployment deal, not a code sale.

What the price includes:
- full source code and IP transfer
- deployment package (Docker, AWS ECS Fargate, infra scripts)
- digital twin with 22-city simulation at Porter-like scale
- ingestion adapters and schema mapper for Porter's trip feed
- shadow-mode integration (read-only scoring, no operational writeback)
- fraud detection and ops workflow (analyst queue, case management, enforcement actions)
- demand forecasting and route-efficiency modules
- complete operator runbooks, handover documentation, and architecture docs
- 90-day deployment, hardening, and knowledge-transfer support window
- board pack, ROI calculator, and KPI definitions

Why Rs 3.25 Crore is rational:
- Porter's FY25 revenue is Rs 4,306 crore. The ask is 0.075% of annual revenue.
- Even a 2% fraud/leakage rate on Porter's transaction volume implies Rs 86 crore of annual leakage. Recovering 5% of that is Rs 4.3 crore in the first year alone.
- An equivalent internal build would require 3-5 senior engineers for 12-18 months: Rs 8-15 crore in loaded salary cost, plus opportunity cost.
- The platform compresses time-to-proof from 12+ months to 90 days.

### Strong Fallback: Rs 3 Crore Milestone-Gated

- Rs 1 crore on signing (source access, deployment package, documentation)
- Rs 1 crore on shadow-mode validation success (agreed precision and recall targets met within 60 days)
- Rs 1 crore on live rollout acceptance and handover completion (within 90 days)

Why this works:
- Porter bears less upfront risk
- every tranche is tied to verified product performance, not promises
- the founder has skin in the game until handover is complete

### Floor Ask: Rs 1.75 Crore

Only if scope is materially reduced:
- non-exclusive license (Porter can use it, but so can others)
- limited to 5 cities instead of full rollout
- reduced support window (30 days instead of 90)
- no custom extensions beyond ingestion mapping and shadow-mode setup
- no ongoing retraining support

When to use:
- only if Porter's decision-maker signals that the full scope exceeds their procurement threshold for a same-day decision
- never offer this preemptively; let them name a constraint first

### What You Say

"We are not selling a prototype or a repo. We are selling a working leakage-control asset with source access, deployment path, operator runbooks, shadow-mode integration, and a 90-day rollout and handover program. The price is anchored to recoverable value, not engineering hours."

### What You Must Never Say

- "I built this mostly with AI so we can finish the rest fast."
- "You can just buy the repo and figure it out."
- "We can keep adding anything you want after the deal."
- "The price is negotiable if you just give us a chance."
- Anything that frames this as a startup looking for a lifeline rather than a company selling a proven asset.

---

## 2. Stakeholder Map - Named Porter Leadership

### Uttam Digga - CEO and Co-Founder

Background:
- Co-founded Porter in 2014 (IIT graduate)
- Previously served as COO before restructuring in Aug 2023
- Deep operational background: personally onboarded early truck drivers
- Entrepreneur Of The Year 2025 (EY award, Start-up category, jointly with Pranav)
- Hands-on leader who understands driver economics and city operations

What he cares about:
- strategic control and competitive moat
- speed to operational improvement, not theoretical models
- whether this strengthens Porter's unit economics as they scale from 35 to 50+ cities
- whether this is a distraction or a force multiplier

How to speak to him:
- lead with operational pain and recovery potential, not technology
- use language like "control layer" and "intervention speed", not "ML model" or "dashboard"
- acknowledge that as an ex-COO he knows driver fraud intimately; do not explain the problem to him, validate that this solves it faster

His likely objection:
- "We already have internal teams looking at fraud."

Your answer:
- "This is not about whether you have teams. It is about whether those teams have a structured scoring-to-action pipeline with shadow-mode safety, reviewed-case KPIs, and a tighter intervention loop. This compresses the path from signal to action."

### Pranav Goel - Executive Vice Chairman and Co-Founder

Background:
- Co-founded Porter in 2014 (IIT graduate)
- Manages investor relations, strategic vision, business development
- Led Porter through Series F and unicorn milestone (Rs 10,400 Cr valuation)
- Entrepreneur Of The Year 2025 (EY award, jointly with Uttam)

What he cares about:
- investor narrative: margin improvement, operational efficiency, defensible tech
- whether this purchase fits into Porter's growth story and IPO trajectory
- board-level optics: is this a smart capital-allocation decision
- strategic positioning vs competitors (Lalamove, Shadowfax, Delhivery)

How to speak to him:
- frame the purchase as margin improvement and operational maturity, not as "buying software"
- connect it to Porter's profitability story: FY25 was the first profitable year (Rs 55 Cr net profit). This platform protects and expands that margin.
- the board pack should be immediately forwardable to Peak XV Partners, Kedaara, and Mahindra (Porter's key investors)

His likely objection:
- "Why not build this as part of our data platform roadmap?"

Your answer:
- "You can. But the comparison is not buy vs. build in isolation. It is: do you want to spend 12-18 months and Rs 8-15 crore of engineering salary to reach the same point, while leakage continues uncontrolled? Or do you want to compress that to 90 days and start recovering value immediately? For the board, this is a time-to-value decision."

### Shruti Ranjan Satpathy - Chief Product and Technology Officer (CPTO)

Background:
- Appointed CPTO during the Aug 2023 leadership restructuring
- Owns both product and engineering at Porter
- Responsible for platform integrations, API architecture, data infrastructure

What he cares about:
- integration complexity: how hard is it to plug this into Porter's existing systems
- security posture: will this pass InfoSec review
- supportability: what happens when the founder is gone
- tech stack compatibility: does this fit or fight Porter's existing architecture
- code quality: is this production-grade or demo-grade

How to speak to him:
- speak technically and honestly; do not oversell
- acknowledge that the model is trained on synthetic data and that shadow-mode validation is the real proof
- show the API contract, the schema mapper, the Docker deployment, the test suite
- emphasize: "This is designed to be handed over, not to create dependency"

His likely objection:
- "We need to run a security review before we can approve this."

Your answer:
- "That is expected and welcome. The system is built with AES-256-GCM encryption for PII, JWT authentication with RBAC, rate limiting, audit logging, and scoped CORS. The security posture is designed to be reviewable, not hidden. We can provide the security summary document and walk your InfoSec team through it."

### CFO / Finance Controller (Name Not Publicly Available)

What this role cares about:
- payback period
- whether the ROI model is audit-safe or speculative
- whether the savings claim survives scrutiny
- procurement classification: capex vs opex

How to speak to this role:
- use the CFO memo (Day 02 artifact)
- frame the purchase as "leakage-reduction investment" not "software spend"
- never claim specific savings amounts as guarantees; always frame them as scenarios with assumptions

Their likely objection:
- "These are synthetic numbers. How do we know this works in practice?"

Your answer:
- "The benchmark numbers are pre-integration evidence. The reviewed-case KPIs become the buyer-safe truth layer after your analysts validate cases in shadow mode. We are not asking you to trust synthetic ROI as final truth. We are asking you to evaluate whether the operating model and validation path justify a controlled investment."

### Fraud / Risk Operations Head

What this role cares about:
- false alarm rate: will this drown their team in noise
- workflow discipline: does this fit their existing investigation process
- actionability: can they actually suspend or flag a driver based on this
- audit trail: can they justify their decisions to management

How to speak to this role:
- show the analyst workspace: case queue, evidence, action buttons, override reasons, audit log
- emphasize the two-tier scoring: action tier (high confidence) vs watchlist (monitor) to prevent alert fatigue
- frame it as: "This gives your team structured decision support, not a black box"

Their likely objection:
- "We already investigate fraud cases manually."

Your answer:
- "Manual investigation is the right approach. This platform does not replace your team. It routes higher-quality signals to your team faster, with evidence, and tracks reviewed outcomes so you can measure and improve over time."

### Vikas Choudhary - Co-Founder (Tech Background)

Background:
- IIT Kanpur (Electrical Engineering), Stanford GSB
- Built Porter's original technology platform
- May not be in day-to-day operations but carries founder authority

Role in this decision:
- technical validation from a founder who built the original system
- if he is in the room, expect deep technical questions
- he will evaluate whether this is a serious system or a weekend project

---

## 3. Positioning Statement

### Two-Sentence Version

"Porter Intelligence Platform is a leakage-control operating system for intra-city logistics. It detects fraud, payout anomalies, and operational abuse in real time, runs first in shadow mode with zero operational risk, and becomes a measurable savings layer once validated on Porter's own data."

### One-Sentence Version

"This is a control layer for leakage and fraud, not another dashboard."

### 20-Second Elevator Version

"Porter processes lakhs of trips daily across 35 cities. Some fraction of those trips involve fraud, route abuse, or payout anomalies. This platform scores every trip, routes high-risk cases to an operations workflow, and lets your team act before the money is gone. It runs in shadow mode first, so there is zero risk to your live systems."

---

## 4. Opening Script

Use this in the first 90 seconds of any conversation:

"Thank you for your time. I want to be direct about what this is and what it is not.

This is not another analytics dashboard. It is a leakage-control layer built specifically for intra-city logistics at Porter's scale.

It does three things:
1. It scores every trip for fraud and payout anomaly risk in real time.
2. It routes high-risk cases into an operations workflow where your analysts can review, confirm, and act.
3. It runs in shadow mode first, so you validate signal quality before any operational coupling.

The question for this meeting is not whether the model looks interesting. The question is whether a structured path from detection to intervention to measurable recovery justifies a same-day commercial decision."

---

## 5. Founder Standard For Day 01

By the end of Day 01, you should be able to answer without hesitation:

- What exactly are we selling? A leakage-control operating asset with source, deployment, shadow mode, workflow, and handover.
- Who exactly needs to believe the story? Uttam (CEO), Pranav (strategy), Shruti (CPTO), the CFO, and the fraud/risk head.
- Why is the pricing ladder structured this way? Because the primary ask is anchored to recoverable value, the fallback is milestone-gated to reduce buyer risk, and the floor preserves deal seriousness.
- How do you describe the product in under 20 seconds? "Scores every trip, routes high-risk cases to ops, runs in shadow mode first, becomes a savings layer on real data."

Success test:
- if someone interrupts you after 30 seconds, they should still understand:
  - the pain (leakage at scale is real and growing)
  - the product category (control layer, not dashboard)
  - the commercial structure (asset + deployment + handover, not hourly services)
