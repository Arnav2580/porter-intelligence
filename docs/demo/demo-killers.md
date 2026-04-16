# Porter Intelligence Platform — CXO Demo Audit
## "Demo Killers" — Full Findings Report

**Audit type:** Live demo walkthrough — every API endpoint hit, every dashboard panel exercised  
**Conducted by:** CXO-perspective audit (no prior bias toward fixing vs reporting)  
**Date:** 2026-04-10  
**API version:** 1.0.0  
**Runtime mode tested:** `demo` (synthetic feed enabled, shadow mode on, no Redis, no Postgres)  
**Model status:** Loaded ✓ — 500,000 trips in memory, XGBoost scoring functional  

---

## Company Context: Why This Audit Matters

Porter is India's dominant intra-city logistics platform. As of April 2026:

- **Revenue:** ₹4,340 Cr (FY25)
- **Valuation:** ₹10,400 Cr (Series F, Jan 2026) — unicorn status with profitability
- **Scale:** 22 cities, 6 lakh driver-partners, 30 lakh business customers
- **Daily trips:** ~43,200 trips/day in live simulator configuration
- **Known real fraud:** Incognia partnership revealed ~4,200 fraudulent overlapping orders per day before mitigation
- **Fraud types documented:** Multi-account cloning, fake cancellations, GPS manipulation, cash extortion, route deviation

This platform is being positioned as a fraud detection and operations intelligence layer for Porter. A demo failure in front of Porter ops leadership, their investors, or any prospective enterprise buyer is not recoverable. This report documents every flaw found during a live demo run.

---

## How to Read This Report

Findings are grouped into three severity tiers:

| Tier | Definition |
|---|---|
| **CRITICAL** | Kills the demo. The moment a buyer sees this, credibility is gone. Fix before any external showing. |
| **HIGH** | Breaks the narrative. The platform scores correctly but the story around it falls apart. Fix before a serious sales conversation. |
| **MEDIUM** | Chips away at credibility. Survives a casual demo but will be caught by a technical buyer or an ops person who knows Porter's real data. Fix before pilot. |

---

## CRITICAL FINDINGS

---

### C1 — watchlist_threshold exposed as 0.82 instead of 0.45

**Severity:** CRITICAL — Demo killer  
**Where it breaks:** Dashboard header badge, FraudFeed tier labels, any UI reading `/health`  
**Reproducible:** Yes, every time  

#### What Actually Happens

Open the dashboard. The live fraud feed shows trips. Every trip scoring between 0.45 and 0.82 — which is the entire WATCHLIST tier — is labelled **"CLEAR"** in the UI.

The `/health` endpoint returns:
```json
{
  "thresholds": {
    "watchlist_threshold": 0.8199999999999996,
    "action_threshold": 0.94
  }
}
```

The `FraudFeed.jsx` component reads `thresholds.watchlist_threshold` from the health endpoint and uses it to assign tier labels. With `watchlist_threshold = 0.82`, any trip scoring 0.45–0.81 gets labelled CLEAR. Meanwhile, the `/fraud/tier-summary` endpoint correctly returns:
```json
{"name": "watchlist", "threshold_low": 0.45, "threshold_high": 0.88}
```

So the health endpoint and the tier-summary endpoint **contradict each other**. Two panels on the same dashboard show different threshold logic for the same model.

#### Root Cause

`api/main.py` health endpoint:
```python
# WRONG — loads threshold.json which stores the legacy single-stage threshold (0.82)
"watchlist_threshold": app_state.get("threshold", 0.45),
```

`threshold.json` contains `{"threshold": 0.82}`. This is the model's optimal single-stage classification threshold from training — it was never meant to be used as the watchlist boundary. The two-stage config is in `two_stage_config.json`:
```json
{
  "watchlist_threshold": 0.45,
  "action_threshold": 0.94
}
```

#### Fix Required

`api/main.py` health endpoint:
```python
# CORRECT
"watchlist_threshold": (app_state.get("two_stage_config") or {}).get("watchlist_threshold", 0.45),
```

Also, `threshold.json` should be deprecated or renamed to avoid future confusion. It represents a single-stage threshold that is never used in the platform's two-stage scoring logic.

#### Business Impact

A buyer watching the fraud feed sees trips that should be flagged as WATCHLIST silently labelled CLEAR. The platform appears to have a much lower fraud detection rate than it actually does. In a worst case, an investor asks "why is this trip CLEAR when it scored 0.71?" and there is no good answer.

