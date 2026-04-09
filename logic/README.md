# Porter Intelligence Platform — Logic Reference

This folder contains a deep, technical explanation of every algorithm, data flow, and decision path in the Porter Intelligence Platform. Each file is self-contained but cross-referenced. Read them in order for the full picture, or jump to any file independently.

---

## Files

| # | File | What It Covers |
|---|------|---------------|
| 01 | [Fraud Scoring Engine](./01-fraud-scoring-engine.md) | XGBoost model, two-stage tiered scoring, threshold tuning, confidence weighting |
| 02 | [Feature Engineering](./02-feature-engineering.md) | All 35 features: trip-level, driver profile, behavioural sequence, computation logic |
| 03 | [Ingestion Pipeline](./03-ingestion-pipeline.md) | Webhook, Redis Streams, PostgreSQL staging fallback, consumer loop, ACK/NACK |
| 04 | [Case Lifecycle](./04-case-lifecycle.md) | Case creation, analyst queue, status transitions, batch review, audit trail |
| 05 | [Security Model](./05-security-model.md) | AES-256-GCM encryption, JWT HS256 auth, 4-role RBAC, placeholder detection |
| 06 | [Digital Twin Simulator](./06-digital-twin.md) | 22-city simulator, city profiles, zone demand, 5 fraud patterns, trip generation |
| 07 | [Demand Forecasting](./07-demand-forecasting.md) | Prophet models, zone-level hourly series, regressors, model persistence |
| 08 | [Driver Intelligence](./08-driver-intelligence.md) | Risk scoring formula, ring detection, timeline, enforcement recommendations |
| 09 | [Runtime and Startup](./09-runtime-and-startup.md) | Lifespan sequence, runtime mode detection, shadow mode, config loading |
| 10 | [ROI and Reporting](./10-roi-and-reporting.md) | ROI calculator, scenario modelling, board pack PDF generation |

---

## How To Read

- **If you want the ML story**: start with [01](./01-fraud-scoring-engine.md) -> [02](./02-feature-engineering.md) -> [08](./08-driver-intelligence.md) -> [07](./07-demand-forecasting.md).
- **If you want the data flow**: start with [03](./03-ingestion-pipeline.md) -> [01](./01-fraud-scoring-engine.md) -> [04](./04-case-lifecycle.md).
- **If you want the security story**: read [05](./05-security-model.md) standalone, then [09](./09-runtime-and-startup.md).
- **If you want the business story**: start with [10](./10-roi-and-reporting.md) -> [04](./04-case-lifecycle.md) -> [06](./06-digital-twin.md).

---

## Source Code Map

Every claim in these files traces to a specific source file. The key source modules:

| Module | Path | Purpose |
|--------|------|---------|
| Scoring | `model/scoring.py` | Tier definitions, escalation rules |
| Features | `model/features.py` | Feature column list, computation functions |
| Training | `model/train.py` | XGBoost training, threshold tuning, baseline rules |
| Demand | `model/demand.py` | Prophet demand forecasting |
| Driver Intel | `model/driver_intelligence.py` | Risk timeline, ring detection |
| Streams | `ingestion/streams.py` | Redis Stream producer/consumer |
| Webhook | `ingestion/webhook.py` | HTTP ingestion endpoints |
| Simulator | `ingestion/live_simulator.py` | Digital twin trip generator |
| City Profiles | `ingestion/city_profiles.py` | 22-city zone/demand/fraud profiles |
| Cases | `api/routes/cases.py` | Case CRUD, batch review, audit |
| Enforcement | `enforcement/dispatch.py` | Webhook dispatch, shadow suppression |
| Encryption | `security/encryption.py` | AES-256-GCM PII encrypt/decrypt |
| Auth | `auth/dependencies.py` | JWT verification, RBAC enforcement |
| Roles | `auth/models.py` | 4 roles, permission matrix |
| State | `api/state.py` | Lifespan, startup loading sequence |
| Runtime | `runtime_config.py` | Mode detection, synthetic feed control |
| ROI | `api/routes/roi.py` | ROI calculator logic |
| Reports | `api/routes/reports.py` | Board pack PDF, daily summary |
| Case Store | `database/case_store.py` | Shadow/live case persistence routing |
