# Acceptance Criteria Checklist

[Handover Hub](./README.md) | [Deployment and Support Scope](./deployment-and-support-scope.md)

This document defines the five measurable conditions that determine shadow-mode success and trigger Tranche 2 payment.

---

## Criteria Summary

| # | Criterion | Target | Measurement Window |
|---|-----------|--------|--------------------|
| 1 | Ingestion path works | 95%+ ingestion success rate | First 7 days of shadow operation |
| 2 | Shadow mode operates without writeback | 0 outbound enforcement webhooks | Full shadow period |
| 3 | Analyst workflow is functional | 3+ analysts actively reviewing cases | By end of Day 30 |
| 4 | Reviewed-case precision is acceptable | 70%+ precision on action-tier cases | Minimum 200 reviewed cases |
| 5 | Deployment and documentation delivered | Porter technical lead written sign-off | By end of Day 60 |

---

## Criterion 1: Ingestion Path Works

**What is measured:** The percentage of Porter trip events that are successfully received, schema-mapped, scored, and either persisted (action/watchlist tier) or acknowledged (clear tier) without error.

**How to verify:**
```
GET /ingest/status
```
Response includes `stream_length` (total received), `pending_messages` (processing lag), and `staged_trips` (fallback buffer size). A healthy ingest path shows:
- `pending_messages` stays near 0 under normal load
- `staged_trips` is 0 (no fallback buffer accumulation)
- No 4xx/5xx responses on `POST /ingest/trip-completed`

**Failure modes and remedies:**
- Schema mapping failures — update `ingestion/schema_map.default.json` to add field aliases for Porter's trip event format
- Redis unavailability — PostgreSQL staging fallback activates automatically; drain via `GET /ingest/status`

**Pass condition:** 95%+ of trip events ingested successfully over a rolling 7-day window from first live trip.

---

## Criterion 2: Shadow Mode Operates Without Writeback

**What is measured:** The enforcement dispatch module must not send any HTTP POST to `PORTER_DISPATCH_URL` during the shadow period.

**How to verify:**
```
GET /shadow/status
```
Response includes `shadow_mode_active: true` and a `shadow_case_count` field showing how many cases have been scored and stored in the `shadow_cases` table with `live_write_suppressed: true`.

**Technical guarantee:** The `should_enforce_actions()` function in `enforcement/dispatch.py` returns `False` when shadow mode is active. No enforcement call is made regardless of fraud probability or tier.

**Audit trail:** Every shadow case includes `live_write_suppressed: true` in the database record. This is verifiable by Porter's DBA or audit team at any point.

**Pass condition:** `PORTER_DISPATCH_URL` receives zero HTTP calls for the duration of the shadow period. Verified by Porter's network team or application logs.

---

## Criterion 3: Analyst Workflow Is Functional

**What is measured:** A minimum of 3 Porter operations analysts can log in, see their case queue, review cases, record decisions, and see audit trails for those decisions.

**How to verify:**
- Log in with analyst credentials at the dashboard URL
- Navigate to the case queue and verify cases appear
- Open a case and record a decision (confirm or false alarm)
- Check `GET /cases/{id}/history` for the audit trail entry

**Roles required:**
- `ops_analyst` — can claim, review, and decide cases
- `ops_manager` — can see all cases, access reports and dashboard summary
- `read_only` — viewer access to the dashboard and KPI panel

**Pass condition:** 3 or more `ops_analyst` accounts have each reviewed at least 5 cases with recorded decisions and visible audit trails.

---

## Criterion 4: Reviewed-Case Precision Is Acceptable

**What is measured:** Of all action-tier cases reviewed and closed by Porter analysts, at least 70% must be confirmed as fraud (not dismissed as false alarms).

**Formula:**
```
reviewed_case_precision = confirmed_cases / (confirmed_cases + false_alarm_cases)
```

This is the buyer-safe precision metric — it measures what Porter analysts actually validated, not what the model predicted.

**How to verify:**
```
GET /cases/summary/dashboard
```
The response includes `reviewed_case_precision` for the last 24 hours and `precision_trend_7d` for the 7-day daily breakdown.

**Minimum sample size:** The 70% target is not binding until at least 200 action-tier cases have been reviewed and closed. This prevents small-sample noise from triggering early judgment.

**Why 70%:** This is a conservative floor. The model's benchmark precision at the action threshold (0.94) is ~85%+. The 70% target accounts for Porter-specific data distribution differences that may appear in the first deployment weeks.

**Pass condition:** Minimum 200 reviewed action-tier cases, with `reviewed_case_precision >= 0.70`.

---

## Criterion 5: Deployment and Documentation Delivered

**What is measured:** Porter's designated technical lead confirms in writing that the handover package is complete and adequate for independent operation.

**What the handover package includes:**
- Architecture documentation (`docs/` and `logic/` directories)
- API reference (available at `/docs` on the running platform)
- Deployment guide (`docs/deployment/one-command-setup.md`)
- Runbooks: secret rotation, model retraining, city expansion, restore from backup
- Security notes and runtime mode documentation
- Model card: training data, feature list, thresholds, evaluation metrics

**How to verify:** Porter's CPTO, CTO, or designated technical lead provides written confirmation (email or signed document) that the package meets their requirements for independent operation.

**Pass condition:** Written confirmation received from Porter's designated technical lead.

---

## Acceptance Determination

- Criteria 1, 2, and 3 are binary (pass/fail evaluated at Day 30)
- Criterion 4 requires minimum 200 reviewed cases (evaluated at Day 45-60)
- Criterion 5 requires written sign-off (evaluated at Day 60)
- All 5 criteria must be met for Tranche 2 payment to be triggered
- If criteria are not met within 60 days from Tranche 1, both parties agree on a 30-day extension or scope adjustment
- No single criterion failure blocks the others from being evaluated and recorded

---

## Live Monitoring

During shadow validation, Porter can verify live status at any time:

| Endpoint | What It Shows |
|----------|---------------|
| `GET /health` | System health (database, Redis, model loaded) |
| `GET /shadow/status` | Shadow mode active, case count, suppression confirmed |
| `GET /ingest/status` | Ingestion lag, pending messages, staged trips |
| `GET /kpi/live` | Live fraud detection KPIs |
| `GET /cases/summary/dashboard` | Case queue metrics, precision trend |
| `GET /metrics` | Prometheus metrics (trips scored, stream lag, API latency) |