---

### C2 — `/kpi/live` crashes with HTTP 500 when PostgreSQL is unavailable

**Severity:** CRITICAL — Demo killer  
**Where it breaks:** KPI Panel on the main dashboard  
**Reproducible:** Yes, any time Postgres is not running locally  

#### What Actually Happens

Navigate to the dashboard. The KPI Panel — the single most important panel for proving business value — shows nothing. No numbers. No error message. Just blank.

In the browser console:
```
GET http://localhost:8000/kpi/live → 500 Internal Server Error
```

In the API log:
```
OSError: Multiple exceptions: [Errno 61] Connect call failed ('127.0.0.1', 5432),
[Errno 61] Connect call failed ('::1', 5432, 0, 0)
File "/Users/arnav/Porter/api/routes/live_kpi.py", line 118, in kpi_live
```

#### Root Cause

`api/routes/live_kpi.py` executes a SQLAlchemy query with no try/except around the database connection:
```python
async with AsyncSessionLocal() as db:
    result = await db.execute(select(...))  # crashes if Postgres is down
```

When asyncpg cannot connect to Postgres, it raises `OSError` which propagates as an unhandled exception → FastAPI returns 500 with no JSON body, just "Internal Server Error" as plain text.

The `/kpi/summary` endpoint handles this correctly — it reads from a pre-loaded benchmark JSON file and works without any database. `/kpi/live` has no such fallback.

#### Fix Required

Wrap the DB query in try/except and return a graceful degraded response when Postgres is unavailable:
```python
try:
    async with AsyncSessionLocal() as db:
        result = await db.execute(...)
except Exception:
    return JSONResponse(
        status_code=200,
        content={
            "status": "degraded",
            "message": "Database unavailable — showing benchmark metrics",
            "review_confidence": {"status": "awaiting_reviews", ...},
            # fallback to benchmark numbers from kpi/summary
        }
    )
```

#### Business Impact

The KPI Panel is the primary commercial proof point. "₹6.87 Cr annual recovery", "81.5% fraud caught", "0.53% false positive rate" — these are the numbers that justify the purchase. If the KPI Panel is blank for the first 5 minutes of a demo while someone fumbles with Docker, the demo is effectively over.

---

### C3 — `/shadow/status` and `/ingest/status` both return HTTP 500 without dependencies

**Severity:** CRITICAL  
**Where it breaks:** Shadow Mode panel (Analyst view), Ingestion status panel  
**Reproducible:** Yes, any time Redis or Postgres is unavailable  

#### What Actually Happens

```
GET /shadow/status → 500 Internal Server Error
GET /ingest/status → 500 Internal Server Error
```

Both endpoints crash completely without Redis or Postgres. They return `"Internal Server Error"` as plain text, not JSON. The frontend panels that consume these endpoints show blank states with no error messaging.

#### Root Cause

Same pattern as C2 — no try/except around database/Redis connections. When these fail, the raw exceptions propagate up through FastAPI's ASGI stack.

The shadow mode endpoint attempts to check Redis for the stream PEL count. The ingest status endpoint queries Postgres for staging records. Both fail silently to the user.

#### Fix Required

Every endpoint that depends on external infrastructure (Redis, Postgres) must have:
1. A try/except around the dependency call
2. A meaningful degraded JSON response (not plain text 500)
3. A `"status": "degraded"` field so the frontend can show a proper state

#### Business Impact

During an Analyst view demo — where you show the workflow from "trip flagged" → "analyst reviews" → "action taken" — the Shadow Mode panel is completely blank. This panel is supposed to show that the platform can run in observation-only mode before going live. It is one of the most important buy-in features for ops teams nervous about automated enforcement.

---

### C4 — Log spam: one Redis connection error every 2 seconds

**Severity:** CRITICAL — Visible presentation risk  
**Where it breaks:** Terminal output during any demo where screen is shared  
**Reproducible:** Every time Redis is unavailable  

#### What Actually Happens

The API log emits:
```
{"level": "WARNING", "msg": "Live simulator publish error: Error connecting to localhost:6379..."}
{"level": "WARNING", "msg": "Live simulator publish error: Error connecting to localhost:6379..."}
{"level": "ERROR", "msg": "Stream consumer loop error: Error connecting to localhost:6379..."}
```

This repeats every 2 seconds, forever, generating ~90 error lines per minute in the terminal.

