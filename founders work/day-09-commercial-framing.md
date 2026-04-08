# Day 09 - Commercial Framing And Price Defense

[Index](./README.md) | [Prev](./day-08-handover-and-key-person-risk.md) | [Next](./day-10-board-pack.md)

Objective:
- make the price feel rational instead of emotional
- arm the founder with real comparisons that survive scrutiny from Porter's CFO and CPTO

---

## 1. Core Commercial Frame

### What You Are NOT Selling

Do not let anyone frame this as:
- engineering hours ("How many hours did this take?")
- number of dashboard screens ("It is only a few pages")
- model complexity ("XGBoost is basic ML")
- lines of code ("We could write this in a few months")

If anyone frames it this way, redirect immediately.

### What You ARE Selling

Frame every pricing conversation around these three anchors:

1. **Loss-reduction asset**: "The price is anchored to recoverable leakage, not to engineering effort."
2. **Speed-to-value asset**: "The price buys 90-day time-to-proof instead of 12-18 months."
3. **Internal build avoidance asset**: "The price is a fraction of what equivalent internal build would cost."

### The Opening Line For Any Price Conversation

"The right comparison is not software spend. The right comparison is how much leakage remains uncontrolled if this system is not in place."

---

## 2. Price vs. Three Real Comparisons

### Comparison 1: Price vs. Recoverable Leakage

| | Amount |
|---|---|
| Porter FY25 revenue | Rs 4,306 Cr |
| Leakage at 2% (conservative) | Rs 86 Cr/year |
| Leakage at 3% (realistic) | Rs 129 Cr/year |
| Platform cost | Rs 3.25 Cr (one-time) |
| Platform cost as % of annual leakage (conservative) | 3.8% |
| Platform cost as % of annual leakage (realistic) | 2.5% |

Script:
"The platform costs 2.5% of the annual leakage it is designed to recover. If it recovers even 10% of the leakage, the payback is under 4 months. If it recovers 25%, the payback is under 6 weeks. The question is not whether the price is high. The question is whether the leakage is real."

### Comparison 2: Price vs. Internal Build Cost

| | Buy | Build Internally |
|---|---|---|
| Cost | Rs 3.25 Cr (one-time) | Rs 8-15 Cr (loaded salary over 12-18 months) |
| Time to first analyst review | 30 days | 12-18 months |
| What you get immediately | Working system + deployment + docs + handover | Nothing until build is complete |
| Leakage during build period | Controlled from Day 30 | Uncontrolled for 12-18 months |
| Ongoing engineering overhead | 0.3 FTE after handover | Full team maintenance ongoing |

The internal build math:
- 3 senior ML/backend engineers x Rs 40-60 lakh CTC x 18 months = Rs 5.4-8.1 Cr in salary alone
- 1 senior frontend engineer x Rs 35-50 lakh CTC x 12 months = Rs 1.2-1.7 Cr
- 1 DevOps engineer x Rs 30-40 lakh CTC x 6 months = Rs 0.5-0.7 Cr
- Product management, QA, and documentation overhead: Rs 1-2 Cr
- **Total loaded cost: Rs 8-13 Cr minimum** before the first analyst reviews a case

Script:
"Porter can absolutely build this internally. Shruti's team has the talent. The question is time and opportunity cost. Internal build is Rs 8-15 crore and 12-18 months before the first analyst review. Buying is Rs 3.25 crore and 30 days to shadow mode. During the 12-18 months of internal build, the leakage continues uncontrolled. That uncontrolled leakage costs more than the platform."

### Comparison 3: Price vs. Payback Period

| Scenario | Annual Recovery | Payback Period | Year 1 ROI |
|---|---|---|---|
| Conservative (2% leakage, 40% detection, 30% recovery) | Rs 10.3 Cr | 3.8 months | 217% |
| Realistic (3% leakage, 55% detection, 45% recovery) | Rs 31.9 Cr | 5.9 weeks | 881% |
| Aggressive (4% leakage, 65% detection, 55% recovery) | Rs 61.5 Cr | 2.7 weeks | 1,792% |

Script:
"If the payback path is credible, the price becomes a capital-allocation decision, not a software-procurement objection. Under the conservative scenario — which assumes only 5 cities, 2 analysts, and slow adoption — the payback is still under 4 months. Under the realistic scenario, it is under 6 weeks."

