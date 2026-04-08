# Porter Intelligence Platform — Official Documentation

Last updated: 2026-04-08

This is the complete technical documentation for the Porter Intelligence Platform. It is written for someone reading the codebase for the first time and covers everything from initial setup to advanced operations.

---

## Who Is This For

- **New engineer** joining the project: start with the [Quickstart Tutorial](./01-quickstart-tutorial.md)
- **Technical evaluator** assessing the platform: read the [Architecture Deep Dive](./02-architecture-deep-dive.md)
- **ML engineer** understanding the models: read the [Data and ML Pipeline](./03-data-and-ml-pipeline.md)
- **API consumer** building integrations: read the [API Reference](./04-api-reference.md)
- **Data engineer** connecting feeds: read [Ingestion and Shadow Mode](./05-ingestion-and-shadow-mode.md)
- **Frontend developer** extending the UI: read [Frontend and Dashboard](./06-frontend-and-dashboard.md)
- **Security reviewer** auditing the platform: read [Security and Auth](./07-security-and-auth.md)
- **DevOps engineer** deploying to production: read [Deployment and Infrastructure](./08-deployment-and-infrastructure.md)
- **QA engineer** running tests: read [Testing and Quality](./09-testing-and-quality.md)
- **Sales/demo presenter** running demos: read the [Demo Guide](./10-demo-guide.md)
- **Anyone stuck**: read [Troubleshooting and FAQ](./11-troubleshooting-and-faq.md)

---

## Reading Order

### Fast Path (30 minutes)

1. [Quickstart Tutorial](./01-quickstart-tutorial.md) — get the platform running locally
2. [Architecture Deep Dive](./02-architecture-deep-dive.md) — understand the full system
3. [API Reference](./04-api-reference.md) — see every endpoint

### Full Path (2-3 hours)

1. [Quickstart Tutorial](./01-quickstart-tutorial.md)
2. [Architecture Deep Dive](./02-architecture-deep-dive.md)
3. [Data and ML Pipeline](./03-data-and-ml-pipeline.md)
4. [API Reference](./04-api-reference.md)
5. [Ingestion and Shadow Mode](./05-ingestion-and-shadow-mode.md)
6. [Frontend and Dashboard](./06-frontend-and-dashboard.md)
7. [Security and Auth](./07-security-and-auth.md)
8. [Deployment and Infrastructure](./08-deployment-and-infrastructure.md)
9. [Testing and Quality](./09-testing-and-quality.md)
10. [Demo Guide](./10-demo-guide.md)
11. [Troubleshooting and FAQ](./11-troubleshooting-and-faq.md)

---

## System Overview In 60 Seconds

Porter Intelligence Platform is a **fraud detection and leakage-control operating system** for intra-city logistics.

**What it does:**
1. Ingests trip events from a logistics pipeline (webhook, CSV, or simulated)
2. Scores every trip for fraud risk using an XGBoost ML model
3. Classifies trips into three tiers: ACTION (investigate now), WATCHLIST (monitor), CLEAR (no action)
4. Creates fraud cases in a PostgreSQL database for action/watchlist trips
5. Routes cases to an analyst workflow where humans review, decide, and act
6. Tracks enforcement actions (driver suspend, flag, monitor) with audit trails
7. Provides management dashboards for KPIs, fraud heatmaps, and ROI
8. Supports shadow mode for risk-free validation on real data before live enforcement

**Tech stack:**
- Backend: Python 3.11, FastAPI, async SQLAlchemy
- ML: XGBoost (fraud), Prophet (demand forecasting), scikit-learn
- Storage: PostgreSQL 15, Redis 7
- Frontend: React 19, Vite, Leaflet
- Security: AES-256-GCM, JWT + RBAC, rate limiting, audit logging
- Infrastructure: Docker Compose (local), AWS ECS Fargate (production)
- Observability: Prometheus, Grafana

**Scale:**
- Digital twin simulates 22 cities at Porter-like volume
- Designed for 100k+ trips/day with horizontal scaling
- 14 REST API endpoints across 12 routers

---

## Project Structure

