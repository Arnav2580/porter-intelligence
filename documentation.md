# Porter Intelligence Platform Documentation

Last verified: 2026-04-27

This is the current engineering documentation for the repository. It replaces older notes that mentioned a 31-feature model, `SECRET_KEY`, `ALLOWED_ORIGINS`, fixed Vercel/ngrok rewrites, or action thresholds such as `0.94`.

## 1. What The System Does

Porter Intelligence scores logistics trip completion events for behavioral fraud, persists high-risk cases, and gives analysts a dashboard to review, resolve, and report on those cases.

The platform has five main jobs:

1. Accept trip events through webhook, batch CSV, or synthetic simulator flows.
2. Normalize trip payloads into the canonical schema.
3. Build a 44-feature model vector and score it with XGBoost.
4. Classify the score into `action`, `watchlist`, or `clear`.
5. Expose case workflow, live KPIs, driver intelligence, ROI, reports, legal packets, and operational dashboards.

## 2. Verified State

The following checks pass in this workspace:

```bash
./venv/bin/pytest -q                 # 63 passed
./venv/bin/flake8 .                  # passed
./venv/bin/bandit -q -r . -c bandit.yaml # passed
cd dashboard-ui && npm run lint      # passed
cd dashboard-ui && npm run build     # passed
```

The frontend API-call audit found all currently used dashboard paths registered in FastAPI:

- `/health`
- `/auth/token`
- `/auth/admin/users`
- `/cases/summary/counts`
- `/cases/summary/dashboard`
- `/cases/batch-review`
- `/demo/scenarios`
- `/demo/reset`
- `/efficiency/reallocation`
- `/efficiency/summary`
- `/fraud/live-feed`
- `/fraud/score`
- `/fraud/tier-summary`
- `/intelligence/top-risk`
- `/kpi/live`
- `/query`
- `/roi/calculate`

## 3. Important Fixes Applied

### Backend import break

`api/main.py` imports `API_DESCRIPTION`. `generator/config.py` now exports it alongside `API_TITLE` and `API_VERSION`, so app import and test collection succeed.

### Threshold drift

The platform had stale fallback thresholds in multiple places. The current threshold contract is:

| Tier | Threshold |
|---|---:|
| `action` | `>= 0.80` |
| `watchlist` | `>= 0.50` and `< 0.80` |
| `clear` | `< 0.50` |

Updated code paths:

- [api/main.py](api/main.py): `/health` fallback thresholds
- [api/inference.py](api/inference.py): KPI report fallback thresholds
- [dashboard-ui/src/pages/Analyst.jsx](dashboard-ui/src/pages/Analyst.jsx): color and severity helpers

### Frontend deploy secrets and stale proxy URLs

Removed hardcoded tunnel URLs and committed viewer credentials:

- [dashboard-ui/.env.production](dashboard-ui/.env.production) no longer contains a real viewer password.
- [dashboard-ui/netlify/edge-functions/api-proxy.js](dashboard-ui/netlify/edge-functions/api-proxy.js) reads `PORTER_API_UPSTREAM`.
- [dashboard-ui/public/_redirects](dashboard-ui/public/_redirects) no longer forwards to a fixed third-party tunnel.
- [dashboard-ui/vercel.json](dashboard-ui/vercel.json) and [vercel.json](vercel.json) no longer commit a temporary backend URL.

### CI pipeline blockers

Fixed:

- Python lint failures in generator/stateless scorer formatting.
- Bandit `try/except/pass` findings in [model/scoring.py](model/scoring.py).
- Frontend lint failure from unused Dashboard helpers.
- ESLint awareness of Netlify Edge's `Deno` global.

## 4. Runtime Modes

Runtime settings live in [runtime_config.py](runtime_config.py).