---

## 3. The CFO Memo (Ready To Print Or Read)

> **To: Finance Controller, Porter**
> **Re: Porter Intelligence Platform — Commercial Evaluation**
>
> Porter Intelligence Platform should be evaluated as a leakage-control asset, not a software purchase.
>
> Porter reported Rs 4,306 crore in FY25 revenue with Rs 55 crore net profit — the company's first profitable year. Industry estimates place fraud and operational leakage at 2-4% of transaction volume in intra-city logistics.
>
> The platform costs Rs 3.25 crore (0.075% of annual revenue). It needs to recover Rs 3.25 crore in prevented leakage to break even — a threshold that represents 2.5% of the conservative annual leakage estimate.
>
> The payment structure is milestone-gated: Rs 1 crore on signing, Rs 1 crore on shadow-mode validation success, Rs 1.25 crore on live rollout and handover. Porter pays the full amount only after the platform has proven measurable value on Porter's own data.
>
> The ROI calculator converts buyer assumptions into three scenarios. The conservative case shows Rs 10.3 crore in annual recoverable value with a 3.8-month payback. The realistic case shows Rs 31.9 crore with a 6-week payback.
>
> The commercial question is: does faster control, faster validation, and a lower-risk rollout path justify the upfront price versus waiting 12-18 months for an internal build to converge — during which time the leakage continues uncontrolled?

---

## 4. Price Defense — Script For Each Objection

### "Rs 3.25 crore is too much for software."

Wrong move: immediately offer a discount.
Right move: reframe what they are buying.

"If this were a generic dashboard, Rs 3.25 crore would be unreasonable. I agree.

But this is not a dashboard. This is the system that ingests trip data, scores it for fraud risk in real time, isolates high-risk cases in shadow mode, routes them to an analyst workflow with evidence and audit trails, enables enforcement actions, and comes with deployment, documentation, and a 90-day handover program.

The correct comparison is not software spend. It is: Rs 3.25 crore versus Rs 86-172 crore of annual leakage that currently has no structured intervention system."

Then stop. Let them respond.

### "Can we get it for Rs 2 crore?"

Do not panic. Do not immediately agree. Ask what they want to reduce.

"Rs 2 crore is possible if we reduce scope. Which of these would you want to remove?
- Source code and IP transfer
- 90-day support and handover program
- Full 22-city digital twin
- Enforcement dispatch integration
- Analyst training sessions

If the scope stays the same, the price stays the same. If you want to reduce scope to 5 cities with no enforcement integration and a 30-day support window, I can work with Rs 2 crore."

The goal is to make them feel the value of what they would lose, not to simply concede.

### "Why should we pay Rs 1 crore upfront before seeing real results?"

"Because Rs 1 crore on signing gives you immediate source code access, the deployment package, and the documentation. That alone is worth Rs 1 crore — you could hand it to your engineering team tomorrow and they would have a working system.

The remaining Rs 2.25 crore is milestone-gated. You pay it only after shadow mode validates on your data and live rollout succeeds. The Rs 1 crore upfront is not a bet. It is purchasing a tangible asset package."

### "Our procurement process requires competitive bids."

"I understand. But there is no competing product that combines all of these in a single package: real-time fraud scoring, shadow-mode safety, analyst workflow, schema-mapped ingestion, enforcement dispatch, and handover documentation for intra-city logistics. This is a purpose-built asset for Porter's specific problem.

If procurement requires formal comparison, the relevant comparison is internal build cost (Rs 8-15 crore, 12-18 months) versus this asset (Rs 3.25 crore, 90 days). I can provide that analysis in writing for your procurement file."

### "Can we pay the full amount after shadow mode succeeds?"

"I understand the preference. But zero upfront commitment creates the wrong incentive for both sides: integration gets deprioritized without skin in the game.

The Rs 1 crore on signing is for the tangible asset package you receive immediately — source code, deployment, documentation. The milestone structure already protects you: Rs 2.25 crore is withheld until the platform proves value. That is a stronger protection than a free trial, because both sides are invested in making shadow mode succeed."

---

## 5. Internal Build Rebuttal — Extended Version

This will come from Shruti or Uttam. It is the most important price objection to handle well.

