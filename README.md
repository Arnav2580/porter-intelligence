# Porter Intelligence Platform

Enterprise ML fraud detection, demand forecasting, and fleet intelligence for large-scale logistics operations.

## Modules

- **Fraud Detection** — XGBoost two-stage classifier, 88.3% action-tier precision, 0.53% FPR
- **Demand Forecasting** — Prophet models per zone, surge detection, 24-hour horizon
- **Driver Intelligence** — 30-day risk timeline, ring detection, peer comparison
- **Route Efficiency** — Dead mile analysis, vehicle utilisation, reallocation engine

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI, asyncpg, SQLAlchemy |
| ML | XGBoost, Prophet, scikit-learn |
| Storage | PostgreSQL, Redis Streams |
| Ingestion | Redis Streams consumer pipeline |
| Frontend | React, Vite, Leaflet |
| Observability | Prometheus, Grafana, APScheduler |
| Security | AES-256-GCM, JWT, RBAC |
| Infrastructure | AWS ECS Fargate, RDS, ElastiCache |

## Setup
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
uvicorn api.main:app --port 8000
```

## API

14 endpoints across 5 routers. Full documentation at `/docs` after startup.

Health check: `GET /health`
Fraud score: `POST /fraud/score`
Case management: `GET /cases/`
Analytics: `GET /kpi/summary`
