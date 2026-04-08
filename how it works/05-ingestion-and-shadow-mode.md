# 05 — Ingestion And Shadow Mode

[Index](./README.md) | [Prev: API Reference](./04-api-reference.md) | [Next: Frontend](./06-frontend-and-dashboard.md)

This document explains how trip data enters the platform, how it flows through the scoring pipeline, and how shadow mode provides risk-free validation.

---

## Ingestion Architecture

```
                 Three Ingestion Paths
                 ─────────────────────
    Webhook              Batch CSV           Digital Twin
    POST /ingest/        POST /ingest/       ingestion/
    trip-completed       batch-csv           live_simulator.py
         │                    │                    │
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────────────────────────────────────────────┐
    │          Schema Mapper (field translation)       │
    │          ingestion/schema_mapper.py               │
    └─────────────────────┬───────────────────────────┘
                          │
                          ▼
    ┌─────────────────────────────────────────────────┐
    │          Redis Stream: porter:trips               │
    │          Consumer group: scoring-workers          │
    └─────────────────────┬───────────────────────────┘
                          │
              ┌───────────┼───────────┐
              │                       │
         Redis OK              Redis unavailable
              │                       │
              ▼                       ▼
    Stream consumer           Inline scoring
    (async, background)       (synchronous fallback)
              │                       │
              ▼                       ▼
    ┌─────────────────────────────────────────────────┐
    │     Stateless Scorer → Tier Assignment            │
    │     → Case Persistence (if action/watchlist)      │
    │     → Enforcement Dispatch (if action + live)     │
    └─────────────────────────────────────────────────┘
```

---

## Path 1: Webhook Ingestion

**Endpoint:** `POST /ingest/trip-completed`
**Source:** `ingestion/webhook.py`

This is the production ingestion path. Porter's trip pipeline sends a POST request when a trip completes.

### Request format

```json
{
  "trip_id": "PORTER-TRIP-12345",
  "driver_id": "DRV-67890",
  "pickup_lat": 12.9352,
  "pickup_lon": 77.6245,
  "dropoff_lat": 12.9698,
  "dropoff_lon": 77.7500,
  "fare": 450,
  "distance_km": 8.2,
  "duration_min": 32,
  "payment_type": "CASH",
  "vehicle_category": "MINI",
  "completed_at": "2026-04-08T14:30:00Z",
  "zone": "koramangala",
  "city": "bangalore"
}
```

### HMAC signature verification

In production, requests must include an `X-Porter-Signature` header:

```
X-Porter-Signature: sha256=a1b2c3d4e5f6...
```

The signature is computed as `HMAC-SHA256(WEBHOOK_SECRET, request_body)`. The platform verifies this before processing.

### Field normalisation

The webhook normalises Porter's field names to the internal schema:

| Porter Field | Internal Field | Transformation |
|---|---|---|
| `fare` | `fare_inr` | Direct copy |
| `distance_km` | `declared_distance_km` | Direct copy |
| `duration_min` | `declared_duration_min` | Direct copy |
| `payment_type` | `payment_mode` | Map: CASH→cash, UPI→upi, CARD→credit, WALLET→upi |
| `vehicle_category` | `vehicle_type` | Map: TWO_WHEELER→two_wheeler, MINI→mini_truck, etc. |
| `zone` | `pickup_zone_id` | Direct copy or "unknown" |

### Processing flow

1. Verify HMAC signature (if required)
2. Normalise fields to internal schema
3. Return `200` immediately (non-blocking)
4. Background task: publish to Redis Stream
5. If Redis unavailable: buffer to PostgreSQL staging table

---

## Path 2: Batch CSV Upload

**Endpoint:** `POST /ingest/batch-csv`
**Source:** `ingestion/webhook.py`

Upload a CSV file for bulk scoring. Used for historical data analysis or demo walkthroughs.

### Usage

```bash
curl -X POST http://localhost:8000/ingest/batch-csv \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_trips.csv" \
  -F "mapping_name=default"
```

### Schema mapper

The `SchemaMapper` class (`ingestion/schema_mapper.py`) translates arbitrary CSV column names to the internal schema.

**How it works:**
1. Load an alias map (JSON file mapping internal field names to lists of accepted aliases)
2. For each CSV row, look up each internal field by trying all aliases
3. Apply type conversions (float, int, bool, timestamp)
4. Normalise payment modes and vehicle types
5. Derive temporal features (hour, day, is_night, is_peak)