### The Setup

They will say: "We have strong engineers. We can build this ourselves."

### The Wrong Response

- "No you cannot." (Insulting.)
- "But this has AI." (Vague and unpersuasive.)
- "Your engineers would not build it as well." (Antagonistic.)

### The Right Response

"Porter absolutely can build this internally. I have no doubt about Shruti's team. The question is not capability. It is time, cost, and opportunity cost.

Let me break it down honestly:

**What you would need to build:**
- Trip-level fraud scoring with a trained model and feature engineering pipeline
- Two-tier scoring with threshold management
- Ingestion pipeline with schema mapping for your trip events
- Shadow-mode safety layer with isolated case storage
- Analyst workflow: case queue, evidence display, decisions, audit logging
- Enforcement dispatch: webhook integration with your driver management system
- Manager dashboard: KPI surface, city heatmap, case age tracking
- Demand forecasting: per-zone models for surge detection and fleet optimization
- Route efficiency: dead mile analysis, reallocation suggestions
- Security: PII encryption, JWT auth, RBAC, rate limiting
- Documentation: API reference, runbooks, model card, deployment guides
- Testing: unit, integration, API contracts, auth, encryption, shadow mode

**What that costs internally:**
- 3-5 senior engineers for 12-18 months = Rs 8-15 crore loaded cost
- Plus product management, QA, DevOps, and documentation effort
- Plus opportunity cost: those engineers are not working on Porter's core product

**What buying costs:**
- Rs 3.25 crore, milestone-gated
- 90 days to live rollout
- Engineering overhead after handover: 0.3 FTE

**The real question:**
Where should Porter's engineering time go? Building a fraud detection system from scratch, or expanding to 50 cities, improving unit economics, and building the product roadmap that supports the IPO trajectory?

The buy decision is a speed-to-value and engineering-allocation decision. The code quality is comparable to what your team would build. The difference is 90 days versus 18 months."

---

## 6. Fallback Structures

If they resist the primary ask, do not panic. Move through the ladder calmly.

### Fallback 1: Milestone-Gated (Rs 3 Crore)

"If you prefer to de-risk further:
- Rs 1 crore on signing
- Rs 1 crore on shadow-mode validation success (60 days)
- Rs 1 crore on live rollout and handover (90 days)

Same asset, same scope. Slightly lower total, fully milestone-protected."

### Fallback 2: Reduced Scope (Rs 1.75-2 Crore)

"If the full scope exceeds today's decision threshold:
- Non-exclusive license (not exclusive to Porter)
- Limited to 5 cities initially
- 30-day support window instead of 90
- No enforcement dispatch integration (shadow mode only)
- No custom extensions

Rs 1.75 crore. Still includes source code, deployment, documentation, and shadow mode."

### Floor Rule

Do not go below Rs 1.75 crore. Below that, the deal does not justify the support effort and the product is devalued for future conversations. If they push below Rs 1.75 crore, walk away professionally:

"I appreciate the interest, but at that level we would be undervaluing the asset and underinvesting in the support needed to make it succeed. I would rather revisit when the timing and budget align."

---

## 7. Same-Day Ask Ladder (Summary)

| Level | Amount | Structure | When To Use |
|---|---|---|---|
| Primary | Rs 3.25 Cr | Full asset + 90-day rollout + handover | Default ask |
| Fallback 1 | Rs 3.0 Cr | Milestone-gated, same scope | If they want lower total but same scope |
| Fallback 2 | Rs 1.75-2.0 Cr | Reduced scope (5 cities, 30-day support, no enforcement) | If they want a smaller commitment |
| Floor | Rs 1.75 Cr | Minimum viable deal | Only if necessary to keep the conversation alive |
| Walk-away | Below Rs 1.75 Cr | Decline professionally | Preserve deal credibility |

---

## 8. Day 09 Founder Output

By the end of Day 09, you should have:
- three real comparisons (vs. leakage, vs. internal build, vs. payback) with actual numbers
- one CFO memo ready to print or email
- one price defense script for every likely objection
- one internal-build rebuttal that is detailed, honest, and non-antagonistic
- a fallback ladder memorized so you can move through it calmly in the room
- confidence that the price is defensible — not because it is cheap, but because the recovery math supports it
