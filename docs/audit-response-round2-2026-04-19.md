# Audit Response — Round 2 (2026-04-19)

Follow-up remediation after the round-1 audit (`docs/audit-response-2026-04-19.md`)
closed out round-1 but flagged 8 remaining issues. This document enumerates each,
cites the code that fixes it, and cites verification proof from
`/tmp/phase2_round2.out` (Phase 2 verification suite, all 13 sections green).

Commit: `4115dbb` (main)
Production deploy: `https://porter-intelligence-dashboard-erjnvkdnb-arnav2580s-projects.vercel.app`
Branch: main, pushed.

---

## Fix 1 — Full auth coverage on data-reading endpoints

**Issue.** Round-1 audit found 15 GET and 3 POST endpoints that returned sensitive
benchmark / fraud / driver data with *no* bearer requirement.

**Fix.** Added `Depends(require_permission(...))` (RBAC dep from
[auth/dependencies.py](auth/dependencies.py#L57)) to every open endpoint:

| Endpoint | File:Line | Permission |
|---|---|---|
| GET `/kpi/live` | [api/routes/live_kpi.py:136](api/routes/live_kpi.py#L136) | read:cases |
| GET `/kpi/report` | api/inference.py:423 | read:cases |
| GET `/roi/summary` | [api/routes/roi.py:220](api/routes/roi.py#L220) | read:cases |
| GET `/fraud/heatmap` | api/inference.py:269 | read:cases |
| GET `/fraud/live-feed` | api/inference.py:343 | read:cases |
| GET `/fraud/tier-summary` | api/inference.py:489 | read:cases |
| GET `/intelligence/top-risk` | [api/routes/driver_intelligence.py:328](api/routes/driver_intelligence.py#L328) | read:cases |
| GET `/efficiency/*` (5 routes) | api/routes/route_efficiency.py | read:cases |
| GET `/demand/forecast/{zone}` | api/inference.py:753 | read:cases |
| GET `/shadow/status` | [api/routes/shadow.py:28](api/routes/shadow.py#L28) | read:cases |
| GET `/ingest/status` | [ingestion/webhook.py:425](ingestion/webhook.py#L425) | read:cases |
| GET `/ingest/schema-map/default` | [ingestion/webhook.py:452](ingestion/webhook.py#L452) | read:cases |
| POST `/fraud/score` | api/inference.py:78 | read:cases |
| POST `/query` | api/routes/query.py | read:cases |
| POST `/ingest/batch-csv` | [ingestion/webhook.py:341](ingestion/webhook.py#L341) | write:all |

**Proof (phase2 §2, §3, §5).**
- All 15 GET + 3 POST paths return `401` without bearer.
- Same 15 paths return `200` with admin bearer.

---

## Fix 2 — `/ingest/batch-csv` hardening

**Issue.** Endpoint had no size/row caps, no content-type check, no auth, and
threw 500s on malformed input.

**Fix.**
- Added `write:all` auth dep ([ingestion/webhook.py:341](ingestion/webhook.py#L341))
- 10 MB size cap → `413` ([webhook.py:38, 360](ingestion/webhook.py#L38))
- 10 000 row cap → `413` ([webhook.py:39, 397](ingestion/webhook.py#L39))
- `.csv` extension check → `415`
- UTF-8 / mapping validation → `400` (was `500`)

**Proof (phase2 §9).**
```
POST /ingest/batch-csv (no token)            → 401 ✓
POST /ingest/batch-csv (admin, .txt)         → 415 ✓
POST /ingest/batch-csv (admin, 11 MB csv)    → 413 ✓
POST /ingest/batch-csv (admin, 10001-row)    → 413 ✓
```

---

## Fix 3 — ROI economics positive, thresholds corrected, pilot language updated

**Issue.** `/roi/summary` reported a negative net annual benefit and referenced
the wrong thresholds (0.65/0.40) and wrong pilot length (60 days).

**Fix in [api/routes/roi.py](api/routes/roi.py).**
- `action_precision` default `0.883 → 0.853` (line 217)
- `recovery_per_trip` default `6.85 → 5.08` (line 218)
- Formula: `gross_recovery = annual_trips * recovery_per_trip` (line 241) — matches benchmark methodology
- `RECOVERY_RATE (0.30) → REALIZATION_RATE (0.50)` (line 237) — 50% haircut benchmark→prod
- Disclosures updated (lines 287-293):
  - threshold `0.65 → 0.80`
  - watchlist `0.40 → 0.50`
  - pilot `60-day → 90-day`
  - FPR band `>15% → >20%`

**Proof (phase2 §6).**
```
net_annual_benefit_inr = 10,328,040    (₹1.03 Cr/yr)
year_1_roi_pct         = 37.7
payback_months         = 8.7
data_source            = synthetic_benchmark
disclosures            : all 6 lines reflect 0.80 / 0.50 / 90-day / >20% FPR
```

---

## Fix 4 — Fail-closed on action-tier persistence failure

**Issue.** `POST /fraud/score` could dispatch enforcement even when the case
record failed to persist — no audit trail would exist for the action.

**Fix in [api/inference.py:902-910](api/inference.py#L902).**
```python
if tier.name == "action":
    raise HTTPException(
        status_code=503,
        detail=(
            "Action-tier persistence failed; refusing to dispatch "
            "enforcement without an audit record. Please retry."
        ),
    ) from exc
```
Enforcement dispatch at line 919 is now unreachable when persistence has failed
for an action-tier case.

**Proof.** Code-path inspection; tests in `tests/test_inference_api.py` exercise
the happy path; the fail-closed branch is the explicit raise above.

---

## Fix 5 — CVE patches

**Issue.** 33 pip-audit findings, 1 npm high (vite).

**Fix.**
- **npm**: `vite` upgraded → `npm audit: 0 vulnerabilities` (phase2 §11)
- **pip**: 33 → 8 residuals. The 8 remaining are *bounded by Python 3.9* — newer
  fixed versions require Py ≥ 3.10. Documented in
  [docs/handover/security-notes.md](docs/handover/security-notes.md) §6 with
  remediation plan: upgrade venv to Python 3.11 in next maintenance window.
- **Framework compat fixes bundled**:
  - `fastapi 0.110.0 → 0.128.8` (resolves `starlette 0.47` conflict)
  - `xgboost 2.0.3 → 2.1.4` (resolves sklearn 1.6 `__sklearn_tags__` AttributeError)
- `requirements.txt` frozen via `pip freeze`.

**Proof (phase2 §10, §11).**
```
pip-audit : 8 residual findings (all Py3.9-bounded, documented)
npm audit : found 0 vulnerabilities
```

---

## Fix 6 — Database + Redis live

**Issue.** `/health` returned `database: unavailable` and `redis: unavailable`
in round-1 verification.

**Fix.** `docker compose up -d postgres redis`; schema created via `init_db()`.

**Proof (phase2 §1).**
```
status    : ok
database  : ok
redis     : ok
thresholds: {'watchlist_threshold': 0.5, 'action_threshold': 0.8}
```

---

## Fix 7 — `data_source` labelling + threshold sync

### 7a — `data_source` on every benchmark endpoint

Added labels to ensure clients can distinguish live vs. synthetic:

| Endpoint | Label | Cite |
|---|---|---|
| `/kpi/live` | `synthetic_benchmark` | [live_kpi.py:98](api/routes/live_kpi.py#L98) |
| `/kpi/report` | `synthetic_benchmark` | [live_kpi.py:301](api/routes/live_kpi.py#L301) |
| `/roi/summary` | `synthetic_benchmark` | [roi.py:254](api/routes/roi.py#L254) |
| `/shadow/status` | `synthetic_benchmark` | [shadow.py:63,76](api/routes/shadow.py#L63) |
| `/intelligence/top-risk` | `synthetic_benchmark` | [driver_intelligence.py:365,388](api/routes/driver_intelligence.py#L365) |
| `/efficiency/summary` | `synthetic_benchmark` | [route_efficiency.py:146](api/routes/route_efficiency.py#L146) |
| `/efficiency/fleet-zones` | `synthetic_benchmark` | [route_efficiency.py:348,358](api/routes/route_efficiency.py#L348) |
| `/fraud/heatmap` | `synthetic_benchmark` | api/inference.py |
| `/fraud/live-feed` | `synthetic_benchmark` | api/inference.py |
| `/cases` | `live_database` or `synthetic_benchmark` | [cases.py:415,424](api/routes/cases.py#L415) |

**Proof (phase2 §7).** All 9 endpoints return correct `data_source`.

### 7b — FraudFeed thresholds aligned

[dashboard-ui/src/components/FraudFeed.jsx:115-116](dashboard-ui/src/components/FraudFeed.jsx#L115):
```js
const actionThreshold    = thresholds?.action_threshold    ?? 0.80;
const watchlistThreshold = thresholds?.watchlist_threshold ?? 0.50;
```
Defaults match `model/weights/two_stage_config.json`, `model.scoring.get_*_threshold()`,
and `enforcement.dispatch.ACTION_THRESHOLD` (phase2 §8).

### 7c — Security notes handover doc

[docs/handover/security-notes.md](docs/handover/security-notes.md) created with
9 sections: auth coverage matrix, batch-csv hardening, fail-closed policy,
threshold policy, data_source labelling policy, residual CVEs + remediation,
credentials, operational guardrails, test coverage.

---

## Fix 8 — Lint cleanup (18 → 0 errors)

**Issue.** ESLint reported 18 `react-hooks/set-state-in-effect` + empty-catch
errors that would block CI.

**Fix.**
- Restructured every `useEffect` that set state to use cancelled-flag async tick pattern
  ([Dashboard.jsx:139-160](dashboard-ui/src/pages/Dashboard.jsx#L139),
  [FraudFeed.jsx:129-141](dashboard-ui/src/components/FraudFeed.jsx#L129)).
- Replaced `useEffect` + `setState` in `useAuth.js` with a lazy `useState` initializer
  ([useAuth.js:5-9](dashboard-ui/src/hooks/useAuth.js#L5)).
- Removed empty-catch bodies in `DriverIntelligence`, `ReallocationPanel`,
  `TierSummaryBar`, `ZoneMap`, `Analyst.jsx`; removed unused `mapRef`.

**Proof (phase2 §13).**
```
$ npx eslint src --ext .jsx,.js
exit=0
```

---

## Verification summary (phase2 §1-13)

| # | Check | Result |
|---|---|---|
| 1 | `/health` | status:ok, db:ok, redis:ok, thresholds 0.80/0.50 |
| 2 | 15 previously-OPEN GET → 401 | all 401 |
| 3 | 3 previously-OPEN POST → 401 | all 401 |
| 4 | Admin token mint | length=187 |
| 5 | Same 15 GET with admin token → 200 | all 200 |
| 6 | ROI economics | net=+₹1.03 Cr, ROI=37.7%, payback=8.7 mo |
| 7 | `data_source` labels | 9/9 correct |
| 8 | Threshold alignment | 0.80/0.50 across config+scoring+dispatch+frontend |
| 9 | batch-csv hardening | 401/415/413/413 |
| 10 | pip-audit | 8 residuals (Py3.9-bounded, documented) |
| 11 | npm audit | 0 vulns |
| 12 | pytest | 63 passed |
| 13 | ESLint | exit=0 |

---

## Commit + deploy

```
commit 4115dbb  audit-remediation round-2 2026-04-19
         main → origin/main  (pushed)

vite build       → 458 KB js / 44 KB css, 0 localhost refs
vercel --prod --force
  deployment id: dpl_5uAhFPudzGFTzS962YnE9eqptgoF
  url          : porter-intelligence-dashboard-erjnvkdnb-arnav2580s-projects.vercel.app
  state        : READY
```

---

## Residuals documented for next sprint

1. **Py 3.9 → 3.11 venv upgrade** — unblocks the 8 CVE residuals
   (`filelock`, `pillow`, `pytest`, `python-multipart`, `requests`, and others).
   Remediation plan in [security-notes.md](docs/handover/security-notes.md) §6.
2. **Database-backed `data_source=live_database` on remaining benchmark endpoints** —
   `/kpi/live`, `/roi/summary`, `/efficiency/*` still return synthetic. Switch is
   a one-line label change per endpoint once the production trip table is populated
   via the 90-day shadow pilot.
3. **Alembic migrations** — schema currently managed via `Base.metadata.create_all`.
   For production upgrades, add alembic once schema stabilises.
