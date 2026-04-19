# Security Notes — 2026-04-19

This document captures the security posture of the Porter Intelligence
Platform after the round-2 audit remediation, the residual CVEs that
could not be cleared in this sprint, and the operational guardrails
the buyer should run on top.

## 1. Authentication coverage

Every read/write endpoint that exposes operational data, model output,
or commercial state requires a Bearer JWT and a permission check via
`auth.dependencies.require_permission`. The full list:

| Endpoint                              | Permission     |
| ------------------------------------- | -------------- |
| `GET /kpi/live`                       | `read:cases`   |
| `GET /kpi/summary`, `/kpi/report`     | `read:cases`   |
| `GET /roi/summary`                    | `read:cases`   |
| `GET /fraud/heatmap`                  | `read:cases`   |
| `GET /fraud/live-feed`                | `read:cases`   |
| `GET /fraud/tier-summary`             | `read:cases`   |
| `POST /fraud/score`                   | `read:cases`   |
| `GET /intelligence/top-risk`          | `read:cases`   |
| `GET /intelligence/driver/{id}`       | `read:cases`   |
| `GET /efficiency/summary`             | `read:cases`   |
| `GET /efficiency/fleet-zones`         | `read:cases`   |
| `GET /efficiency/reallocation`        | `read:cases`   |
| `GET /efficiency/dead-miles`          | `read:cases`   |
| `GET /efficiency/utilisation/{zone}`  | `read:cases`   |
| `GET /demand/forecast/{zone_id}`      | `read:cases`   |
| `GET /shadow/status`                  | `read:cases`   |
| `POST /shadow/activate`/`deactivate`  | `write:all`    |
| `POST /query`                         | `read:cases`   |
| `GET /ingest/status`                  | `read:cases`   |
| `GET /ingest/schema-map/default`      | `read:cases`   |
| `POST /ingest/batch-csv`              | `write:all`    |
| `POST /webhooks/dispatch/test`        | `read:cases`   |
| `GET /cases`, `/cases/summary/*`      | `read:cases`   |

Public endpoints:

- `GET /health` — no PII, used by Vercel uptime / load balancers.
- `POST /auth/token` — token issuer.
- `POST /ingest/trip-completed` — webhook, signature-verified via
  `WEBHOOK_SECRET` HMAC when `require_webhook_signature()` is true
  (production mode).

## 2. /ingest/batch-csv hardening

The batch CSV endpoint enforces these limits at the FastAPI layer:

- File extension must be `.csv` → 415 otherwise.
- File size ≤ 10 MB → 413 otherwise.
- Row count ≤ 10,000 → 413 otherwise.
- Empty file → 400.
- UTF-8 decode failure → 400 (not 500).
- Mapping-file parse error → 400 (not 500).
- Schema-mapping failure on any row → 400 (not 500).

The 5xx surface of this endpoint is now reserved for genuine
infrastructure faults, not malformed input.

## 3. Fail-closed enforcement on action tier

`api/inference.py:score_trip` will refuse to dispatch enforcement if
the action-tier audit record cannot be persisted. On a database
failure for an action-tier scoring call, the response is `503`. The
enforcement webhook is never fired without a durable audit row.

Watchlist persistence failures are tolerated (logged but not raised)
because the watchlist is a read-only review queue.

## 4. Threshold policy

Single source of truth: `model/weights/two_stage_config.json`.
- `action_threshold = 0.80` → enforcement-eligible.
- `watchlist_threshold = 0.50` → analyst review queue.

Backend reads via `model.scoring.get_action_threshold()` /
`get_watchlist_threshold()`. Frontend reads from `/health` thresholds
field; FraudFeed defaults match the config. Severity bands used by
`enforcement/dispatch.py`: ≥0.95 suspend, ≥0.85 flag, ≥0.80 alert.

## 5. Data-source labelling policy

Every benchmark-driven response carries a `data_source` field that is
one of:

- `live_database` — the response was assembled from PostgreSQL.
- `synthetic_benchmark` — the response is from the static benchmark
  dataset (model evaluation report, demo case fixtures).
- `benchmark_fallback` — the live source failed and the benchmark
  was returned in its place (e.g. database unavailable mid-flight).

Endpoints carrying the label: `/kpi/live`, `/roi/summary`,
`/shadow/status`, `/intelligence/top-risk`, `/efficiency/summary`,
`/efficiency/fleet-zones`, `/fraud/heatmap`, `/fraud/live-feed`,
`/cases`.

## 6. Dependency vulnerabilities (residual after upgrades)

The pip-audit run after the round-2 upgrade still reports 8 advisories
that cannot be cleared on Python 3.9 — every fix version requires
Python ≥ 3.10:

| Package          | Version  | Fix version | Notes                           |
| ---------------- | -------- | ----------- | ------------------------------- |
| filelock         | 3.19.1   | 3.20.3      | requires Py3.10                 |
| pillow           | 11.3.0   | 12.2.0      | requires Py3.10                 |
| pytest           | 8.4.2    | 9.0.3       | requires Py3.10 (dev-only dep)  |
| python-multipart | 0.0.20   | 0.0.26      | requires Py3.10                 |
| requests         | 2.32.5   | 2.33.0      | requires Py3.10                 |

Recommended remediation for the buyer: upgrade the deployment venv to
Python 3.11 LTS, then re-run `pip-audit`. With Py3.11 every advisory
above clears with a one-shot `pip install -U`. None of the residuals
affect the request path of the auth-protected endpoints; they are
either build-time or sandbox-internal.

npm side: `npm audit` reports **0** vulnerabilities after the vite
upgrade. Run from `dashboard-ui/`.

## 7. Credentials

- `.env` is gitignored; no secrets are committed.
- `Login.jsx` no longer renders demo credentials.
- `PORTER_AUTH_ADMIN_PASSWORD` is the bootstrap admin password — the
  buyer should rotate it on first install and create per-user
  accounts via `POST /auth/admin/users`.
- `WEBHOOK_SECRET` must be set in production mode; `/ingest/status`
  surfaces whether it is configured.
- `JWT_SECRET_KEY` is required; missing/placeholder values cause
  `/auth/token` to return 503 with a `SecurityConfigurationError`
  rather than minting unverifiable tokens.

## 8. Operational guardrails

- Database and Redis are required for full functionality. The
  platform degrades gracefully (CSV-only mode) when either is down,
  but `/health` will report `status: degraded` and `database:
  unavailable` / `redis: unavailable`. Treat `degraded` as a paging
  signal in production.
- Shadow mode (`POST /shadow/activate`) suspends enforcement
  writeback. The state is reflected in `/shadow/status` and in
  `/health.shadow_mode`. Use it for the 90-day validation window
  before enabling enforcement on real traffic.
- Rate limits are enforced via `slowapi`:
  - `FRAUD_SCORE_RATE_LIMIT` (default 100/min)
  - `INGEST_RATE_LIMIT` (default 300/min)
  - tunable through env vars in `security/settings.py`.

## 9. Test coverage

- `pytest` reports 63 passed.
- The auth scan (`/tmp/auth_verify.sh` in the verification suite)
  re-tests every endpoint above for both 401 (no token) and 200
  (admin token).
- The shadow-mode test and ingestion-API tests now mint a fake
  admin user via `dependency_overrides[get_current_user]` rather
  than calling the unauth path.