If a presenter shares their screen during a demo and the terminal is visible — even briefly — the buyer sees a platform that is continuously throwing errors. There is no graceful handling of Redis unavailability beyond logging.

#### Root Cause

The live simulator loop retries publishing to Redis on every tick (every 2 seconds) with no backoff. The stream consumer loop retries every 5 seconds with no backoff either. Neither loop detects that Redis is persistently unavailable and reduces retry frequency.

`ingestion/live_simulator.py` and `ingestion/streams.py` both use patterns like:
```python
while True:
    try:
        await redis.xadd(...)
    except Exception as e:
        logger.warning(f"Live simulator publish error: {e}")
    await asyncio.sleep(2)  # retry immediately
```

#### Fix Required

Implement exponential backoff with a maximum interval when Redis is confirmed down:
```python
redis_backoff = 1
redis_last_error = None

while True:
    try:
        await redis.xadd(...)
        redis_backoff = 1  # reset on success
    except ConnectionError as e:
        redis_backoff = min(redis_backoff * 2, 300)  # cap at 5 minutes
        if redis_backoff > 30:
            logger.warning(f"Redis unavailable, retry in {redis_backoff}s (suppressing further logs)")
        await asyncio.sleep(redis_backoff)
        continue
    await asyncio.sleep(2)
```

#### Business Impact

During a screen-share demo, continuous error output destroys the "enterprise-grade platform" impression instantly. Even technically unsophisticated buyers notice a terminal scrolling with red ERROR lines.

---

### C5 — `recoverable_inr` shown as 100% of fare in the live feed

**Severity:** CRITICAL — Financial credibility failure  
**Where it breaks:** Fraud Activity Feed, any panel showing recoverable amounts  
**Reproducible:** Yes, whenever benchmark CSV is being served  

#### What Actually Happens

The fraud live feed shows:
```
fare=130.39   recoverable=130.39   ratio=1.00
fare=197.69   recoverable=197.69   ratio=1.00
fare=58.63    recoverable=58.63    ratio=1.00
```

Every item in the feed has `recoverable` exactly equal to `fare_inr`. The platform is claiming it can recover 100% of the disputed fare — which is financially impossible and will immediately be challenged by any finance or ops person.

The `/fraud/score` endpoint correctly computes `recoverable_inr = round(fare_inr * 0.15, 2)` (15% of fare). But the live feed reads directly from the benchmark CSV which has `recoverable_amount_inr` set equal to the full fare amount in the generator.

#### Root Cause

`generator/fraud.py` sets `recoverable_amount_inr = fare_inr` for fraudulent trips (or applies a multiplier > 1.0 in some cases). The benchmark CSV was generated with this logic. When the live feed reads from this CSV and serves it directly, the raw `recoverable_amount_inr` column is used without any cap or percentage-based correction.

The live simulator (`ingestion/live_simulator.py`) generates new trips with a similar miscalculation — it sets `recoverable` to the full fare amount instead of a percentage.

#### Fix Required

In the live feed endpoint (`api/inference.py`), cap recoverable to a realistic percentage:
```python
# When reading from benchmark CSV:
item.recoverable = min(item.recoverable, round(item.fare_inr * 0.20, 2))
```

In the generator, update `recoverable_amount_inr` to reflect realistic recovery rates:
- Cash extortion: ~80% (most recovered through chargebacks)
- Fake trip: ~15% (platform credit only)
- Route deviation: ~20% (partial refund)
- Duplicate trip: ~100% (full reversal)

#### Business Impact

A Porter finance analyst sees "recoverable ₹197 on a ₹197 fare." They immediately say "that's not how chargebacks work." The entire financial model of the platform is questioned. The ROI calculator (which correctly uses ₹6.79/trip benchmark) is contradicted by the live feed showing 100% recovery.

---

## HIGH FINDINGS

---

### H1 — Clean trip shows misleading fraud signals on a CLEAR score

**Severity:** HIGH  
**Where it breaks:** Trip Scorer panel, any analyst reviewing why a trip was cleared  

#### What Actually Happens

Score the clean trip scenario (6km, 24min, ₹82 UPI, 10am daytime, established zone):
- **Score:** 0.046 — correctly CLEAR ✓
- **Top signals shown:** "Fare inflated 1.05×", "Speed anomaly (0.25 km/min)", "New/unverified driver account"

All three signals are wrong for a legitimate trip:

