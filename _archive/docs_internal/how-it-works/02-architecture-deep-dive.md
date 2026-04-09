# 02 — Architecture Deep Dive

[Index](./README.md) | [Prev: Quickstart](./01-quickstart-tutorial.md) | [Next: ML Pipeline](./03-data-and-ml-pipeline.md)

This document explains every component of the Porter Intelligence Platform, how they connect, and why each design decision was made.

---

## System Architecture Diagram

```
                                    EXTERNAL
                                    --------
                    Porter Trip Pipeline (webhook / CSV / API)
                                      |
                                      v
 +-------------------------------------------------------------------+
 |                        INGESTION LAYER                             |
 |  ingestion/webhook.py    ingestion/schema_mapper.py                |
 |  POST /ingest/trips      POST /ingest/batch-csv                   |
 |  HMAC signature verify   Configurable field translation            |
 +-------------------------------|-----------------------------------+
                                 |
                                 v
 +-------------------------------------------------------------------+
 |                        TRANSPORT LAYER                             |
 |  Redis Stream: porter:trips                                        |
 |  Consumer group: scoring-workers                                   |
 |  Fallback: inline scoring if Redis unavailable                     |
 |  Staging: PostgreSQL ingestion_staging (retry/replay)              |
 +-------------------------------|-----------------------------------+
                                 |
                                 v
 +-------------------------------------------------------------------+
 |                        SCORING LAYER                               |
 |  model/scoring.py         api/inference.py                         |
 |  XGBoost predict_proba -> Two-stage tiering                        |
 |  35 features              Action >= 0.94 | Watch 0.45-0.94 | Clear|
 +------------|-----------------|-----------------------------------+
              |                 |
              v                 v
 +------------------------+  +------------------------------------+
 | CASE PERSISTENCE       |  | ENFORCEMENT DISPATCH               |
 | database/models.py     |  | enforcement/dispatch.py            |
 | FraudCase (live)       |  | Webhook to Porter dispatch system  |
 | ShadowCase (shadow)    |  | Suppressed in shadow mode          |
 | DriverAction           |  | Log-only if URL not configured     |
 | AuditLog               |  +------------------------------------+
 +------------|----------+
              |
              v
 +-------------------------------------------------------------------+
 |                        API LAYER (FastAPI)                         |
 |  14 endpoints across 12 routers                                    |
 |  JWT auth + RBAC | Rate limiting | Security headers               |
 |  Pydantic validation | Async SQLAlchemy                            |
 +------------|----------|-----------------------------------------+
              |          |
              v          v
 +-------------------+  +-------------------------------------------+
 | FRONTEND (React)  |  | OBSERVABILITY                             |
 | Dashboard.jsx     |  | Prometheus /metrics                       |
 | Analyst.jsx       |  | Grafana dashboards                        |
 | Heatmap, KPIs,    |  | /health endpoint                          |
 | ROI Calculator    |  | APScheduler drift + lag monitoring         |
 +-------------------+  +-------------------------------------------+
```

---

## Component-By-Component Breakdown

### 1. Runtime Configuration (`runtime_config.py`)

The platform has three runtime modes that control behavior:

| Mode | `APP_RUNTIME_MODE` | Synthetic Feed | Shadow Mode | Enforcement |
|---|---|---|---|---|
| **Demo** | `demo` | On (default) | Off | Suppressed |
| **Shadow** | `prod` | Off | On (`SHADOW_MODE=true`) | Suppressed |
| **Production** | `prod` | Off | Off | Active |

The `RuntimeSettings` dataclass is frozen and immutable. It is computed once at startup from environment variables.

Key rules:
- Production mode forces `synthetic_feed_enabled = False` regardless of env var
- Shadow mode can only be activated in prod mode (demo mode is already non-operational)
- Enforcement dispatch checks shadow mode before every webhook call

### 2. Startup Sequence (`api/state.py`)

When the API starts, `state.py` performs a 13-step initialization sequence:

```
Step 1:  Resolve runtime mode (demo/prod) and shadow mode
Step 2:  Load XGBoost fraud model from model/weights/xgb_fraud_model.json
Step 3:  Load scoring thresholds from model/weights/threshold.json
Step 4:  Load feature names from model/weights/feature_names.json
Step 5:  Load two-stage config from model/weights/two_stage_config.json
Step 6:  Load evaluation report from data/raw/evaluation_report.json
Step 7:  Load trip and driver CSVs into pandas DataFrames
Step 8:  Warm Redis feature cache (driver and zone features)
Step 9:  Load Prophet demand models from model/weights/demand_models.pkl
Step 10: Initialize PostgreSQL tables (create if not exist)
Step 11: Precompute route-efficiency and top-risk caches
Step 12: Start Redis Stream consumer (background task)
Step 13: Start digital twin simulator if demo mode (background task)
```

