# Day 11 - Fail-Safe Demo Script

[Index](./README.md) | [Prev](./day-10-board-pack.md) | [Next](./day-12-close-packet.md)

Objective:
- make the demo survivable even if something breaks
- ensure every failure mode has a pre-planned pivot that maintains momentum and credibility

---

## 1. Primary Demo Path — Timed

Total time: 15 minutes. Every minute is allocated. Do not improvise the order.

| Minute | Screen | What To Show | What To Say |
|---|---|---|---|
| 0:00-0:30 | Dashboard home | Runtime mode, 22-city overview | "This is the platform running at Porter-like scale." |
| 0:30-1:30 | KPI panel | Open cases, recoverable value, fraud rate, model status | "These are the operational KPIs your leadership sees every morning." |
| 1:30-3:00 | Fraud heatmap | Zone-level risk across cities, color-coded | "Red zones have elevated fraud activity. This is the city control view." |
| 3:00-5:00 | ROI calculator | Realistic scenario with Rs 4,306 Cr revenue | "At Porter's scale, even conservative estimates show Rs 10+ Cr annual recovery." |
| 5:00-6:00 | Demo scenarios | Fraud ring, cash extortion, GPS spoofing presets | "These are pre-built walkthrough scenarios based on real fraud archetypes." |
| 6:00-7:00 | Schema mapper | `/ingest/schema-map/default` endpoint | "This is the integration layer. Your field names map to our schema." |
| 7:00-8:00 | Batch upload | Upload 20 masked sample records | "20 masked trip events flowing through ingestion, scoring, and into the queue." |
| 8:00-9:00 | Flagged cases | Show results in analyst queue | "3 action-tier, 5 watchlist. Here they are with evidence and signals." |
| 9:00-10:00 | Case detail | Open one case: trip info, signals, driver snapshot | "The analyst sees the evidence, not just the score." |
| 10:00-11:00 | Decision flow | Confirm fraud, add notes, take driver action | "Confirm, dismiss, or escalate. Every decision logged and auditable." |
| 11:00-11:30 | Audit trail | Show the logged action with timestamp and analyst | "The audit trail means every decision is explainable." |
| 11:30-12:00 | Shadow status | `/shadow/status` and `/health` | "Shadow mode confirmed. Zero writeback. Completely isolated." |
| 12:00-13:00 | Manager view | KPI dashboard, city comparison, case age | "This is leadership visibility: 'are we in control' in under 5 minutes." |
| 13:00-14:00 | Board pack | PDF download from `/reports/board-pack` | "The board pack travels without me. Architecture, KPIs, ROI, rollout plan." |
| 14:00-15:00 | Transition | Step back from demo | "The full operating package is what makes this buyable." |

### Exact Endpoint Route Order

```
1. /                           (dashboard home)
2. /kpi/live                   (KPI surface)
3. /fraud/heatmap              (zone-level fraud map)
4. /roi/calculate              (ROI planner)
5. /demo/scenarios             (preset walkthrough cases)
6. /ingest/schema-map/default  (field mapping)
7. POST /ingest/batch-csv      (sample upload)
8. /ingest/queue-status        (ingestion confirmation)
9. /cases/                     (analyst queue)
10. /cases/{case_id}           (case detail)
11. PATCH /cases/{case_id}     (decision)
12. /shadow/status             (shadow confirmation)
13. /kpi/live                  (manager view)
14. /reports/board-pack        (PDF download)
```

---

## 2. Failure Mode Playbook

Every failure has a pre-planned pivot. The rule: acknowledge the failure briefly, pivot calmly, and continue without losing the commercial narrative.

### Failure 1: Login Does Not Work

**What happens:** The login page hangs, returns an error, or the JWT token fails.

**What to say:**
"Let me sort this out — in the meantime, let me show you the board pack while the system reconnects."

**What to do:**
1. Open the board pack PDF (have it pre-downloaded on desktop)
2. Walk through Pages 1 and 5 (pain + ROI)
3. Try login again after 2 minutes
4. If still broken: continue the entire demo from the board pack and schema mapper endpoint (API-level demo via curl or Postman, pre-prepared)

**Why this works:** The board pack contains all the information. The login failure does not invalidate the product.