1. **"Fare inflated 1.05×"** — 5% above expected fare is statistical noise, not a fraud signal. Expected fare for 6km two-wheeler = ₹78, actual = ₹82. A 5% variance is within normal surge/rounding tolerance.

2. **"Speed anomaly (0.25 km/min)"** — 0.25 km/min = 15 km/h. That is normal Bangalore traffic speed. The `distance_time_ratio` feature is being triggered even for perfectly normal trips.

3. **"New/unverified driver account"** — This is a false alarm caused by a Redis cold-start bug (see root cause below). The driver has no Redis entry, defaults to `total_trips: 0`, and the scorer labels them as new/unverified.

When a CLEAR trip shows fraud signals, analysts learn to ignore the signals entirely — destroying the value of the signal system for actual fraud cases.

#### Root Cause — Part 1: Redis cold start

`ml/feature_store.py` → `get_driver_features()` returns this default when Redis is cold:
```python
return {
    "driver_id":   driver_id,
    "total_trips": 0,          # ← This is the problem
    "cancel_rate": 0.0,
    "cash_ratio":  0.5,
    ...
    "driver_account_age_days": 30,  # ← Also a problem
}
```

In `ml/stateless_scorer.py`, `build_feature_vector()` maps this:
```python
drv_lifetime_trips = float(driver_features.get("driver_lifetime_trips",
                          driver_features.get("total_trips", 500)))
```

With Redis cold, `driver_features` has `total_trips: 0`, so `drv_lifetime_trips = 0`. The `_build_top_signals()` function in `api/inference.py` treats `driver_lifetime_trips = 0` as "New/unverified driver account" via the invert=True normalisation.

**Fix:** Change the default `total_trips` in `get_driver_features()` from `0` to `500`:
```python
return {
    "total_trips":             500,   # median established driver, not unknown
    "driver_account_age_days": 365,   # median established driver
    ...
}
```

#### Root Cause — Part 2: Signals fire on CLEAR trips

`_build_top_signals()` in `api/inference.py` does not gate on the trip's tier. It fires for every trip including CLEAR ones, then shows signals like "Fare inflated 1.05×" which is meaningless noise.

**Fix:** Gate signals on the fraud tier:
```python
if tier == "clear" and fraud_prob < 0.2:
    return ["No fraud signals — trip appears legitimate"]
```

#### Root Cause — Part 3: Speed signal threshold too sensitive

`distance_time_ratio` norm_max is set to 2.0 km/min. Normal city traffic is 0.2–0.4 km/min. Any trip at normal city speed produces a non-zero signal. The threshold should be calibrated to only fire above ~0.8 km/min (48 km/h — clearly anomalous in city conditions).

---

### H2 — GPS Spoof scenario: signals don't match the fraud story

**Severity:** HIGH  
**Where it breaks:** TripScorer demo walkthrough for the GPS spoof scenario  

#### What Actually Happens

Score the GPS spoof scenario (declared 1.4km, Hebbal→Yeshwanthpur, actual ~3.8km haversine):
- **Score:** 0.9998 — correctly ACTION ✓
- **Top signals shown:** "Fare inflated 15.53×", "New/unverified driver account" (false), "Cash ratio 50% (7d)"

**Missing signal:** "Distance declared less than actual route" — which is the entire point of GPS spoofing.

The scenario description says: *"Declared 1.4km but actual Hebbal→Yeshwanthpur route is 3.8km — driver declared a fraction of the true distance while charging full fare."*

But the signal "Fare inflated 15.53×" makes no sense when the declared distance is only 1.4km and the fare is ₹640. If the declared distance is 1.4km, the expected fare for a two-wheeler is ₹30 + ₹8 × 1.4 = ₹41. So ₹640 / ₹41 = 15.6× — the fare inflation signal fires because the fare is high relative to the *declared* (spoofed) distance, not because the distance is spoofed.

A buyer watching this will say "wait, is the GPS being spoofed to under-declare distance or to over-declare fare? The signal says fare inflation, not distance spoofing." The explanation breaks down.

#### Root Cause

The `distance_vs_haversine_ratio` feature in `_SIGNAL_META` is defined as `('Distance inflated {v:.2f}×', 3.0, False)`. This signal fires when declared distance > haversine distance (the driver claims to have gone farther than the straight-line route). But GPS spoofing to *under-declare* distance produces `distance_vs_haversine_ratio < 1.0` — the declared distance is *less* than haversine. The signal never fires for this fraud type.

#### Fix Required

