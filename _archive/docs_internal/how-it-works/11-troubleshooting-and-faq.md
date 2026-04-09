# 11 — Troubleshooting And FAQ

[Index](./README.md) | [Prev: Demo Guide](./10-demo-guide.md)

This document covers every common issue you might encounter, how to diagnose it, how to fix it, and answers to frequently asked questions.

---

## Quick Diagnostics

Before diving into specific issues, run these three commands to understand the current state:

```bash
# 1. Check if all services are running:
docker compose ps

# 2. Check API health and dependency status:
curl -s http://localhost:8000/health | python3 -m json.tool

# 3. Check API logs for errors:
docker compose logs api --tail 50
```

The `/health` endpoint returns the state of every dependency:

```json
{
  "status": "ok",
  "model_loaded": true,
  "database": "ok",
  "redis": "ok",
  "runtime_mode": "demo",
  "shadow_mode": false,
  "security_ready": true,
  "security_warnings": []
}
```

If `status` is `"degraded"`, the database is unreachable. If `model_loaded` is `false`, the XGBoost model file is missing. If `security_ready` is `false`, check `security_warnings` for details.

---

## Startup Issues

### API container won't start

**Symptom:** `docker compose ps` shows the `api` container as `restarting` or `exited`.

**Check logs:**

```bash
docker compose logs api --tail 100
```

**Common causes:**

| Log message | Cause | Fix |
|---|---|---|
| `Security configuration invalid for prod runtime` | Missing or placeholder secrets in prod mode | Set real values for `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `WEBHOOK_SECRET`, and all `PORTER_AUTH_*_PASSWORD` vars in `.env`. Or set `APP_RUNTIME_MODE=demo` for development. |
| `Connection refused...port 5432` | PostgreSQL not ready yet | The API depends on the PostgreSQL healthcheck. Wait 30 seconds and check again. If it persists, check `docker compose logs postgres`. |
| `Connection refused...port 6379` | Redis not ready yet | Same as above — wait for Redis healthcheck. Check `docker compose logs redis`. |
| `ModuleNotFoundError: No module named 'xgboost'` | Dependencies not installed in container | Run `docker compose build --no-cache api` to rebuild the image. |
| `ENCRYPTION_KEY must be configured` | Missing or placeholder encryption key | Generate a key: `python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"` and set it in `.env`. |

### API starts but shows security warnings

**Symptom:** Health endpoint returns `"security_ready": false` with warnings.

This happens when environment variables contain placeholder values. The platform recognises these as placeholders:

- Values starting with `replace-` or `change-`
- Values like `change-me`, `replace-with-*`, `your-*`
- Empty strings

**Fix:** Replace every placeholder in `.env` with real values:

```bash
# Generate JWT secret:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Generate encryption key:
python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

# Generate webhook secret:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Set strong passwords for seed users (at least 12 characters, mixed case + symbols)
```

In **demo mode** (`APP_RUNTIME_MODE=demo`), placeholder values produce warnings but the API still starts. In **prod mode**, they cause hard errors and the API refuses to start.

### "Warning: Model not found. Run python train.py first."

**Symptom:** API starts but `model_loaded` is `false` in the health check. Scoring returns fallback results.

**Cause:** The file `model/weights/xgb_fraud_model.json` does not exist.

**Fix:**

```bash
# Option 1: Train the model (requires trip data in data/raw/):
python model/train.py

# Option 2: If you don't have training data, the API still works.
# Scoring will use a default threshold of 0.45 and may return
# less accurate results. The rest of the platform (cases, 
# ingestion, dashboard) works normally.
```

### "No trip data found" / "No driver data found"

**Symptom:** Console shows these warnings at startup. Dashboard KPIs show zeros.

**Cause:** No CSV data files in `data/raw/`. The API looks for:

- `data/raw/trips_full_fraud.csv` (preferred) or `data/raw/trips_with_fraud_10k.csv`
- `data/raw/drivers_full.csv` (preferred) or `data/raw/drivers_sample_1000.csv`

**Fix:**

