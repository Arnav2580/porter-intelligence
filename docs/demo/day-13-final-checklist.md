# Day 13 — Final Demo Checklist

Pre-meeting validation checklist. Run top to bottom before every rehearsal and before the real meeting.

---

## 1. System Readiness

### Backend

| Check | Command | Expected |
|---|---|---|
| Tests pass | `pytest tests/ -v` | 63/63 PASSED |
| API starts | `uvicorn api.main:app --port 8000` | No import errors |
| Health check | `GET /health` | `status: ok`, `model_loaded: true` |
| Model loaded | `/health` response | `model_loaded: true` |
| Redis connected | `/health` response | `redis: ok` |
| DB connected | `/health` response | `database: ok` |
| Shadow mode OFF | `/health` response | `shadow_mode: false` |

### Frontend

| Check | Command | Expected |
|---|---|---|
| Build clean | `cd dashboard-ui && npm run build` | 0 errors, 0 warnings |
| Dev server starts | `npm run dev` | Vite on port 5173 |
| Dashboard loads | Browser → localhost:5173 | No console errors |
| MODEL READY badge | Dashboard header | Green dot, "MODEL READY" |

---

## 2. Demo Flow — Step by Step

### Phase 1: Digital Twin (3 minutes)

1. Open Dashboard → `localhost:5173`
2. Confirm "DEMO MODE" or "PRODUCTION MODE" badge in header
3. Point to live fraud feed (right column) — trips scoring in real time
4. Point to zone heatmap (far right column) — Bangalore zones lighting up
5. Say: "This is the digital twin — 22 cities, 5 fraud archetypes, scoring every trip as it completes."

**What to show:** Live feed scrolling with ACTION (red) and WATCHLIST (amber) trips. Zone map with fraud density heat.

**What to say:** "We ran this across 100,000 trips. 88.3% of what we flagged as action-tier was confirmed fraud. 0.53% false positive rate."

### Phase 2: Ingestion (2 minutes)

1. Navigate to `localhost:8000/docs` in a second tab
2. Show `POST /ingest/trip-completed` — paste a sample trip payload
3. Show `GET /ingest/status` — queue depth, messages processed
4. Say: "Your trip pipeline sends a webhook here. The schema mapper normalises your field names to ours. No changes to your dispatch system required."

**Sample fraud payload for live ingest demo:**
```json
{
  "trip_id": "LIVE_DEMO_001",
  "driver_id": "DRV_DEMO_001",
  "fare_inr": 1200,
  "declared_distance_km": 8.0,
  "declared_duration_min": 4.0,
  "pickup_lat": 12.9352,
  "pickup_lon": 77.6245,
  "dropoff_lat": 12.9698,
  "dropoff_lon": 77.7500,
  "pickup_zone_id": "blr_koramangala",
  "dropoff_zone_id": "blr_whitefield",
  "payment_mode": "cash",
  "vehicle_type": "two_wheeler",
  "surge_multiplier": 1.8,
  "is_night": true,
  "hour_of_day": 22,
  "day_of_week": 4,
  "is_peak_hour": false,
  "zone_demand_at_time": 2.1,
  "status": "completed",
  "requested_at": "2026-04-17T22:00:00",
  "customer_complaint_flag": false
}
```

### Phase 3: Shadow Mode (2 minutes)

1. Show `GET /shadow/status` response: `shadow_mode: false`
2. Show `POST /shadow/activate` — toggle it on, show `live_write_suppressed: true`
3. Say: "Shadow mode means the platform is fully running — scoring, casing, intelligence — but the enforcement webhook doesn't fire. Your analysts can review what we would have done, against what you did. No operational risk."
4. Toggle back off: `POST /shadow/deactivate`

### Phase 4: Analyst Workflow (4 minutes)

1. Navigate to `localhost:5173/analyst` (or `/login` first)
2. Show the case queue — pending cases by tier (ACTION in red, WATCHLIST in amber)
3. Click one ACTION-tier case — show trip details, fraud probability, top signals
4. Walk through: Under Review → Confirm Fraud
5. Show that enforcement dispatch log fires (or is suppressed in shadow mode)
6. Say: "Every decision by every analyst is logged with timestamp, reason, and outcome. Full audit trail."

### Phase 5: Manager View / KPI (2 minutes)

1. Back to Dashboard, scroll to KPI Panel
2. Point to: Reviewed Cases (24h), Reviewed Precision, Confirmed Recoverable
3. Show ROI Calculator — change Trips/Day to Porter's numbers (43,200/day = ~500K drivers)
4. Click "Recalculate ROI" → show the three scenarios (conservative/realistic/aggressive)
5. Click "Export ROI Brief" — PDF opens in new tab, ready to print

**ROI numbers to quote:**
- 43,200 trips/day → realistic annual savings: **₹6.80 crore**
- Payback: under 6 months at ₹3.25 crore platform price
- ROI: 109%+ in year 1

