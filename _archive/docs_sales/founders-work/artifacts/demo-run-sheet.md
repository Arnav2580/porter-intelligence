# Demo Run Sheet

Purpose: deterministic live-demo sequence with fallback pivots and exact timing.

---

## Primary Flow (15 Minutes)

| Step | Time | What To Show | What To Say |
|---|---|---|---|
| 1 | 0:00 | Dashboard home, runtime mode indicator | "This is the platform running at Porter-like scale. 22 cities, realistic volumes." |
| 2 | 0:30 | KPI panel: open cases, recoverable value, fraud rate | "These are the operational KPIs. Cases, recovery, fraud rate, model status." |
| 3 | 1:30 | Fraud heatmap: zone-level risk across cities | "This is the city view. Red zones have elevated fraud activity. Your manager checks this every morning." |
| 4 | 3:00 | ROI calculator: realistic scenario with Rs 4,306 Cr revenue | "At Porter's revenue, even conservative estimates show Rs 10+ Cr annual recovery. Realistic: Rs 32 Cr." |
| 5 | 5:00 | `/demo/scenarios`: preset fraud cases (fraud ring, cash extortion, GPS spoofing) | "These are pre-built walkthrough scenarios. Real fraud archetypes your team would encounter." |
| 6 | 6:00 | `/ingest/schema-map/default`: field mapping layer | "This is the integration layer. Your field names map to our schema. No code changes." |
| 7 | 7:00 | Upload 20 masked sample records via batch CSV | "20 masked trip events. Watch them flow through ingestion, scoring, and into the case queue." |
| 8 | 8:00 | Show flagged cases from the upload in analyst queue | "Out of 20, the model flagged 3 action-tier and 5 watchlist. Here they are with evidence." |
| 9 | 9:00 | Open one case: trip detail, signals, driver snapshot | "The analyst sees the evidence, not just the score. They decide, not the model." |
| 10 | 10:00 | Make a decision (confirm fraud), record notes, driver action | "Confirm, dismiss, or escalate. Every decision logged with timestamp and analyst ID." |
| 11 | 11:00 | Show audit trail for the case | "The audit trail means every decision is explainable to management and compliance." |
| 12 | 12:00 | Shadow status: `/shadow/status` and `/health` response | "Shadow mode confirmed. Zero writeback. Zero enforcement webhooks. Completely isolated." |
| 13 | 13:00 | Manager view: case age, city comparison, analyst throughput | "This is leadership visibility. 'Are we in control' in under 5 minutes." |
| 14 | 14:00 | Board pack PDF download | "The board pack travels without me. Architecture, KPIs, ROI, rollout plan." |
| 15 | 15:00 | Transition to commercial ask | "If this were only a model, it would not be buyable. The full operating package is what makes it buyable." |

---

## Backup Flow (If Live Scoring Fails)

If ingestion, scoring, or login fails during the demo:

| Step | What To Do | What To Say |
|---|---|---|
| 1 | Move to board pack PDF | "Let me show you the system summary while we sort this out." |
| 2 | Show schema map endpoint | "This is the integration layer. It works independently of the scoring engine." |
| 3 | Show shadow status | "Shadow mode is confirmed. The safety boundary is active." |
| 4 | Show pre-built scenarios | "These are realistic fraud cases the platform handles. Let me walk you through one." |
| 5 | Open analyst workspace with existing cases | "The workflow is the value. Let me show you how your analyst interacts with a case." |
| 6 | Close on rollout path | "The live hookup is one proof path. The product is the operating system, the workflow, and the deployment package." |

### The Calm Pivot Line

"The live hookup is not the product. The product is the control layer, the workflow, and the rollout path. I can show you that end to end right now."

---

## Five Rehearsal Variants

### Run 1: Clean Path
- Full primary flow, no interruptions
- Practice the silence after the price ask

### Run 2: Shruti Challenges Data Quality Early
- At Step 7, Shruti asks: "This is synthetic data, right?"
- Response: "Correct. The digital twin uses synthetic data to demonstrate the operating model. Shadow mode on your data is the real validation. Let me show you the shadow-mode boundary."
- Skip ahead to Step 12 (shadow mode), then return to analyst workflow

### Run 3: Login Or Page Refresh Issue
- Dashboard takes 10+ seconds to load
- Response: "While that loads, let me show you the board pack." Open the PDF. Walk through Pages 1 and 5. Return to dashboard when ready.

### Run 4: Live Scoring Produces No Flags
- All 20 uploaded records score below threshold
- Response: "The model did not flag any of these 20 trips, which means they did not match the fraud patterns in the training data. Let me show you the preset scenarios that demonstrate what flagged cases look like." Move to `/demo/scenarios`.

### Run 5: Buyer Asks For Shadow Mode Only
- They are not interested in the full demo
- Response: "Absolutely. Let me show you exactly three things: the shadow-mode safety boundary, the analyst workflow, and the ingestion path. That is the pilot scope."
- Show Steps 6, 9-11, 12 only.

---

## Demo Reset

If you need to restart the demo environment:

- Endpoint: `POST /demo/reset`
- Requires: `admin` or `ops_manager` role
- What it does: clears demo-generated cases, resets the queue, re-seeds scenarios
- When to use: between rehearsal runs, or if the demo state gets confused

Say if asked: "Demo reset exists because a serious buyer demo should be restartable and deterministic."

---

## Pre-Demo Technical Checks

Run these before leaving for the meeting:

```
# Health check
curl http://localhost:8000/health

# Shadow mode confirmation
curl http://localhost:8000/shadow/status

# KPI surface
curl http://localhost:8000/kpi/live

# Schema map
curl http://localhost:8000/ingest/schema-map/default

# Demo scenarios
curl http://localhost:8000/demo/scenarios

# Board pack PDF
curl -o board-pack.pdf http://localhost:8000/reports/board-pack
```

All should return 200. If any fail, debug before leaving.