| Env | Meaning |
|---|---|
| `APP_RUNTIME_MODE=prod` | production semantics; synthetic feed is forced off |
| `APP_RUNTIME_MODE=demo` | demo semantics; synthetic feed defaults on |
| `ENABLE_SYNTHETIC_FEED=true/false` | enables synthetic simulator except in prod |
| `SHADOW_MODE=true/false` | disables operational writeback/enforcement boundaries |

Data provenance returned by `/health` comes from `describe_data_provenance()`.

## 5. Security Contract

Security validation lives in [security/settings.py](security/settings.py).

Current env var names:

| Variable | Required For | Notes |
|---|---|---|
| `JWT_SECRET_KEY` | auth token signing | replaces stale `SECRET_KEY` docs |
| `ENCRYPTION_KEY` | PII encryption | base64 32-byte key |
| `WEBHOOK_SECRET` | webhook HMAC | required when webhook signatures are enforced |
| `API_ALLOWED_ORIGINS` | CORS | replaces stale `ALLOWED_ORIGINS` docs |
| `PORTER_AUTH_ADMIN_PASSWORD` | bootstrap admin login | never commit |
| `PORTER_AUTH_OPS_MANAGER_PASSWORD` | bootstrap ops manager login | never commit |
| `PORTER_AUTH_ANALYST_PASSWORD` | bootstrap analyst login | never commit |
| `PORTER_AUTH_VIEWER_PASSWORD` | bootstrap viewer login | never commit |

Production rejects placeholder or missing required secrets.

## 6. Backend Structure

### App entrypoint

[api/main.py](api/main.py)

Responsibilities:

- Creates the FastAPI app.
- Configures CORS, security headers, rate-limit handler, and Prometheus latency middleware.
- Registers routers.
- Exposes root, `/health`, `/metrics`, and dispatch test route.

### Startup state

[api/state.py](api/state.py)

Responsibilities:

- Loads XGBoost model from `model/weights/xgb_fraud_model.json`.
- Loads thresholds and feature names from `model/weights`.
- Loads benchmark trip and driver CSVs when present.
- Warms Redis feature-store caches when dependencies are available.
- Initializes database tables.
- Starts Redis stream consumer.
- Starts synthetic simulator only when runtime allows it.
- Starts APScheduler drift and stream-lag jobs.

### Inference endpoints

[api/inference.py](api/inference.py)

Registered route families:

- `/fraud/heatmap`
- `/fraud/live-feed`
- `/fraud/driver/{driver_id}`
- `/demand/forecast/{zone_id}`
- `/kpi/summary`
- `/kpi/report`
- `/fraud/score`
- `/fraud/tier-summary`

### Route modules

| File | Purpose |
|---|---|
| `api/routes/auth.py` | token login, user identity, admin user setup instructions |
| `api/routes/cases.py` | queue, summary, review, history, driver action |
| `api/routes/demo.py` | demo scenarios and safe reset |
| `api/routes/driver_intelligence.py` | top-risk and individual driver intelligence |
| `api/routes/live_kpi.py` | database-backed live KPI panel |
| `api/routes/query.py` | natural-language operations query |
| `api/routes/reports.py` | daily summary, model performance, board pack |
| `api/routes/roi.py` | ROI calculator |
| `api/routes/route_efficiency.py` | dead miles, utilisation, reallocation |
| `api/routes/shadow.py` | shadow-mode status and toggles |
| `api/routes/legal.py` | downloadable legal/commercial documents |

The deployed router surface is registered in `api/router_registry.py`. Legacy
compatibility shims that used to live at `api/routes/fraud.py`,
`api/routes/kpi.py`, and `api/routes/demand.py` have been moved to
`_archive/unused_modules/api_route_shims/` because they were not registered in
runtime.

## 7. Model And Features

The model currently uses 44 ordered features.

Canonical files:

- [model/features.py](model/features.py): training-time feature engineering.
- [model/weights/feature_names.json](model/weights/feature_names.json): ordered runtime feature list.
- [ml/stateless_scorer.py](ml/stateless_scorer.py): request-time vector builder without pandas.
- [model/weights/xgb_fraud_model.json](model/weights/xgb_fraud_model.json): XGBoost model weights.
- [model/weights/two_stage_config.json](model/weights/two_stage_config.json): tier thresholds and benchmark metadata.