```bash
# Generate synthetic data:
python generator/trips.py
python generator/drivers.py

# Or use the sample data:
ls data/samples/
```

The API works without data files — it runs in "CSV-only mode" where endpoints that depend on preloaded data will return empty results, but ingestion, scoring (with model), and case management still function.

---

## Database Issues

### PostgreSQL connection refused

**Symptom:** Health endpoint shows `"database": "unavailable"`. API logs show `Connection refused` on port 5432.

**Check:**

```bash
# Is PostgreSQL running?
docker compose ps postgres

# Check PostgreSQL logs:
docker compose logs postgres --tail 30

# Test connection directly:
docker compose exec postgres pg_isready -U porter
```

**Common causes:**

| Cause | Fix |
|---|---|
| Container not started | `docker compose up -d postgres` |
| Port 5432 already in use by host PostgreSQL | Stop host PostgreSQL: `brew services stop postgresql` (macOS) or change the port mapping in `docker-compose.yml` |
| Volume corruption | `docker compose down -v && docker compose up -d` (destroys all data) |
| Wrong `DATABASE_URL` in `.env` | Default is `postgresql+asyncpg://porter:porter@localhost:5432/porter_intelligence`. For Docker, use `localhost` (not `postgres`) since the API runs on the host network during development. |

### Database timeout at startup

**Symptom:** Console shows `Database timeout — running without DB`.

The API gives PostgreSQL 10 seconds to respond during startup. If it takes longer:

```bash
# Check if PostgreSQL is still initializing:
docker compose logs postgres --tail 10

# Wait and restart the API:
docker compose restart api
```

This can happen on first run when PostgreSQL creates the database and runs initial setup. Subsequent starts are fast.

### Tables not created

**Symptom:** API calls return `relation "fraud_cases" does not exist` or similar.

Tables are created automatically at startup via `init_db()`. If this fails:

```bash
# Check that the database exists:
docker compose exec postgres psql -U porter -d porter_intelligence -c "\dt"

# If the database doesn't exist, create it:
docker compose exec postgres createdb -U porter porter_intelligence

# Restart the API to trigger table creation:
docker compose restart api
```

---

## Redis Issues

### Redis connection refused

**Symptom:** Health endpoint shows `"redis": "unavailable"`. Stream consumer and feature cache are disabled.

**Check:**

```bash
docker compose ps redis
docker compose logs redis --tail 20
docker compose exec redis redis-cli ping
```

**Impact of Redis being down:**

| Feature | Without Redis |
|---|---|
| Stream ingestion | Falls back to inline scoring (synchronous) |
| Feature cache | Falls back to in-memory computation (slower) |
| Rate limiting | Falls back to in-memory limiter (per-process only) |
| Staging drain | Trips buffered to PostgreSQL, drained when Redis returns |

The platform is designed to degrade gracefully without Redis. Scoring still works, but at lower throughput.

### Redis Stream consumer not processing

**Symptom:** Trips are published but not scored. Stream grows without being consumed.

**Check:**

```bash
# Check stream length:
docker compose exec redis redis-cli XLEN porter:trips

# Check consumer group info:
docker compose exec redis redis-cli XINFO GROUPS porter:trips

# Check pending entries (unacknowledged):
docker compose exec redis redis-cli XPENDING porter:trips scoring-workers - + 10
```

**Common causes:**

| Cause | Fix |
|---|---|
| Consumer group doesn't exist | It is created on first publish. Restart the API. |
| Consumer crashed | Check `docker compose logs api` for stream consumer errors. Restart the API. |
| Messages stuck in PEL | Unacknowledged messages stay in the Pending Entries List. Restart the API — the consumer will re-read pending messages. |

---

## Frontend Issues

### Dashboard shows "API Offline" or connection error

**Symptom:** The dashboard at `http://localhost:3000` shows a retry screen.

**Check:**

```bash
# Is the API running?
curl http://localhost:8000/health

# Is the frontend pointing to the right API?
cat dashboard-ui/.env.production
```

**Common causes:**