Add a second distance signal for under-declaration:
```python
"distance_vs_haversine_ratio": (
    "Distance over-declared {v:.2f}×" if val > 1.0 else 
    "Distance under-declared ({v:.2f}× of actual route)",
    3.0, False
)
```

Or re-design the GPS spoof scenario to use over-declaration instead of under-declaration, so the existing signal fires correctly.

---

### H3 — Fraud heatmap shows only 3 cities despite 22-city simulator

**Severity:** HIGH  
**Where it breaks:** Zone Map on the main dashboard  

#### What Actually Happens

The live simulator runs 22 cities (Bangalore, Mumbai, Delhi, Hyderabad, Chennai, Pune, Ahmedabad, Jaipur, and 14 others). The health endpoint confirms `city_count: 22`.

The fraud heatmap shows:
```
Total zones: 24
Cities: ['bangalore', 'delhi', 'mumbai']
```

Only 12 Bangalore zones, 6 Delhi zones, 6 Mumbai zones. Zero zones for the other 19 cities.

When the `fitBounds()` auto-zoom fires, it zooms the map to the triangle formed by Bangalore-Delhi-Mumbai. The other 19 cities do not exist on the map. The "22 city" claim in the header is directly contradicted by the map.

#### Root Cause

The `/fraud/heatmap` endpoint reads zone fraud rates from `trips_full_fraud.csv` via `app_state["trips_df"]`. This CSV was generated only for Bangalore, Delhi, and Mumbai (the original 3-city dataset). The live simulator generates trips for 22 cities, but because Redis is down and Postgres is down, those trips are never persisted anywhere the heatmap can read.

The heatmap's zone list is derived from the zones present in the loaded trips DataFrame, not from the live simulator's city configuration.

#### Fix Required

Two options:
1. **Short-term:** Pre-populate the trips_df with the 22-city coverage from the generator so the heatmap always shows all cities.
2. **Correct fix:** The heatmap endpoint should aggregate from the live simulator's in-memory event stream, or from a pre-computed zone stats cache updated every minute.

---

### H4 — Efficiency Reallocation panel is always empty

**Severity:** HIGH  
**Where it breaks:** Reallocation Panel on the dashboard  

#### What Actually Happens

The efficiency summary shows real, meaningful data:
```json
{
  "overall_utilisation": 0.9629,
  "total_dead_mile_rate": 0.1715,
  "total_dead_cost_per_day": 52323.86,
  "idle_vehicle_hours_now": 1243,
  "annual_dead_cost_estimate": 19098208.90
}
```

₹52,323/day in dead-mile costs. 1,243 idle vehicle hours right now. ₹1.9 Cr annual dead-cost estimate.

But `/efficiency/reallocation` returns:
```json
{"suggestions": [], "total": 0, "generated_at": "2026-04-10T17:14:03"}
```

Zero suggestions. The Reallocation Panel on the dashboard shows a blank "no suggestions" state despite ₹52,000/day in identified waste.

#### Root Cause

The reallocation suggestion engine requires comparing zone-level surplus and deficit in real-time (vehicles waiting in one zone while another zone has unmet demand). This comparison is powered by the live simulator's trip stream feeding Redis. Without Redis, the reallocation engine has no demand signal to compare against supply, so it generates no suggestions.

#### Fix Required

Pre-compute reallocation suggestions from the historical trips_df and efficiency data at startup, refreshing every 5 minutes. This gives the panel meaningful output even without live Redis.

---

### H5 — Live feed shows "LIVE" badge when actually serving benchmark data

**Severity:** HIGH  
**Where it breaks:** Fraud Activity Feed header badge  

#### What Actually Happens

In demo mode with `ENABLE_SYNTHETIC_FEED=true`, `synthetic_feed_enabled=True` in `app_state`. The `is_benchmark` flag is `not synthetic_feed_enabled = False`. So the live feed header shows a green pulsing "LIVE" badge.

But with Redis down, the simulator is not actually publishing any trips to Redis. The live feed is falling back to the benchmark CSV (100k-trip evaluation set). The data being shown is 2–3 weeks old benchmark data, not live simulation data.

The badge says LIVE. The data is not live. They are in direct contradiction.

#### Root Cause

`is_benchmark` is determined by whether the synthetic feed flag is enabled, not by whether it is actually working:
```python
is_benchmark = not synthetic_feed_enabled  # checks flag, not actual Redis connectivity
```

