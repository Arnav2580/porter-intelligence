# Porter Intelligence Platform

**Trip-level fraud scoring, case workflow, driver intelligence, route efficiency, demand forecasting, and operating analytics for logistics networks.**

Porter Intelligence is a full-stack ML platform built around FastAPI, React/Vite, PostgreSQL, Redis Streams, and an XGBoost classifier. It ingests completed trip events, normalizes them into a canonical trip schema, builds a 44-feature behavioral vector, scores fraud probability, classifies each trip into a two-stage tier, persists reviewable cases, and exposes dashboard, analyst, KPI, report, ROI, legal, shadow-mode, and intelligence endpoints.

This README is the current source of truth for the repository as of **2026-04-28**. It intentionally replaces older README text that referred to a 31-feature model, `SECRET_KEY`, `ALLOWED_ORIGINS`, `/auth/login`, `/ingest/webhook`, `/route/reallocation`, `fraud_model.ubj`, fixed ngrok rewrites, or unregistered route shim modules. Those names are stale for the current codebase.

Detailed companion docs:

- [documentation.md](documentation.md) - deeper engineering documentation.
- [docs/architecture-map.md](docs/architecture-map.md) - repository map and Mermaid diagrams.
- [docs/architecture-map.mmd](docs/architecture-map.mmd) - readable Mermaid AI / Mermaid Live control-room diagram.
- [_archive/unused_modules/api_route_shims/README.md](_archive/unused_modules/api_route_shims/README.md) - archived route shims that are no longer part of the live API surface.

---

## Table Of Contents

