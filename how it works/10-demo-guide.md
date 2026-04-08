# 10 — Demo Guide

[Index](./README.md) | [Prev: Testing](./09-testing-and-quality.md) | [Next: Troubleshooting](./11-troubleshooting-and-faq.md)

This document explains how to run the demo end-to-end: setup, walkthrough, scenarios, and how to reset.

---

## Quick Start (5 Minutes)

### 1. Start the stack in demo mode

```bash
# In .env, set:
APP_RUNTIME_MODE=demo
ENABLE_SYNTHETIC_FEED=true

# Start:
docker compose up --build -d

# Wait for health:
curl -s http://localhost:8000/health | python3 -m json.tool
```

### 2. Start the frontend

```bash
cd dashboard-ui
npm install
npm run dev
```

### 3. Open the dashboard

- Dashboard: http://localhost:3000
- Analyst workspace: http://localhost:3000/analyst
- API docs: http://localhost:8000/docs

---

## Demo Mode Behaviour

When `APP_RUNTIME_MODE=demo`:

| Feature | Behaviour |
|---|---|
| Digital twin | Active — generates trips across 22 cities |
| Scoring | Active — every generated trip is scored |
| Case creation | Active — flagged trips create cases in analyst queue |
| Enforcement | **Suppressed** — no webhook dispatch |
| Encryption | Relaxed — plaintext fallback allowed |
| Synthetic feed | Configurable via `PORTER_TWIN_*` variables |

---

## Digital Twin Configuration

Control the trip generator with environment variables:

```bash
# Generate 30 trips per minute (default):
PORTER_TWIN_TRIPS_PER_MIN=30

# Scale up to 2x volume:
PORTER_TWIN_SCALE_MULTIPLIER=2.0

# Grow volume by 1% per day:
PORTER_TWIN_DAILY_GROWTH_PCT=1.0

# Only generate for specific cities:
PORTER_TWIN_ACTIVE_CITIES=bangalore,mumbai,delhi

# Adjust base fraud rate:
PORTER_TWIN_BASE_FRAUD_RATE=0.062
```

### Checking simulator status

```bash
curl http://localhost:8000/health | python3 -m json.tool
# Look for: "synthetic_feed": true, "trips_per_min": 30
```

---

## Demo Walkthrough (15 Minutes)

### Minute 0-2: Dashboard Overview

1. Open http://localhost:3000
2. Show the KPI panel: open cases, recoverable value, fraud rate
3. Show the zone heatmap: red zones = high fraud activity
4. Show the runtime mode indicator: "demo" mode confirmed

### Minute 2-4: ROI Calculator

1. Scroll to the ROI calculator
2. Enter Porter's numbers: Rs 4,306 Cr revenue, 270K trips/day, 3% fraud rate
3. Show three scenarios: conservative, realistic, aggressive
4. Highlight: "Even conservative estimates show Rs 10+ Cr annual recovery"

### Minute 4-6: Trip Scoring

1. Open the Trip Scorer component
2. Score a suspicious trip: high fare, cash payment, night time
3. Show the response: fraud probability, tier, top signals
4. Score a clean trip: normal fare, UPI payment, daytime
5. Show the contrast: clean trip scores below threshold

### Minute 6-8: Schema Mapper + Batch Upload

1. Show the schema mapping:
   ```bash
   curl http://localhost:8000/ingest/schema-map/default | python3 -m json.tool
   ```
2. Upload sample records:
   ```bash
   curl -X POST http://localhost:8000/ingest/batch-csv \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@data/samples/porter_sample_10_trips.csv"
   ```
3. Show the ingestion result: rows accepted, queue mode

### Minute 8-10: Analyst Workflow

1. Open http://localhost:3000/analyst
2. Log in as `analyst_1`
3. Show the case queue: sorted by tier (action first), then by age
4. Open an action-tier case
5. Show: trip details, fraud signals, driver snapshot, case age
6. Confirm fraud: add analyst notes
7. Take driver action: suspend driver with reason

### Minute 10-12: Shadow Mode + Audit

1. Show the audit trail:
   ```bash
   curl http://localhost:8000/cases/{case_id}/history \
     -H "Authorization: Bearer $TOKEN"
   ```
2. Show shadow mode status:
   ```bash
   curl http://localhost:8000/shadow/status
   ```
3. Explain: "Shadow mode scores everything but never takes action"

### Minute 12-14: Management View

1. Show the KPI surface: reviewed-case precision, false alarm rate
2. Show the dashboard summary: city breakdown, analyst load, precision trend
3. Show the board pack download:
   ```bash
   curl -o board-pack.pdf http://localhost:8000/reports/board-pack
   ```

### Minute 14-15: Close

1. Summarise: "This is the full operating layer — ingestion, scoring, analyst workflow, enforcement, and management visibility."
2. Point to shadow mode as the safe entry point

---

## Pre-Built Demo Scenarios

The platform includes pre-built scenarios accessible via the API:

```bash
curl http://localhost:8000/demo/scenarios \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Available scenarios

| Scenario | What It Shows |
|---|---|
| Fraud ring | Coordinated fake cancellation ring with 5+ drivers |
| Cash extortion | Driver demanding cash above metered fare |
| GPS spoofing | Fake trip with near-zero distance/time ratio |
| Route deviation | Detour to inflate distance and fare |
| Payout spike | Artificially inflated surge pricing |

Each scenario pre-loads cases into the analyst queue with realistic data.

---

## Resetting Demo State

### Reset cases and data

```bash
curl -X POST http://localhost:8000/demo/reset \
  -H "Authorization: Bearer $TOKEN"
```

This clears all cases and reloads sample data.

### Full environment reset

```bash
# Stop everything and delete volumes:
docker compose down -v

# Restart:
docker compose up --build -d
```

---

## Pre-Demo Checklist

Run these checks before any demo:

```bash
# 1. Health check
curl -s http://localhost:8000/health | python3 -m json.tool

# 2. Shadow mode check
curl -s http://localhost:8000/shadow/status | python3 -m json.tool

# 3. KPI surface
curl -s http://localhost:8000/kpi/live \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 4. Schema map available
curl -s http://localhost:8000/ingest/schema-map/default | python3 -m json.tool

# 5. Demo scenarios loaded
curl -s http://localhost:8000/demo/scenarios \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 6. Board pack downloadable
curl -s -o /tmp/board-pack-test.pdf http://localhost:8000/reports/board-pack
```

All must return 200. If any fail, check the [Troubleshooting guide](./11-troubleshooting-and-faq.md).

---

## Common Demo Questions And Answers

### "Is this real data?"

"This is benchmark data generated at Porter-like scale. The model, the pipeline, and the workflow are real. The shadow-mode validation path replaces benchmark claims with reviewed-case truth on Porter's actual data."

### "What happens if the model is wrong?"

"Two things protect you. First, the two-stage scoring means only trips above 94% probability trigger action — the bar is very high. Second, shadow mode lets you validate on real data before any enforcement action is taken."

### "How long to integrate with our systems?"

"The schema mapper handles field translation — your fields map to our schema. Integration is a 1-week setup task, not a rewrite. Shadow mode runs for 30-60 days after that."

### "What if our fraud patterns are different?"

"That is exactly what shadow mode answers. The model retrains on your data. The 88% precision number is a benchmark — your reviewed-case precision is the real number, measured during shadow validation."

---

## Next

- [Troubleshooting and FAQ](./11-troubleshooting-and-faq.md) — common issues and fixes
