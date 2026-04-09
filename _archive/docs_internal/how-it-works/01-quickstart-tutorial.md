# 01 — Quickstart Tutorial

[Index](./README.md) | [Next: Architecture](./02-architecture-deep-dive.md)

Get the Porter Intelligence Platform running locally from zero in under 10 minutes.

---

## Prerequisites

You need these installed on your machine:

| Tool | Version | Check Command |
|---|---|---|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | 2.0+ | `git --version` |

---

## Option A: One-Command Docker Setup (Recommended)

This starts the entire stack: PostgreSQL, Redis, API, Prometheus, and Grafana.

### Step 1: Clone and enter the repo

```bash
git clone <your-repo-url> Porter
cd Porter
```

### Step 2: Create your environment file

```bash
cp .env.example .env
```

Now edit `.env` and replace all placeholder values:

```bash
# Generate secure random keys:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# Use the output for JWT_SECRET_KEY and WEBHOOK_SECRET

# Generate AES encryption key:
python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
# Use the output for ENCRYPTION_KEY

# Set passwords (use strong random passwords):
PORTER_AUTH_ADMIN_PASSWORD=YourStrongAdminPassword123!
PORTER_AUTH_OPS_MANAGER_PASSWORD=YourStrongOpsPassword123!
PORTER_AUTH_ANALYST_PASSWORD=YourStrongAnalystPassword123!
PORTER_AUTH_VIEWER_PASSWORD=YourStrongViewerPassword123!
GRAFANA_ADMIN_PASSWORD=YourGrafanaPassword123!

# Set CORS origins:
API_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Step 3: Start the full stack

```bash
docker compose up --build -d
```

This builds and starts 5 services:
- `postgres` on port 5432
- `redis` on port 6379
- `api` on port 8000
- `prometheus` on port 9090
- `grafana` on port 3001

Wait for all healthchecks to pass (~30 seconds):

```bash
docker compose ps
```

All services should show "healthy" or "running."

### Step 4: Verify the API is running

```bash
curl http://localhost:8000/health
```

You should see:

```json
{
  "status": "ok",
  "model_loaded": true,
  "database": "ok",
  "redis": "ok",
  "runtime_mode": "prod",
  "shadow_mode": false,
  "platform": "Porter Intelligence Platform"
}
```

### Step 5: Start the frontend

```bash
cd dashboard-ui
npm install
npm run dev
```

The dashboard opens at http://localhost:3000

### Step 6: Log in

Open the Analyst workspace at http://localhost:3000/analyst

Login credentials (from your .env):
- Username: `admin` | Password: whatever you set for `PORTER_AUTH_ADMIN_PASSWORD`
- Username: `analyst_1` | Password: whatever you set for `PORTER_AUTH_ANALYST_PASSWORD`
- Username: `ops_manager` | Password: whatever you set for `PORTER_AUTH_OPS_MANAGER_PASSWORD`
- Username: `viewer` | Password: whatever you set for `PORTER_AUTH_VIEWER_PASSWORD`

---

## Option B: Local Development Setup (Without Docker)

Use this if you want to run the API directly for development.

### Step 1: Start PostgreSQL and Redis

```bash
# Using Docker for just the databases:
docker run -d --name porter-pg -p 5432:5432 \
  -e POSTGRES_USER=porter \
  -e POSTGRES_PASSWORD=porter \
  -e POSTGRES_DB=porter_intelligence \
  postgres:15-alpine

docker run -d --name porter-redis -p 6379:6379 redis:7-alpine
```

### Step 2: Create a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Set environment variables

```bash
cp .env.example .env
# Edit .env with real values (see Step 2 in Option A)
source .env  # Or use python-dotenv (automatic)
```

### Step 4: Start the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API starts at http://localhost:8000. Swagger docs at http://localhost:8000/docs.

### Step 5: Start the frontend

```bash
cd dashboard-ui
npm install
npm run dev
```

---

## Option C: Demo Mode (Synthetic Data + Digital Twin)

To run with the digital twin generating synthetic trip data continuously:

```bash
# In .env, set:
APP_RUNTIME_MODE=demo
ENABLE_SYNTHETIC_FEED=true

# Then start:
docker compose up --build -d
```

In demo mode:
- The digital twin generates trips across 22 cities
- Trips flow through the scoring pipeline automatically
- Cases appear in the analyst queue in real time
- No external data connection needed

### Controlling the digital twin

| Variable | Purpose | Default |
|---|---|---|
| `PORTER_TWIN_TRIPS_PER_MIN` | Trip generation rate | 30 |
| `PORTER_TWIN_SCALE_MULTIPLIER` | Volume multiplier | 1.0 |
| `PORTER_TWIN_DAILY_GROWTH_PCT` | Daily volume growth | 0.0 |
| `PORTER_TWIN_ACTIVE_CITIES` | Comma-separated city filter | all 22 |

---

## First Things To Try

Once the platform is running, try these in order:

### 1. Check system health

```bash
curl http://localhost:8000/health | python3 -m json.tool
```

### 2. Score a single trip

```bash
curl -X POST http://localhost:8000/fraud/score \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(curl -s -X POST http://localhost:8000/auth/token \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d 'username=admin&password=YOUR_ADMIN_PASSWORD' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')" \
  -d '{
    "trip_id": "TRIP-TEST-001",
    "driver_id": "DRV-TEST-001",
    "fare_inr": 1200,
    "distance_km": 5.2,
    "duration_minutes": 45,
    "pickup_zone": "koramangala",
    "dropoff_zone": "whitefield",
    "vehicle_type": "mini_truck",
    "payment_mode": "cash",
    "hour_of_day": 22,
    "day_of_week": 5,
    "is_surge": true
  }'
```

### 3. View the fraud heatmap

```bash
curl http://localhost:8000/fraud/heatmap \
  -H "Authorization: Bearer YOUR_TOKEN" | python3 -m json.tool
```

### 4. Check the KPI surface

```bash
curl http://localhost:8000/kpi/live \
  -H "Authorization: Bearer YOUR_TOKEN" | python3 -m json.tool
```

### 5. Open the dashboard

Navigate to http://localhost:3000 in your browser.

### 6. Open the Swagger docs

Navigate to http://localhost:8000/docs for the interactive API explorer.

---

## Stopping Everything

```bash
# Stop all services:
docker compose down

# Stop and remove all data volumes:
docker compose down -v
```

---

## Next Steps

- [Architecture Deep Dive](./02-architecture-deep-dive.md) — understand how everything connects
- [Demo Guide](./10-demo-guide.md) — run the full demo for a buyer meeting
- [API Reference](./04-api-reference.md) — explore all endpoints