### Failure 2: Dashboard Loads Slowly Or Partially

**What happens:** The dashboard takes 10+ seconds to render, or some components (heatmap, KPI panel) do not load.

**What to say:**
"The dashboard is loading — while it renders, let me explain what you will see."

**What to do:**
1. Narrate the dashboard while it loads: "The KPI panel shows open cases, recoverable value, and fraud rate. The heatmap shows zone-level risk."
2. If it loads partially, use whatever is visible
3. If it does not load after 30 seconds, pivot to the analyst workspace (which is a simpler page and more likely to load)

**Why this works:** Narrating while waiting shows confidence. The analyst workspace is the most important screen anyway.

### Failure 3: Batch Upload Fails

**What happens:** The `POST /ingest/batch-csv` endpoint returns an error, or zero records are accepted.

**What to say:**
"The batch upload hit an issue — let me show you the ingestion path through the pre-loaded scenarios instead."

**What to do:**
1. Switch to `/demo/scenarios`
2. Show the pre-loaded fraud ring, cash extortion, and GPS spoofing cases
3. Open one of these cases in the analyst queue
4. Continue the analyst workflow demo from these pre-loaded cases

**Why this works:** The pre-loaded scenarios demonstrate the same pipeline. The batch upload failure is an environment issue, not a product issue.

### Failure 4: Scoring Returns No Flagged Cases

**What happens:** All 20 uploaded records score below threshold. The queue shows zero new cases.

**What to say:**
"The model did not flag any of these 20 trips, which means they did not match the fraud patterns in the training data. Let me show you what flagged cases look like using the preset scenarios."

**What to do:**
1. Switch to `/demo/scenarios`
2. Show the pre-loaded cases with high fraud probability
3. Explain: "In production, your trip volume generates thousands of scoreable events per hour. The detection rate depends on actual fraud prevalence. These presets show what the output looks like when fraud is present."

**Why this works:** Honesty about why it happened maintains credibility. The presets prove the workflow.

### Failure 5: An API Endpoint Returns 500

**What happens:** Any endpoint returns an internal server error.

**What to say:**
"That endpoint hit an error — let me move to the next screen and we can come back to it."

**What to do:**
1. Skip the failed endpoint
2. Move to the next item in the demo sequence
3. If the error persists across multiple endpoints, pivot to the board pack and offer to re-run the demo on a stable environment later

**Never say:** "This never happens" (it clearly just did) or "Let me debug this" (do not debug in the room).

### Failure 6: The Entire Environment Is Down

**What happens:** Nothing loads. The server is unreachable.

**What to say:**
"The demo environment is not responding. I came prepared for this. Let me walk you through the product using the board pack, the finance memo, and the schema mapper documentation. I can run a live demo for your team on a stable environment within 24 hours."

**What to do:**
1. Open the board pack PDF (pre-downloaded)
2. Walk through all 6 pages (15 minutes)
3. Show the schema mapper configuration file on your laptop
4. Show the test suite output (pre-captured screenshot or terminal output)
5. Close on the commercial ask

**Why this works:** Preparation is credibility. Having the fallback materials ready shows professionalism. The product is real even if the environment is temporarily down.

### Failure 7: Someone Asks A Question You Cannot Answer

**What to say:**
"That is a good question and I want to give you an accurate answer rather than guess. Let me note it down and get back to you within 24 hours."

**What to do:**
1. Write the question down visibly (on paper, in front of them)
2. Do not make up an answer
3. Continue the demo
4. Send the answer by email the same day

**Why this works:** Honesty builds trust. Making up an answer destroys it.

---

## 3. The Calm Pivot Line (Memorize This)

For any unexpected failure, use one of these:

- "The live hookup is not the product. The product is the control layer, the workflow, and the rollout path. I can show that end to end right now."

- "We can keep going without losing the commercial proof. The product value does not depend on this one screen working perfectly right now."

- "Let me show you a different angle on the same system."

The tone is calm, not apologetic. Do not over-explain the failure. Acknowledge, pivot, continue.

---

## 4. Final Two-Minute Opening (Exact Words)

Use this to open the demo. It frames everything that follows and sets up the fallback gracefully.

