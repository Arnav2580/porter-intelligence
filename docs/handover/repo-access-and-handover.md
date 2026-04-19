# Repository Access and Handover Package

[Handover Hub](./README.md) | [Package Structure](./package-structure.md)

This document describes what is in the transfer package, how to access it, and how a new technical owner gets from zero to independently operating the platform.

---

## What Is Being Transferred

### Source Code

| Path | Description |
|------|-------------|
| `api/` | FastAPI backend — routes, inference, schemas, state management |
| `ml/` | Stateless inference engine, Redis feature store |
| `model/` | XGBoost training pipeline, demand forecasting, feature engineering, scoring logic |
| `ingestion/` | Webhook ingestion, Redis Stream consumer, schema mapper, staging fallback, live simulator |
| `database/` | SQLAlchemy models, async connection, case store, Redis client |
| `auth/` | JWT creation and verification, dependency injection, RBAC, seed user config |
| `security/` | AES-256-GCM PII encryption, security settings, placeholder detection |
| `enforcement/` | Dispatch module for driver enforcement actions |
| `monitoring/` | Prometheus metrics definitions |
| `generator/` | 22-city profile config for digital twin |
| `dashboard-ui/` | React frontend — dashboard, analyst queue, KPI panel, ROI calculator, trip scorer |
| `infrastructure/` | Docker Compose, AWS ECS task definition, Prometheus config, Grafana provisioning |
| `scripts/` | Local setup, data generation, model training helper scripts |
| `tests/` | 63-test pytest suite covering all major paths |

### What Is Included in the Repository

| File | Location | Description |
|------|----------|-------------|
| `xgb_fraud_model.json` | `model/weights/` | Trained XGBoost binary classifier |
| `demand_models.pkl` | `model/weights/` | 12 Prophet demand forecasting models (Bangalore zones) |
| `feature_names.json` | `model/weights/` | Ordered feature column list used at inference time |
| `two_stage_config.json` | `model/weights/` | Two-stage tier boundaries and evaluation metrics |
| `threshold.json` | `model/weights/` | Stored scoring threshold artifact |
| `trips_with_fraud_10k.csv` | `data/raw/` | Sample labelled benchmark dataset used for demos and validation |
| `drivers_sample_1000.csv` | `data/raw/` | Sample driver master dataset used for local runs |
| `evaluation_report.json` | `data/raw/` | Benchmark and two-stage evaluation metrics snapshot |

### What Requires Separate Transfer

| File | Location | Description |
|------|----------|-------------|
| `trips_full_fraud.csv` | `data/raw/` | 500K-row labelled benchmark dataset (~180MB). Provided on secure transfer, not kept in Git due to size. |

### Documentation

| Location | Description |
|----------|-------------|
| `docs/` | Deployment guides, runbooks, security notes, handover docs, architecture overview |
| `docs/architecture.md` | Component topology, deployment layout, and design decisions |
| `docs/runbooks/` | Operational runbooks: add-a-city, retrain-model, secret rotation |
| `api/` (running) | Live OpenAPI spec at `/docs` and `/openapi.json` |

---

## Repository Access Transfer

### Step 1: Add Buyer as Collaborator (GitHub)

```
Settings → Collaborators → Add people
Role: Maintain (read, write, no admin)
```

Or for organization transfer:
```
Settings → Transfer repository → Transfer to: [buyer org]
```

### Step 2: Verify Buyer Can Clone

```bash
git clone https://github.com/[repo]/porter-intelligence.git
cd porter-intelligence
```

### Step 3: Verify Model Weights Are Accessible

The committed transfer artifacts are:
- `model/weights/xgb_fraud_model.json`
- `model/weights/demand_models.pkl`
- `model/weights/feature_names.json`
- `model/weights/two_stage_config.json`
- `model/weights/threshold.json`
- `data/raw/trips_with_fraud_10k.csv`
- `data/raw/drivers_sample_1000.csv`
- `data/raw/evaluation_report.json`

