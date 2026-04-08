# 04 — API Reference

[Index](./README.md) | [Prev: ML Pipeline](./03-data-and-ml-pipeline.md) | [Next: Ingestion](./05-ingestion-and-shadow-mode.md)

Complete reference for every API endpoint. All endpoints are served by FastAPI at `http://localhost:8000`.

---

## Authentication

All endpoints except `/health`, `/metrics`, and `/auth/token` require a JWT bearer token.

### Get a token

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=YOUR_ADMIN_PASSWORD"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "role": "admin",
  "name": "Platform Admin",
  "expires_in": 28800
}
```

Use the token in all subsequent requests:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Seed users

| Username | Role | Permissions |
|---|---|---|
| `admin` | admin | All permissions |
| `ops_manager` | ops_manager | Read cases, write status, read reports |
| `analyst_1` | ops_analyst | Read/write own cases, driver actions |
| `viewer` | viewer | Read-only access |

Rate limit: **10 requests/minute** on auth endpoints.

---

## Core Endpoints

### `GET /health`

Health check. No auth required.

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

### `GET /metrics`

Prometheus scrape endpoint. No auth required. Returns Prometheus text format.

---

## Auth Router (`/auth/*`)

### `POST /auth/token`

Login and get JWT token. Accepts `application/x-www-form-urlencoded` with `username` and `password` fields.

### `GET /auth/me`

Returns the current user's profile (username, role, name). Requires valid JWT.

---

## Fraud Scoring Router (`/fraud/*`)

### `POST /fraud/score`

**Rate limit:** 100/minute

Score a single trip for fraud. This is the core scoring endpoint.

**Request body:**
```json
{
  "trip_id": "TRIP-001",
  "driver_id": "DRV-001",
  "vehicle_type": "mini_truck",
  "pickup_zone_id": "blr_koramangala",
  "dropoff_zone_id": "blr_whitefield",
  "pickup_lat": 12.9352,
  "pickup_lon": 77.6245,
  "dropoff_lat": 12.9698,
  "dropoff_lon": 77.7500,
  "declared_distance_km": 5.2,
  "declared_duration_min": 45,
  "fare_inr": 1200,
  "payment_mode": "cash",
  "surge_multiplier": 1.5,
  "requested_at": "2026-04-08T22:30:00",
  "is_night": true,
  "hour_of_day": 22,
  "day_of_week": 5,
  "is_peak_hour": false,
  "zone_demand_at_time": 1.2,
  "status": "completed",
  "customer_complaint_flag": false
}
```

**Response:**
```json
{
  "trip_id": "TRIP-001",
  "fraud_probability": 0.9612,
  "tier": "action",
  "tier_label": "ACTION REQUIRED",
  "tier_color": "#EF4444",
  "is_fraud_predicted": true,
  "fraud_risk_level": "CRITICAL",
  "action_required": "Investigate immediately. No secondary review needed.",
  "auto_escalate": false,
  "top_signals": [
    "Cash payment detected",
    "Fare inflated 2.35x",
    "Night trip (higher risk window)"
  ],
  "confidence": "high",
  "scored_at": "2026-04-08T22:30:01"
}
```

**Side effects:**
- If tier is action or watchlist: a FraudCase row is persisted to PostgreSQL
- If tier is action AND not shadow mode: enforcement webhook is dispatched

### `GET /fraud/heatmap`

Zone-level fraud rate heatmap for the live map.

**Response:**
```json
{
  "zones": [
    {
      "zone_id": "blr_koramangala",
      "zone_name": "Koramangala",
      "city": "bangalore",
      "lat": 12.9352,
      "lon": 77.6245,
      "fraud_rate": 0.0823,
      "fraud_count": 142,
      "risk_level": "HIGH"
    }
  ],
  "total_trips": 50000,
  "total_fraud": 2350,
  "generated_at": "2026-04-08T10:00:00"
}
```

Risk levels: CRITICAL (> 12%), HIGH (> 8%), MEDIUM (> 4%), LOW (< 4%).

### `GET /fraud/live-feed?limit=50`

Last N fraud-flagged trips for the activity feed. Sorted by most recent.

### `GET /fraud/driver/{driver_id}`

Risk profile for a specific driver: risk score, level, fraud rate, cancellation velocity, ring membership, recommendation.

### `GET /fraud/tier-summary`

Two-stage scoring tier summary with per-tier metrics and combined system performance.

### `GET /demand/forecast/{zone_id}`

24-hour demand forecast for a zone. Uses Prophet ML model if available, falls back to rule-based patterns.

### `GET /kpi/summary`

Evaluation benchmark KPI summary. Returns total trips, fraud detected, baseline vs XGBoost comparison, improvement %, net recoverable, FPR, annual projection.

### `GET /kpi/report`

Full sanitised evaluation report for buyer inspection. Strips internal fields (royalty calculations).

---

## Cases Router (`/cases/*`)

### `GET /cases/`

List fraud cases with filtering.

**Query parameters:**
| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status (open, under_review, confirmed, false_alarm, escalated) |
| `tier` | string | Filter by tier (action, watchlist) |
| `zone_id` | string | Filter by zone |
| `limit` | int | Max results (default 50, max 200) |
| `offset` | int | Pagination offset |

**Response:**
```json
{
  "cases": [
    {
      "id": "uuid",
      "trip_id": "TRIP-001",
      "driver_id": "DRV-001",
      "zone_id": "blr_koramangala",
      "city": "Bangalore",
      "tier": "action",
      "fraud_probability": 0.96,
      "top_signals": ["Cash payment", "Fare inflated 2.3x"],
      "fare_inr": 1200,
      "recoverable_inr": 180,
      "status": "open",
      "assigned_to": null,
      "analyst_notes": null,
      "auto_escalated": false,
      "case_age_hours": 2.5,
      "created_at": "2026-04-08T10:00:00",
      "resolved_at": null
    }
  ],
  "total": 142,
  "offset": 0,
  "limit": 50
}
```

### `GET /cases/summary/counts`

Quick count by status for dashboard header.

### `GET /cases/summary/dashboard`

Manager-focused dashboard summary with: queue stats, 24h throughput, tier breakdown, city breakdown, zone breakdown, analyst load, 7-day precision trend.

### `GET /cases/{case_id}`

Get a single case by ID with full details.

### `GET /cases/{case_id}/history`

Get case timeline with all status changes, analyst decisions, and driver actions. Events are sorted newest-first.

### `PATCH /cases/{case_id}`

Update case status. Requires `write:case_status` permission.

**Request body:**
```json
{
  "status": "confirmed",
  "analyst_notes": "Clear GPS spoofing pattern confirmed.",
  "override_reason": null
}
```

**Note:** Dismissing an action-tier case as `false_alarm` requires an `override_reason`.

Valid status values: `open`, `under_review`, `confirmed`, `false_alarm`, `escalated`.

### `POST /cases/batch-review`

Batch update multiple cases at once (max 100).

```json
{
  "case_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "status": "false_alarm",
  "analyst_notes": "Bulk review: all verified clean.",
  "override_reason": "Batch review by ops_manager"
}
```

### `POST /cases/{case_id}/driver-action`

Take an enforcement action on a driver. Requires `write:driver_actions` permission.

```json
{
  "action_type": "suspend",
  "reason": "Confirmed fraud ring leader. 5 coordinated fake cancellations."
}
```

Valid action types: `suspend`, `flag`, `monitor`, `clear`.

---

## Ingestion Router (`/ingest/*`)

### `POST /ingest/trip-completed`

**Rate limit:** 300/minute

Receive a single trip event from Porter's system. Accepts optional HMAC signature verification via `X-Porter-Signature` header.

Returns `200` immediately. Scoring happens asynchronously via Redis Stream.

### `POST /ingest/batch-csv`

**Rate limit:** 300/minute

Upload a CSV file for batch scoring. Accepts multipart form with:
- `file`: CSV file (required)
- `mapping_file`: Custom schema mapping JSON (optional)
- `mapping_name`: Name of built-in mapping to use (default: "default")

### `GET /ingest/status`

Ingestion pipeline status: webhook URL, signature check status, queue status.

### `GET /ingest/schema-map/default`

Returns the default field alias mapping used for CSV/webhook ingestion. Useful for onboarding demos.

---

## Driver Intelligence Router (`/driver-intelligence/*`)

### `GET /driver-intelligence/{driver_id}`

Full driver intelligence profile: 30-day risk timeline, peer comparison vs zone median, ring intelligence, actionable recommendation.

---

## Demo Router (`/demo/*`)

### `GET /demo/scenarios`

Pre-built fraud walkthrough scenarios (fraud ring, cash extortion, GPS spoofing).

### `POST /demo/reset`

Reset demo state. Clears cases and reloads data.

---

## Reports Router (`/reports/*`)

### `GET /reports/board-pack`

Download the board pack as a PDF. Contains: executive summary, architecture, KPI trust, deployment plan, ROI, decision request.

---

## ROI Router (`/roi/*`)

### `POST /roi/calculate`

Calculate ROI for given parameters.

**Request:**
```json
{
  "gmv_crore": 4306,
  "trips_per_day": 270000,
  "fraud_rate_pct": 3.0,
  "platform_price_crore": 3.25
}
```

**Response:** Three scenarios (conservative, realistic, aggressive) with annual savings, payback period, ROI %, and savings as % of GMV.

---

## Route Efficiency Router (`/route-efficiency/*`)

### `GET /route-efficiency/summary`

Fleet efficiency summary: dead mile rates, utilisation, reallocation suggestions.

### `GET /route-efficiency/dead-miles`

Per-zone dead mile analysis.

### `GET /route-efficiency/suggestions`

Ranked vehicle reallocation suggestions.

---

## Shadow Router (`/shadow/*`)

### `GET /shadow/status`

Shadow mode status: whether shadow mode is active, what it means, and confirmation that enforcement is suppressed.

---

## KPI Router (`/kpi/*`)

### `GET /kpi/live`

Live reviewed-case KPIs computed from analyst decisions in the database. Returns precision, false-alarm rate, recovery rate, throughput, case age metrics.

---

## Webhook Test

### `POST /webhooks/dispatch/test`

Test the enforcement webhook dispatch. Sends a test payload to `PORTER_DISPATCH_URL` if configured.

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status Code | Meaning |
|---|---|
| 400 | Bad request (invalid input) |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 429 | Rate limited |
| 503 | Service unavailable (model not loaded, DB down) |

---

## Next

- [Ingestion and Shadow Mode](./05-ingestion-and-shadow-mode.md) — how data flows into the platform
- [Frontend and Dashboard](./06-frontend-and-dashboard.md) — React UI documentation
