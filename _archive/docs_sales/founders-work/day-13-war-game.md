# Day 13 - War Game Script

[Index](./README.md) | [Prev](./day-12-close-packet.md) | [Next](./day-14-meeting-day.md)

Objective:
- rehearse the meeting until the founder sounds calm, clear, and non-defensive
- prepare for every hard question Porter can throw at you
- practice silence after the ask

---

## 1. Full Run Of Show

| Phase | Duration | What Happens |
|---|---|---|
| Opening | 2 minutes | State pain, product category, what you will show |
| Demo - Digital Twin | 3 minutes | Show 22-city simulation, heatmap, KPI surface |
| Demo - Ingestion | 2 minutes | Show schema mapping and 20-record ingestion proof |
| Demo - Shadow Mode | 2 minutes | Show shadow status, explain no-writeback guarantee |
| Demo - Analyst Workflow | 4 minutes | Show queue, case detail, decision, audit trail |
| Demo - Manager View | 2 minutes | Show KPI dashboard, city comparison, case age |
| Demo - ROI Calculator | 2 minutes | Walk through realistic scenario with Porter's numbers |
| Transition to Commercial | 1 minute | "Here is what makes this buyable" |
| Commercial Ask | 2 minutes | State the price, the structure, the milestones |
| Silence | 30-60 seconds | Say nothing. Wait for their response. |
| Objection Handling | 10 minutes | Address whatever comes up |
| Close | 2 minutes | Ask for commitment, get next step nailed |
| **Total** | **~30 minutes** | |

---

## 2. Hard Objections — The Complete Set

These are ranked from most likely to least likely. For each one, there is a wrong response (defensive) and a right response (confident, honest, forward-moving).

### Objection 1: "We can build this internally."

**Probability: Very High (90%)**

Shruti or Uttam will say this. It is the default response of any technical organization being asked to buy instead of build.

Wrong response:
- "No you cannot" (insulting)
- "But AI built this so it was fast" (undermines credibility)
- "Your team would struggle with this" (antagonistic)

Right response:
"You absolutely can. Porter has strong engineering talent. The question is not capability. It is time and opportunity cost.

An internal build requires allocating 3-5 senior engineers, building detection, workflow, ingestion, shadow safety, documentation, and handover from scratch. That is 12-18 months before your first analyst review and Rs 8-15 crore in loaded cost.

This platform compresses that to 90 days at Rs 3.25 crore. In a year where you are scaling from 35 to 50 cities and protecting a Rs 55 crore profit, the question is: where do you want your engineering time spent?"

Then stop talking. Let them process.

### Objection 2: "How do we know it works on our data?"

**Probability: Very High (85%)**

This is the fairest objection in the room. It comes from anyone technical.

Wrong response:
- "The benchmark shows 88.3% precision" (synthetic proof is not real proof)
- "Trust me, it will work" (no one trusts this)

Right response:
"You do not know yet, and I would not ask you to take my word for it. That is exactly what shadow mode is for.

The model is currently trained on synthetic data. I am being direct about that. The validation path is: connect a feed from your trip pipeline, run shadow mode for 30-60 days, and measure reviewed-case precision against your analysts' judgment. Your team decides whether the signals are real.

If shadow mode validates, you pay the second tranche. If it does not, we retune before anything operational changes. The structure protects you."

### Objection 3: "What happens after you leave?"

**Probability: High (75%)**

This is the key-person risk objection. It comes from Pranav (board governance lens) or Shruti (operational continuity lens).

Wrong response:
- "I will always be available" (unrealistic, increases dependency)
- "The code is self-documenting" (no code is)

Right response:
"The product is packaged for handover, not for founder dependence.

You receive: full source code, architecture documentation, API reference, operator runbooks, deployment guides, model card, and a 90-day support and knowledge transfer window. The runbooks cover: adding a city, retraining the model, rotating secrets, restoring from backup, and troubleshooting common failures.

After Day 90, your team owns and operates this independently. If I disappear, you should still be able to start, configure, deploy, retrain, and recover the system. That is the design standard."

### Objection 4: "Rs 3.25 crore is too high."

**Probability: High (70%)**

This comes from the CFO or from anyone who has not yet connected the price to the recovery value.

Wrong response:
- Immediately offer a discount (signals desperation)
- Apologize for the price (signals lack of confidence)
- Justify the price by listing engineering hours (wrong frame)

Right response:
"If this were a dashboard, Rs 3.25 crore would be unreasonable. But this is a leakage-control operating system.

Porter's annual revenue is Rs 4,306 crore. Industry estimates put fraud and operational leakage at 2-4% of transaction volume. Even at 2%, that is Rs 86 crore of annual leakage. The platform costs less than 4% of the conservative annual leakage estimate.

The relevant comparison is not software spend. It is: Rs 3.25 crore versus uncontrolled leakage that currently has no structured intervention system. If the platform captures even 5% of that leakage, it pays for itself in the first quarter."

Then stop. Do not add more. Do not discount. Wait.

If they push further:
"If you want to reduce upfront risk, the milestone-gated structure lets you pay Rs 1 crore on signing and the rest only after shadow-mode validation proves value on your data."

### Objection 5: "We need InfoSec review."

**Probability: High (70%)**

This is reasonable and expected. It comes from Shruti or a security team member.

Wrong response:
- "It is secure, trust me" (dismissive)
- "We can skip that for now" (alarming)