The full 500K-row benchmark file `data/raw/trips_full_fraud.csv` is transferred separately over a secure channel.

### Step 4: Provide Environment Template

The buyer receives `.env.example` with all required environment variable names and comments. They populate it with their own secrets before deployment.

---

## Clean Repo State

Before handover, verify the repository is clean:

```bash
# No uncommitted changes
git status

# No debug/test secrets in tracked files
grep -r "change-me\|replace-me\|placeholder" --include="*.py" --include="*.env" .

# No large binaries other than model weights
find . -name "*.csv" -size +100M

# .gitignore covers venv, .env, __pycache__, logs
cat .gitignore
```

Files that should NOT be committed:
- `.env` (never committed — contains real secrets)
- `venv/` (excluded in .gitignore)
- `logs/` (excluded in .gitignore)
- `__pycache__/` (excluded in .gitignore)

Files that MUST be committed:
- `model/weights/xgb_fraud_model.json`
- `model/weights/demand_models.pkl`
- `model/weights/feature_names.json`
- `model/weights/two_stage_config.json`
- `model/weights/threshold.json`
- `data/raw/trips_with_fraud_10k.csv`
- `data/raw/drivers_sample_1000.csv`
- `data/raw/evaluation_report.json`
- `docs/handover/`
- `docs/`
- `infrastructure/`
- `.env.example`

---

## Buyer Onboarding Sequence

A new technical owner follows this sequence to go from repository access to independently running the platform:

### 1. Read First

1. `docs/README.md` — documentation hub overview
2. `docs/handover/package-structure.md` — understand what you have
3. `docs/architecture.md` — component topology and design decisions
4. `docs/handover/deployment-runbook.md` — how to start it

### 2. Get It Running Locally

```bash
git clone [repo]
cd porter-intelligence
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY, ENCRYPTION_KEY, WEBHOOK_SECRET, auth passwords
./scripts/local_up.sh
curl http://localhost:8000/health
```

Expected health response:
```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "model_loaded": true,
  "mode": "demo"
}
```

### 3. Verify the Core Path

```bash
# Get an auth token
curl -X POST http://localhost:8000/auth/token \
  -d "username=analyst_1&password=<PORTER_AUTH_ANALYST_PASSWORD>"

# Score a trip
curl -X POST http://localhost:8000/fraud/score \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"trip_id":"test","driver_id":"drv1","fare_inr":1500,"declared_distance_km":3,"declared_duration_min":5,"payment_mode":"cash","vehicle_type":"bike","pickup_zone_id":"blr_koramangala","hour_of_day":2,"is_night":1}'
```

### 4. Run the Test Suite

```bash
source venv/bin/activate
pytest tests/ -q
# Expect: 63 passed
```

### 5. Read the Runbooks

Located in `docs/runbooks/`:
- `rotate-secrets.md` — how to rotate JWT, encryption, and webhook secrets
- `retrain-model.md` — how to retrain the XGBoost model on new labelled data
- `add-a-city.md` — how to add a new city to the digital twin
- `restore-from-backup.md` — disaster recovery procedure

---

## Questions a New Owner Must Be Able to Answer

The handover is complete only when Porter's technical lead can answer these without assistance:

1. **How do I start it?** — `./scripts/local_up.sh` or Docker Compose
2. **How do I verify it is healthy?** — `GET /health` returns `ok` on all components
3. **How do I rotate secrets?** — `docs/runbooks/rotate-secrets.md`
4. **How do I retrain the model?** — `docs/runbooks/retrain-model.md`
5. **How do I restore from a backup?** — `docs/runbooks/restore-from-backup.md`
6. **How do I add a new city?** — `docs/runbooks/add-a-city.md`
7. **What does shadow mode do?** — Scores and stores cases without enforcement dispatch
8. **What triggers enforcement?** — Action tier (≥0.94 fraud probability) in live mode
9. **How is PII protected?** — AES-256-GCM encryption at rest, key in `ENCRYPTION_KEY`
10. **Where are the model weights?** — `model/weights/` committed to the repository
