# Deployment Runbook

Step-by-step bring-up of the Porter Intelligence Platform. Assumes a
fresh clone of the repository on a Linux/macOS host with Python 3.11+,
Node 20+, PostgreSQL 14+, and Redis 7+ installed.

---

## 1. Clone and bootstrap

```bash
git clone <repo-url> porter-intelligence
cd porter-intelligence
cp .env.example .env
```

Edit `.env` and set, at minimum:

- `JWT_SECRET_KEY` — 32+ random bytes, base64
- `ENCRYPTION_KEY` — 32-byte Fernet key
- `WEBHOOK_SECRET` — shared secret for inbound webhook signing
- `PORTER_AUTH_ADMIN_PASSWORD` — admin bootstrap password
- `PORTER_AUTH_OPS_MANAGER_PASSWORD`
- `PORTER_AUTH_ANALYST_PASSWORD`
- `DATABASE_URL` — async SQLAlchemy URL, e.g.
  `postgresql+asyncpg://user:pass@localhost/porter`
- `REDIS_URL` — e.g. `redis://localhost:6379/0`

Optional per-deployment overrides live in `config/commercial.py`; see
`docs/architecture.md` § 5.

---

## 2. Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run migrations:

```bash
PYTHONPATH=$(pwd) ./venv/bin/alembic upgrade head
```

Start the API:

```bash
PYTHONPATH=$(pwd) ./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8002
```

Smoke test:

```bash
curl -s http://localhost:8002/health
# {"status":"ok", ...}

TOKEN=$(curl -s -X POST http://localhost:8002/auth/token \
  -d "username=admin&password=$PORTER_AUTH_ADMIN_PASSWORD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8002/cases?limit=5
```

---

## 3. Dashboard

```bash
cd dashboard-ui
npm install
npm run build
```

Local preview:

```bash
npm run dev
# http://localhost:5173
```

Deploy to Vercel:

```bash
vercel --prod
```

`vercel.json` rewrites `/api/:path*` to the backend host. Set the backend
URL as a Vercel env var and redeploy when the host changes.

---

## 4. Verify end-to-end

From the Vercel URL:

1. Log in with an administrator-issued account.
2. Open the analyst queue — expect 5+ cases from the benchmark seed.
3. Open a case — trip map, driver profile, evidence timeline all render.
4. Open the manager view — KPI cards render with a visible
   `data_source: synthetic_benchmark` label until live data arrives.

From the API:

```bash
bash scripts/verify_endpoints.sh
```

Expected: 200 on every authenticated route, 401 on `/fraud/score`
without a token.

---

## 5. Model retraining

See `docs/runbooks/retrain-model.md`. After retraining, inspect
`model/weights/two_stage_config.json`; the action and watchlist
thresholds are read from this file at call time, no deploy required.

---

## 6. Adding a city

See `docs/runbooks/add-a-city.md`. Seeds, heatmap tiles, and zone
polygons are all driven from data files under `data/` — no code changes.

---

## 7. Rolling back

- Dashboard: `vercel rollback` to the previous deployment.
- Backend: redeploy the previous image tag or restart uvicorn with the
  previous release branch. Schema migrations are forward-only; coordinate
  rollbacks with DB operator.

---

## 8. Operational concerns

- **Secrets**: rotate via `docs/runbooks/rotate-secrets.md`.
- **Backups**: PostgreSQL nightly snapshot + retention per
  infrastructure policy. Redis is ephemeral.
- **Logs**: uvicorn stdout is JSON-structured; ship to the platform's
  log sink of choice.
- **Rate limits**: enforced at the API layer in
  `api/middleware/ratelimit.py`; Vercel enforces additional edge limits.