Everything is stored in the `app_state` dictionary, which is accessible to all request handlers via `from api.state import app_state`.

**Design decision:** The `app_state` dict pattern was chosen for simplicity and demo speed. For multi-replica production, the mutable state (trips_df, drivers_df) should be moved to PostgreSQL/Redis reads. The stateless scoring path (Redis-backed features) already works without app_state.

### 3. Application Layer (`api/main.py`)

The FastAPI application is assembled in `main.py`:

**Middleware stack** (applied to every request, in order):
1. `PrometheusMiddleware` — tracks HTTP request latency per endpoint
2. `SecurityHeadersMiddleware` — adds X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy
3. `CORSMiddleware` — configurable allowed origins via `API_ALLOWED_ORIGINS`

**Rate limiting** (via slowapi):
- Auth endpoints: 10/minute
- Fraud scoring: 100/minute
- Ingestion: 300/minute

**Routers registered:**
1. `inference_router` — `/fraud/*` scoring and analytics
2. `auth_router` — `/auth/*` login and token
3. `cases_router` — `/cases/*` case CRUD and driver actions
4. `query_router` — `/query/*` natural language
5. `intelligence_router` — `/driver-intelligence/*`
6. `demo_router` — `/demo/*` scenarios and reset
7. `reports_router` — `/reports/*` board pack PDF
8. `roi_router` — `/roi/*` ROI calculator
9. `efficiency_router` — `/route-efficiency/*`
10. `shadow_router` — `/shadow/*` status
11. `live_kpi_router` — `/kpi/*` reviewed-case KPIs
12. `ingest_router` — `/ingest/*` webhook and batch

**Core endpoints** (not in routers):
- `GET /` — serves dashboard HTML or welcome message
- `GET /health` — health, runtime mode, dependency readiness
- `GET /metrics` — Prometheus scrape endpoint
- `POST /webhooks/dispatch/test` — test enforcement webhook

### 4. Database Layer

**PostgreSQL** (via async SQLAlchemy + asyncpg):

6 tables defined in `database/models.py`:

| Table | Purpose | Key Fields |
|---|---|---|
| `fraud_cases` | Live fraud cases from scoring | trip_id, driver_id, tier, fraud_probability, status, top_signals, analyst_notes |
| `shadow_cases` | Isolated shadow-mode cases | Same as fraud_cases + source_channel, live_write_suppressed |
| `driver_actions` | Enforcement actions on drivers | driver_id, action_type (suspend/flag/monitor/clear), performed_by, expires_at |
| `audit_logs` | Immutable audit trail | user_id, action, resource, details (JSONB), ip_address |
| `model_metrics` | Model performance tracking | precision_action, recall, fpr, fraud_caught, total_trips |
| `ingestion_staging` | Retry/replay for failed ingestion | payload (JSONB), status (pending/queued/failed), retry_count |

**Connection pooling:**
- Pool size: 10
- Max overflow: 20
- Async engine via `create_async_engine`

**Redis** (via redis-py async):
- Feature cache: driver and zone features precomputed at startup
- Stream transport: `porter:trips` stream for async scoring
- Connection via `REDIS_URL` environment variable

### 5. Scoring Pipeline

The scoring pipeline is the core intelligence of the platform. See [Data and ML Pipeline](./03-data-and-ml-pipeline.md) for full details.

**Quick summary:**

```
Trip Event -> Feature Engineering (35 features) -> XGBoost predict_proba
    -> Two-Stage Tiering:
        >= 0.94: ACTION (investigate immediately)
        0.45 - 0.94: WATCHLIST (monitor, escalate if 3+ in 24h)
        < 0.45: CLEAR (no action)
    -> Persist FraudCase (action/watchlist only)
    -> Dispatch enforcement webhook (action only, live mode only)
```

### 6. Ingestion Pipeline

See [Ingestion and Shadow Mode](./05-ingestion-and-shadow-mode.md) for full details.

**Quick summary:**

Three ingestion paths:
1. **Webhook** (`POST /ingest/trips`): single trip event with optional HMAC verification
2. **Batch CSV** (`POST /ingest/batch-csv`): bulk upload of trip records
3. **Digital twin** (`ingestion/live_simulator.py`): synthetic event generator (demo mode only)

All paths feed into Redis Stream `porter:trips`. Consumer group `scoring-workers` processes events asynchronously. If Redis is unavailable, inline scoring fallback ensures no events are lost.

### 7. Enforcement Dispatch

`enforcement/dispatch.py` sends HTTP webhooks to Porter's driver management system when a trip reaches action tier.

