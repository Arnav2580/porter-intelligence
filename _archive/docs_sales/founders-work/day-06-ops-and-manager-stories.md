# Day 06 - Analyst And Manager Stories

[Index](./README.md) | [Prev](./day-05-shadow-mode-story.md) | [Next](./day-07-cxo-talk-tracks.md)

Objective:
- make the workflow feel operational and human, not technical and abstract
- answer the question "who uses this every day and what does their morning look like"

---

## 1. The Analyst Story — First 30 Minutes At Porter

### Context

Porter's fraud and operations team likely handles complaints, disputes, and driver issues today through manual processes: spreadsheets, internal tools, ad-hoc queries, and escalation chains. The platform replaces the "how do we find fraud" step with a structured detection-to-action pipeline.

### Minute-By-Minute Walkthrough

**Minute 0-2: Login and Queue Overview**

The analyst opens the platform and sees the case queue. The queue shows:
- action-tier cases (fraud probability above 0.94): these are high-confidence cases that demand immediate review
- watchlist cases (probability 0.45 to 0.94): these are monitoring cases that may escalate
- case counts by city, by age, and by tier

The analyst filters by their assigned city (e.g., Bangalore) and sorts by oldest action-tier cases first. No action-tier case should sit unreviewed for more than 4 hours.

One-line explanation: "The queue tells you what to work on, in what order, and how urgent it is."

**Minute 2-8: Opening The First Case**

The analyst opens a case. The case detail view shows:
- trip details: route, fare, distance, duration, payment mode, vehicle category
- fraud signals: the top 5 risk factors that contributed to the score (e.g., fare_to_expected_ratio: 2.3x, cash_trip_ratio: 92%, same_zone_repeat: 7 trips in 4 hours)
- driver snapshot: account age, lifetime trips, rating, cancellation velocity, dispute history
- related cases: other cases involving the same driver in the last 30 days
- zone context: zone fraud rate (rolling 7-day), zone demand level

The analyst is not looking at a black-box score. They are looking at the evidence the model used to flag this trip, presented in human-readable format.

One-line explanation: "Every case shows you the evidence, not just the score. The analyst decides, not the model."

**Minute 8-12: Making A Decision**

The analyst evaluates the evidence and chooses one of:

1. **Confirm fraud**: the evidence supports the flag. This triggers the case status change and makes the case eligible for enforcement action.
2. **False alarm**: the evidence does not support the flag. The analyst marks it as false alarm and can optionally add a reason. This feeds back into reviewed-case precision tracking.
3. **Escalate**: the case is complex or involves a pattern (e.g., a potential fraud ring). The analyst escalates to a senior reviewer or manager.

If dismissing an action-tier case as false alarm, the analyst is required to provide an override reason. This prevents lazy dismissals and creates accountability.

One-line explanation: "Confirm, dismiss, or escalate. Every decision is recorded and auditable."

**Minute 12-18: Recording Notes And Driver Actions**

