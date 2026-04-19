# Porter Intelligence Platform

**Real-time fraud detection, driver intelligence, and fleet analytics for large-scale ride-hailing and logistics operations.**

Porter replaces manual, reactive compliance workflows with a fully automated ML pipeline: trips are scored the moment they complete, high-risk cases surface instantly to analysts, and enforcement actions are dispatched within seconds — all with a complete audit trail.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Solution](#2-solution)
3. [Live Benchmarks](#3-live-benchmarks)
4. [Architecture Overview](#4-architecture-overview)
5. [Tech Stack](#5-tech-stack)
6. [Fraud Detection Model](#6-fraud-detection-model)
7. [Feature Engineering — 31 Features](#7-feature-engineering--31-features)
8. [Ingestion Pipeline](#8-ingestion-pipeline)
9. [Case Lifecycle](#9-case-lifecycle)
10. [Driver Intelligence](#10-driver-intelligence)
11. [Demand Forecasting](#11-demand-forecasting)
12. [Route Efficiency](#12-route-efficiency)
13. [Security Architecture](#13-security-architecture)
14. [Shadow Mode](#14-shadow-mode)
15. [Digital Twin (Synthetic Data Engine)](#15-digital-twin-synthetic-data-engine)
16. [API Reference](#16-api-reference)
17. [Frontend Dashboard](#17-frontend-dashboard)
18. [Deployment](#18-deployment)
19. [Testing](#19-testing)
20. [Project Structure](#20-project-structure)
21. [Quickstart](#21-quickstart)

---

## 1. Problem Statement

Large ride-hailing and logistics platforms operating across multiple Indian cities face a silent revenue crisis: fare manipulation, ghost trips, collusion rings, and surge abuse drain 5–7% of gross revenue every year.

### The scale of the problem

- **500,000+ active drivers** across Tier-1 and Tier-2 cities
- **5.9% observed fraud rate** across all trip categories
- **₹6.87 crore annual revenue leakage** (extrapolated from pilot data)
- **Baseline detection precision: 18.7%** using rule-based systems — meaning 81.3% of flagged trips are false positives
- **Average analyst review time: 4.2 minutes per trip** at 18.7% precision
- **Effective analyst throughput: 3–4 confirmed fraud cases per hour**

### Why rules alone fail

Rule-based systems (fare > 3x expected, distance > 50 km, zone mismatch) flag too broadly. Every rule has a threshold, and fraudsters learn it. They operate just below it. Worse, legitimate edge cases (airport trips, surge pricing, long rural routes) constantly trigger false positives and erode analyst trust in the system.

The root issue is that fraud is a **multi-dimensional behavioral pattern**, not a single-variable threshold. Detecting it requires combining trip geometry, fare economics, driver history, payment behaviour, zone context, and temporal signals simultaneously.

---

## 2. Solution

Porter is a full-stack ML intelligence platform built around a two-stage XGBoost classifier. It scores every trip as it completes, routes high-confidence fraud to an analyst queue, and dispatches enforcement to your existing dispatch system — all within seconds of trip completion.

### What Porter does

| Function | Capability |
|---|---|
| **Real-time scoring** | Scores each trip within 200ms of completion using 31 features |
| **Two-stage tiers** | `action` (≥0.80 fraud probability) and `watchlist` (≥0.50) — different response per tier |
| **Analyst workflow** | Queue management, case review, bulk actions, outcome logging |
| **Enforcement dispatch** | Webhook to existing dispatch/compliance system, suppressed during shadow mode |
| **Driver intelligence** | 30-day rolling risk timeline, ring detection, peer comparison against cohort |
| **Demand forecasting** | Prophet model per zone, 24-hour horizon, surge prediction |
| **Route efficiency** | Dead mile analysis, vehicle utilisation scoring, reallocation recommendations |
| **Shadow mode** | Full platform operation with enforcement suppressed — validation without risk |
| **Digital twin** | Synthetic trip generator across 22 Indian cities, 5 fraud archetypes |
| **Audit trail** | Every action by every analyst is logged with timestamp, reason, and outcome |

### Business impact

- **88.3% action-tier precision** (threshold ≥ 0.80, top ~3.8% of trips by risk score) → analysts spend time on real fraud
- **₹6.80 net recoverable per trip** flagged (after false positive cost)
- **Projected annual recovery: ₹6.80 crore** on a 500K-driver fleet
- **4.7x improvement** in analyst confirmed-fraud throughput

---

## 3. Live Benchmarks

| Metric | Baseline (rules) | Porter XGBoost | Improvement |
|---|---|---|---|
| Action-tier precision (≥0.80) | 18.7% | 88.3% | +69.6 pp |
| Action-tier FPR (synthetic benchmark) | 81.3% | 0.53% | −80.8 pp |
| ROC-AUC | — | 0.97 | — |
| Cases per analyst hour | ~3.4 | ~16.2 | 4.7× |
| Scoring latency (p95) | — | 180ms | — |
| Annual recovery (500K fleet) | ₹1.28 cr | ₹6.80 cr | 5.3× |
| False positive cost avoided | — | ₹0.87 cr/yr | — |
| Net recoverable per trip | ₹1.15 | ₹6.80 | 5.9× |

**Threshold configuration** (ground truth: `model/weights/two_stage_config.json`):
- `action` tier: fraud probability ≥ 0.80 → immediate enforcement dispatch
- `watchlist` tier: fraud probability ≥ 0.50 → analyst queue
- `clear`: fraud probability < 0.50 → no action

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PORTER INTELLIGENCE PLATFORM                        │
└─────────────────────────────────────────────────────────────────────────────┘

  DATA SOURCES                INGESTION               PROCESSING
  ─────────────               ─────────               ──────────
  Trip webhooks   ──────────► Webhook API  ──────────► Redis Stream
  Batch CSV       ──────────► Schema mapper            porter:trips
  Live simulator  ──────────► Staging fallback         │
  City feeds      ──────────► City profiles            │
                                                        ▼
  ┌──────────────────────────────────────────── SCORING WORKER ──────────────┐
  │  XREAD porter:trips → build_feature_vector(31 features) → XGBoost score  │
  │  → tier classification → write to cases table → XACK                     │
  └───────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
  ┌──────────────────── CASE MANAGEMENT ─────────────────────────────────────┐
  │  cases table (PostgreSQL)                                                 │
  │  status: pending → under_review → confirmed / cleared                    │
  │  analyst isolation: case locked to reviewing analyst                      │
  │  shadow_cases: parallel table, enforcement suppressed                     │
  └───────────────────────────────────────────────────────────────────────────┘
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
  │  ENFORCEMENT │   │  ANALYTICS   │   │  INTELLIGENCE    │
  │  DISPATCH    │   │  ENGINE      │   │  ENGINE          │
  │  Webhook     │   │  KPI board   │   │  Driver risk     │
  │  suppressed  │   │  ROI calc    │   │  Ring detection  │
  │  in shadow   │   │  Board pack  │   │  Peer compare    │
  └──────────────┘   └──────────────┘   └──────────────────┘

  SECURITY LAYER (all paths)
  ─────────────────────────
  JWT HS256 auth → RBAC (admin / ops_analyst / city_ops / read_only)
  AES-256-GCM PII encryption → Prometheus metrics → Rate limiting

  FRONTEND
  ────────
  React + Vite (Netlify) → Vite proxy → FastAPI (Render / AWS ECS Fargate)
  Analyst dashboard / KPI panel / Trip scorer / ROI calculator
```

**Request flow:**
1. Trip data arrives via webhook, batch CSV, or live Redis simulator
2. Schema mapper normalises city-specific field names to Porter's canonical schema
3. Event written to `porter:trips` Redis Stream
4. Scoring worker reads stream, builds 31-feature vector, scores with XGBoost
5. Score → tier → case written to PostgreSQL `cases` table
6. `action` tier cases trigger enforcement dispatch webhook
7. Analysts review cases in the dashboard, log outcomes
8. Reviewed outcomes feed back into KPI board, reports, and ROI calculations

---

## 5. Tech Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **API framework** | FastAPI | 0.115 | Async REST API, OpenAPI docs |
| **ML model** | XGBoost | 2.0 | Two-stage fraud classifier |
| **Forecasting** | Prophet | 1.1 | Zone-level demand forecasting |
| **Feature engineering** | scikit-learn, pandas, numpy | latest | Feature preprocessing, transformations |
| **Database** | PostgreSQL 16 | — | Cases, audit log, driver profiles |
| **Cache / streams** | Redis 7 | — | Real-time trip stream, rate limiting |
| **Async ORM** | SQLAlchemy 2 + asyncpg | — | Async DB access |
| **Auth** | PyJWT | — | HS256 JWT token issuance and validation |
| **Encryption** | Python cryptography | — | AES-256-GCM PII field encryption |
| **PDF generation** | reportlab | — | Board packs, legal close packet |
| **Rate limiting** | slowapi | — | Per-endpoint request throttling |
| **Frontend** | React 18 + Vite | — | Analyst dashboard |
| **Maps** | Leaflet + react-leaflet | — | Trip route visualisation |
| **Observability** | Prometheus + Grafana | — | Request latency, model metrics |
| **Infrastructure** | AWS ECS Fargate + RDS + ElastiCache | — | Production hosting |
| **Frontend hosting** | Netlify | — | React dashboard CDN |
| **Containerisation** | Docker + Docker Compose | — | Local dev and CI |
| **Task scheduling** | APScheduler | — | Periodic KPI refresh, simulator ticks |
| **Dependency injection** | FastAPI Depends | — | Auth, DB session, rate limiter |

---

## 6. Fraud Detection Model

### Model type

**XGBoost binary classifier** — gradient-boosted decision trees. Chosen over neural networks for:
- Explainability (SHAP feature importance directly from tree splits)
- Tabular data performance (XGBoost consistently outperforms deep learning on structured trip data)
- Training speed and auditability
- Robust handling of missing values and mixed-type features

### Training configuration

| Parameter | Value |
|---|---|
| `n_estimators` | 400 |
| `max_depth` | 6 |
| `learning_rate` | 0.08 |
| `subsample` | 0.8 |
| `colsample_bytree` | 0.8 |
| `min_child_weight` | 5 |
| `scale_pos_weight` | 16 (class imbalance correction) |
| `eval_metric` | `aucpr` (area under precision-recall curve) |
| `early_stopping_rounds` | 30 |

The `scale_pos_weight` of 16 reflects the approximately 1:16 fraud:clean ratio in training data. Without this correction, the model would learn to output low probabilities uniformly to minimise log-loss.

### Two-stage tier system

```
XGBoost output: fraud_probability ∈ [0.0, 1.0]
                        │
           ┌────────────┼────────────┐
           │            │            │
         ≥ 0.80       ≥ 0.50      < 0.50
           │            │            │
        ACTION      WATCHLIST      CLEAR
     Enforcement   Analyst queue   No action
      dispatch     (manual review) logged
```

- **Action tier (≥0.80):** High confidence. Enforcement webhook fires immediately. Analyst can review post-facto.
- **Watchlist tier (≥0.50, <0.80):** Ambiguous. Queued for analyst review. No automatic action.
- **Clear (<0.50):** Logged as clean. No queue entry created.

The threshold values are configured in `model/weights/two_stage_config.json` (ground truth). The current defaults (0.50 / 0.80) were calibrated on the synthetic benchmark to maximise confirmed-fraud throughput while keeping FPR below 1%.

### Model files

| File | Purpose |
|---|---|
| `model/fraud_model.ubj` | Trained XGBoost model (binary format) |
| `model/features.py` | Canonical `FEATURE_COLUMNS` list (31 features) |
| `model/query.py` | Model loading, scoring, feature validation |
| `ml/stateless_scorer.py` | Stateless `score_trip()` for Redis Stream worker |

### Inference path

1. `score_trip(trip_dict)` called from Redis Stream consumer
2. `build_feature_vector(trip_dict)` maps raw trip fields to all 31 FEATURE_COLUMNS
3. Vector assembled as `pd.DataFrame` with exact column order
4. `model.predict_proba(df)[0][1]` → fraud probability
5. Tier assigned, case written to DB

---

## 7. Feature Engineering — 31 Features

All 31 features are defined in `model/features.py` as `FEATURE_COLUMNS`. The feature vector is built in `ml/stateless_scorer.py::build_feature_vector()`.

### Trip Economics (7 features)

| Feature | Description |
|---|---|
| `declared_distance_km` | Declared trip distance |
| `declared_duration_min` | Declared trip duration |
| `fare_inr` | Total fare in Indian Rupees |
| `surge_multiplier` | Surge pricing factor applied |
| `fare_to_expected_ratio` | Actual fare divided by zone-expected fare |
| `fare_per_km` | Per-kilometre fare rate |
| `zone_demand_at_time` | Demand index in pickup zone at trip time |

### Trip Geometry (3 features)

| Feature | Description |
|---|---|
| `pickup_dropoff_haversine_km` | Straight-line distance between pickup and dropoff |
| `distance_vs_haversine_ratio` | Declared distance divided by haversine (detour ratio) |
| `distance_time_ratio` | km per minute — implausibly high values flag ghost trips |

### Temporal Signals (6 features)

| Feature | Description |
|---|---|
| `hour_of_day` | 0–23, captures time-of-day fraud patterns |
| `day_of_week` | 0–6, Mon=0 |
| `is_night` | 1 if 22:00–05:00 |
| `is_peak_hour` | 1 if 07:00–10:00 or 17:00–21:00 |
| `is_friday` | 1 if Friday (high surge abuse day) |
| `is_late_month` | 1 if day ≥ 25 (incentive-window abuse) |

### Payment Signals (2 features)

| Feature | Description |
|---|---|
| `payment_is_cash` | 1 if cash payment (harder to trace, higher fraud rate) |
| `payment_is_credit` | 1 if credit card |

### Driver History (8 features)

| Feature | Description |
|---|---|
| `driver_cancellation_velocity_1hr` | Cancellations in last 1 hour |
| `driver_cancel_rate_rolling_7d` | 7-day rolling cancellation rate |
| `driver_dispute_rate_rolling_14d` | 14-day rolling dispute rate |
| `driver_trips_last_24hr` | Trip count in last 24 hours |
| `driver_cash_trip_ratio_7d` | Fraction of cash trips in last 7 days |
| `driver_account_age_days` | Days since driver account creation |
| `driver_rating` | Driver rating (1.0–5.0) |
| `driver_lifetime_trips` | Total completed trips (career) |

### Driver Classification (2 features)

| Feature | Description |
|---|---|
| `driver_verification_encoded` | Verification tier (0=unverified, 1=basic, 2=full) |
| `driver_payment_type_encoded` | Payment type preference encoding |

### Zone and Trip Context (3 features)

| Feature | Description |
|---|---|
| `zone_fraud_rate_rolling_7d` | Fraud rate in pickup zone over last 7 days |
| `same_zone_trip` | 1 if pickup and dropoff in same zone (short-haul indicator) |
| `is_cancelled` | 1 if trip was cancelled (ghost trip pattern) |

### Top 7 features by importance (SHAP, pilot dataset)

1. `fare_to_expected_ratio` — single strongest signal; legitimate trips rarely exceed 2× expected
2. `driver_cancellation_velocity_1hr` — burst cancellations correlate with incentive farming
3. `distance_vs_haversine_ratio` — extreme detour ratios flag route manipulation
4. `zone_fraud_rate_rolling_7d` — zone context amplifies individual trip signals
5. `driver_cash_trip_ratio_7d` — cash-heavy patterns tied to ghost trip rings
6. `driver_dispute_rate_rolling_14d` — sustained disputes indicate systematic fraud
7. `is_cancelled` — cancelled trips with fare logged are a known fraud pattern

---

## 8. Ingestion Pipeline

Porter accepts trip data through three entry points, all normalised through the same schema mapper before entering the Redis Stream.

### Entry points

| Source | Endpoint | Use case |
|---|---|---|
| Webhook (live) | `POST /ingest/webhook` | Real-time trip completion events from city systems |
| Batch CSV | `POST /ingest/batch` | Bulk historical upload (up to 10,000 trips) |
| Live simulator | Internal scheduler | Synthetic stream for demos and validation |

### Schema mapping

Different city systems use different field names. The schema mapper normalises all inputs:

```
city system field           →   Porter canonical field
─────────────────────────────────────────────────────
"trip_dist" / "distance"    →   declared_distance_km
"amt" / "total_fare"        →   fare_inr
"driver_id" / "drv_id"      →   driver_id
"pickup_lat" / "lat1"       →   pickup_lat
...
```

Schema maps are stored in `ingestion/schema_map.default.json` and city-specific overrides in `ingestion/city_profiles.py`.

If a required field is missing after mapping, the event is written to the **staging table** (`ingestion_staging`) with `status='pending'` for manual review or retry.

### Redis Stream pipeline

```
Ingest API → XADD porter:trips <trip_fields>
                                │
                                ▼
                    Scoring worker (XREAD blocking)
                    │  build_feature_vector()
                    │  xgb_model.predict_proba()
                    │  write case to PostgreSQL
                    └► XACK porter:trips scoring-workers <message-id>
```

At-least-once delivery: the worker only ACKs after the case is written to the database. If the worker crashes mid-processing, the message remains in the pending-entries list and will be redelivered on restart.

### Live simulator

`ingestion/live_simulator.py` generates a continuous stream of synthetic trips at a configurable rate. Used for:
- Demo environments (dashboard live without real city data)
- Load testing
- Shadow mode validation

Simulator trips are tagged with `source: synthetic` and use the city profile system to generate geographically plausible coordinates, fare ranges, and driver profiles.

---

## 9. Case Lifecycle

Every trip that scores above the watchlist threshold (≥0.50) becomes a **case** in the PostgreSQL `cases` table.

### Status machine

```
  PENDING  ──► UNDER_REVIEW ──► CONFIRMED  ──► (enforcement dispatched)
                    │
                    └──────────► CLEARED    ──► (no action, logged)
```

- **PENDING:** Case created automatically by scoring worker. No analyst assigned.
- **UNDER_REVIEW:** Analyst claims the case. Case is now locked to that analyst (isolation prevents concurrent edits).
- **CONFIRMED:** Analyst confirms fraud. Enforcement dispatch fires (unless shadow mode active).
- **CLEARED:** Analyst determines false positive. No action. Logged for model feedback.

### Analyst isolation

Only one analyst can hold a case in `UNDER_REVIEW` at a time. The `reviewed_by` field is set atomically with the status transition. Attempting to claim an already-claimed case returns HTTP 409 Conflict.

### Enforcement dispatch

When a case is confirmed (or when a trip scores `action` tier at ingest time), Porter sends a webhook to the operator's dispatch system:

```json
{
  "driver_id": "DRV_12345",
  "trip_id": "TRIP_98765",
  "fraud_probability": 0.9847,
  "tier": "action",
  "top_signals": [
    "fare_to_expected_ratio: 4.2 (threshold 2.0)",
    "driver_cancellation_velocity_1hr: 8 (threshold 3)",
    "zone_fraud_rate_rolling_7d: 0.31 (elevated)"
  ],
  "action": "suspend_driver"
}
```

The dispatch URL is configured via `PORTER_DISPATCH_URL` environment variable. If not set, dispatch is logged locally.

### Shadow cases

In shadow mode, all cases are written to `shadow_cases` instead of `cases`. Enforcement webhook is suppressed. `live_write_suppressed: true` is set on the response. This lets operators validate Porter's decisions against their own ground truth before going live.

---

## 10. Driver Intelligence

The driver intelligence module builds a comprehensive risk profile for each driver, surfaced via the `/intelligence/driver/{driver_id}` endpoint.

### Components

**30-day risk timeline**
Plots fraud score over the last 30 days, smoothed with a 3-day rolling average. Enables detection of gradual drift vs. sudden spike patterns.

**Ring detection**
Identifies clusters of drivers operating together:
- Shared pickup/dropoff coordinates (within 200m tolerance)
- Synchronized trip patterns (trips within 5-minute windows)
- Payment method correlation (shared cash accounts)
- Zone co-occurrence above expected chance level

**Peer comparison**
Compares a driver's metrics against their cohort (same city, same vehicle class, similar tenure):
- `dispute_rate_vs_cohort`: percentile rank among peers
- `cash_trip_ratio_vs_cohort`: how far above/below peer average
- `cancellation_velocity_vs_cohort`: outlier detection

**Signals tracked**
- Cancellation velocity (1hr, 24hr, 7-day rolling)
- Dispute rate (14-day, 30-day rolling)
- Cash trip ratio (7-day rolling)
- Ghost trip indicators (cancelled trips with fare logged)
- Zone concentration (operating exclusively in high-fraud zones)

---

## 11. Demand Forecasting

Porter uses Facebook Prophet to forecast demand per zone with a 24-hour horizon. This feeds the surge prediction and route efficiency modules.

### Model per zone

A separate Prophet model is trained for each city zone. Zones with insufficient history fall back to a city-level aggregate model.

**Seasonality components:**
- Daily (rush hours, night lows)
- Weekly (weekday vs. weekend patterns)
- Custom (payday spikes on 1st and 15th of month)

### Surge prediction

The system predicts surge multipliers by combining:
1. Demand forecast (Prophet output)
2. Active driver count at time T (from recent trip completions)
3. Historical surge ratios for the zone × hour combination

Surge alerts are triggered when predicted demand/supply ratio exceeds 2.5×.

### Outputs

- `GET /kpi/forecast` — next 24-hour demand forecast per zone
- `GET /kpi/surge-alerts` — current active and predicted surge zones
- Used by route efficiency engine to recommend pre-positioning

---

## 12. Route Efficiency

The route efficiency module analyses fleet utilisation patterns to identify and quantify inefficiency.

### Dead mile analysis

"Dead miles" are kilometres driven without a passenger. High dead-mile ratios indicate:
- Poor pre-positioning (drivers clustered in low-demand zones)
- Systematic cancellations (driver drives to pickup, cancels)
- Zone avoidance behaviours

### Vehicle utilisation scoring

Each driver receives a utilisation score (0–100):
- Trips per hour online
- Fare-per-kilometre vs. zone average
- Peak hour availability
- Dead mile ratio

### Reallocation recommendations

The engine produces `GET /route/reallocation` recommendations — a list of zones currently over/under-supplied relative to forecast demand, with suggested driver counts to move.

---

## 13. Security Architecture

### Authentication

**JWT HS256** tokens issued at login (`POST /auth/login`). Token payload:
```json
{
  "sub": "analyst_001",
  "role": "ops_analyst",
  "exp": 1735689600
}
```

Token secret: `SECRET_KEY` env var (minimum 32 characters, validated at startup).

### Role-based access control (4 roles)

| Role | Permissions | Typical user |
|---|---|---|
| `admin` | All — including `read:all`, `write:cases`, `manage:users` | Platform owner |
| `ops_analyst` | `read:cases`, `write:cases`, `read:reports` | Fraud analyst |
| `city_ops` | `read:cases`, `read:reports` (own city only) | City operations manager |
| `read_only` | `read:reports` | Executive, auditor |

`require_permission("perm")` is a FastAPI dependency injected on protected routes. Attempting to call a route without the required permission returns HTTP 403.

### PII encryption

All Personally Identifiable Information stored in the database is encrypted at rest using **AES-256-GCM**:
- `driver_name`
- `driver_phone`
- `passenger_name`
- `passenger_phone`

Encryption key: `ENCRYPTION_KEY` env var. The `security/encryption.py` module provides `encrypt_field()` and `decrypt_field()` helpers used by all model read/write paths.

### Rate limiting

slowapi rate limits are applied per endpoint:
- `/auth/login`: 10 requests/minute (brute-force protection)
- `/fraud/score`: 100 requests/minute
- `/ingest/webhook`: 500 requests/minute (bulk ingest paths)

### Security headers

All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

### CORS

Allowed origins are loaded from `security/settings.py::get_allowed_origins()`, which reads `ALLOWED_ORIGINS` env var (comma-separated list). Defaults to `http://localhost:5173` for local development.

---

## 14. Shadow Mode

Shadow mode is Porter's safety mechanism for initial deployment. The platform runs fully — scoring, casing, intelligence — but enforcement is suppressed.

### What changes in shadow mode

| Component | Normal mode | Shadow mode |
|---|---|---|
| Scoring | Active | Active (unchanged) |
| Case creation | `cases` table | `shadow_cases` table |
| Enforcement dispatch | Fires webhook | Suppressed — logged only |
| Analyst review | Full workflow | Read-only view available |
| KPI reporting | Live reviewed data | Shadow data (separate) |

### Activation

```bash
POST /shadow/activate
Authorization: Bearer <admin_token>
```

This sets `app_state["shadow_mode"] = True`. The `/health` endpoint reports `shadow_mode: true` so operators can confirm the state.

### Validation workflow

Recommended shadow mode process:
1. Activate shadow mode
2. Run ingestion for 30 days (real or synthetic)
3. Compare Porter's decisions against manual review outcomes
4. Once precision target (≥70% confirmed cases) is reached, deactivate shadow mode
5. Go live with enforcement

The acceptance criteria for deactivation are documented in `docs/handover/acceptance-criteria.md`.

---

## 15. Digital Twin (Synthetic Data Engine)

The digital twin is a complete synthetic trip generator that produces realistic fraud and clean trips for any of 22 Indian cities.

### Coverage

**22 cities:** Mumbai, Delhi, Bangalore, Chennai, Hyderabad, Pune, Kolkata, Ahmedabad, Surat, Jaipur, Lucknow, Kanpur, Nagpur, Indore, Thane, Bhopal, Visakhapatnam, Patna, Vadodara, Ghaziabad, Ludhiana, Agra.

### Fraud archetypes (5 patterns)

| Archetype | Description | Key signals |
|---|---|---|
| **Ghost trip** | Trip logged but never driven | `is_cancelled=1`, `distance_vs_haversine_ratio` near 0 |
| **Fare manipulation** | Fare charged above metered rate | `fare_to_expected_ratio` > 2.5 |
| **Surge abuse** | Fake demand spike to trigger surge | High `zone_demand_at_time`, multiple same-zone trips |
| **Incentive farming** | Collusion to hit bonus thresholds | `driver_cancellation_velocity_1hr` burst, `is_late_month=1` |
| **Ring operation** | Coordinated multi-driver fraud | Shared zone, synchronized timing, correlated cash ratio |

### Usage

The generator is accessed via `generator/config.py`. The live simulator (`ingestion/live_simulator.py`) uses it to produce a continuous stream of synthetic trips for demo and validation environments.

A sample dataset of 10 trips is committed at `data/samples/porter_sample_10_trips.csv` for test fixture use.

---

## 16. API Reference

All endpoints require authentication (`Authorization: Bearer <token>`) unless noted. Full interactive documentation available at `/docs` after startup.

### Core

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Platform health, DB/Redis status, runtime mode |
| `GET` | `/metrics` | None | Prometheus metrics scrape |
| `POST` | `/webhooks/dispatch/test` | None | Test downstream dispatch connectivity |

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | None | Issue JWT token |
| `GET` | `/auth/me` | Any | Current user info |

### Fraud Scoring

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/fraud/score` | `ops_analyst` | Score a single trip |
| `POST` | `/fraud/score-batch` | `ops_analyst` | Score up to 100 trips |
| `GET` | `/fraud/evaluate` | `ops_analyst` | Score all trips in loaded dataset |

### Cases

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/cases/` | `ops_analyst` | List cases (paginated, filterable by tier/status) |
| `POST` | `/cases/{id}/review` | `ops_analyst` | Claim case for review |
| `POST` | `/cases/{id}/confirm` | `ops_analyst` | Confirm fraud (triggers dispatch) |
| `POST` | `/cases/{id}/clear` | `ops_analyst` | Clear case as false positive |
| `POST` | `/cases/bulk-action` | `ops_analyst` | Bulk confirm/clear up to 50 cases |

### Driver Intelligence

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/intelligence/driver/{driver_id}` | `ops_analyst` | Full driver risk profile |
| `GET` | `/intelligence/rings` | `admin` | Detected collaboration rings |
| `GET` | `/intelligence/top-risk` | `ops_analyst` | Top 20 highest-risk drivers |

### Reports

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/reports/board-pack` | `admin` | PDF board pack (reviewed case summary) |
| `GET` | `/reports/summary` | `ops_analyst` | Operational summary (reviewed cases) |

### KPI

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/kpi/summary` | `ops_analyst` | Live KPI summary from reviewed cases |
| `GET` | `/kpi/trend` | `ops_analyst` | 30-day trend data |

### ROI

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/roi/calculate` | `read_only` | ROI and payback projection |

### Route Efficiency

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/route/efficiency` | `city_ops` | Fleet efficiency summary |
| `GET` | `/route/reallocation` | `city_ops` | Driver reallocation recommendations |

### Natural Language Query

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/query` | `ops_analyst` | Ask a natural-language question about operations |

### Ingestion

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/ingest/webhook` | `admin` | Single trip event (live webhook) |
| `POST` | `/ingest/batch` | `admin` | Batch CSV upload (up to 10,000 trips) |
| `GET` | `/ingest/queue-status` | `admin` | Redis Stream queue depth and lag |

### Shadow Mode

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/shadow/activate` | `admin` | Activate shadow mode |
| `POST` | `/shadow/deactivate` | `admin` | Deactivate shadow mode |
| `GET` | `/shadow/status` | `admin` | Current shadow mode state |

### Demo Controls

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/demo/preset/{name}` | `admin` | Load a named demo preset |
| `POST` | `/demo/reset` | `admin` | Reset all demo state |

### Legal

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/legal/download` | `admin` | ZIP of full buyer close packet (4 PDFs) |
| `GET` | `/legal/download/nda` | `admin` | NDA PDF |
| `GET` | `/legal/download/commercial-schedule` | `admin` | Commercial schedule PDF |
| `GET` | `/legal/download/acceptance-criteria` | `admin` | Acceptance criteria PDF |
| `GET` | `/legal/download/support-scope` | `admin` | Deployment and support scope PDF |

---

## 17. Frontend Dashboard

The React dashboard (`dashboard-ui/`) is deployed to Netlify. It communicates with the FastAPI backend through a Netlify proxy (configured in `netlify.toml`) to avoid CORS issues in production.

### Pages

| Page | Route | Purpose |
|---|---|---|
| Dashboard | `/` | KPI overview, live case feed, system status |
| Analyst | `/analyst` | Case queue, review workflow, bulk actions |

### Components

| Component | File | Purpose |
|---|---|---|
| `KPIPanel` | `components/KPIPanel.jsx` | Live metrics — precision, recovery, case volume |
| `QueryPanel` | `components/QueryPanel.jsx` | Natural-language query interface |
| `TripScorer` | `components/TripScorer.jsx` | Manual trip scoring form |
| `ROICalculator` | `components/ROICalculator.jsx` | Interactive ROI projection tool |

### API communication

All API calls use native `fetch()` — no Axios. Requests are routed through the Netlify proxy to the backend API URL configured in `VITE_API_BASE_URL`.

### Local development

```bash
cd dashboard-ui
npm install
npm run dev   # starts on http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`.

---

## 18. Deployment

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing secret (≥32 chars) |
| `ENCRYPTION_KEY` | Yes | AES-256-GCM PII encryption key |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `PORTER_DISPATCH_URL` | No | Enforcement webhook URL |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins |
| `RUNTIME_MODE` | No | `demo` / `shadow` / `prod` (default: `prod`) |

Copy `.env.example` to `.env` and fill in values.

### Docker Compose (local / staging)

```bash
docker compose up --build
```

Services started:
- `api` — FastAPI on port 8000
- `db` — PostgreSQL on port 5432
- `redis` — Redis on port 6379
- `worker` — Redis Stream scoring worker

### AWS ECS Fargate (production)

```bash
cd infrastructure/aws
./setup.sh      # one-time: ECR repo, ECS cluster, RDS, ElastiCache
./deploy.sh     # build image, push to ECR, update ECS service
```

The ECS task definition is in `infrastructure/aws/ecs-task-definition.json`. The API container runs on 2 vCPU / 4GB RAM. Auto-scaling is configured for 1–10 tasks based on CPU utilisation.

### Database initialisation

```bash
# Apply schema
alembic upgrade head

# Or use the direct DDL
psql $DATABASE_URL < database/schema.sql
```

### Health check

```bash
curl https://your-api-domain.com/health
```

Expected response:
```json
{
  "status": "ok",
  "model_loaded": true,
  "database": "ok",
  "redis": "ok",
  "shadow_mode": false,
  "version": "1.0.0"
}
```

---

## 19. Testing

**63 tests across 18 test files.** All tests pass on a clean checkout with the test database and Redis running.

```bash
pytest tests/ -v
```

### Test files

| File | Tests | Coverage |
|---|---|---|
| `test_auth.py` | Auth endpoints, JWT issuance, RBAC enforcement |
| `test_case_workflow_api.py` | Full case lifecycle (pending → confirmed/cleared) |
| `test_demo_api.py` | Demo preset and reset endpoints |
| `test_enforcement.py` | Dispatch webhook integration |
| `test_health_contract.py` | `/health` response schema contract |
| `test_ingestion_api.py` | Webhook, batch CSV, sample file upload |
| `test_ingestion_queue.py` | Redis Stream XADD/XREAD/XACK cycle |
| `test_legal_download.py` | `/legal/download` ZIP + individual PDFs |
| `test_live_kpi_metrics.py` | KPI calculation from reviewed cases |
| `test_live_simulator.py` | Simulator trip generation and stream write |
| `test_reports_board_pack.py` | PDF board pack generation |
| `test_roi_api.py` | ROI calculation with various fleet sizes |
| `test_schema_mapper.py` | City-specific field name normalisation |
| `test_security.py` | Encryption, RBAC boundaries, token validation |
| `test_shadow_api.py` | Shadow mode activation/deactivation API |
| `test_shadow_mode.py` | Shadow case routing, enforcement suppression |

### Test configuration

Tests use the fixtures defined in `tests/conftest.py`:
- `security_env` — sets `SECRET_KEY` and `ENCRYPTION_KEY` env vars for tests requiring auth
- Database tests use a separate test database (configured via `DATABASE_URL` env var)

---

## 20. Project Structure

```
Porter/
├── api/
│   ├── main.py                    # FastAPI app, middleware, router registration
│   ├── inference.py               # Core scoring, batch evaluation endpoints
│   ├── schemas.py                 # Pydantic request/response models
│   ├── state.py                   # App startup state, lifespan handler
│   ├── limiting.py                # Rate limiter configuration (slowapi)
│   └── routes/
│       ├── auth.py                # Login, token, /me
│       ├── cases.py               # Case management and review workflow
│       ├── demo.py                # Demo control endpoints
│       ├── driver_intelligence.py # Driver risk profiles, ring detection
│       ├── legal.py               # Close packet PDF download endpoints
│       ├── live_kpi.py            # Live KPI from reviewed cases
│       ├── query.py               # Natural-language query endpoint
│       ├── reports.py             # Board pack PDF generation
│       ├── roi.py                 # ROI and payback calculations
│       ├── route_efficiency.py    # Fleet efficiency and reallocation
│       └── shadow.py              # Shadow mode control endpoints
├── auth/
│   ├── config.py                  # Auth configuration constants
│   ├── dependencies.py            # get_current_user, require_permission
│   └── jwt.py                     # Token issuance and validation
├── database/
│   ├── connection.py              # AsyncSessionLocal, engine setup
│   ├── models.py                  # SQLAlchemy ORM models
│   ├── redis_client.py            # Redis connection and ping
│   └── case_store.py              # Case read/write helpers
├── enforcement/
│   └── dispatch.py                # Enforcement webhook client
├── generator/
│   └── config.py                  # Synthetic data config, API metadata
├── ingestion/
│   ├── webhook.py                 # Ingest router (webhook, batch)
│   ├── streams.py                 # Redis Stream producer/consumer
│   ├── live_simulator.py          # Continuous synthetic trip generator
│   ├── schema_mapper.py           # Field name normalisation
│   ├── schema_map.default.json    # Default field mappings
│   ├── city_profiles.py           # Per-city trip parameter profiles
│   └── staging.py                 # Staging table write for incomplete events
├── ml/
│   └── stateless_scorer.py        # Stateless score_trip() for stream worker
├── model/
│   ├── features.py                # FEATURE_COLUMNS (31 features)
│   ├── fraud_model.ubj            # Trained XGBoost model
│   └── query.py                   # Model loading and predict_proba wrapper
├── security/
│   ├── encryption.py              # AES-256-GCM encrypt/decrypt
│   └── settings.py                # CORS origin loader
├── dashboard-ui/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx      # Main KPI and case overview
│   │   │   └── Analyst.jsx        # Case review workflow
│   │   └── components/
│   │       ├── KPIPanel.jsx       # Live metrics display
│   │       ├── QueryPanel.jsx     # NL query interface
│   │       ├── TripScorer.jsx     # Manual scoring form
│   │       └── ROICalculator.jsx  # ROI projection tool
│   ├── .env.production            # VITE_API_BASE_URL (no secrets)
│   └── netlify.toml               # Netlify proxy and build config
├── tests/
│   ├── conftest.py                # Test fixtures and env setup
│   └── test_*.py                  # 63 tests across 16 test files
├── data/
│   └── samples/
│       └── porter_sample_10_trips.csv  # Test fixture (10 sample trips)
├── docs/
│   └── handover/
│       ├── repo-access-and-handover.md
│       ├── acceptance-criteria.md
│       └── deployment-and-support-scope.md
├── infrastructure/
│   └── aws/
│       ├── setup.sh               # One-time AWS resource provisioning
│       ├── deploy.sh              # ECS deploy script
│       └── ecs-task-definition.json
├── runtime_config.py              # Data provenance description
├── requirements.txt               # Python dependencies
├── docker-compose.yml             # Local dev stack
├── netlify.toml                   # Netlify deploy and proxy config
└── .env.example                   # Environment variable template
```

---

## 21. Quickstart

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Redis 7+
- Node.js 18+ (for dashboard)

### 1. Clone and set up environment

```bash
git clone https://github.com/Arnav2580/Porter.git
cd Porter
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set SECRET_KEY, ENCRYPTION_KEY, DATABASE_URL, REDIS_URL
```

### 2. Start infrastructure

```bash
docker compose up db redis -d
```

Or use your own PostgreSQL and Redis instances — update `DATABASE_URL` and `REDIS_URL` in `.env`.

### 3. Start the API

```bash
uvicorn api.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
Health check: [http://localhost:8000/health](http://localhost:8000/health)

### 4. Get a token

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

### 5. Score a trip

```bash
curl -X POST http://localhost:8000/fraud/score \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": "TRIP_001",
    "driver_id": "DRV_001",
    "fare_inr": 850,
    "declared_distance_km": 12.5,
    "declared_duration_min": 28,
    "pickup_lat": 19.076,
    "pickup_lon": 72.877,
    "dropoff_lat": 19.113,
    "dropoff_lon": 72.856,
    "payment_type": "cash"
  }'
```

Response:
```json
{
  "trip_id": "TRIP_001",
  "fraud_probability": 0.0334,
  "tier": "clear",
  "top_signals": [],
  "case_id": null
}
```

### 6. Start the dashboard (optional)

```bash
cd dashboard-ui
npm install
npm run dev
```

Dashboard: [http://localhost:5173](http://localhost:5173)

---

## Handover Package

For buyers and enterprise operators, a complete handover package is available:

- `docs/handover/repo-access-and-handover.md` — Repository access transfer and onboarding
- `docs/handover/acceptance-criteria.md` — Go-live acceptance criteria and verification
- `docs/handover/deployment-and-support-scope.md` — 90-day deployment plan and support terms

Download the full close packet (NDA, Commercial Schedule, Acceptance Criteria, Support Scope) via `GET /legal/download` (admin token required).

---

*Porter Intelligence Platform — built for operators who need answers, not dashboards.*