| Cause | Fix |
|---|---|
| API not running | Start it: `docker compose up -d` |
| CORS blocking requests | Check that `API_ALLOWED_ORIGINS` in `.env` includes `http://localhost:3000` |
| Frontend pointing to wrong URL | For development, the frontend defaults to `http://localhost:8000`. Check `VITE_API_BASE_URL` in `.env.production` if using a production build. |
| Browser cache | Hard refresh: `Cmd+Shift+R` (macOS) or `Ctrl+Shift+R` (Windows/Linux) |

### Login fails on Analyst page

**Symptom:** Entering credentials on `/analyst` returns an error.

**Check:**

```bash
# Test login directly:
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=analyst_1&password=YOUR_PASSWORD_HERE"
```

**Common causes:**

| Cause | Fix |
|---|---|
| Wrong password | Use the password you set in `PORTER_AUTH_ANALYST_PASSWORD` in `.env` |
| Placeholder password in `.env` | Replace `replace-with-strong-password` with an actual password |
| Rate limited (10/min on auth endpoint) | Wait 60 seconds and try again |
| API not running | Start the API first |

**Default seed usernames:**

| Username | Role | Password env var |
|---|---|---|
| `admin` | admin | `PORTER_AUTH_ADMIN_PASSWORD` |
| `ops_manager` | ops_manager | `PORTER_AUTH_OPS_MANAGER_PASSWORD` |
| `analyst_1` | ops_analyst | `PORTER_AUTH_ANALYST_PASSWORD` |
| `viewer` | read_only | `PORTER_AUTH_VIEWER_PASSWORD` |

### KPI panel shows all zeros

**Symptom:** Dashboard loads but all KPI values are 0.

**Causes:**

1. **No trip data loaded**: Check health endpoint — if `trips_loaded` is 0, see "No trip data found" above.
2. **No cases created**: Cases are created when trips are scored at action or watchlist tier. Use the Trip Scorer to score some trips, or enable the synthetic feed (`ENABLE_SYNTHETIC_FEED=true`).
3. **Database not connected**: KPIs that come from reviewed cases require PostgreSQL.

---

## Scoring Issues

### Trip scoring returns unexpected results

**Symptom:** Scoring a clearly suspicious trip returns a low fraud probability, or a clean trip returns high.

**Check:**

```bash
# Verify model is loaded:
curl -s http://localhost:8000/health | python3 -m json.tool | grep model_loaded

# Check the threshold:
curl -s http://localhost:8000/health | python3 -m json.tool | grep threshold

# Check two-stage config:
cat model/weights/two_stage_config.json
```

**Things to verify:**

1. **Model loaded**: If `model_loaded` is `false`, scoring uses fallback logic.
2. **Feature values**: The model uses 35 features. Missing or zero features skew results. Ensure the trip payload includes realistic values for fare, distance, duration, payment mode, etc.
3. **Threshold**: The default threshold is 0.45. If the trained model produced a different optimal threshold, it is saved in `model/weights/threshold.json`.

### "Feature engineering produced NaN"

**Symptom:** Scoring fails with NaN-related errors.

**Cause:** Input data has missing or invalid values that cause division by zero in feature engineering (e.g., `distance_km = 0` causes `fare_per_km` to be infinity).

**Fix:** Ensure trip data has sensible values:

- `distance_km` > 0
- `duration_min` > 0
- `fare_amount` > 0

The feature engineering code handles most edge cases, but zero distance or duration will produce undefined ratios.

---

## Ingestion Issues

### Webhook returns 401

**Symptom:** `POST /ingest/trip-completed` returns 401 Unauthorized.

**Cause:** HMAC signature verification failed.

**Check:**

In production mode, webhook requests must include a valid `X-Porter-Signature` header:

```bash
# Generate the correct signature:
BODY='{"trip_id": "test", ...}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')

curl -X POST http://localhost:8000/ingest/trip-completed \
  -H "Content-Type: application/json" \
  -H "X-Porter-Signature: sha256=$SIGNATURE" \
  -d "$BODY"
```

In demo mode, unsigned webhooks are accepted by default (`ALLOW_UNSIGNED_WEBHOOKS=true`).

