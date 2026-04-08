# Porter Intelligence Platform

Enterprise ML fraud detection, demand forecasting, and fleet intelligence for large-scale logistics operations.

## Documentation

- [Documentation Hub](./docs/README.md)
- [How It Works](./how%20it%20works/README.md)
- [Founder Work Pack](./founders%20work/README.md)

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

## Quick Start
```bash
./scripts/local_up.sh
```

Detailed deployment and runbooks:
- [One-Command Setup](./docs/deployment/one-command-setup.md)
- [Runbooks](./docs/runbooks/README.md)
- [Handover Package](./docs/handover/README.md)

## API

14 endpoints across 5 routers. Full documentation at `/docs` after startup.

Health check: `GET /health`
Fraud score: `POST /fraud/score`
Case management: `GET /cases/`
Analytics: `GET /kpi/summary`