When `synthetic_feed_enabled=True` but Redis is down, the feed falls back to CSV data but still reports `is_benchmark=False` (live).

#### Fix Required

Check actual Redis connectivity before determining the badge:
```python
redis_healthy = await ping_redis()
is_benchmark = not synthetic_feed_enabled or not redis_healthy
```

---

## MEDIUM FINDINGS

---

### M1 — `demo_start.sh` starts Docker with placeholder secrets → API will reject them

**Severity:** MEDIUM  
**Where it breaks:** Running `demo_start.sh` for the first time on a clean machine  

#### What Actually Happens

`demo_start.sh` does:
```bash
if [[ ! -f ".env" ]]; then
  cp .env.example .env
fi
docker compose up -d
```

`docker-compose.yml` passes env vars including `JWT_SECRET_KEY=${JWT_SECRET_KEY:?}`. If `.env` contains placeholder values (`replace-with-secure-random-64-char-string`), docker compose fails with:
```
required variable JWT_SECRET_KEY is not set
```

Even if that passes, the API security validator will accept these values (they're long enough to pass entropy checks) but they are cryptographically weak. Sessions signed with `replace-with-secure-random-64-char-string` are predictable.

#### Fix Required

`demo_start.sh` should auto-generate secure demo secrets if the `.env` doesn't contain real values:
```bash
if ! grep -q "^JWT_SECRET_KEY=[^r]" .env 2>/dev/null; then
  echo "JWT_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(64))')" >> .env
  echo "ENCRYPTION_KEY=$(python3 -c 'import base64,os; print(base64.b64encode(os.urandom(32)).decode())')" >> .env
fi
```

---

### M2 — Ring member drivers all show 100% fraud rate (obviously synthetic)

**Severity:** MEDIUM  
**Where it breaks:** Driver Intelligence panel, `/intelligence/top-risk`  

#### What Actually Happens

Every driver in the top risk list:
```json
{
  "fraud_rate": 1.0,
  "total_trips": 13,
  "risk_score": 1.0,
  "risk_level": "CRITICAL",
  "recommended_action": "SUSPEND"
}
```

100% fraud rate, 13 trips. Every ring member driver. This is a synthetic data artefact — ring members are generated with all trips flagged as fraud. In real operations, even the most prolific fraud ring members have legitimate trips mixed in (to maintain account credibility). Real fraud rates for flagged drivers are 20–60%, not 100%.

A Porter ops manager will immediately say "this looks made up."

#### Fix Required

The fraud ring generator should inject a realistic noise floor of legitimate trips for ring members — at minimum 30% clean trips. This would give ring leaders fraud rates of ~65–70% and ring members ~40–50%, which is realistic and still clearly actionable.

---

### M3 — `threshold.json` value (0.82) is a ghost — never used, wrongly exposed

**Severity:** MEDIUM  
**Where it breaks:** API credibility, health endpoint data integrity  

#### What Actually Happens

`threshold.json` contains `{"threshold": 0.82}`. This value is:
- Loaded into `app_state["threshold"]`
- Exposed in the health endpoint as `watchlist_threshold` (wrong — it's the single-stage action threshold)
- Never used in any actual scoring path (the platform uses two-stage thresholds: 0.45 watchlist, 0.94 action)

The 0.82 value represents the XGBoost model's optimal single-class decision boundary from the training pipeline. It was written to disk during training as a reference, but the two-stage deployment superseded it.

A technical buyer reading the health endpoint and then reading the API docs will find no coherent explanation for why `watchlist_threshold = 0.82` while every other reference says 0.45.

#### Fix Required

Rename `threshold.json` to `single_stage_threshold.json` (or delete it). Update `api/state.py` to not load it into `app_state["threshold"]` at all, or clearly label it:
```python
app_state["legacy_single_stage_threshold"] = json.load(f)["threshold"]
```
And stop exposing it in the health endpoint.

---

### M4 — Demand forecasting endpoint works but is invisible in the UI

**Severity:** MEDIUM  
**Where it breaks:** Demo completeness — missing an entire feature  

#### What Actually Happens

`GET /demand/forecast/blr_koramangala` returns real, working Prophet-model forecasts:
```json
{
  "zone_id": "blr_koramangala",
  "forecast": [
    {"hour": 0, "hour_label": "17:00", "demand_multiplier": 1.343, "surge_expected": false},
    {"hour": 1, "hour_label": "18:00", "demand_multiplier": 1.65, "surge_expected": false},
    ...
  ]
}
```

This is valuable: real-time demand forecasting per zone, used to predict surge pricing windows and reallocation needs. It works correctly.

But there is **no UI panel** that shows this data. No dashboard component renders it. If a buyer asks "can you show me demand forecasting?" during a demo, the answer is "yes we have the API" while showing them raw JSON. That is not a demo.

#### Fix Required

Add a DemandForecast panel to the dashboard, or integrate it into the Zone Map overlay as a "Demand" mode toggle alongside the existing "Fraud" and "Fleet" modes.

---

### M5 — Driver account age defaults to 30 days for all cold-Redis drivers

**Severity:** MEDIUM  
**Where it breaks:** Analyst view — driver risk profile  

#### What Actually Happens

When Redis is cold (no driver features cached), `get_driver_features()` returns `driver_account_age_days: 30`. This means every driver in a demo without Redis looks like a 30-day-old account.

30 days is below the fraud risk threshold used in training data — new accounts (< 60 days) are flagged as higher risk. So every driver in a cold-Redis demo is artificially elevated to "newer account" risk profile.

Combined with the `total_trips: 0` default (see H1), every driver looks like a brand-new fraudulent account when Redis is unavailable.

#### Fix Required

`get_driver_features()` defaults should represent a median established driver:
```python
return {
    "total_trips":             500,   # median established Porter driver
    "driver_account_age_days": 365,   # 1 year — typical established driver
    "cancel_rate":             0.05,
    "cash_ratio":              0.25,
    "driver_is_verified":      1,
    ...
}
```

---

### M6 — Efficiency summary metrics are contradictory

**Severity:** MEDIUM  
**Where it breaks:** Efficiency panel, any conversation about fleet performance  

#### What Actually Happens

```json
{
  "overall_utilisation": 0.9629,
  "total_dead_mile_rate": 0.1715,
  "worst_efficiency_score": 0.8242,
  "best_efficiency_score": 0.8337
}
```

Claims: 96.3% overall utilisation. But also claims 17.15% dead-mile rate. And the "best" zone efficiency is 83.4%.

If utilisation is 96.3%, how can dead miles be 17.15%? These are measuring different things (trip completion rate vs empty-leg rate), but they are presented side by side on the same panel with no explanation. A logistics analyst will immediately flag this as contradictory.

Additionally: the best zone efficiency (83.4%) and worst zone efficiency (82.4%) are 1 percentage point apart. This means every zone in the fleet has essentially the same efficiency — which implies either the data is fabricated or the efficiency metric is not discriminating.

#### Fix Required

1. Add clear labels distinguishing what each metric measures
2. Re-examine the dead-mile rate calculation — 17% dead miles with 96% utilisation is internally inconsistent
3. The zone efficiency variance needs to be realistic (should span at least 60–95% range)

---

## Platform vs Real Porter Fraud Types — Gap Analysis

| Real Porter Fraud Problem | This Platform | Verdict |
|---|---|---|
| **Multi-account cloning** — drivers run 2 accounts simultaneously (~4,200/day per Incognia) | `duplicate_trip` fraud type in live feed | **PARTIAL** — duplicate trip detection exists but no multi-account fingerprinting logic |
| **GPS manipulation / route deviation** | GPS spoof scenario + distance signals | **PARTIAL** — scoring works, signal explanation wrong (H2) |
| **Cash payment extortion** — demand extra cash on delivery | Cash extortion scenario | **YES ✓** |
| **Fake cancellations** — cancel after accepting, claim cancellation fee | `fake_cancellation` in live feed + ring_walkthrough scenario | **YES ✓** |
| **Inflated distance declaration** | `distance_vs_haversine_ratio` feature | **YES ✓** |
| **Low vehicle utilisation** (1.5/5 trips actual vs potential) | Efficiency panel, dead-miles, reallocation | **PARTIAL** — data correct, reallocation suggestions empty (H4) |
| **22-city intra-city ops** | Simulator covers 22 cities | **PARTIAL** — heatmap shows only 3 (H3) |
| **Two-wheeler as primary vehicle** | Default scenario uses two_wheeler | **YES ✓** |
| **₹4,340 Cr GMV scale** | ROI calculator pre-populated with real Porter numbers | **YES ✓** |
| **Driver fraud rings** | Ring detection, ring member tagging | **YES** — but 100% fraud rate looks synthetic (M2) |
| **Night-time fraud concentration** | `is_night` feature, ring_walkthrough is night | **YES ✓** |
| **Surge pricing abuse** | `surge_multiplier` feature, scenarios use surge | **YES ✓** |

**Gaps vs real Porter fraud surface:**
- No multi-account detection (biggest real problem per Incognia data)
- No route deviation tracking (requires GPS stream, not just declared distance)
- No customer complaint cross-referencing

---

## Summary Scorecard

| # | Finding | Severity | Status |
|---|---|---|---|
| C1 | `watchlist_threshold` = 0.82 → WATCHLIST trips labelled CLEAR | CRITICAL | Open |
| C2 | `/kpi/live` 500 without Postgres → KPI Panel blank | CRITICAL | Open |
| C3 | `/shadow/status` + `/ingest/status` 500 without infra | CRITICAL | Open |
| C4 | Redis log spam — 1 error/2s → terminal looks on fire | CRITICAL | Open |
| C5 | `recoverable` = 100% of fare (should be ~15%) | CRITICAL | Open |
| H1 | Clean trip shows "New/unverified driver" + noise signals | HIGH | Open |
| H2 | GPS spoof signals don't explain the fraud type | HIGH | Open |
| H3 | Heatmap shows 3 cities despite 22-city simulator | HIGH | Open |
| H4 | Reallocation panel empty despite ₹52K/day dead-mile data | HIGH | Open |
| H5 | Live feed shows "LIVE" badge when serving benchmark CSV | HIGH | Open |
| M1 | `demo_start.sh` fails on clean machine with placeholder secrets | MEDIUM | Open |
| M2 | Ring members show 100% fraud rate — obviously synthetic | MEDIUM | Open |
| M3 | `threshold.json` (0.82) ghost value exposed as watchlist threshold | MEDIUM | Open |
| M4 | Demand forecasting endpoint exists but no UI panel | MEDIUM | Open |
| M5 | Cold-Redis driver defaults to 30 days old, 0 trips | MEDIUM | Open |
| M6 | Efficiency summary: 96% utilisation vs 17% dead-miles contradicts | MEDIUM | Open |

**Total: 5 CRITICAL · 5 HIGH · 6 MEDIUM**

---

## What Actually Works Correctly

To be fair: the core ML engine is solid.

| Component | Test Result |
|---|---|
| Ghost trip (2.5min, 2.8km, cash, night, ₹780) | 0.9924 ACTION ✓ |
| Clean trip (6km, 24min, UPI, ₹82, daytime) | 0.046 CLEAR ✓ |
| GPS spoof (1.4km declared, 3.8km actual) | 0.9998 ACTION ✓ |
| Cash extortion (4.1km, ₹1,250, 4.6× inflation) | ACTION ✓ |
| KPI summary (benchmark) | Loads correctly, all numbers consistent |
| ROI calculator | Works, correct inputs, credible output |
| Driver risk ranking | Returns data, logic sound |
| Demand forecasting API | Works, Prophet models functional |
| Fraud heatmap | Works for 3 cities present in training data |

**The model works. The surrounding platform does not hold together under real demo conditions.**

---

## Priority Fix Order

Fix in this sequence to unblock a demo:

1. **C1** — Fix `watchlist_threshold` in health endpoint (10 min fix, `api/main.py` one line)
2. **C4** — Add Redis backoff to simulator and stream consumer (silences the log spam)
3. **C2 + C3** — Wrap all DB/Redis calls in try/except with degraded JSON fallback
4. **H1 + M5** — Fix cold-Redis driver defaults in `ml/feature_store.py` + clear signal gate on CLEAR tier
5. **C5** — Cap recoverable to realistic percentage in live feed
6. **H5** — Fix `is_benchmark` to check actual Redis connectivity
7. **H3** — Pre-populate heatmap with 22-city zone coverage from generator
8. **H4** — Generate reallocation suggestions from historical data at startup

Fixes 1–4 can be done in under 2 hours and eliminate all 5 CRITICAL findings.

---

*Report generated from live demo run — all API calls reproducible. Endpoint URLs tested: `/health`, `/fraud/score`, `/fraud/live-feed`, `/fraud/heatmap`, `/fraud/tier-summary`, `/kpi/live`, `/kpi/summary`, `/roi/calculate`, `/efficiency/summary`, `/efficiency/reallocation`, `/intelligence/top-risk`, `/shadow/status`, `/ingest/status`, `/demand/forecast/{zone_id}`, `/demo/scenarios`*
