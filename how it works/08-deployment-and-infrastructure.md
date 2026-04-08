# 08 — Deployment And Infrastructure

[Index](./README.md) | [Prev: Security](./07-security-and-auth.md) | [Next: Testing](./09-testing-and-quality.md)

This document covers how to deploy the platform locally with Docker Compose and to production on AWS ECS Fargate, plus monitoring with Prometheus and Grafana.

---

## Local Deployment (Docker Compose)

### Services

The `docker-compose.yml` defines 5 services:

| Service | Image | Port | Purpose |
|---|---|---|---|
| `postgres` | postgres:15-alpine | 5432 | Primary database |
| `redis` | redis:7-alpine | 6379 | Stream transport + feature cache |
| `api` | Custom (Dockerfile) | 8000 | FastAPI application |
| `prometheus` | prom/prometheus:v2.49.0 | 9090 | Metrics collection |
| `grafana` | grafana/grafana:10.3.0 | 3001 | Metrics dashboards |

### Starting the stack

```bash
# Create .env from template:
cp .env.example .env
# Edit .env with real values (see 01-quickstart-tutorial.md)

# Build and start:
docker compose up --build -d

# Check health:
docker compose ps
curl http://localhost:8000/health
```

### Service dependencies

```
postgres ──(healthy)──→ api
redis ────(healthy)──→ api
api ──────────────────→ prometheus
prometheus ───────────→ grafana
```

The API waits for PostgreSQL and Redis healthchecks before starting.

### Data persistence

Three Docker volumes preserve data between restarts:

| Volume | Purpose |
|---|---|
| `postgres_data` | PostgreSQL database files |
| `prometheus_data` | Prometheus time-series data |
| `grafana_data` | Grafana dashboards and config |

### Stopping

```bash
# Stop services (keep data):
docker compose down

# Stop and delete all data:
docker compose down -v
```

---

## Dockerfile

The Dockerfile uses a two-stage build:

```dockerfile
FROM python:3.11-slim AS base
# Install build deps, copy requirements, pip install

FROM base AS production
# Copy application code
# Create data directories
# Healthcheck: curl /health every 30s
# CMD: uvicorn with 1 worker
```

### Health check

```
HEALTHCHECK --interval=30s --timeout=10s \
    --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

The 60-second start period allows time for model loading and database initialization.

### Port configuration

The container listens on port 8000 by default. Override with the `PORT` environment variable.

---

## AWS ECS Fargate Deployment

### Architecture

```
Internet → ALB (port 443) → ECS Service → Fargate Tasks (port 8000)
                                              │
                                              ├── RDS PostgreSQL 15
                                              └── ElastiCache Redis 7
```

### Deployment scripts

| Script | Purpose |
|---|---|
| `infrastructure/aws/setup.sh` | Create VPC, subnets, RDS, ElastiCache, ECR repo, ECS cluster |
| `infrastructure/aws/deploy.sh` | Build image, push to ECR, update ECS task definition, deploy |

### deploy.sh usage

```bash
# Set required variables:
export ACCOUNT_ID=123456789012
export REGION=ap-southeast-2

# Deploy with git SHA as image tag:
./infrastructure/aws/deploy.sh

# Deploy with specific tag:
./infrastructure/aws/deploy.sh v1.2.3
```

### What deploy.sh does

1. Reads infrastructure IDs from state file (created by setup.sh)
2. Builds Docker image
3. Pushes to ECR repository
4. Renders ECS task definition with secrets from AWS Secrets Manager
5. Registers new task definition revision
6. Updates ECS service to use new task definition
7. Waits for deployment to stabilize

### ECS Task Definition

Key settings in `infrastructure/aws/ecs-task-definition.json`:

| Setting | Value |
|---|---|
| CPU | 1024 (1 vCPU) |
| Memory | 2048 MB |
| Network mode | awsvpc |
| Log driver | awslogs |

### Secrets management

All sensitive values are stored in AWS Secrets Manager and injected into the container at runtime:

| Secret | Secrets Manager Key |
|---|---|
| `DATABASE_URL` | `porter/prod/database_url` |
| `REDIS_URL` | `porter/prod/redis_url` |
| `JWT_SECRET_KEY` | `porter/prod/jwt_secret_key` |
| `ENCRYPTION_KEY` | `porter/prod/encryption_key` |
| `WEBHOOK_SECRET` | `porter/prod/webhook_secret` |

---

## Monitoring

### Prometheus

**Config:** `infrastructure/prometheus.yml`

Prometheus scrapes the API's `/metrics` endpoint every 15 seconds. Available metrics:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `http_request_duration_seconds` | Histogram | method, path, status | Request latency |
| `http_requests_total` | Counter | method, path, status | Request count |
| `trips_scored_total` | Counter | tier, path | Trips scored by tier |
| `stream_lag` | Gauge | — | Redis Stream PEL count |

### Grafana

**Port:** 3001 (mapped from container port 3000)

Pre-provisioned dashboards are loaded from `infrastructure/grafana/provisioning/`.

**Access:**
- URL: `http://localhost:3001`
- Username: `admin`
- Password: `GRAFANA_ADMIN_PASSWORD` from `.env`

### Health endpoint

`GET /health` returns the status of all dependencies:

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

Use this for:
- Docker healthcheck
- Load balancer health target
- Uptime monitoring

---

## Scaling

### Current design (single worker)

The platform runs with 1 uvicorn worker. This is sufficient for:
- Demo environments
- Shadow mode validation (< 100K trips/day)
- Initial production deployment

### Horizontal scaling path

For higher throughput:

1. **Increase ECS task count**: Run multiple API containers behind the ALB
2. **Scale Redis consumers**: Each container runs its own stream consumer (`worker-N`)
3. **Move mutable state to PostgreSQL/Redis**: The `app_state` dict pattern works for single-replica only. Most scoring already uses the stateless path (Redis-backed features + model in memory).
4. **Consider Kafka**: If trip volume exceeds Redis Stream capacity (millions/day), migrate the stream transport to Kafka or Kinesis. The consumer pattern is identical.

### Database scaling

| Component | Current | Scaling Path |
|---|---|---|
| PostgreSQL | Single instance | RDS Multi-AZ for HA, read replicas for read-heavy queries |
| Redis | Single instance | ElastiCache cluster mode for HA |

---

## Environment Variables Reference

See the full list in [README.md](./README.md#environment-variables) or the `.env.example` file.

---

## Next

- [Testing and Quality](./09-testing-and-quality.md) — test suite and how to run it
- [Demo Guide](./10-demo-guide.md) — running the demo