"What I want to show you today is not a dashboard. It is a leakage-control operating layer that sits on top of your existing systems.

I will show you five things: the benchmark evidence, the ingestion path, the shadow-mode safety boundary, the analyst workflow, and the rollout path.

If at any point you want to switch from the live path to the controlled path, or if you want to dig deeper into a specific area, we can do that without losing the substance of the evaluation. The product should stand up to scrutiny, not just to a smooth presentation."

### Why This Opening Is Fail-Safe

The phrase "switch from the live path to the controlled path" sets up the pivot. If something breaks mid-demo, you are not scrambling — you are doing what you said you might do at the beginning. The audience already has permission for a non-linear path.

---

## 5. Five Rehearsal Runs

### Run 1: Clean Path
- Full primary flow, no interruptions
- Time yourself: you must finish in 15 minutes
- Practice the transition to commercial ask and silence after price

### Run 2: Data Mapping Questioned Early (Shruti Scenario)
- At minute 6, Shruti says: "Wait — your field names do not match ours."
- Response: "That is exactly what the schema mapper handles. Let me show you the mapping config."
- Show the mapping JSON, explain how to change field names
- Return to the upload step

### Run 3: Login Slow (Board Pack First)
- Login takes 30+ seconds
- Open the board pack PDF immediately
- Walk through Pages 1 and 5 while login resolves
- Return to the dashboard when ready

### Run 4: Live Scoring Skipped (Preset Scenarios)
- Upload fails or returns no flags
- Move directly to `/demo/scenarios`
- Open the fraud ring walkthrough
- Continue analyst workflow from presets

### Run 5: Buyer Wants Shadow Mode Only
- At minute 3, someone says: "We are only interested in the shadow-mode validation path."
- Response: "Absolutely. Let me focus on three things: the ingestion path, the shadow-mode safety boundary, and the analyst workflow."
- Show minutes 6-7 (schema mapper), 11:30-12:00 (shadow status), 9:00-11:00 (analyst workflow)
- Skip heatmap, ROI calculator, and manager view
- Close on shadow-mode-specific commercial ask

### Minimum Success Condition For Every Run

No matter what breaks, every run must include:
1. A clear opening (2-minute version above)
2. One honest provenance statement ("benchmark data, not live proof")
3. One proof of the integration path (schema mapper or sample upload)
4. One proof of the analyst workflow (case review and decision)
5. A clean close ask (price, structure, milestones)

If you achieve all five, the demo was successful regardless of what else happened.

---

## 6. Pre-Demo Checklist (Day Of)

Run these checks 1 hour before leaving for the meeting:

```bash
# Health check
curl -s http://localhost:8000/health | python3 -m json.tool

# Shadow mode confirmation
curl -s http://localhost:8000/shadow/status | python3 -m json.tool

# KPI surface
curl -s http://localhost:8000/kpi/live | python3 -m json.tool

# Schema map
curl -s http://localhost:8000/ingest/schema-map/default | python3 -m json.tool

# Demo scenarios
curl -s http://localhost:8000/demo/scenarios | python3 -m json.tool

# Board pack PDF (download and verify it opens)
curl -s -o /tmp/board-pack-test.pdf http://localhost:8000/reports/board-pack
open /tmp/board-pack-test.pdf
```

All must return 200. If any fail, debug and fix before leaving.

### Fallback Materials To Have On Laptop (Pre-Downloaded)

- [ ] Board pack PDF (saved to desktop)
- [ ] Finance memo PDF (saved to desktop)
- [ ] Sample CSV file (20 masked records, saved to desktop)
- [ ] Schema mapping JSON (saved to desktop)
- [ ] Test suite output (screenshot of `pytest` passing, saved to desktop)
- [ ] Architecture diagram (saved to desktop)

---

## 7. Day 11 Founder Output

By the end of Day 11, you should have:
- a timed 15-minute primary demo script (every minute accounted for)
- a pre-planned pivot for 7 specific failure modes
- one calm pivot line memorized that works for any failure
- a 2-minute opening that frames the fallback as intentional
- 5 rehearsal runs completed (timed, out loud, including at least one failure simulation)
- all fallback materials pre-downloaded to your laptop
- confidence that nothing that can go wrong in the demo can kill the deal