Right response:
"That is expected and welcome. A security review is part of responsible procurement.

The security posture includes: AES-256-GCM encryption for PII at rest, JWT authentication with role-based access control, bcrypt password hashing, rate limiting on all public endpoints, audit logging for all privileged actions, scoped CORS, and security headers.

I can provide the security summary document and walk your InfoSec team through the architecture. The product is designed to be reviewable, not to avoid scrutiny."

If they want to delay the deal for review:
"If the InfoSec review is the only remaining gate, can we sign the NDA and commercial schedule today with the condition that the InfoSec review is completed within 14 days before Tranche 1 payment is released? That keeps momentum without bypassing your process."

### Objection 6: "What if the model is wrong?"

**Probability: Medium (50%)**

This comes from the fraud operations head or anyone who has been burned by ML products before.

Right response:
"The model will be wrong sometimes. No fraud detection system is perfect.

The benchmark false-positive rate is 0.53%. But that is on synthetic data. The real rate on your data is what shadow mode measures. If the model is wrong too often, your analysts will see it immediately because they are reviewing every action-tier case.

The two-tier design helps: action-tier cases (above 0.94 probability) are high-confidence flags for immediate review. Watchlist cases (0.45 to 0.94) are monitoring flags that only escalate if a pattern emerges. This prevents alert fatigue while still catching coordinated fraud.

If the model is consistently wrong in a specific pattern, we retune thresholds during the shadow period. The model is not sacred. The workflow is."

### Objection 7: "We are not ready for this right now."

**Probability: Medium (40%)**

This is the stall objection. It means the room is not convinced enough to act.

Right response:
"I understand. But consider what 'not now' costs.

If leakage is 2-3% of revenue, every month of delay is Rs 7-11 crore in uncontrolled loss. Shadow mode can start within a week of signing with zero operational risk. The platform does not force a big-bang deployment.

The real question is not whether you are ready for live enforcement. The question is whether you are ready to start measuring leakage. Shadow mode gives you that measurement with no operational change."

### Objection 8: "Can we do a free trial first?"

**Probability: Medium (35%)**

Wrong response:
- "Sure" (devalues the product)
- "No, take it or leave it" (kills the deal)

Right response:
"I understand the instinct, but a free trial creates the wrong incentive for both sides. Without commercial commitment, the integration effort is deprioritized on your side and under-supported on ours.

The milestone-gated structure is better than a free trial because it creates accountability: you pay Rs 1 crore for source access and deployment. We deploy shadow mode within 30 days. If it does not validate, you have a working system with source code and documentation for Rs 1 crore — far less than the cost of building from scratch. If it does validate, you pay the remaining tranches. That is a better structure than 'free trial that no one has time to run properly.'"

---

## 3. Silence After Price — The Discipline

### The Rule

When you say the price:
1. State the number: "Rs 3.25 crore."
2. State what it includes: "Source access, deployment, shadow-mode integration, 90-day support, and full handover."
3. State the milestone structure: "Rs 1 crore on signing, Rs 1 crore on shadow validation, Rs 1.25 crore on rollout."
4. Stop talking.

### What Will Happen

The room will be silent. This is uncomfortable. Your instinct will be to fill the silence with:
- additional justification
- a preemptive discount
- nervous explanation
- "Does that sound reasonable?"

Do none of these. Silence after the price is the most powerful negotiation tool you have. The first person to speak after a price is stated sets the direction of the negotiation.

### Practice This

Literally say out loud:
"The total is Rs 3.25 crore, structured as Rs 1 crore on signing, Rs 1 crore on shadow validation success, and Rs 1.25 crore on live rollout and handover."

Then count to 10 in your head. Say nothing.

Practice this 5 times until the silence feels natural.

---

## 4. Emotional Preparation

### What You Will Feel In The Room

- Imposter syndrome: "Am I really worth Rs 3.25 crore?"
- Defensive instinct: "I need to explain why this is not overpriced."
- People-pleasing: "I should give them a discount so they like me."

### What To Remember

- You are not selling yourself. You are selling a system that recovers multiples of its cost.
- The price is anchored to recovered value, not to your personal effort.
- Porter's FY25 revenue is Rs 4,306 crore. Your ask is 0.075% of that.
- Uttam and Pranav became billionaires by making good capital allocation decisions. Let them make this one.
- If the product is as good as the demo shows, the price is low. If it is not, shadow mode will reveal that before full payment.

---

## 5. Full Rehearsal Checklist

Run through the entire meeting script 3 times minimum:

**Run 1: Clean path**
- Opening to close with no interruptions
- Practice the silence after the price

**Run 2: Hostile CPTO**
- Shruti asks about every technical limitation
- Practice staying honest and calm: "That is a fair point. Here is how we address it."

**Run 3: Price negotiation**
- CFO pushes back on Rs 3.25 crore
- Practice holding the number, then moving to milestone structure if needed
- Practice saying: "If the payback path is credible, the price becomes a capital-allocation decision, not a procurement objection."

---

## 6. Day 13 Founder Output

By the end of Day 13, you should have:
- a full 30-minute meeting script rehearsed at least 3 times
- a calm, non-defensive answer to every objection in this document
- practiced silence after stating the price (minimum 5 repetitions)
- emotional readiness to ask for Rs 3.25 crore without flinching
- a fallback plan if they want to negotiate (milestone structure, not panic discount)