**Default alias map** (`ingestion/schema_map.default.json`):

Each internal field has multiple accepted aliases. For example, `fare_inr` might accept: `fare_inr`, `fare`, `amount`, `trip_fare`, `total_fare`.

**Custom mappings:**

Partners can upload their own mapping JSON alongside the CSV:

```bash
curl -X POST http://localhost:8000/ingest/batch-csv \
  -F "file=@partner_data.csv" \
  -F "mapping_file=@partner_schema.json" \
  -F "mapping_name=partner_v1"
```

### Viewing the default mapping

```bash
curl http://localhost:8000/ingest/schema-map/default
```

Returns the full alias map with field count and sample template path.

---

## Path 3: Digital Twin (Live Simulator)

**Source:** `ingestion/live_simulator.py`
**Mode:** Demo only (`APP_RUNTIME_MODE=demo`)

The digital twin generates synthetic trip events at Porter-like scale across 22 cities.

### What it simulates

- 22 Indian cities with realistic zone profiles
- City-weighted trip distribution (Bangalore ~18%, Mumbai ~15%, Delhi ~12%, etc.)
- Time-of-day demand patterns per zone
- 5 fraud patterns injected at configurable rates:
  - `fare_inflation` (base rate: 6.2%)
  - `route_abuse` (2.1%)
  - `payout_spike` (1.8%)
  - `cancellation_abuse` (1.4%)
  - `cash_night_ring` (1.3%)

### Configuration

| Environment Variable | Purpose | Default |
|---|---|---|
| `PORTER_TWIN_TRIPS_PER_MIN` | Base trip generation rate | 30 |
| `PORTER_TWIN_SCALE_MULTIPLIER` | Volume multiplier | 1.0 |
| `PORTER_TWIN_DAILY_GROWTH_PCT` | Daily volume growth % | 0.0 |
| `PORTER_TWIN_ACTIVE_CITIES` | Comma-separated city filter | all 22 |
| `PORTER_TWIN_ELAPSED_DAYS` | Days since start (for growth) | 0 |
| `PORTER_TWIN_BASE_FRAUD_RATE` | Base fraud injection rate | 0.062 |

### How it works

The simulator runs as a long-lived asyncio task started by `api/state.py`:

```python
async def run_live_simulator():
    while True:
        trip = generate_live_trip(settings)
        await publish_trip(trip)           # → Redis Stream
        await asyncio.sleep(interval)      # controlled rate
```

Each trip is:
1. Pick a city (weighted by share and time-of-day)
2. Pick pickup and dropoff zones (weighted by demand)
3. Pick a fraud pattern (weighted by zone risk)
4. Build trip with realistic fare, distance, duration
5. Apply fraud mutations if pattern is not clean_baseline
6. Publish to Redis Stream

---

## Redis Stream Transport

**Source:** `ingestion/streams.py`

### Stream configuration

| Setting | Value |
|---|---|
| Stream name | `porter:trips` |
| Consumer group | `scoring-workers` |
| Consumer | `worker-1` |
| Block timeout | 2000ms (long-poll) |
| Batch size | 10 messages per read |

### Producer (`publish_trip`)

```python
async def publish_trip(trip: dict) -> str:
    msg_id = await redis.xadd("porter:trips", {"data": json.dumps(trip)})
    return msg_id
```

### Consumer loop (`consume_loop`)

The consumer is a long-running asyncio task:

```
1. XREADGROUP from porter:trips (block 2s, batch 10)
2. For each message:
   a. Parse trip JSON
   b. Score with stateless scorer
   c. Get tier assignment
   d. If action/watchlist: persist FraudCase to PostgreSQL
   e. XACK the message (only after successful processing)
3. On failure: message stays in PEL for manual inspection
4. On CancelledError: shut down cleanly
5. On other errors: log and retry after 5s
```

### Stream lag monitoring

`get_stream_lag()` returns the PEL (Pending Entries List) count, which represents unprocessed messages. This feeds the health endpoint and Prometheus metrics.

---

## PostgreSQL Staging (Fallback)

**Source:** `ingestion/staging.py`

When Redis is unavailable, trips are buffered to the `ingestion_staging` PostgreSQL table.