**Behavior:**
- If `PORTER_DISPATCH_URL` is set: sends HTTP POST with fraud alert payload
- If not set: logs the action (audit trail) but does not send HTTP
- In shadow mode: always suppressed, never sends HTTP
- Timeout: 5 seconds
- Payload includes: driver_id, trip_id, fraud_probability, confidence_tier, recommended_action, top_signals

### 8. Frontend

See [Frontend and Dashboard](./06-frontend-and-dashboard.md) for full details.

**Quick summary:**
- React 19 + Vite build
- Two pages: Dashboard (management) and Analyst (case review)
- Leaflet.js for fraud heatmaps
- JWT auth stored in sessionStorage
- API calls via `apiGet`, `apiPost`, `apiPatch` helpers in `utils/api.js`

---

## Data Flow: Trip Event To Analyst Decision

This is the complete end-to-end flow:

```
1. Trip event arrives (webhook, CSV, or digital twin)
2. Schema mapper translates external field names to internal format
3. Event is published to Redis Stream "porter:trips"
4. Stream consumer picks up the event
5. Feature engineering: 35 features computed from trip + driver + zone data
6. XGBoost model predicts fraud probability (0.0 to 1.0)
7. Two-stage tiering assigns: action, watchlist, or clear
8. If action or watchlist:
   a. FraudCase row created in PostgreSQL (or ShadowCase if shadow mode)
   b. Top signals extracted (top 5 contributing features)
   c. Recoverable value estimated based on fare and fraud probability
9. If action tier AND live mode:
   a. Enforcement webhook dispatched to Porter's system
10. Case appears in analyst queue (frontend)
11. Analyst reviews: opens case, examines signals and driver profile
12. Analyst decides: confirm fraud, false alarm, or escalate
13. If confirm fraud: analyst can take driver action (suspend/flag/monitor)
14. All decisions logged in audit_logs with timestamp, analyst ID, IP
15. KPI surface updates: reviewed-case precision, false-alarm rate, recovery
```

---

## Design Decisions And Trade-Offs

### Why XGBoost instead of deep learning?

- XGBoost is fast (5-10ms per prediction), interpretable, and works well with tabular data
- The top signals feature requires feature importance, which XGBoost provides natively
- Deep learning models are harder to explain to fraud analysts ("why was this flagged?")
- For tabular fraud data with 35 features, XGBoost typically matches or outperforms neural networks

### Why two-stage scoring instead of binary classification?

- Binary classification (fraud/not fraud) creates too many false alarms at high sensitivity
- Two-stage scoring gives analysts a priority system: handle action-tier first, then watchlist
- Watchlist escalation (3+ appearances in 24h) catches coordinated fraud that single-trip scoring misses
- This design is standard in financial fraud detection (Visa, Mastercard use similar tiering)

### Why Redis Streams instead of Kafka?

- Redis Streams provides pub/sub with consumer groups, message acknowledgment, and replay
- For the current scale (100k trips/day), Redis is sufficient and simpler to operate
- If Porter scales to millions of trips/day, migration to Kafka or Kinesis is a deployment decision, not an architecture change
- The consumer pattern is the same either way

### Why app_state instead of a service layer?

- The `app_state` dict pattern loads everything at startup for fast demo response times
- This is a known scalability compromise: it works for single-replica deployments
- The stateless scoring path (Redis features + model in memory) already works without app_state for most endpoints
- Migration to a service layer is a refactoring task, not an architecture rewrite

### Why shadow mode as a mode toggle?

- Shadow mode is controlled by a single environment variable (`SHADOW_MODE=true`)
- This is simpler and safer than code-level branching
- The enforcement dispatch module checks the mode on every call, not just at startup
- Shadow cases are stored in a separate table (`shadow_cases`), so there is never data mixing

---

## What Is Not Yet Built

| Gap | Impact | Effort to Close |
|---|---|---|
| Model retraining pipeline | Cannot retrain on new data without manual script run | Medium (add training endpoint or scheduled job) |
| Horizontal scaling config | Single-worker deployment only | Low (ECS task count + Redis consumer scaling) |
| Database migrations | Tables created at startup, no Alembic migrations | Medium (add Alembic migration chain) |
| Distributed tracing | No request tracing across services | Medium (add OpenTelemetry) |
| Alert rules | Prometheus metrics exist but no alert configuration | Low (add alertmanager rules) |
| Real Porter data validation | All evidence is synthetic | Blocked on Porter data access |

---

## Next

- [Data and ML Pipeline](./03-data-and-ml-pipeline.md) — deep dive into model training and scoring
- [API Reference](./04-api-reference.md) — every endpoint documented
