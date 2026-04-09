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
| `tests/` | 56-test pytest suite covering all major paths |

### Model Weights

| File | Location | Description |
|------|----------|-------------|
| `xgb_fraud_model.json` | `model/weights/` | Trained XGBoost binary classifier |
| `threshold.json` | `model/weights/` | Optimal action threshold (~0.82) from grid search |
| `two_stage_config.json` | `model/weights/` | Two-stage tier boundaries and evaluation metrics |
| `feature_names.json` | `model/weights/` | Ordered list of 31 feature column names |
| `demand_models.pkl` | `model/weights/` | 12 Prophet demand forecasting models (Bangalore zones) |

### Training Data

| File | Location | Description |
|------|----------|-------------|
| `trips_full_fraud.csv` | `data/raw/` | Full labelled training dataset |
| `drivers_full.csv` | `data/raw/` | Driver master data |
| `customers_full.csv` | `data/raw/` | Customer data |
| `evaluation_report.json` | `data/raw/` | Full benchmark and two-stage evaluation metrics |

### Documentation

| Location | Description |
|----------|-------------|
| `docs/` | Deployment guides, runbooks, security notes, handover docs |
| `logic/` | 10-file deep-dive architecture documentation with Mermaid diagrams |
| `how it works/` | 11-file non-technical system explainer |
| `founders work/` | Commercial framing, deal strategy, and meeting preparation docs |
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

Model weights are in `model/weights/` and are included in the repository. Confirm they are not `.gitignore`d before transfer (they were explicitly committed).

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
- `model/weights/*.json` and `model/weights/*.pkl`
- `data/raw/evaluation_report.json`
- `docs/`, `logic/`, `how it works/`
- `infrastructure/`
- `.env.example`

---

## Buyer Onboarding Sequence

A new technical owner follows this sequence to go from repository access to independently running the platform:

### 1. Read First

1. `docs/README.md` — documentation hub overview
2. `docs/handover/package-structure.md` — understand what you have
3. `logic/README.md` — deep-dive architecture index
4. `docs/deployment/one-command-setup.md` — how to start it

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
# Expect: 56 passed
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