| Field | Type | Purpose |
|---|---|---|
| `payload` | JSONB | Full trip event payload |
| `status` | enum | pending, queued, failed |
| `retry_count` | int | Number of drain attempts |
| `source` | string | webhook, batch_csv, etc. |
| `mapping_name` | string | Schema mapping used |
| `error_message` | string | Why it was staged |

### Drain mechanism

When Redis comes back online, `drain_staged_trips()` is called:
1. Select pending rows (FIFO, limited to 50-100 per drain)
2. Publish each to Redis Stream
3. Mark as queued on success
4. Mark as failed after max retries

Draining happens automatically on the next successful ingestion call.

---

## Shadow Mode

### What is shadow mode?

Shadow mode runs the full scoring pipeline on real data but **never triggers enforcement actions**. Cases are stored in a separate `shadow_cases` table, completely isolated from live operations.

### How to enable

```bash
# In .env:
APP_RUNTIME_MODE=prod
SHADOW_MODE=true
```

### What changes in shadow mode

| Behaviour | Live Mode | Shadow Mode |
|---|---|---|
| Trip scoring | Active | Active (identical) |
| Case creation | `fraud_cases` table | `shadow_cases` table |
| Enforcement webhook | Dispatched for action tier | **Suppressed** |
| Analyst workflow | Full review capability | Full review capability |
| KPI tracking | Live precision metrics | Shadow precision metrics |
| Audit logging | Full audit trail | Full audit trail |

### Shadow mode checks

The `SHADOW_MODE` flag is checked at three critical points:

1. **`runtime_config.py`** at startup: determines `RuntimeSettings.shadow_mode`
2. **`database/case_store.py`** on every case persist: chooses `FraudCase` vs `ShadowCase` table
3. **`enforcement/dispatch.py`** on every webhook call: suppresses if shadow mode

### Shadow mode validation path

```
Day 1-7:   Connect to Porter's trip feed → shadow mode on
Day 8-60:  Score real trips, analysts review shadow cases
           Measure: reviewed-case precision, false alarm rate
Day 45-60: Acceptance criteria evaluation
Day 61:    If accepted → set SHADOW_MODE=false → live enforcement
```

### Why shadow mode matters

- **Zero operational risk**: No driver suspensions, no enforcement actions
- **Real data validation**: Proves the model works on Porter's actual patterns
- **Analyst trust building**: Analysts learn the workflow on real cases
- **Rollback safety**: Switching back to shadow mode is a config change, not a code change

### Checking shadow status

```bash
curl http://localhost:8000/shadow/status
```

```json
{
  "shadow_mode": true,
  "enforcement_suppressed": true,
  "case_table": "shadow_cases",
  "note": "All scoring active. Enforcement dispatch suppressed. Cases stored in shadow_cases table."
}
```

---

## Enforcement Dispatch

**Source:** `enforcement/dispatch.py`

When a trip reaches the action tier in live mode, an HTTP webhook is sent to Porter's driver management system.

### Configuration

| Variable | Purpose | Required |
|---|---|---|
| `PORTER_DISPATCH_URL` | Webhook endpoint URL | No (log-only if not set) |

### Behaviour matrix

| Condition | Action |
|---|---|
| `PORTER_DISPATCH_URL` set + live mode | Send HTTP POST |
| `PORTER_DISPATCH_URL` set + shadow mode | **Suppressed** (logged only) |
| `PORTER_DISPATCH_URL` not set | Log the action (audit trail) |

### Webhook payload

```json
{
  "driver_id": "DRV-001",
  "trip_id": "TRIP-001",
  "fraud_probability": 0.96,
  "confidence_tier": "action",
  "recommended_action": "suspend",
  "top_signals": ["Cash payment", "Fare inflated 2.3x"]
}
```

Timeout: 5 seconds. Non-blocking (dispatched as asyncio task).

---

## Ingestion Pipeline Status

```bash
curl http://localhost:8000/ingest/status
```

Returns:
- Webhook URL and signature configuration
- Queue status (Redis stream lag, staging table counts)
- Configuration notes

---

## Next

- [Frontend and Dashboard](./06-frontend-and-dashboard.md) — React UI documentation
- [Security and Auth](./07-security-and-auth.md) — encryption, JWT, RBAC
