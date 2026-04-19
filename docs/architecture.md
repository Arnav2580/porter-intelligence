# Porter Intelligence Platform — Architecture

This document describes the component topology, deployment layout, and the
design decisions that shaped the platform. It is the single entry point for
a reviewer or new technical owner to understand the whole system before
reading code.

---

## 1. Purpose

Trip-level fraud detection for a logistics platform. Complementary to
device-identity controls (Incognia) that prevent bad actors from entering
the platform. This platform detects fraud committed by actors who already
passed identity checks — leakage inside the trip itself.

Attack vectors addressed:

- Route manipulation and GPS spoofing
- Fare inflation, cash extortion
- Fake cancellations, trip padding
- Driver ring coordination
- Fleet dead-mile leakage

---

## 2. Components

```
+------------------+       +------------------+       +------------------+
| Ingestion        | ----> | Scoring Layer    | ----> | Case Store       |
| (webhook, CSV,   |       | (two-stage model)|       | (PostgreSQL)     |
|  queue)          |       | - XGBoost        |       | - FraudCase      |
+------------------+       | - Rule overlay   |       | - CaseHistory    |
                           | - Threshold gate |       +--------+---------+
                           +--------+---------+                |
                                    |                          v
                                    v                  +------------------+
                           +------------------+        | Analyst Queue    |
                           | Enforcement      |        | (Workspace UI)   |
                           | Dispatcher       |        +--------+---------+
                           | - Action (>=0.80)|                 |
                           | - Watchlist      |                 v
                           |   (>=0.50)       |        +------------------+
                           | - Clear (<0.50)  |        | Management View  |
                           +------------------+        | (KPIs, reports)  |
                                                       +------------------+
```

### Runtime layout

- **FastAPI backend** — `api/` package. Uvicorn on port 8002 in demo, port
  80 in production deployments. All endpoints require JWT except the
  health check and the OAuth token mint.
- **Two-stage scorer** — `model/scoring.py`. Reads thresholds from
  `model/weights/two_stage_config.json` (currently 0.80 / 0.50). Returns
  `action`, `watchlist`, or `clear`.
- **Enforcement dispatcher** — `enforcement/dispatch.py`. Consumes scored
  cases and signals downstream actions; thresholds come from the same
  config, not from hardcoded literals.
- **Operational database** — PostgreSQL, models in `database/models.py`.
  Async SQLAlchemy. Migrations live in `migrations/`.
- **Hot path** — Redis for queueing and coordination.
- **Dashboard** — React + Vite, `dashboard-ui/`. Deployed to Vercel.
  Talks to the API through `/api/*` rewrites.
- **Legal / reporting** — `api/routes/legal.py`, `api/routes/reports.py`.
  Generates buyer-close PDFs. All commercial terms come from
  `config/commercial.py`, overridable via environment variables.

### Authentication and RBAC

- JWT bearer tokens. Source of truth is `auth/dependencies.py`.
- Roles: `ADMIN`, `OPS_MANAGER`, `OPS_ANALYST`, `READ_ONLY`.
- Permissions: fine-grained strings (`read:cases`, `write:all`, etc.)
  mapped per role. Every route declares the permissions it needs via
  `Depends(require_permission("..."))`.

---

## 3. Data Sources and Truthfulness

Every API response that reports a benchmark number carries a
`data_source` field so consumers cannot mistake synthetic results for
production measurements. Values in use:

| `data_source`         | Meaning                                         |
|-----------------------|-------------------------------------------------|
| `synthetic_benchmark` | Derived from scored synthetic data or twin run  |
| `live_database`       | Derived from analyst-reviewed live cases        |
| `benchmark_fallback`  | DB unavailable, returning last benchmark values |

Reviewed-case metrics (the buyer-safe quality layer) only materialise
once analysts resolve real cases. Until then, all KPI cards render the
synthetic benchmark with the label visible in the payload.

---

## 4. Thresholds

Action-tier and watchlist-tier thresholds are **not** code constants.
They live in `model/weights/two_stage_config.json` and are read through
`model.scoring.get_action_threshold()` and
`get_watchlist_threshold()`. Changing a threshold means editing the
config file; no code deploy is required.

Current values:

- Action:    `>=0.80` — case routed to enforcement
- Watchlist: `>=0.50` — case queued for analyst review
- Clear:    `< 0.50` — no action taken

---

## 5. Commercial Configuration

All commercial terms (buyer name, tranche amounts, support windows,
seller identity) live in `config/commercial.py` as a frozen dataclass.
Defaults apply if environment variables are not set. Per-deployment
overrides:

- `PORTER_BUYER_NAME`, `PORTER_PLATFORM_NAME`
- `PORTER_SUPPORT_DAYS`, `PORTER_VALIDATION_DAYS`
- `PORTER_TRANCHE_1_INR`, `PORTER_TRANCHE_1_DISPLAY`
- `PORTER_TRANCHE_2_INR`, `PORTER_TRANCHE_2_DISPLAY`
- `PORTER_TOTAL_INR`, `PORTER_TOTAL_DISPLAY`
- `SELLER_ENTITY_NAME`, `SELLER_ADDRESS`, `SELLER_PAN`,
  `SELLER_GSTIN`, `SELLER_EMAIL`, `SELLER_SIGNATORY`

Both `api/routes/legal.py` and `api/routes/reports.py` read from the
`COMMERCIAL` singleton. No numeric amounts are hardcoded in code.

---

## 6. Dashboard

- React 18 + Vite + react-router-dom.
- Auth via `useAuth` hook; token persisted to `localStorage`.
- All backend calls go through `utils/api.js`, which prepends the
  `/api` Vercel rewrite prefix and attaches the bearer token.
- Login screen carries no demo credentials; access is gated on an
  administrator provisioning a user.

---

## 7. Deployment Surface

- Backend: documented AWS ECS + PostgreSQL + Redis. In review, a single
  uvicorn process behind an ngrok tunnel is sufficient for buyer
  walk-throughs.
- Dashboard: Vercel. `vercel.json` configures the `/api/:path*` rewrite
  to the backend hostname.
- Model artefacts: committed to the repo under `model/weights/`.
- Secrets: `.env` at repo root, never committed. `.env.example`
  documents every variable the platform expects.

See `docs/handover/deployment-runbook.md` for the step-by-step bring-up.

---

## 8. Design Decisions Worth Knowing

1. **Thresholds in config, not code.** A new threshold study should not
   require a deploy. The scorer re-reads the config file on each call,
   and the enforcement dispatcher pulls from the same helper.
2. **`data_source` on every KPI response.** The platform ships before
   live data exists; lying about that in dashboards is the fastest way
   to erode buyer trust during due diligence.
3. **Commercial terms env-driven.** The product code must compile and
   run for deployments unrelated to the current buyer conversation.
4. **No absolute developer paths.** Runbooks use `$(pwd)` and the
   reports module uses `Path(__file__).resolve()` with an env override.
   The repo should clone cleanly on any reviewer's machine.
5. **Auth on every mutation endpoint.** `/fraud/score` and the test
   dispatch webhook both require permissions; there is no "internal
   use only" implicit-trust path.