If the analyst confirmed fraud, they can now take a driver action:
- **Suspend**: immediately flag the driver for suspension (in live mode, this dispatches to Porter's systems)
- **Flag for monitoring**: keep the driver active but increase scrutiny on future trips
- **Clear**: remove a previous flag if the pattern has resolved

The analyst adds case notes explaining their reasoning. Every action, note, and status change is written to the audit log with timestamp, analyst ID, and IP address.

One-line explanation: "The audit trail means every decision can be explained to management, compliance, or the driver."

**Minute 18-30: Working Through The Queue**

The analyst continues through the queue. With evidence pre-assembled and signals pre-ranked, the average case review time drops from 45+ minutes (manual investigation) to 10-15 minutes (structured review).

In 30 minutes, a trained analyst can review 2-3 action-tier cases or 4-6 watchlist cases.

By the end of the first 30 minutes, the analyst has:
- reviewed the highest-priority cases for their city
- confirmed or dismissed each with evidence-based reasoning
- taken driver actions where warranted
- contributed to the reviewed-case precision metric that validates model quality

---

## 2. The Manager Story — City Operations Leadership

### What A Manager Sees

A manager is not reviewing individual cases. A manager is answering five questions:

1. **Are we overwhelmed?** Queue depth by city and tier. If action-tier cases are piling up, the team is understaffed or undertrained.

2. **Are action-tier cases being resolved fast enough?** Case age distribution. If average case age exceeds 8 hours, intervention speed is degrading.

3. **Are false alarms rising?** Reviewed-case false-alarm rate by week. If it is climbing, the model may need threshold adjustment or the scoring is degrading.

4. **Which cities are heating up?** Zone-level fraud rate heatmap. If Bangalore is suddenly 3x the normal rate, something is happening — a new fraud pattern, a seasonal surge, or a driver cohort issue.

5. **How is the team performing?** Analyst throughput: cases reviewed per analyst per day. Confirmation rate vs false-alarm rate per analyst. This is how you identify which analysts need training and which are carrying the team.

### Manager Dashboard Walkthrough

The manager opens the dashboard and sees:

- **KPI panel**: total open cases, recoverable value estimate, fraud rate (rolling 7-day), model status
- **City heatmap**: zone-level risk classification across all operational cities
- **Tier summary**: action-tier count, watchlist count, cleared count
- **Case age indicators**: percentage of action-tier cases older than 4 hours, 8 hours, 24 hours
- **Analyst activity**: cases reviewed today, confirmation rate, average review time

### The Manager Morning Routine (5 Minutes)

1. Check the KPI panel: is anything materially different from yesterday?
2. Scan the heatmap: are any cities unusually hot?
3. Check case age: are action-tier cases being resolved within the 4-hour target?
4. If something is off, drill into the specific city or analyst

One-line explanation: "The manager dashboard answers 'are we in control' in under 5 minutes."

### The Manager Weekly Review (15 Minutes)

1. Reviewed-case precision trend: is the model getting better or worse?
2. Recovery value trend: is the recoverable value growing, stable, or declining?
3. Analyst throughput: is the team keeping up with case volume?
4. City comparison: which cities have the highest fraud rates and which have the best recovery rates?
5. Escalation patterns: what kinds of cases are being escalated and why?

---

## 3. The Story For The Room

### When Someone Asks "Who Uses This Every Day?"

"Two groups. First, your fraud and operations analysts. They open the queue each morning, review flagged cases with pre-assembled evidence, and make confirm-or-dismiss decisions in 10-15 minutes per case. Every decision is auditable.

Second, your city operations managers. They use the dashboard to track queue pressure, case age, false-alarm trends, and city-level fraud patterns. They answer 'are we in control' in under 5 minutes every morning."

### When Someone Asks "How Is This Different From What We Do Now?"

"Today, your team discovers fraud reactively — through driver complaints, customer disputes, or financial reconciliation. That means the damage is already done by the time anyone investigates.

This platform inverts that. It scores every trip in real time and routes high-risk patterns to your team proactively. The analyst is reviewing a case within hours of the trip, not days or weeks. The difference is the gap between detection and action."

### When Someone Asks "What If Our Team Does Not Adopt It?"

"Shadow mode is the adoption on-ramp. Your team trials the workflow for 30-60 days before any operational coupling. If the workflow is too complex, too noisy, or does not fit their process, that shows up in shadow mode before it becomes a production problem.

The workflow is also deliberately simple: open case, read evidence, decide, record, move on. It is not a new system your team needs to learn for months. It is a queue with evidence and action buttons."

---

## 4. Demo Sequence For Ops Story

Show these in this order during the demo:

1. **Queue view**: show the case list with tier indicators, city filters, and age sorting
2. **Case detail**: open one case, show the trip evidence, fraud signals, and driver snapshot
3. **Decision flow**: make a decision (confirm fraud), show the status change
4. **Driver action**: show the suspend/flag/clear action flow
5. **Audit trail**: show that the decision is logged with timestamp, analyst, and reason
6. **Manager view**: switch to the dashboard, show the KPI panel and heatmap
7. **Case age**: show that the case just resolved is no longer in the queue and the case age metric improved

Total demo time for ops story: 4-6 minutes.

---

## 5. Day 06 Founder Output

By the end of Day 06, you should have:
- one detailed analyst narrative (minute-by-minute, not abstract)
- one detailed manager narrative (what they check and how often)
- one answer to "who uses this every day" that is specific and credible
- one answer to "how is this different from what we do now" that names the exact gap
- confidence that the ops story makes the platform feel like a daily tool, not a report