Feature groups:

| Group | Examples |
|---|---|
| Trip economics | fare, surge, fare-to-expected ratio, fare per km |
| Distance/geometry | declared distance, haversine distance, GPS/haversine ratio |
| GPS integrity | ping count, accuracy, mock-location flag, provider, speed |
| Timing integrity | duration, waiting time, loading time, loading anomaly |
| POD/OTP | proof-of-delivery photo, location match, OTP verified, OTP attempts |
| Temporal | hour, day of week, night, peak hour, Friday, late month |
| Payment | cash and credit flags |
| Driver behavior | cancellation velocity, rolling cancel/dispute/cash ratios, 24-hour trips |
| Driver profile | account age, rating, lifetime trips, verification, payment preference |
| Geography/status | zone fraud rate, same-zone trip, cancellation flag |

When changing model features, update all three in one commit:

1. `model/features.py::FEATURE_COLUMNS`
2. `model/weights/feature_names.json`
3. `ml/stateless_scorer.py::build_feature_vector()`

Then retrain or regenerate model weights as needed.

## 8. Ingestion

Ingestion lives under [ingestion](ingestion).

| File | Purpose |
|---|---|
| `webhook.py` | `/ingest/trip-completed`, `/ingest/batch-csv`, status and schema-map routes |
| `schema_mapper.py` | maps partner/city payloads into canonical trip fields |
| `streams.py` | Redis Streams consumer and scoring worker loop |
| `staging.py` | staging fallback when live dependencies are unavailable |
| `live_simulator.py` | synthetic event publisher for demo mode |
| `city_profiles.py` | synthetic city/zone profiles |

Production mode requires signed webhooks unless explicitly disabled outside prod.

## 9. Data And Generated Artifacts

Important current files:

- `data/raw/trips_with_fraud_10k.csv`
- `data/raw/drivers_sample_1000.csv`
- `data/raw/evaluation_report.json`
- `data/raw/trips_sample_5k.csv`
- `data/raw/trips_fraud_v2_sample.csv`
- `model/weights/*`

The workspace has modified generated data/model artifacts. Treat them as intentional unless the owner explicitly asks to revert or regenerate.

Numbers in this repository are synthetic/twin benchmark numbers unless explicitly labeled as production data. Do not present them as live Porter production outcomes.

## 10. Frontend

The dashboard is in [dashboard-ui](dashboard-ui).

Key files:

| File | Purpose |
|---|---|
| `src/App.jsx` | routes `/`, `/login`, `/analyst` |
| `src/utils/api.js` | fetch client, token handling, viewer auto-login support |
| `src/pages/Dashboard.jsx` | executive/live dashboard |
| `src/pages/Analyst.jsx` | analyst workflow |
| `src/pages/Login.jsx` | token login |
| `src/components/TripScorer.jsx` | demo scoring form |
| `src/components/FraudFeed.jsx` | live fraud feed |
| `src/components/KPIPanel.jsx` | live KPI card set |
| `src/components/DriverIntelligence.jsx` | top-risk driver panel |
| `src/components/ReallocationPanel.jsx` | route efficiency suggestions |
| `src/components/ROICalculator.jsx` | commercial calculator |

The API client behavior is:

- Uses `VITE_API_BASE_URL` or falls back to `/api`.
- Adds bearer token when available.
- Can mint a viewer token only if `VITE_VIEWER_PASSWORD` is configured in the environment.
- Does not redirect to login for network outages.
- Redirects named users to login on session expiry.

## 11. Deployment

### Local API