### Batch CSV upload fails

**Symptom:** `POST /ingest/batch-csv` returns errors.

**Common causes:**

| Error | Fix |
|---|---|
| Missing required columns | Check `GET /ingest/schema-map/default` to see expected field names and their aliases |
| File too large | The default upload limit is set by the web server. For very large files, split into smaller batches. |
| Wrong content type | Must be `multipart/form-data` with the file field named `file` |

**Example working upload:**

```bash
curl -X POST http://localhost:8000/ingest/batch-csv \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/samples/porter_sample_10_trips.csv"
```

### Staged trips not draining

**Symptom:** Trips were buffered to PostgreSQL staging (Redis was down), but they are not being replayed.

**Check:**

```bash
# Check staging queue status:
curl -s http://localhost:8000/ingest/queue-status \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

The staging drain runs automatically when Redis comes back online. You can also trigger it manually:

```bash
curl -X POST http://localhost:8000/ingest/drain-staging \
  -H "Authorization: Bearer $TOKEN"
```

---

## Shadow Mode Issues

### Cases not appearing in analyst queue

**Symptom:** Trips are being scored but no cases show up at `/analyst`.

**Check shadow mode status:**

```bash
curl -s http://localhost:8000/shadow/status | python3 -m json.tool
```

If `shadow_mode` is `true`, cases are written to the `shadow_cases` table, not `fraud_cases`. The analyst queue only shows `fraud_cases`.

**Fix:** Set `SHADOW_MODE=false` in `.env` and restart the API to create cases in the main table.

### Enforcement not firing

**Symptom:** Action-tier cases are created but no enforcement webhook is sent.

**Three things suppress enforcement:**

1. **Shadow mode is on**: Set `SHADOW_MODE=false`.
2. **No dispatch URL configured**: Set `PORTER_DISPATCH_URL` in `.env` to Porter's webhook endpoint.
3. **Tier is not action**: Only action-tier trips (>= 0.94 probability) trigger enforcement.

**Test the dispatch connection:**

```bash
curl -X POST http://localhost:8000/webhooks/dispatch/test
```

This sends a test payload and reports whether the dispatch URL is configured and reachable.

---

## Environment Variable Issues

### Which variables are required?

The minimum set to start the API in **demo mode**:

```bash
APP_RUNTIME_MODE=demo
DATABASE_URL=postgresql+asyncpg://porter:porter@localhost:5432/porter_intelligence
REDIS_URL=redis://localhost:6379
```

In demo mode, placeholder secrets produce warnings but the API starts.

The minimum set for **production mode** (all must be real values, not placeholders):

```bash
APP_RUNTIME_MODE=prod
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/porter_intelligence
REDIS_URL=redis://host:6379
JWT_SECRET_KEY=<random 48+ character string>
ENCRYPTION_KEY=<base64-encoded 32-byte key>
WEBHOOK_SECRET=<random 48+ character string>
API_ALLOWED_ORIGINS=https://your-domain.com
PORTER_AUTH_ADMIN_PASSWORD=<strong password>
PORTER_AUTH_OPS_MANAGER_PASSWORD=<strong password>
PORTER_AUTH_ANALYST_PASSWORD=<strong password>
PORTER_AUTH_VIEWER_PASSWORD=<strong password>
```

### Runtime mode not taking effect

**Symptom:** You set `APP_RUNTIME_MODE=demo` but the health endpoint shows `prod`.

**Check:**

1. `.env` file is in the project root (same directory as `docker-compose.yml`)
2. No conflicting `APP_ENV` variable overriding the mode
3. You restarted the API after changing `.env`: `docker compose restart api`

The mode resolution order is:
1. `APP_RUNTIME_MODE` (checked first)
2. `APP_ENV` (fallback)
3. Default: `prod`

Accepted values for demo mode: `demo`, `sandbox`, `staging`
Accepted values for prod mode: `prod`, `production`, `live`

### CORS errors in browser console

**Symptom:** Browser console shows `Access-Control-Allow-Origin` errors. API calls from the dashboard fail.

**Fix:** Add the frontend URL to `API_ALLOWED_ORIGINS` in `.env`:

```bash
# For local development:
API_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# For production:
API_ALLOWED_ORIGINS=https://your-dashboard-domain.com,https://your-api-domain.com
```

In demo mode, if `API_ALLOWED_ORIGINS` is not set, `localhost:3000` and `localhost:8000` are allowed by default.

---

## Docker Issues

### Build fails

**Symptom:** `docker compose build` fails.

**Common causes:**

| Error | Fix |
|---|---|
| `pip install` fails | Check `requirements.txt` for version conflicts. Try `docker compose build --no-cache`. |
| Disk space | Docker needs several GB for images. Run `docker system prune` to free space. |
| Network errors during build | Check internet connection. Pip needs to download packages. |

### Out of memory

**Symptom:** Container gets OOM-killed. Docker logs show `Killed`.

The API loads the XGBoost model, trip data, and driver data into memory at startup. Memory usage depends on data size:

| Data size | Approx memory |
|---|---|
| 10K trips, 1K drivers | ~200 MB |
| 100K trips, 10K drivers | ~500 MB |
| 500K trips, 50K drivers | ~1.5 GB |

**Fix:** Increase Docker's memory limit. In Docker Desktop: Settings > Resources > Memory. Set to at least 4 GB.

For the ECS task definition, the default is 2048 MB. Scale up if loading large datasets.

### Volumes and data persistence

```bash
# List volumes:
docker volume ls | grep porter

