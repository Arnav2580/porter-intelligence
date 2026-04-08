# One-Command Setup

[Docs Hub](../README.md) | [Runbooks](../runbooks/README.md)

Objective:
- start the platform in a reproducible local environment with one main path

## Prerequisites

- Python 3.9+ for local development
- Docker Desktop for local infrastructure
- Node.js 20+ for the React dashboard build
- a populated `.env` copied from `.env.example`

## Recommended Quick Start

Primary path:

```bash
./scripts/local_up.sh
```

What the script does:

- creates `venv` if needed
- installs Python dependencies
- copies `.env.example` to `.env` if missing
- starts PostgreSQL and Redis with `docker compose`
- starts the FastAPI backend
- verifies `GET /health`

Manual path if you want each step explicitly:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Dashboard UI:

```bash
cd dashboard-ui
npm install
npm run dev
```

## What Starts

- PostgreSQL for persistent operational records
- Redis for queue/cache behavior
- FastAPI backend on `:8000`
- React dashboard in local development mode

## Verification

Run:

```bash
curl http://localhost:8000/health
```

Healthy signals to expect:
- `status: ok`
- `database: ok`
- `redis: ok`
- `model_loaded: true`

## Runtime Modes

- `prod`
  - synthetic feed disabled
  - security validation enforced
- `demo`
  - synthetic feed allowed if explicitly enabled
- `shadow`
  - flagged cases stored in `shadow_cases`
  - enforcement disabled

## Troubleshooting

Backend does not start:
- verify `.env` exists
- verify Docker is running
- verify `JWT_SECRET_KEY` and `ENCRYPTION_KEY` are set
- inspect `logs/local-api.log`

Dashboard cannot connect:
- confirm API is running on `:8000`
- check `VITE_API_BASE_URL` in `dashboard-ui/.env.production` or local shell

Database unavailable:
- restart `docker compose up -d`
- verify `DATABASE_URL`