```bash
./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Local dashboard

```bash
cd dashboard-ui
npm run dev
```

For local direct backend calls:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

### Docker Compose

```bash
cp .env.example .env
# fill every placeholder
docker compose up --build
```

### Netlify

Use [netlify.toml](netlify.toml):

- `base = "dashboard-ui"`
- `publish = "dist"`
- edge function path: `dashboard-ui/netlify/edge-functions`

Set this hosting env var for same-origin `/api` proxying:

```bash
PORTER_API_UPSTREAM=https://your-fastapi-host
```

Set frontend env vars only in the provider, not in committed files:

```bash
VITE_API_BASE_URL=/api
VITE_VIEWER_PASSWORD=<optional-viewer-password>
```

### Vercel

Current Vercel config does not commit a backend rewrite. Either:

- set `VITE_API_BASE_URL` to a public API host, or
- configure platform rewrites outside source control for the deployment environment.

### AWS

AWS scripts and runbooks live in [infrastructure/aws](infrastructure/aws). ECS task definitions expect secrets from AWS Secrets Manager.

## 12. Observability

Prometheus endpoint:

```text
GET /metrics
```

Local compose services:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

Metric helpers live in [monitoring/metrics.py](monitoring/metrics.py). Drift and stream-lag jobs are scheduled from [api/state.py](api/state.py).

## 13. Case Workflow

Primary flow:

1. A trip is scored.
2. `action` or `watchlist` cases are persisted.
3. Analyst opens `/analyst`.
4. Case can be reviewed, confirmed, cleared, or acted on.
5. Audit/history is available via case history routes.
6. KPI and reports aggregate reviewed outcomes.

Shadow mode keeps operational writeback disabled while allowing measurement and analyst review.

## 14. Development Checklist

Before handing off a change:

```bash
./venv/bin/pytest -q
./venv/bin/flake8 .
./venv/bin/bandit -q -r . -c bandit.yaml
cd dashboard-ui && npm run lint
cd dashboard-ui && npm run build
```

For model/feature changes, additionally validate:

```bash
./venv/bin/python model/features.py
```

Only run training/regeneration intentionally, because it changes model/data artifacts.

## 15. Known Boundaries And Watch Items

- Redis and PostgreSQL are optional for some local fallback flows, but production health should show both as available.
- The app can run degraded if DB/Redis are unavailable; `/health` reports this explicitly.
- `threshold.json` is a legacy single-threshold artifact. Two-stage tiering uses `two_stage_config.json`.
- Historical files under `docs/` include audit notes and old failure descriptions. They are useful history, not always current operating documentation.
- `api/router_registry.py` is the live router source of truth. If a new route
  module is added, register it there and add or update an API contract test.
- Do not commit temporary tunnels, provider preview URLs as API origins, real passwords, JWT secrets, encryption keys, or webhook secrets.

## 16. Quick API Smoke

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Login:

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=$PORTER_AUTH_ADMIN_PASSWORD"
```

Score a trip after obtaining a token:

```bash
curl -s -X POST http://localhost:8000/fraud/score \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": "smoke-trip-001",
    "driver_id": "driver-001",
    "declared_distance_km": 8.2,
    "actual_trip_duration_mins": 34,
    "fare_inr": 420,
    "surge_multiplier": 1.1,
    "pickup_lat": 12.9352,
    "pickup_lon": 77.6245,
    "dropoff_lat": 12.9698,
    "dropoff_lon": 77.7500,
    "pickup_zone_id": "blr_koramangala",
    "dropoff_zone_id": "blr_whitefield",
    "payment_mode": "cash",
    "vehicle_type": "mini_truck"
  }'
```

## 17. Ownership Notes For Colleagues

If you are modifying backend behavior, start from `api/router_registry.py` to
see the deployed route surface, then follow the route module. If you are
modifying scoring, start from `model/features.py`, `ml/stateless_scorer.py`,
and `model/weights/feature_names.json`. If you are modifying the dashboard,
start from `dashboard-ui/src/utils/api.js` and the page/component making the
API call.

Keep docs close to code changes. The stale-doc problem in this repository came from changing architecture, thresholds, deployment strategy, and feature count without updating the root documentation.