```
Porter/
|-- api/                    # FastAPI backend application
|   |-- main.py             # App init, middleware, router registration
|   |-- state.py            # Startup loader (models, data, caches, background tasks)
|   |-- inference.py        # Core scoring and analytics endpoints
|   |-- schemas.py          # Pydantic request/response models
|   |-- limiting.py         # Rate limiting configuration
|   |-- routes/
|       |-- auth.py         # Login, token issuance
|       |-- cases.py        # Case CRUD, batch review, driver actions
|       |-- demo.py         # Demo scenarios, reset, presets
|       |-- driver_intelligence.py  # Driver risk profiles
|       |-- live_kpi.py     # Reviewed-case KPI surface
|       |-- query.py        # Natural language query
|       |-- reports.py      # Board pack PDF generation
|       |-- roi.py          # ROI calculator
|       |-- route_efficiency.py  # Fleet efficiency and reallocation
|       |-- shadow.py       # Shadow mode status
|
|-- auth/                   # Authentication and authorization
|   |-- config.py           # Seed user configuration
|   |-- dependencies.py     # FastAPI dependency injection (require_permission)
|   |-- jwt.py              # JWT creation, verification, password hashing
|   |-- models.py           # UserRole enum and role-permission matrix
|
|-- dashboard-ui/           # React frontend application
|   |-- src/
|       |-- pages/
|       |   |-- Dashboard.jsx  # Management dashboard
|       |   |-- Analyst.jsx    # Analyst case review workspace
|       |-- components/        # KPIPanel, ZoneMap, TripScorer, ROICalculator, etc.
|       |-- utils/
|           |-- api.js         # API helper (apiGet, apiPost, apiPatch)
|           |-- auth.js        # Auth utilities
|
|-- database/               # Database layer
|   |-- connection.py       # Async SQLAlchemy engine and session factory
|   |-- models.py           # ORM models (FraudCase, ShadowCase, DriverAction, AuditLog, etc.)
|   |-- redis_client.py     # Redis connection and helpers
|   |-- case_store.py       # Case persistence utilities
|
|-- enforcement/            # Enforcement dispatch
|   |-- dispatch.py         # Webhook to Porter's driver management system
|
|-- generator/              # Synthetic data generation
|   |-- config.py           # Constants, paths, feature names, pilot criteria
|   |-- cities.py           # 22-city profiles with demand patterns
|   |-- drivers.py          # Synthetic driver generation
|   |-- customers.py        # Synthetic customer generation
|   |-- trips.py            # Synthetic trip generation with fraud injection
|   |-- fraud.py            # Fraud archetype definitions
|
|-- ingestion/              # Data ingestion pipeline
|   |-- webhook.py          # HTTP webhook endpoint and batch CSV upload
|   |-- streams.py          # Redis Streams async consumer
|   |-- schema_mapper.py    # Configurable field name translation
|   |-- live_simulator.py   # Digital twin (22-city synthetic event generator)
|   |-- city_profiles.py    # City-specific demand and fraud profiles
|   |-- staging.py          # PostgreSQL staging for retry/replay
|
|-- model/                  # ML models and scoring
|   |-- train.py            # XGBoost training pipeline
|   |-- scoring.py          # Two-stage scoring engine (action/watchlist/clear)
|   |-- features.py         # Feature engineering (35 features)
|   |-- demand.py           # Prophet demand forecasting
|   |-- driver_intelligence.py  # Risk timeline, peer comparison, ring detection
|   |-- route_efficiency.py # Dead mile analysis, reallocation suggestions
|   |-- query.py            # Natural language query handler
|   |-- weights/            # Saved model artifacts
|       |-- xgb_fraud_model.json
|       |-- threshold.json
|       |-- feature_names.json
|       |-- two_stage_config.json
|       |-- demand_models.pkl
|
|-- security/               # Security modules
|   |-- encryption.py       # AES-256-GCM PII encryption
|   |-- settings.py         # Security configuration validation
|
|-- infrastructure/         # Deployment infrastructure
|   |-- aws/                # AWS ECS Fargate deployment scripts
|   |-- prometheus.yml      # Prometheus scrape config
|   |-- grafana/            # Grafana dashboard provisioning
|
|-- tests/                  # Test suite (17 files)
|-- data/                   # Data directory (raw CSVs, samples)
|-- docker-compose.yml      # Full local stack (PostgreSQL, Redis, API, Prometheus, Grafana)
|-- Dockerfile              # Multi-stage Python build
|-- requirements.txt        # Python dependencies
|-- runtime_config.py       # Runtime mode detection (demo/prod/shadow)
|-- .env.example            # Environment variable template
```

---

## Environment Variables

Every configuration value is controlled by environment variables. See [.env.example](../.env.example) for the full template.

| Variable | Purpose | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `JWT_SECRET_KEY` | JWT signing key | Yes |
| `ENCRYPTION_KEY` | AES-256-GCM key (base64-encoded 32 bytes) | Yes |
| `WEBHOOK_SECRET` | HMAC webhook verification key | Yes |
| `API_ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | Yes |
| `APP_RUNTIME_MODE` | `demo` or `prod` | No (default: prod) |
| `ENABLE_SYNTHETIC_FEED` | Enable digital twin simulator | No (default: false in prod) |
| `SHADOW_MODE` | Enable shadow mode (no enforcement writeback) | No (default: false) |
| `PORTER_AUTH_*_PASSWORD` | Seed user passwords (admin, ops_manager, analyst, viewer) | Yes |
| `PORTER_DISPATCH_URL` | Enforcement webhook URL (Porter's system) | No (log-only if not set) |
| `PORTER_TWIN_TRIPS_PER_MIN` | Digital twin trip generation rate | No (default: 30) |
| `LOG_LEVEL` | Logging level | No (default: info) |

---

## Related Resources

- [Founders Work Pack](../founders%20work/README.md) — sale process materials
- [Checklist](../_archive/archive/checklist.md) — execution plan
- [API Docs (live)](http://localhost:8000/docs) — Swagger UI (when running)