# Inspect a volume:
docker volume inspect porter_postgres_data

# Remove all data and start fresh:
docker compose down -v
docker compose up --build -d
```

---

## Testing Issues

### Tests fail with missing environment variables

**Symptom:** `pytest` fails with `SecurityConfigurationError` or missing env var errors.

**Fix:** The `tests/conftest.py` autouse fixture sets all required env vars automatically. If tests still fail:

1. Make sure you are running from the project root: `pytest tests/ -v`
2. Check that `conftest.py` is in the `tests/` directory
3. Check that no `.env` file is overriding test values (the monkeypatch fixture takes precedence)

### Tests fail with import errors

**Symptom:** `ModuleNotFoundError` when running tests.

**Fix:**

```bash
# Activate virtual environment:
source venv/bin/activate

# Install all dependencies:
pip install -r requirements.txt

# Run from project root:
cd /path/to/Porter
pytest tests/ -v
```

### Tests pass locally but fail in Docker

**Symptom:** Tests work on your machine but fail in the container.

**Common causes:**

1. **Different Python version**: The Dockerfile uses Python 3.11. Check your local version.
2. **Missing system dependencies**: Some packages need system libraries (e.g., `libpq-dev` for psycopg2).
3. **Path differences**: Tests use relative paths from project root. Ensure the working directory is correct.

---

## Performance Issues

### API response time is slow

**Symptom:** Scoring requests take more than 1 second.

**Check:**

1. **First request after startup**: The first scoring request is slower because it warms up caches. Subsequent requests are fast.
2. **Redis unavailable**: Without Redis, every scoring request recomputes features from scratch instead of using cached values.
3. **Large dataset**: If `trips_loaded` is very large (500K+), feature lookups are slower.

**Monitoring:**

```bash
# Check Prometheus metrics (if enabled):
curl -s http://localhost:8000/metrics | grep http_request_duration
```

### Startup takes too long

The API performs multiple initialization steps:

| Step | Typical time |
|---|---|
| Load XGBoost model | < 1 second |
| Load trip/driver CSVs | 1-5 seconds (depends on file size) |
| Precompute feature store (Redis) | 5-15 seconds |
| Precompute efficiency cache | 5-15 seconds |
| Precompute driver risk cache | 3-10 seconds |
| Initialize database tables | 1-2 seconds |
| Start stream consumer | < 1 second |
| Start live simulator (demo mode) | < 1 second |

Total: 15-45 seconds depending on data size and Redis availability.

Each step has a timeout. If a step times out, it is skipped with a warning and the API continues. The Docker healthcheck has a 60-second start period to accommodate this.

---

## Frequently Asked Questions

### Can I run just the API without Docker?

Yes. You need PostgreSQL and Redis running somewhere (locally or remotely):

```bash
# Set up .env with your database and Redis URLs
cp .env.example .env
# Edit .env