1. [Current Verification Status](#1-current-verification-status)
2. [Problem Statement](#2-problem-statement)
3. [What The Platform Does](#3-what-the-platform-does)
4. [Architecture Overview](#4-architecture-overview)
5. [Runtime Flow](#5-runtime-flow)
6. [Tech Stack](#6-tech-stack)
7. [Fraud Detection Model](#7-fraud-detection-model)
8. [Feature Engineering - 44 Features](#8-feature-engineering---44-features)
9. [Data Files And Data Provenance](#9-data-files-and-data-provenance)
10. [Ingestion Pipeline](#10-ingestion-pipeline)
11. [Case Lifecycle](#11-case-lifecycle)
12. [Driver Intelligence](#12-driver-intelligence)
13. [Demand Forecasting](#13-demand-forecasting)
14. [Route Efficiency](#14-route-efficiency)
15. [Security Architecture](#15-security-architecture)
16. [Shadow Mode](#16-shadow-mode)
17. [Digital Twin And Synthetic Data Engine](#17-digital-twin-and-synthetic-data-engine)
18. [Live API Surface](#18-live-api-surface)
19. [Frontend Dashboard](#19-frontend-dashboard)
20. [Deployment And Runtime Configuration](#20-deployment-and-runtime-configuration)
21. [Testing And Quality Gates](#21-testing-and-quality-gates)
22. [Project Structure](#22-project-structure)
23. [What Is Active vs Archived](#23-what-is-active-vs-archived)
24. [Quickstart](#24-quickstart)
25. [Production Handoff Notes](#25-production-handoff-notes)

---

## 1. Current Verification Status

The current codebase has been cleaned so that the live API surface is explicit and test-protected.

Verified locally:

```bash
./venv/bin/pytest -q
# 65 passed

./venv/bin/flake8 .
# passed

./venv/bin/bandit -q -r . -c .bandit
# passed

cd dashboard-ui
npm run lint
npm run build
# passed
```

Current production-readiness corrections already applied:

| Area | Current state |
|---|---|
| Router registration | `api/router_registry.py` is now the single live router registration surface. |
| Unused route shims | `api/routes/fraud.py`, `api/routes/kpi.py`, and `api/routes/demand.py` were not registered at runtime and have been moved to `_archive/unused_modules/api_route_shims/`. |
| Backend root route | `/` now returns API metadata. It no longer tries to serve the old empty `dashboard/` directory. The real UI lives in `dashboard-ui/`. |
| API contract | `tests/test_api_contract.py` locks the deployed route table so hidden route drift fails tests. |
| Feature contract | The model uses 44 features. The old 31-feature documentation is obsolete. |
| Threshold contract | `action >= 0.80`, `watchlist >= 0.50`, `clear < 0.50`. |
| Secrets | The code uses `JWT_SECRET_KEY` and `API_ALLOWED_ORIGINS`, not `SECRET_KEY` or `ALLOWED_ORIGINS`. |
| Frontend secrets | `dashboard-ui/.env.production` no longer contains a committed viewer password. |
| Proxy configuration | Hardcoded ngrok tunnel URLs were removed from committed deploy files. |
| Netlify proxy | `dashboard-ui/netlify/edge-functions/api-proxy.js` reads `PORTER_API_UPSTREAM` from hosting environment. |

The current test count is **65 tests across 19 backend test files**. Frontend build/lint is separate and also passes.

---

## 2. Problem Statement

Large logistics and ride-hailing platforms face revenue leakage from behavioral fraud that happens after an account has already passed identity checks. Device fingerprinting and KYC can catch fake accounts, but verified drivers can still manipulate trip behavior.

Common fraud and abuse patterns:

| Pattern | What happens | Signals |
|---|---|---|
| Cash extortion | Driver inflates fare or demands extra cash | High fare-to-expected ratio, cash payment, complaint flag |
| Ghost trip | Trip is logged but the route is impossible or not actually driven | Very low GPS pings, impossible speed, cancelled status, coordinate mismatch |
| Route deviation | Driver claims a longer route than the direct route supports | GPS distance vs haversine ratio, fare per km, duration anomalies |
| Fake cancellation | Driver accepts, waits, cancels, or cycles cancellation behavior | Cancellation velocity, cancellation rate, status signals |
| GPS spoofing | Device reports manipulated route or unusually perfect/mock location data | Mock provider, GPS accuracy, ping count, speed spikes |
| Loading fraud | Loading or waiting charges are inflated | Loading time vs goods-category norms |
| Partial delivery / POD issues | Proof of delivery or location evidence does not line up | POD photo flag, POD location match, OTP signals |

The core issue is that fraud is not a single threshold. It is a multi-dimensional behavioral pattern across trip economics, route geometry, GPS integrity, driver history, payment mode, zone history, proof-of-delivery data, OTP behavior, and time context. This repository implements that combined detection surface.

---

## 3. What The Platform Does

Porter Intelligence has five major runtime jobs:

1. **Ingest trip data** through live webhook, batch CSV, or demo simulator.
2. **Normalize schema** with `ingestion/schema_mapper.py` and `ingestion/schema_map.default.json`.
3. **Score trip fraud** through `ml/stateless_scorer.py` and XGBoost model weights.
4. **Persist and review cases** through PostgreSQL-backed case workflow.
5. **Expose operations surfaces** through dashboard, analyst UI, live KPIs, reports, ROI, legal packets, driver intelligence, route efficiency, and shadow-mode endpoints.

### Capability Matrix

| Function | Current implementation |
|---|---|
| Real-time trip scoring | `POST /fraud/score`, `ml/stateless_scorer.py`, `model/weights/xgb_fraud_model.json` |
| Stream processing | `ingestion/streams.py` consumes Redis Stream messages and scores trips |
| Two-stage tiers | `model/weights/two_stage_config.json` and `model/scoring.py` |
| Case workflow | `api/routes/cases.py`, `database/case_store.py`, `database/models.py` |
| Analyst dashboard | `dashboard-ui/src/pages/Analyst.jsx` |
| Executive dashboard | `dashboard-ui/src/pages/Dashboard.jsx` |
| Driver intelligence | `api/routes/driver_intelligence.py`, `model/driver_intelligence.py` |
| Demand forecasting | `model/demand.py`, `model/weights/demand_models.pkl`, `GET /demand/forecast/{zone_id}` |
| Route efficiency | `api/routes/route_efficiency.py`, `model/route_efficiency.py` |
| ROI calculator | `api/routes/roi.py`, `dashboard-ui/src/components/ROICalculator.jsx` |
| Legal downloads | `api/routes/legal.py`, ReportLab PDF generation |
| Natural language query | `api/routes/query.py`, `model/query.py` |
| Shadow mode | `api/routes/shadow.py`, `SHADOW_MODE` runtime flag |
| Synthetic demo feed | `ingestion/live_simulator.py`, `generator/*`, Redis stream |
| Observability | `/metrics`, `monitoring/metrics.py`, Prometheus, Grafana |
| Router contract | `api/router_registry.py`, `tests/test_api_contract.py` |

---

## 4. Architecture Overview

```text
                                      Browser
                                        |
                                        v
                          dashboard-ui React + Vite
                                        |
                                        v
                               dashboard-ui/src/utils/api.js
                                        |
                                        v
┌──────────────────────────────── FastAPI Control Plane ────────────────────────────────┐
│ api/main.py                                                                           │
│ - middleware: CORS, security headers, Prometheus latency                              │
│ - core routes: /, /health, /metrics, /webhooks/dispatch/test                          │
│ - live routers registered through api/router_registry.py                              │
└───────────────────────────────────────┬───────────────────────────────────────────────┘
                                        |
          ┌─────────────────────────────┼─────────────────────────────┐
          v                             v                             v
  Ingestion and streams          Runtime scoring                 API route modules
  ingestion/webhook.py           api/inference.py                api/routes/*
  ingestion/streams.py           ml/stateless_scorer.py          cases, auth, reports,
  Redis Stream                   model/scoring.py                legal, roi, query,
  porter:trips                   model/weights/*                 efficiency, shadow
          |                             |                             |
          v                             v                             v
      Redis cache                 XGBoost model                 PostgreSQL case store
      driver/zone                 44-feature vector             database/case_store.py
      features                    two-stage tier                database/models.py
          |                             |                             |
          └─────────────────────────────┴─────────────────────────────┘
                                        |
                                        v
                          Business output surfaces
        Fraud feed | case queue | KPI board | reports | ROI | legal | intelligence
```

### Runtime source of truth

| Concern | Source file |
|---|---|
| FastAPI app | `api/main.py` |
| Router registration | `api/router_registry.py` |
| Startup state | `api/state.py` |
| Trip scoring endpoints | `api/inference.py` |
| Case workflow | `api/routes/cases.py` |
| Auth and RBAC | `auth/*`, `api/routes/auth.py` |
| Ingestion endpoints | `ingestion/webhook.py` |
| Stream worker | `ingestion/streams.py` |
| Feature engineering | `model/features.py` |
| Runtime scorer | `ml/stateless_scorer.py` |
| Feature order | `model/weights/feature_names.json` |
| Model weights | `model/weights/xgb_fraud_model.json` |
| Tier thresholds | `model/weights/two_stage_config.json` |
| Frontend API calls | `dashboard-ui/src/utils/api.js` |
| Visual architecture map | `docs/architecture-map.mmd` |

---

## 5. Runtime Flow

### Live trip scoring flow

```text
1. Partner system sends a completed trip event.
2. POST /ingest/trip-completed receives the payload.
3. ingestion/schema_mapper.py maps partner fields to canonical schema.
4. Event is written to Redis Stream porter:trips.
5. ingestion/streams.py reads the stream.
6. ml/stateless_scorer.py builds the 44-feature vector.
7. XGBoost model returns fraud probability.
8. model/scoring.py applies two-stage tier thresholds.
9. action/watchlist cases are persisted through database/case_store.py.
10. Dashboard and analyst screens fetch the latest cases/KPIs through FastAPI.
11. Optional enforcement dispatch is controlled by enforcement/dispatch.py and shadow-mode guardrails.
```

### Direct API scoring flow

```text
Dashboard TripScorer or API client
  -> POST /fraud/score
  -> api/inference.py
  -> ml/stateless_scorer.py
  -> model weights + Redis driver/zone features
  -> tier + explanation response
```

### Case review flow

```text
Flagged case
  -> GET /cases or /cases/summary/dashboard
  -> Analyst.jsx
  -> PATCH /cases/{case_id} or POST /cases/batch-review
  -> database/case_store.py
  -> KPI/report surfaces update from reviewed outcomes
```

---

## 6. Tech Stack

The versions below reflect `requirements.txt` and `dashboard-ui/package.json`.

| Layer | Technology | Version in repo | Purpose |
|---|---|---:|---|
| API framework | FastAPI | 0.128.8 | Async REST API and OpenAPI docs |
| ASGI server | Uvicorn | 0.27.1 | Local/prod API process |
| ASGI toolkit | Starlette | 0.49.3 | FastAPI runtime base |
| Data validation | Pydantic | 2.12.5 | Request/response schemas |
| ML model | XGBoost | 2.1.4 | Binary fraud classifier |
| Data science | pandas / numpy | 2.2.1 / 1.26.4 | Feature engineering and data transforms |
| ML utilities | scikit-learn | 1.6.1 | Training/evaluation support |
| Forecasting | Prophet | 1.1.5 | Demand models |
| Database | PostgreSQL | compose uses 15-alpine | Case store and audit workflow |
| Async DB driver | asyncpg | 0.29.0 | PostgreSQL async access |
| ORM | SQLAlchemy | 2.0.28 | Async sessions and models |
| Cache / streams | Redis | compose uses 7-alpine | Stream queue, feature cache, rate state |
| Redis client | redis-py | 5.0.1 | Python Redis access |
| Auth crypto | python-jose / passlib / bcrypt | 3.5.0 / 1.7.4 / 4.0.1 | JWT and password hashing |
| PII encryption | cryptography | 46.0.7 | AES-GCM helpers |
| PDF generation | reportlab | 4.2.0 | Board packs and legal PDFs |
| Rate limiting | slowapi | 0.1.9 | Per-route limits |
| Scheduler | APScheduler | 3.10.4 | Drift and lag jobs |
| Metrics | prometheus_client | 0.20.0 | `/metrics` endpoint |
| Frontend | React | 19.2.4 | Dashboard UI |
| Frontend routing | react-router-dom | 7.13.2 | Dashboard routes |
| Build tool | Vite | 8.0.8 | Frontend dev/build |
| Maps | Leaflet | 1.9.4 | Map visualization |
| Containerization | Docker / Compose | repo config | Local/prod packaging |
| Observability | Prometheus + Grafana | repo config | Metrics and dashboards |

---

## 7. Fraud Detection Model

### Model type

The fraud model is an **XGBoost binary classifier** loaded from:

```text
model/weights/xgb_fraud_model.json
```

It predicts:

```text
fraud_probability in [0.0, 1.0]
```

XGBoost is used because the input data is structured tabular behavior: distances, fare ratios, temporal features, GPS integrity, driver profile, payment flags, and zone-level rates.

### Model source files

| File | Role |
|---|---|
| `model/features.py` | Training-time feature construction and canonical `FEATURE_COLUMNS` list. |
| `model/train.py` | Training pipeline and model artifact generation. |
| `model/evaluate.py` | Benchmark/evaluation support. |
| `model/scoring.py` | Tier logic and threshold loading. |
| `ml/stateless_scorer.py` | Runtime single-trip vector builder and scoring path. |
| `ml/feature_store.py` | Redis-backed driver/zone feature lookup and precompute helpers. |
| `model/weights/xgb_fraud_model.json` | Current XGBoost fraud model. |
| `model/weights/feature_names.json` | Runtime feature order expected by the model. |
| `model/weights/two_stage_config.json` | Action/watchlist/clear thresholds and benchmark metadata. |
| `model/weights/threshold.json` | Legacy single-threshold artifact. Not the tier source of truth. |
| `model/weights/demand_models.pkl` | Demand forecasting models. |

### Two-stage tier system

Current threshold source:

```text
model/weights/two_stage_config.json
```

```text
XGBoost fraud_probability
          |
          +-- >= 0.80 -> action
          |
          +-- >= 0.50 -> watchlist
          |
          +-- <  0.50 -> clear
```

| Tier | Condition | Operational meaning |
|---|---:|---|
| `action` | `fraud_probability >= 0.80` | High-confidence fraud. Eligible for investigation/enforcement path. |
| `watchlist` | `0.50 <= fraud_probability < 0.80` | Needs analyst review or monitoring. |
| `clear` | `fraud_probability < 0.50` | No fraud action. |

### Benchmark metadata currently stored in `two_stage_config.json`

These are synthetic benchmark / digital twin numbers, not live production claims.

| Metric | Value |
|---|---:|
| Synthetic benchmark trips | 8,000 |
| Synthetic benchmark fraud trips | 540 |
| Synthetic benchmark action precision | 96.49% |
| Synthetic benchmark action FPR | 0.13% |
| Synthetic benchmark fraud caught | 82.6% |
| Synthetic benchmark net recoverable per trip | INR 6.85 |
| Digital twin trips | 1,296,000 |
| Digital twin fraud trips | 55,146 |
| Digital twin fraud rate | 4.26% |
| Digital twin action precision | 85.26% |
| Digital twin action recall | 85.88% |
| Digital twin action FPR | 0.66% |
| Digital twin combined recall | 88.19% |

Digital twin subgroup FPR:

| Subgroup | FPR |
|---|---:|
| Surge trips | 0.59% |
| New driver trips | 0.65% |
| Night trips | 1.46% |
| Cargo trips | 2.03% |
| Overall | 0.66% |

Important disclosure: these validation numbers come from synthetic benchmark and digital twin data. Real company data validation should happen in shadow mode before enforcement is enabled.

---

## 8. Feature Engineering - 44 Features

The current model contract is **44 features**, not 31.

The three files that must stay synchronized are:

1. `model/features.py`
2. `model/weights/feature_names.json`
3. `ml/stateless_scorer.py`

If any feature is added, removed, renamed, or reordered in one of these files without updating the others, runtime scoring can silently degrade or fail.

### Full feature list

| # | Feature | Group | Meaning |
|---:|---|---|---|
| 1 | `declared_distance_km` | Trip economics/geometry | Declared trip distance. |
| 2 | `actual_trip_duration_mins` | Timing | Actual duration in minutes. Runtime also supports older `declared_duration_min` fallback. |
| 3 | `fare_inr` | Trip economics | Total fare in INR. |
| 4 | `surge_multiplier` | Trip economics | Surge multiplier applied to fare expectation. |
| 5 | `zone_demand_at_time` | Zone context | Demand index around pickup time. |
| 6 | `fare_to_expected_ratio` | Derived economics | Actual fare divided by expected fare after surge adjustment. |
| 7 | `distance_time_ratio` | Derived timing | Distance divided by duration. High values can indicate impossible speed. |
| 8 | `fare_per_km` | Derived economics | Fare density per kilometer. |
| 9 | `pickup_dropoff_haversine_km` | Geometry | Straight-line pickup-to-dropoff distance. |
| 10 | `distance_vs_haversine_ratio` | Geometry | GPS/declared distance relative to straight-line distance. |
| 11 | `gps_ping_count` | GPS integrity | Low ping count can indicate spoofing or incomplete telemetry. |
| 12 | `gps_accuracy_avg_m` | GPS integrity | Suspiciously perfect or poor GPS accuracy signal. |
| 13 | `mock_location_flag` | GPS integrity | Device mock-location indicator. |
| 14 | `gps_provider_encoded` | GPS integrity | Encoded provider: GPS/network/mock. |
| 15 | `avg_speed_kmh` | GPS/timing | Average trip speed. |
| 16 | `max_speed_kmh` | GPS/timing | Maximum recorded speed. |
| 17 | `waiting_time_mins` | Timing | Waiting time before or during trip. |
| 18 | `loading_time_mins` | Porter logistics signal | Loading time for goods movement. |
| 19 | `loading_anomaly_score` | Porter logistics signal | Loading time normalized against goods-category p75 norm. |
| 20 | `pod_photo_captured` | POD integrity | Whether proof-of-delivery photo exists. |
| 21 | `pod_location_match` | POD integrity | Whether POD location matches expected dropoff. |
| 22 | `otp_verified` | OTP integrity | Whether OTP verification succeeded. |
| 23 | `otp_attempt_count` | OTP integrity | Number of OTP attempts. |
| 24 | `hour_of_day` | Temporal | Hour from 0 to 23. |
| 25 | `day_of_week` | Temporal | Day of week. |
| 26 | `is_night` | Temporal | Night trip flag. |
| 27 | `is_peak_hour` | Temporal | Peak-hour flag. |
| 28 | `is_friday` | Temporal | Friday flag. |
| 29 | `is_late_month` | Temporal | Day-of-month incentive-window flag. |
| 30 | `payment_is_cash` | Payment | Cash payment flag. |
| 31 | `payment_is_credit` | Payment | Credit/card payment flag. |
| 32 | `driver_cancellation_velocity_1hr` | Driver behavior | Recent cancellation count in one-hour window. |
| 33 | `driver_cancel_rate_rolling_7d` | Driver behavior | Rolling 7-day cancellation rate. |
| 34 | `driver_dispute_rate_rolling_14d` | Driver behavior | Rolling 14-day dispute rate. |
| 35 | `driver_trips_last_24hr` | Driver behavior | Recent trip volume. |
| 36 | `driver_cash_trip_ratio_7d` | Driver behavior | Rolling cash-trip ratio. |
| 37 | `driver_account_age_days` | Driver profile | Account age. |
| 38 | `driver_rating` | Driver profile | Driver rating. |
| 39 | `driver_lifetime_trips` | Driver profile | Lifetime trip count. |
| 40 | `driver_verification_encoded` | Driver profile | Encoded verification state. |
| 41 | `driver_payment_type_encoded` | Driver profile | Encoded driver payment preference/account type. |
| 42 | `zone_fraud_rate_rolling_7d` | Zone context | Historical fraud rate for pickup zone. |
| 43 | `same_zone_trip` | Zone context | Pickup/dropoff zone equality flag. |
| 44 | `is_cancelled` | Status | Cancellation status flag. |

### Feature groups

| Group | Features |
|---|---|
| Trip economics | `fare_inr`, `surge_multiplier`, `fare_to_expected_ratio`, `fare_per_km`, `zone_demand_at_time` |
| Geometry | `declared_distance_km`, `pickup_dropoff_haversine_km`, `distance_vs_haversine_ratio` |
| Timing | `actual_trip_duration_mins`, `distance_time_ratio`, `waiting_time_mins`, temporal flags |
| GPS integrity | ping count, accuracy, mock location, provider, speed fields |
| POD / OTP | proof-of-delivery and OTP verification fields |
| Payment | cash and credit flags |
| Driver behavior | cancellation, dispute, trip velocity, cash-ratio history |
| Driver profile | account age, rating, lifetime trips, verification, payment type |
| Zone and status | zone fraud rate, same-zone flag, cancellation flag |

### Runtime feature construction

`ml/stateless_scorer.py::build_feature_vector()` builds the scoring vector without a pandas DataFrame. It receives:

```text
trip dict
driver_features dict
zone_features dict
feature_names list
```

Then it:

1. Computes direct trip fields.
2. Computes haversine distance.
3. Computes fare expectation using `generator.config.VEHICLE_TYPES`.
4. Computes fare/distance/time ratios.
5. Encodes payment and GPS provider fields.
6. Reads driver/zone features from Redis feature store.
7. Outputs a `numpy.float32` vector in `feature_names.json` order.

---

## 9. Data Files And Data Provenance

### Active data files in this working tree

| Path | Purpose |
|---|---|
| `data/raw/drivers_sample_1000.csv` | Driver sample used by startup loaders and model/dashboards. |
| `data/raw/trips_with_fraud_10k.csv` | Benchmark trips with fraud labels. Loaded by startup if full export is absent. |
| `data/raw/evaluation_report.json` | Evaluation/benchmark report consumed by KPI/report endpoints. |
| `data/raw/hard_negatives.csv` | Hard negative examples used to reduce false positives. |
| `data/raw/trips_sample_5k.csv` | Additional generated sample trip file. |
| `data/raw/trips_fraud_v2_sample.csv` | V2 fraud sample file. |
| `data/samples/porter_sample_10_trips.csv` | Small portable sample for demos/tests. |
| `data/masked/.gitkeep` | Placeholder for masked data exports. |
| `data/blind_test/` | Local blind-test area. Full CSVs are ignored by `.gitignore`. |

Some full-scale data files are intentionally ignored by Git:

```text
data/raw/trips_full.csv
data/raw/trips_full_fraud.csv
data/raw/drivers_full.csv
data/raw/customers_full.csv
data/masked/*.csv
data/blind_test/*.csv
```

### Startup data loading order

`api/state.py` loads trip data in this order:

```text
data/raw/trips_full_fraud.csv
data/raw/trips_with_fraud_10k.csv
```

It loads driver data in this order:

```text
data/raw/drivers_full.csv
data/raw/drivers_sample_1000.csv
```

If those files are absent, the app can still boot in a degraded/CSV-empty mode, but many dashboard surfaces will show fallback or empty-state data.

### Provenance labels

`runtime_config.py::describe_data_provenance()` describes the active data mode for `/health`:

| Runtime condition | Data provenance text |
|---|---|
| synthetic feed enabled | Synthetic demo feed persisted to PostgreSQL |
| shadow mode enabled | Shadow-mode case records with writeback disabled |
| production mode | Database-backed records from ingestion/shadow operation |
| non-production mode | Database-backed records from non-production runtime |

---

## 10. Ingestion Pipeline

### Live endpoints

The actual ingestion endpoints are:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/ingest/trip-completed` | Accept one trip completion event. |
| `POST` | `/ingest/batch-csv` | Upload batch CSV data. |
| `GET` | `/ingest/status` | Inspect ingestion/queue status. |
| `GET` | `/ingest/schema-map/default` | Return the default schema map. |

Older names such as `/ingest/webhook`, `/ingest/batch`, and `/ingest/queue-status` are not part of the current live route table.

### Pipeline shape

```text
POST /ingest/trip-completed
  -> ingestion/webhook.py
  -> ingestion/schema_mapper.py
  -> ingestion/schema_map.default.json
  -> Redis Stream porter:trips
  -> ingestion/streams.py
  -> ml/stateless_scorer.py
  -> database/case_store.py
```

### Schema mapping

`ingestion/schema_mapper.py` maps external or city-specific field names into the canonical trip schema. The default mapping lives in:

```text
ingestion/schema_map.default.json
```

If a payload cannot be normalized safely, staging/fallback code in `ingestion/staging.py` can preserve the event for later inspection instead of dropping it silently.

### Redis stream worker

The stream worker in `ingestion/streams.py` is the async processing path for queued trip events. It reads Redis Stream messages, scores them, persists flagged cases, and acknowledges after work completes.

### Live simulator

`ingestion/live_simulator.py` is for demo and non-production flows. It publishes synthetic trip events into Redis. Runtime behavior is controlled by:

```text
APP_RUNTIME_MODE
ENABLE_SYNTHETIC_FEED
PORTER_TWIN_TRIPS_PER_MIN
PORTER_TWIN_SCALE_MULTIPLIER
PORTER_TWIN_DAILY_GROWTH_PCT
PORTER_TWIN_ELAPSED_DAYS
PORTER_TWIN_ACTIVE_CITIES
```

In production mode, `runtime_config.py` forces `synthetic_feed_enabled = False` even if `ENABLE_SYNTHETIC_FEED=true` is present.

---

## 11. Case Lifecycle

Cases are created for trips that require operational attention and are stored through:

```text
database/case_store.py
database/models.py
api/routes/cases.py
```

### Live case endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/cases` | List cases. |
| `GET` | `/cases/` | List cases with trailing-slash compatibility. |
| `GET` | `/cases/summary/counts` | Count summary. |
| `GET` | `/cases/summary/dashboard` | Analyst/dashboard summary. |
| `GET` | `/cases/{case_id}` | Fetch one case. |
| `GET` | `/cases/{case_id}/history` | Fetch audit/history. |
| `PATCH` | `/cases/{case_id}` | Update case status/details. |
| `POST` | `/cases/{case_id}/driver-action` | Record driver action. |
| `POST` | `/cases/batch-review` | Bulk review cases. |

### Operational status flow

The exact persistence fields are defined in `database/models.py`, but conceptually the workflow is:

```text
flagged
  -> pending analyst review
  -> under review / reviewed
  -> confirmed or cleared
  -> audit history and KPI aggregation
```

### Enforcement dispatch

Dispatch integration lives in:

```text
enforcement/dispatch.py
```

The dispatch test route is:

```text
POST /webhooks/dispatch/test
```

The downstream URL is configured by:

```text
PORTER_DISPATCH_URL
```

If `PORTER_DISPATCH_URL` is missing, dispatch is skipped/logged rather than calling an unknown external system. Shadow mode also suppresses operational writeback.

---

## 12. Driver Intelligence

Driver intelligence surfaces are implemented by:

```text
api/routes/driver_intelligence.py
model/driver_intelligence.py
```

Live endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/intelligence/top-risk` | Top-risk drivers. |
| `GET` | `/intelligence/driver/{driver_id}` | Driver detail view. |
| `GET` | `/fraud/driver/{driver_id}` | Fraud-oriented driver scoring surface from inference module. |

Signals used across driver intelligence and scoring:

- Rolling cancellation rate.
- Rolling dispute rate.
- 24-hour trip count.
- Cash trip ratio.
- Account age.
- Rating.
- Lifetime trips.
- Verification encoding.
- Payment type encoding.
- Zone fraud rate.

The dashboard consumes top-risk driver data through `dashboard-ui/src/components/DriverIntelligence.jsx` and the analyst workspace uses the same surface to populate driver quick-picks.

---

## 13. Demand Forecasting

Demand forecasting lives in:

```text
model/demand.py
model/weights/demand_models.pkl
api/inference.py
```

Live endpoint:

```text
GET /demand/forecast/{zone_id}
```

Startup loading happens in `api/state.py`:

```text
from model.demand import load_demand_models
```

If demand models are absent, startup logs that no demand models were found and the app continues. This is intentional so the fraud/case workflow can run even if forecasting artifacts are not generated in a local environment.

---

## 14. Route Efficiency

Route efficiency lives in:

```text
api/routes/route_efficiency.py
model/route_efficiency.py
```

Live endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/efficiency/summary` | Efficiency summary. |
| `GET` | `/efficiency/reallocation` | Reallocation recommendations. |
| `GET` | `/efficiency/dead-miles` | Dead-mile analysis. |
| `GET` | `/efficiency/fleet-zones` | Fleet zone view. |
| `GET` | `/efficiency/utilisation/{zone_id}` | Zone-level utilisation. |

Startup can precompute a route-efficiency cache from loaded trip CSVs and write it to Redis with key:

```text
route-efficiency:bootstrap
```

The frontend route-efficiency panel is:

```text
dashboard-ui/src/components/ReallocationPanel.jsx
```

---

## 15. Security Architecture

### Auth flow

Current login endpoint:

```text
POST /auth/token
```

It expects `application/x-www-form-urlencoded` fields:

```text
username=<username>
password=<password>
```

It does **not** use `/auth/login` in the current codebase.

Seed users are configured in `auth/config.py`:

| Username | Env var | Role | Display name |
|---|---|---|---|
| `admin` | `PORTER_AUTH_ADMIN_PASSWORD` | `admin` | Platform Administrator |
| `ops_manager` | `PORTER_AUTH_OPS_MANAGER_PASSWORD` | `ops_manager` | Operations Manager |
| `analyst_1` | `PORTER_AUTH_ANALYST_PASSWORD` | `ops_analyst` | Fraud Analyst |
| `viewer` | `PORTER_AUTH_VIEWER_PASSWORD` | `read_only` | Dashboard Viewer |

### Roles and permissions

Source of truth:

```text
auth/models.py
```

| Role | Permissions |
|---|---|
| `admin` | `read:all`, `write:all`, `delete:all`, `manage:users` |
| `ops_manager` | `read:all`, `write:cases`, `write:driver_actions`, `read:reports` |
| `ops_analyst` | `read:cases`, `read:kpi`, `read:drivers`, `write:case_status`, `write:case_notes`, `write:driver_actions` |
| `read_only` | `read:dashboard`, `read:kpi` |

### Secrets and runtime validation

Security validation lives in:

```text
security/settings.py
```

Production mode rejects missing or placeholder values for required secrets.

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | JWT signing secret. |
| `ENCRYPTION_KEY` | PII encryption key. |
| `WEBHOOK_SECRET` | Webhook signature verification secret. |
| `API_ALLOWED_ORIGINS` | CORS allowed origins. |
| `PORTER_AUTH_ADMIN_PASSWORD` | Admin seed password. |
| `PORTER_AUTH_OPS_MANAGER_PASSWORD` | Ops manager seed password. |
| `PORTER_AUTH_ANALYST_PASSWORD` | Analyst seed password. |
| `PORTER_AUTH_VIEWER_PASSWORD` | Viewer seed password. |

Stale env names:

| Stale name | Current name |
|---|---|
| `SECRET_KEY` | `JWT_SECRET_KEY` |
| `ALLOWED_ORIGINS` | `API_ALLOWED_ORIGINS` |
| `RUNTIME_MODE` | `APP_RUNTIME_MODE` / `APP_ENV` |

### Webhook signatures

`security/settings.py::require_webhook_signature()` requires webhook signatures in production mode. In non-production, unsigned webhook behavior can be controlled with:

```text
ALLOW_UNSIGNED_WEBHOOKS
```

### PII encryption

PII encryption helpers live in:

```text
security/encryption.py
```

Plaintext PII is not allowed in production mode. Demo plaintext behavior is guarded by:

```text
ALLOW_PLAINTEXT_PII
```

### Security headers

`api/main.py` adds:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

---

## 16. Shadow Mode

Shadow mode is the safe deployment path for real operational validation. It lets the platform score and persist reviewable decisions while suppressing external writeback/enforcement.

Runtime flag:

```text
SHADOW_MODE=true
```

Live endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/shadow/status` | Current shadow-mode status. |
| `POST` | `/shadow/activate` | Activate shadow mode. |
| `POST` | `/shadow/deactivate` | Deactivate shadow mode. |

`/health` includes:

```json
{
  "shadow_mode": true,
  "data_provenance": "Shadow-mode case records persisted to isolated PostgreSQL storage with operational writeback disabled."
}
```

Recommended production rollout:

1. Deploy with `APP_RUNTIME_MODE=prod`.
2. Keep `SHADOW_MODE=true`.
3. Connect real ingestion.
4. Score real trips without enforcement writeback.
5. Compare model flags against manual review outcomes.
6. Calibrate thresholds if required.
7. Disable shadow mode only after acceptance criteria are met.

---

## 17. Digital Twin And Synthetic Data Engine

The synthetic data engine lives under:

```text
generator/
ingestion/live_simulator.py
ingestion/city_profiles.py
```

Core files:

| File | Purpose |
|---|---|
| `generator/config.py` | Global generation constants, vehicle types, API title/version/description. |
| `generator/cities.py` | City and zone helpers. |
| `generator/customers.py` | Synthetic customer generation. |
| `generator/drivers.py` | Synthetic driver generation. |
| `generator/trips.py` | Synthetic trip generation. |
| `generator/fraud.py` | Fraud injection engine. |
| `generator/hard_negatives.py` | Hard-negative generation for false-positive control. |
| `ingestion/live_simulator.py` | Demo stream publisher. |
| `ingestion/city_profiles.py` | City profile definitions for simulator. |

Fraud patterns represented in the current generator configuration include:

- `cash_extortion`
- `fake_trip`
- `route_deviation`
- `fake_cancellation`
- `duplicate_trip`
- `loading_fraud`
- `partial_delivery`
- `gps_spoof`

Synthetic feed is for demos and validation only. Production mode disables it automatically.

---

## 18. Live API Surface

The live API route table is registered through:

```text
api/router_registry.py
```

The contract is locked by:

```text
tests/test_api_contract.py
```

### Core

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API metadata. |
| `GET` | `/health` | Health, dependency, runtime, and security state. |
| `GET` | `/metrics` | Prometheus metrics. |
| `POST` | `/webhooks/dispatch/test` | Test downstream dispatch connectivity. |

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/token` | Form login and JWT issuance. |
| `GET` | `/auth/me` | Current user details. |
| `GET` | `/auth/admin/users` | Admin user configuration surface. |
| `POST` | `/auth/admin/users` | Admin user setup guidance. |

### Fraud and scoring

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/fraud/score` | Score one trip. |
| `GET` | `/fraud/heatmap` | Zone fraud heatmap. |
| `GET` | `/fraud/live-feed` | Recent fraud feed. |
| `GET` | `/fraud/tier-summary` | Two-stage tier summary. |
| `GET` | `/fraud/driver/{driver_id}` | Driver fraud detail from inference surface. |

### Cases

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/cases` | List cases. |
| `GET` | `/cases/` | List cases with trailing slash. |
| `GET` | `/cases/summary/counts` | Case count summary. |
| `GET` | `/cases/summary/dashboard` | Dashboard case summary. |
| `GET` | `/cases/{case_id}` | Fetch one case. |
| `PATCH` | `/cases/{case_id}` | Update one case. |
| `GET` | `/cases/{case_id}/history` | Case audit history. |
| `POST` | `/cases/{case_id}/driver-action` | Record driver action. |
| `POST` | `/cases/batch-review` | Bulk case review. |

### KPI, reports, ROI, legal

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/kpi/live` | Live KPI panel. |
| `GET` | `/kpi/summary` | KPI summary from inference module. |
| `GET` | `/kpi/report` | Sanitized model/KPI report. |
| `GET` | `/reports/board-pack` | Board-pack PDF. |
| `GET` | `/reports/daily-summary` | Daily summary. |
| `GET` | `/reports/model-performance` | Model performance report. |
| `POST` | `/roi/calculate` | ROI calculation. |
| `GET` | `/roi/summary` | ROI summary. |
| `GET` | `/legal/download` | Full legal close packet. |
| `GET` | `/legal/download/nda` | NDA PDF. |
| `GET` | `/legal/download/commercial-schedule` | Commercial schedule PDF. |
| `GET` | `/legal/download/acceptance-criteria` | Acceptance criteria PDF. |
| `GET` | `/legal/download/support-scope` | Support scope PDF. |
| `GET` | `/legal/term-sheet` | Term sheet PDF. |
| `GET` | `/legal/commercial-schedule` | Commercial schedule PDF. |

### Intelligence, demand, efficiency, query

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/intelligence/top-risk` | Top-risk driver list. |
| `GET` | `/intelligence/driver/{driver_id}` | Driver intelligence detail. |
| `GET` | `/demand/forecast/{zone_id}` | Demand forecast by zone. |
| `GET` | `/efficiency/summary` | Fleet efficiency summary. |
| `GET` | `/efficiency/reallocation` | Reallocation suggestions. |
| `GET` | `/efficiency/dead-miles` | Dead-mile analysis. |
| `GET` | `/efficiency/fleet-zones` | Fleet-zone view. |
| `GET` | `/efficiency/utilisation/{zone_id}` | Zone utilisation. |
| `POST` | `/query` | Natural-language operations query. |

### Ingestion, demo, shadow

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ingest/trip-completed` | Single trip ingest. |
| `POST` | `/ingest/batch-csv` | Batch CSV ingest. |
| `GET` | `/ingest/status` | Ingestion status. |
| `GET` | `/ingest/schema-map/default` | Default schema map. |
| `GET` | `/demo/scenarios` | Demo scenarios. |
| `GET` | `/demo/preset/{name}` | Demo preset. |
| `POST` | `/demo/reset` | Reset demo state. |
| `GET` | `/shadow/status` | Shadow status. |
| `POST` | `/shadow/activate` | Activate shadow mode. |
| `POST` | `/shadow/deactivate` | Deactivate shadow mode. |

---

## 19. Frontend Dashboard

The frontend lives in:

```text
dashboard-ui/
```

It is a React 19 + Vite app with routes:

| Frontend route | Component | Purpose |
|---|---|---|
| `/` | `dashboard-ui/src/pages/Dashboard.jsx` | Executive/live dashboard. |
| `/login` | `dashboard-ui/src/pages/Login.jsx` | Login form. |
| `/analyst` | `dashboard-ui/src/pages/Analyst.jsx` | Protected analyst workspace. |

### Key frontend files

| File | Purpose |
|---|---|
| `dashboard-ui/src/App.jsx` | React router wiring. |
| `dashboard-ui/src/main.jsx` | React entrypoint. |
| `dashboard-ui/src/utils/api.js` | API client, token handling, viewer auto-login support. |
| `dashboard-ui/src/utils/auth.js` | Auth utility helpers. |
| `dashboard-ui/src/components/ProtectedRoute.jsx` | Analyst route protection. |
| `dashboard-ui/src/components/FraudFeed.jsx` | Fraud live feed. |
| `dashboard-ui/src/components/TripScorer.jsx` | Manual trip scoring form. |
| `dashboard-ui/src/components/KPIPanel.jsx` | Live KPI cards. |
| `dashboard-ui/src/components/DriverIntelligence.jsx` | Top-risk drivers. |
| `dashboard-ui/src/components/ReallocationPanel.jsx` | Route-efficiency suggestions. |
| `dashboard-ui/src/components/QueryPanel.jsx` | Natural-language query. |
| `dashboard-ui/src/components/ROICalculator.jsx` | ROI calculator. |
| `dashboard-ui/src/components/ZoneMap.jsx` | Zone/map visualization. |

### API client behavior

`dashboard-ui/src/utils/api.js`:

- Uses `VITE_API_BASE_URL` or falls back to `/api`.
- Adds `Authorization: Bearer <token>` when a token exists.
- Uses `VITE_VIEWER_PASSWORD` only if configured in the hosting environment.
- Does not redirect to login for ordinary network outages.
- Redirects named sessions to `/login?reason=session_expired` when token expiry is detected.

Do **not** commit `VITE_VIEWER_PASSWORD`.

---

## 20. Deployment And Runtime Configuration

### Required backend environment

The template is `.env.example`.

```bash
DATABASE_URL=postgresql+asyncpg://porter:porter@localhost:5432/porter_intelligence
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=replace-with-secure-random-64-char-string
ENCRYPTION_KEY=replace-with-base64-encoded-32-byte-key
WEBHOOK_SECRET=replace-with-secure-random-64-char-string
API_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
APP_ENV=production
APP_RUNTIME_MODE=prod
ENABLE_SYNTHETIC_FEED=false
SHADOW_MODE=false
ALLOW_PLAINTEXT_PII=false
ALLOW_UNSIGNED_WEBHOOKS=false
AUTH_TOKEN_RATE_LIMIT=10/minute
FRAUD_SCORE_RATE_LIMIT=100/minute
INGEST_RATE_LIMIT=300/minute
PORTER_AUTH_ADMIN_PASSWORD=replace-with-strong-password
PORTER_AUTH_OPS_MANAGER_PASSWORD=replace-with-strong-password
PORTER_AUTH_ANALYST_PASSWORD=replace-with-strong-password
PORTER_AUTH_VIEWER_PASSWORD=replace-with-strong-password
GRAFANA_ADMIN_PASSWORD=replace-with-strong-password
PORTER_TWIN_TRIPS_PER_MIN=30
PORTER_TWIN_SCALE_MULTIPLIER=1.0
PORTER_TWIN_DAILY_GROWTH_PCT=0.0
PORTER_TWIN_ELAPSED_DAYS=0
PORTER_TWIN_ACTIVE_CITIES=
LOG_LEVEL=info
```

### Runtime modes

`runtime_config.py` understands:

| Env value | Behavior |
|---|---|
| `APP_RUNTIME_MODE=prod` | Production semantics. Synthetic feed forced off. |
| `APP_RUNTIME_MODE=demo` | Demo semantics. Synthetic feed defaults on. |
| `APP_ENV=production` | Fallback mode source if `APP_RUNTIME_MODE` is absent. |
| `APP_ENV=demo` | Fallback demo mode if `APP_RUNTIME_MODE` is absent. |

### Docker Compose

```bash
cp .env.example .env
# Replace every placeholder before starting production-like compose.
docker compose up --build
```

Compose starts:

| Service | Port | Purpose |
|---|---:|---|
| `postgres` | 5432 | PostgreSQL case store. |
| `redis` | 6379 | Redis stream/cache. |
| `api` | 8000 | FastAPI. |
| `prometheus` | 9090 | Metrics. |
| `grafana` | 3001 | Dashboards. |

### Netlify

Root file:

```text
netlify.toml
```

Netlify frontend settings:

| Setting | Value |
|---|---|
| Base | `dashboard-ui` |
| Publish | `dist` |
| Build command | `npm run build` |
| Edge function path | `dashboard-ui/netlify/edge-functions` |

If using the Netlify edge proxy, set:

```text
PORTER_API_UPSTREAM=https://your-api-host
VITE_API_BASE_URL=/api
```

### Vercel

Files:

```text
vercel.json
dashboard-ui/vercel.json
```

No hardcoded backend tunnel is committed. Use `VITE_API_BASE_URL` or platform-level rewrites configured outside source control.

### AWS

AWS scripts live in:

```text
infrastructure/aws/
```

Important files:

| File | Purpose |
|---|---|
| `infrastructure/aws/setup.sh` | One-time AWS provisioning. |
| `infrastructure/aws/deploy.sh` | Build/push/deploy flow. |
| `infrastructure/aws/pause.sh` | Pause cost-heavy infrastructure. |
| `infrastructure/aws/teardown.sh` | Tear down provisioned infrastructure. |
| `infrastructure/aws/ecs-task-definition.json` | ECS task definition template. |
| `infrastructure/aws/README.md` | AWS runbook. |

---

## 21. Testing And Quality Gates

### Current commands

```bash
./venv/bin/pytest -q
./venv/bin/flake8 .
./venv/bin/bandit -q -r . -c .bandit

cd dashboard-ui
npm run lint
npm run build
```

### Backend test files

| File | Coverage |
|---|---|
| `tests/test_api_contract.py` | Live API route contract and router registry guardrail. |
| `tests/test_auth.py` | Password hashing, seed users, token behavior. |
| `tests/test_case_workflow_api.py` | Case workflow API. |
| `tests/test_cases.py` | Case store and case route behavior. |
| `tests/test_demo_api.py` | Demo reset/scenario behavior. |
| `tests/test_enforcement.py` | Dispatch webhook behavior. |
| `tests/test_health_contract.py` | `/health` response contract. |
| `tests/test_ingestion_api.py` | Ingestion endpoints. |
| `tests/test_ingestion_queue.py` | Queue/stream behavior. |
| `tests/test_legal_download.py` | Legal download ZIP/PDF behavior. |
| `tests/test_live_kpi_metrics.py` | KPI metrics. |
| `tests/test_live_simulator.py` | Simulator config and event behavior. |
| `tests/test_model.py` | Model/scoring behavior. |
| `tests/test_reports_board_pack.py` | Board pack generation. |
| `tests/test_roi_api.py` | ROI calculation behavior. |
| `tests/test_schema_mapper.py` | Schema mapping. |
| `tests/test_security.py` | Security validation. |
| `tests/test_shadow_api.py` | Shadow API. |
| `tests/test_shadow_mode.py` | Shadow-mode behavior. |

### Why `test_api_contract.py` matters

This project previously had unused compatibility modules under `api/routes/` that looked active but were not registered. `tests/test_api_contract.py` prevents that class of architecture drift by comparing the live FastAPI route table to an explicit expected set.

---

## 22. Project Structure

```text
Porter/
├── api/
│   ├── main.py                     # FastAPI app, middleware, core endpoints
│   ├── router_registry.py          # Single live router registration surface
│   ├── state.py                    # Startup lifespan: model/data/db/redis/cache/scheduler
│   ├── inference.py                # Fraud, KPI, demand, heatmap, live-feed endpoints
│   ├── schemas.py                  # Pydantic request/response contracts
│   ├── limiting.py                 # slowapi limiter
│   └── routes/
│       ├── auth.py                 # /auth/token, /auth/me, admin user surface
│       ├── cases.py                # Case queue, summaries, review, history
│       ├── demo.py                 # Demo scenarios, presets, reset
│       ├── driver_intelligence.py  # Top-risk and driver profile surfaces
│       ├── legal.py                # Legal PDF/download endpoints
│       ├── live_kpi.py             # Database-backed live KPI endpoint
│       ├── query.py                # Natural-language query endpoint
│       ├── reports.py              # Daily summary, model performance, board pack
│       ├── roi.py                  # ROI calculator and summary
│       ├── route_efficiency.py     # Fleet efficiency, dead miles, utilisation
│       └── shadow.py               # Shadow-mode status and toggles
├── auth/
│   ├── config.py                   # Env-backed seed users
│   ├── dependencies.py             # Current-user and permission dependencies
│   ├── jwt.py                      # Password hashing and JWT helpers
│   └── models.py                   # Roles and permissions
├── config/
│   └── commercial.py               # Commercial terms loaded from env
├── database/
│   ├── connection.py               # Async SQLAlchemy engine/session
│   ├── models.py                   # ORM models
│   ├── case_store.py               # Case persistence/query helpers
│   └── redis_client.py             # Redis helpers
├── dashboard-ui/
│   ├── src/
│   │   ├── pages/                  # Dashboard, Analyst, Login
│   │   ├── components/             # KPI, fraud feed, scorer, ROI, map, etc.
│   │   ├── hooks/                  # useAuth, useCountUp
│   │   ├── utils/                  # api.js, auth.js
│   │   └── assets/                 # images and SVGs
│   ├── netlify/edge-functions/     # Netlify API proxy
│   ├── public/                     # favicon, icons, redirects
│   ├── package.json
│   ├── vite.config.js
│   └── vercel.json
├── data/
│   ├── raw/                        # Current sample/generated CSV and reports
│   ├── samples/                    # Portable tiny samples
│   ├── masked/                     # Masked export placeholder
│   └── blind_test/                 # Local ignored blind-test exports
├── docs/
│   ├── architecture-map.md
│   ├── architecture-map.mmd
│   ├── architecture.md
│   ├── benchmarks/
│   ├── demo/
│   ├── deployment/
│   ├── handover/
│   └── runbooks/
├── enforcement/
│   └── dispatch.py                 # Downstream dispatch webhook integration
├── generator/
│   ├── config.py                   # Generator constants and API metadata
│   ├── cities.py
│   ├── customers.py
│   ├── drivers.py
│   ├── trips.py
│   ├── fraud.py
│   └── hard_negatives.py
├── ingestion/
│   ├── webhook.py                  # Ingest API
│   ├── schema_mapper.py            # Field normalization
│   ├── schema_map.default.json
│   ├── streams.py                  # Redis stream consumer
│   ├── staging.py
│   ├── live_simulator.py
│   └── city_profiles.py
├── infrastructure/
│   ├── prometheus.yml
│   ├── prometheus-alerts.yml
│   ├── aws/
│   └── grafana/provisioning/
├── ml/
│   ├── stateless_scorer.py
│   └── feature_store.py
├── model/
│   ├── features.py
│   ├── train.py
│   ├── evaluate.py
│   ├── scoring.py
│   ├── demand.py
│   ├── driver_intelligence.py
│   ├── kpi.py
│   ├── query.py
│   ├── route_efficiency.py
│   └── weights/
├── monitoring/
│   ├── metrics.py
│   └── drift.py
├── scripts/
│   ├── local_up.sh
│   ├── demo_start.sh
│   ├── seed_demo_db.py
│   ├── fallback_check.sh
│   └── build_handover_package.sh
├── security/
│   ├── settings.py
│   └── encryption.py
├── tests/
│   └── test_*.py
├── _archive/
│   └── unused_modules/api_route_shims/ # Archived unregistered route shims
├── runtime_config.py
├── logging_config.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── docker-compose.demo.yml
├── netlify.toml
├── vercel.json
├── railway.json
├── railway.toml
└── .env.example
```

---

## 23. What Is Active vs Archived

### Active production/runtime code

Active code is imported by the app, included in router registration, used by tests, used by startup, used by the frontend, or part of deploy/runtime configuration.

Important active roots:

```text
api/
auth/
config/
dashboard-ui/
database/
data/
enforcement/
generator/
ingestion/
infrastructure/
ml/
model/
monitoring/
scripts/
security/
tests/
runtime_config.py
logging_config.py
```

### Archived or non-runtime material

`_archive/` contains historical materials and modules not part of the live app. The repo `.gitignore` marks `_archive/` as local-only/internal by default.

Currently relevant archive item:

```text
_archive/unused_modules/api_route_shims/
```

These files used to live in `api/routes/`:

```text
api/routes/fraud.py
api/routes/kpi.py
api/routes/demand.py
```

They were import-only compatibility shims, not registered live routers. They were archived to reduce confusion and prevent colleagues from editing files that appear important but do not affect deployed behavior.

### Generated/cache/local-only folders

These should not be treated as source architecture:

```text
venv/
dashboard-ui/node_modules/
dashboard-ui/dist/
dashboard-ui/.netlify/
dashboard-ui/.vercel/
.vercel/
.pytest_cache/
__pycache__/
logs/
infrastructure/aws/state/
```

---

## 24. Quickstart

### Prerequisites

- Python 3.11 recommended.
- Node.js 20 recommended for frontend.
- Docker and Docker Compose for local PostgreSQL/Redis/Prometheus/Grafana.
- PostgreSQL and Redis if running without Compose.

### 1. Install Python dependencies

```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Replace every `replace-with-*` placeholder. Production mode will reject placeholder secrets.

For local development, a minimal useful set is:

```bash
DATABASE_URL=postgresql+asyncpg://porter:porter@localhost:5432/porter_intelligence
REDIS_URL=redis://localhost:6379
APP_RUNTIME_MODE=demo
ENABLE_SYNTHETIC_FEED=false
SHADOW_MODE=false
JWT_SECRET_KEY=<strong-random-secret>
ENCRYPTION_KEY=<base64-32-byte-key>
WEBHOOK_SECRET=<strong-random-secret>
API_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000
PORTER_AUTH_ADMIN_PASSWORD=<password>
PORTER_AUTH_OPS_MANAGER_PASSWORD=<password>
PORTER_AUTH_ANALYST_PASSWORD=<password>
PORTER_AUTH_VIEWER_PASSWORD=<password>
```

### 3. Start infrastructure

Full stack:

```bash
docker compose up --build
```

Only database and Redis:

```bash
docker compose up postgres redis -d
```

### 4. Start API locally

```bash
./venv/bin/uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Useful URLs:

```text
http://localhost:8000/
http://localhost:8000/health
http://localhost:8000/docs
http://localhost:8000/metrics
```

### 5. Get an auth token

The current login endpoint is `/auth/token`, not `/auth/login`.

```bash
TOKEN=$(
  curl -s -X POST http://localhost:8000/auth/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin&password=$PORTER_AUTH_ADMIN_PASSWORD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
)
```

### 6. Score one trip

```bash
curl -s -X POST http://localhost:8000/fraud/score \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": "TRIP_SMOKE_001",
    "driver_id": "DRV_SMOKE_001",
    "vehicle_type": "mini_truck",
    "pickup_zone_id": "blr_koramangala",
    "dropoff_zone_id": "blr_whitefield",
    "pickup_lat": 12.9352,
    "pickup_lon": 77.6245,
    "dropoff_lat": 12.9698,
    "dropoff_lon": 77.7500,
    "declared_distance_km": 8.2,
    "declared_duration_min": 34,
    "fare_inr": 420,
    "payment_mode": "cash",
    "surge_multiplier": 1.1,
    "requested_at": "2026-04-28T10:30:00+05:30",
    "is_night": false,
    "hour_of_day": 10,
    "day_of_week": 1,
    "is_peak_hour": true,
    "zone_demand_at_time": 1.3,
    "status": "completed",
    "customer_complaint_flag": false
  }' | python3 -m json.tool
```

Expected response shape:

```json
{
  "trip_id": "TRIP_SMOKE_001",
  "fraud_probability": 0.1234,
  "tier": "clear",
  "tier_label": "CLEAR",
  "tier_color": "#22C55E",
  "is_fraud_predicted": false,
  "fraud_risk_level": "LOW",
  "action_required": "No action required.",
  "auto_escalate": false,
  "top_signals": [],
  "narrative": "...",
  "confidence": "high",
  "scored_at": "..."
}
```

The exact probability depends on model weights and Redis feature-store defaults.

### 7. Start frontend locally

```bash
cd dashboard-ui
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Open:

```text
http://localhost:5173
```

### 8. Run verification

```bash
./venv/bin/pytest -q
./venv/bin/flake8 .
./venv/bin/bandit -q -r . -c .bandit

cd dashboard-ui
npm run lint
npm run build
```

---

## 25. Production Handoff Notes

Before connecting this to a company CD pipeline:

1. Keep `api/router_registry.py` as the live API registration source.
2. Keep `tests/test_api_contract.py` updated whenever endpoints intentionally change.
3. Keep `model/features.py`, `model/weights/feature_names.json`, and `ml/stateless_scorer.py` synchronized.
4. Keep `model/weights/two_stage_config.json` as the threshold source of truth.
5. Never commit real secrets, tokens, viewer passwords, ngrok URLs, or provider preview URLs as API origins.
6. Use `APP_RUNTIME_MODE=prod` for production.
7. Use `SHADOW_MODE=true` for first real-data deployment.
8. Set `API_ALLOWED_ORIGINS` explicitly for deployed frontend origins.
9. Set `PORTER_API_UPSTREAM` only in Netlify hosting env if using the Netlify edge proxy.
10. Use AWS Secrets Manager or equivalent for `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `WEBHOOK_SECRET`, auth passwords, DB URL, and Redis URL.
11. Treat synthetic benchmark numbers as benchmark evidence, not production performance claims.
12. Keep `_archive/` for unused/historical material so live source directories stay clean.

The current architecture has been moved toward production-grade maintainability by making router registration explicit, archiving unused route shims, removing stale dashboard-root coupling, cleaning hardcoded deploy secrets/URLs, and locking the live route table with tests.