### Phase 6: Trip Scorer Live Demo (2 minutes, optional)

1. Scroll to Trip Scorer panel on Dashboard
2. Click a preloaded scenario (e.g. "Ghost Trip — Cancelled with Fare")
3. Click "⚡ Score This Trip"
4. Show result: probability in red, "ACTION REQUIRED" badge pulsing
5. Then select a clean scenario, score it — "CLEAR" in green
6. Say: "This is what your analysts see on every trip. They're not looking at raw data — they're looking at a decision."

---

## 3. Issue List — Status as of Day 13

All critical issues resolved. No blockers for demo day.

| Issue | Status | Notes |
|---|---|---|
| Feature names mismatched in stateless scorer (14/31 features → 0.0) | **FIXED** | `build_feature_vector()` rewritten with exact FEATURE_COLUMNS names |
| Duplicate `POST /roi/calculate` route | **FIXED** | Removed async wrapper, kept `build_roi_response()` |
| `greenlet` missing from requirements.txt | **FIXED** | Added `greenlet==3.2.5` |
| SyntaxError in `api/routes/legal.py` (curly quotes) | **FIXED** | Replaced with straight quotes |
| `data/samples/` accidentally archived | **FIXED** | Restored — needed by `test_batch_csv_endpoint_accepts_sample` |
| Feature count wrong in architecture docs (35 → 31) | **FIXED** | Documented in `docs/architecture.md` |
| Private files in public GitHub repo | **FIXED** | Removed: `_archive/`, `data/raw/`, `model/weights/`, `docs/handover/`, `docs/demo/`, `docs/security/`, `docs/runbooks/rotate-secrets.md` |

---

## 4. Known Limitations — Be Honest About These

These are not bugs. They are design constraints the buyer should know.

| Limitation | Honest answer |
|---|---|
| Model trained on synthetic data | "Correct. That is what shadow mode validates. Precision is measured on your data, not ours." |
| No live city data connection yet | "The schema mapper is built for your field names. We connect during deployment, not before signing." |
| Model weights not in public GitHub | "Intentional. Weights transfer on signing, under NDA. Code is public; IP is protected." |
| Redis required for full feature enrichment | "Without Redis, the stateless scorer uses trip-level features only. Driver history features come from the Redis feature store during deployment." |
| 63 tests, none use a real database | "Tests use FastAPI TestClient with dependency injection. DB integration tests are part of the deployment validation phase." |

---

## 5. Fallback Plan

If the live demo environment fails during the meeting:

### Fallback A: API offline
- Show `docs/demo/fail-safe-demo.md` screenshots
- Walk through the ROI calculator numbers manually
- Say: "The live environment had a connectivity issue. Let me walk you through the outputs directly."

### Fallback B: Frontend not connecting
- Navigate directly to `localhost:8000/docs` — OpenAPI UI is always available
- Use curl commands from the quickstart to score a trip live in terminal

### Fallback C: Everything down
- Open the board pack PDF (available locally at `_archive/docs_sales/founders-work/artifacts/porter-intelligence-board-pack.pdf`)
- Walk through benchmarks: 88.3% precision, 0.53% FPR, ₹6.80/trip recovery
- Say: "The numbers stand on their own. We can schedule a technical deep-dive when the environment is back."

---

## 6. Numbers to Have Ready (No Looking Up)

| Metric | Value |
|---|---|
| Training set | 100,000 trips |
| Fraud rate in dataset | 5.9% |
| Action-tier precision | 88.3% |
| Action-tier FPR | 0.53% |
| Fraud caught (action + watchlist) | 81.5% |
| Net recovery per trip | ₹6.80 |
| Benchmark annual recovery (500K fleet) | ₹6.80 crore |
| Platform price | ₹3.25 crore |
| Milestone structure | ₹1Cr on signing / ₹1Cr on shadow validation / ₹1.25Cr on rollout |
| Shadow mode validation window | 30–60 days |
| Support window post-handover | 90 days |
| Number of features | 31 |
| Number of cities in digital twin | 22 |
| Number of fraud archetypes | 5 |
| Tests passing | 63/63 |
| API endpoints | 47 |

---

## 7. Environment Setup (Pre-Meeting)

Run these in order, 30 minutes before the meeting:

```bash
# 1. Activate venv and verify dependencies
cd /path/to/Porter
source venv/bin/activate
pip install -r requirements.txt --quiet

# 2. Start backend
uvicorn api.main:app --port 8000 &

# 3. Verify health
curl -s http://localhost:8000/health | python3 -m json.tool

# 4. Start frontend
cd dashboard-ui && npm run dev &

# 5. Open browser tabs:
#    - localhost:5173 (dashboard)
#    - localhost:5173/login (analyst workspace)
#    - localhost:8000/docs (API documentation)

# 6. Run final test
cd .. && pytest tests/ -q
```

Expected output: `63 passed in under 3 seconds`

---

*Day 13 complete. Day 14 is the meeting.*