# Install dependencies:
pip install -r requirements.txt

# Start the API:
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Can I run without PostgreSQL?

Partially. The API will start and log `Database unavailable: running in CSV-only mode`. You can:

- Score trips (if the model is loaded)
- View preloaded data from CSV files
- Use the dashboard for basic metrics

You cannot:

- Create or review cases
- Use the analyst workflow
- Persist any data across restarts
- Use shadow mode

### Can I run without Redis?

Yes. The platform degrades gracefully:

- Ingestion falls back to inline scoring (synchronous, slower)
- Feature cache uses in-memory fallback
- Rate limiting uses in-memory store
- Stream consumer is disabled
- Trips needing async processing are buffered to PostgreSQL staging table

### How do I switch between demo and production mode?

Edit `.env`:

```bash
# Demo mode (relaxed security, synthetic feed enabled):
APP_RUNTIME_MODE=demo

# Production mode (strict security, no synthetic data):
APP_RUNTIME_MODE=prod
```

Then restart: `docker compose restart api`

Key differences:

| Behaviour | Demo | Prod |
|---|---|---|
| Placeholder secrets | Warning | Hard error (API won't start) |
| Synthetic feed | Enabled by default | Always disabled |
| Plaintext PII | Allowed (if `ALLOW_PLAINTEXT_PII=true`) | Never allowed |
| Unsigned webhooks | Accepted by default | Rejected (signature required) |
| CORS defaults | localhost allowed | No defaults (must configure) |

### How do I reset everything and start fresh?

```bash
# Nuclear reset (deletes all data):
docker compose down -v
docker compose up --build -d

# Soft reset (demo data only):
curl -X POST http://localhost:8000/demo/reset \
  -H "Authorization: Bearer $TOKEN"
```

### How do I add a new user role?

User roles are defined in `auth/models.py`. To add a new role:

1. Add the role to the `UserRole` enum
2. Add permissions to the `ROLE_PERMISSIONS` dict
3. Add a seed user entry in `auth/config.py`
4. Add the password environment variable to `.env`
5. Update `tests/conftest.py` with the new env var

### How do I connect Porter's real data feed?

1. Set up the schema mapper for Porter's field names:
   ```bash
   # Check the current mapping:
   curl http://localhost:8000/ingest/schema-map/default
   
   # If Porter uses different field names, create a custom mapping file
   # and set SCHEMA_MAP_FILE in .env
   ```

2. Configure the webhook endpoint in Porter's system to point to:
   ```
   POST https://your-api-host/ingest/trip-completed
   ```

3. Set the `WEBHOOK_SECRET` in both systems for HMAC verification.

4. Start in shadow mode first:
   ```bash
   SHADOW_MODE=true
   ```

5. Monitor for 30-60 days, then switch to live mode.

### What is the difference between shadow mode and demo mode?

| | Demo mode | Shadow mode |
|---|---|---|
| Purpose | Development and demonstrations | Production validation |
| Data source | Synthetic (digital twin) | Real Porter data |
| Cases stored in | `fraud_cases` table | `shadow_cases` table |
| Enforcement | Suppressed | Suppressed |
| Security | Relaxed | Full production security |
| When to use | Demos, development, testing | First 30-60 days of real deployment |

Shadow mode is a production feature. Demo mode is a development feature. They can be combined (shadow + demo), but typically are not.

### How do I check if the model is performing well?

```bash
# View the evaluation report:
curl -s http://localhost:8000/kpi/report \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# View live KPI surface (from reviewed cases):
curl -s http://localhost:8000/kpi/live \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

The key metrics to watch:

| Metric | Good | Bad |
|---|---|---|
| Reviewed-case precision | >= 85% | < 70% |
| False alarm rate | <= 8% | > 15% |
| Action-tier precision | >= 90% | < 80% |
| 24h throughput | > 0 | 0 (nothing being reviewed) |

### Where are the logs?

| Log source | How to access |
|---|---|
| API application logs | `docker compose logs api` |
| PostgreSQL logs | `docker compose logs postgres` |
| Redis logs | `docker compose logs redis` |
| Prometheus logs | `docker compose logs prometheus` |
| Grafana logs | `docker compose logs grafana` |
| Enforcement dispatch | Logged to API logs with `ENFORCEMENT:` prefix |
| Audit trail (analyst decisions) | `GET /cases/{id}/history` API endpoint |

To follow logs in real time:

```bash
docker compose logs -f api
```

To set log verbosity:

```bash
# In .env:
LOG_LEVEL=debug   # debug, info, warning, error
```

---

## Error Reference

Quick lookup for specific error messages:

| Error | Where | Meaning | Fix |
|---|---|---|---|
| `SecurityConfigurationError` | Startup | Required security env var missing or placeholder | Set real values in `.env` |
| `401 Unauthorized` | Any authenticated endpoint | JWT token missing, expired, or invalid | Re-authenticate via `POST /auth/token` |
| `403 Forbidden` | Any authorized endpoint | User's role lacks the required permission | Use a user with the correct role |
| `429 Too Many Requests` | Rate-limited endpoints | Rate limit exceeded | Wait and retry. Limits: auth 10/min, scoring 100/min, ingestion 300/min |
| `503 Service Unavailable` | Startup | Security validation failed in prod mode | Fix all security configuration errors |
| `connection refused :5432` | Startup or health | PostgreSQL unreachable | Start PostgreSQL, check `DATABASE_URL` |
| `connection refused :6379` | Startup or health | Redis unreachable | Start Redis, check `REDIS_URL` |
| `HMAC signature mismatch` | `POST /ingest/trip-completed` | Webhook signature invalid | Check `WEBHOOK_SECRET` matches between sender and receiver |
| `Override reason required` | `PATCH /cases/{id}` | Dismissing an action-tier case as false alarm | Provide `override_reason` field in the request body |

---

## Getting Help

If this guide does not solve your issue:

1. **Check the API docs**: `http://localhost:8000/docs` (Swagger UI with every endpoint documented)
2. **Check the source code**: Each module has docstrings explaining its purpose
3. **Run the test suite**: `pytest tests/ -v` — failing tests often reveal configuration issues
4. **Check the health endpoint**: `GET /health` — the single best diagnostic tool

---

## Document Index

| # | Document | What it covers |
|---|---|---|
| 00 | [README](./README.md) | Documentation hub, project structure, environment variables |
| 01 | [Quickstart Tutorial](./01-quickstart-tutorial.md) | Three ways to get the platform running |
| 02 | [Architecture Deep Dive](./02-architecture-deep-dive.md) | Full system architecture and data flow |
| 03 | [Data and ML Pipeline](./03-data-and-ml-pipeline.md) | Feature engineering, XGBoost, Prophet, scoring |
| 04 | [API Reference](./04-api-reference.md) | Every endpoint with request/response examples |
| 05 | [Ingestion and Shadow Mode](./05-ingestion-and-shadow-mode.md) | Three ingestion paths, Redis Streams, shadow mode |
| 06 | [Frontend and Dashboard](./06-frontend-and-dashboard.md) | React app structure, pages, components |
| 07 | [Security and Auth](./07-security-and-auth.md) | Encryption, JWT, RBAC, rate limiting, audit logging |
| 08 | [Deployment and Infrastructure](./08-deployment-and-infrastructure.md) | Docker, AWS ECS, Prometheus, Grafana |
| 09 | [Testing and Quality](./09-testing-and-quality.md) | Test suite, fixtures, how to run |
| 10 | [Demo Guide](./10-demo-guide.md) | 15-minute walkthrough, scenarios, reset |
| 11 | [Troubleshooting and FAQ](./11-troubleshooting-and-faq.md) | This document |
