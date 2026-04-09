# 09 — Testing And Quality

[Index](./README.md) | [Prev: Deployment](./08-deployment-and-infrastructure.md) | [Next: Demo Guide](./10-demo-guide.md)

This document covers the test suite: what is tested, how to run tests, and what the test fixtures do.

---

## Test Suite Overview

The platform has 17 test files covering all major subsystems:

| Test File | What It Tests |
|---|---|
| `test_auth.py` | JWT token creation, verification, password hashing, login flow |
| `test_security.py` | AES-256-GCM encryption, key validation, plaintext fallback |
| `test_enforcement.py` | Dispatch webhook, shadow mode suppression, log-only mode |
| `test_shadow_mode.py` | Shadow mode case isolation, enforcement suppression |
| `test_shadow_api.py` | Shadow status API endpoint |
| `test_health_contract.py` | Health endpoint response contract |
| `test_schema_mapper.py` | CSV field mapping, alias resolution, type conversions |
| `test_ingestion_api.py` | Webhook ingestion endpoint, batch CSV upload |
| `test_ingestion_queue.py` | Redis Stream publishing, staging fallback |
| `test_case_workflow_api.py` | Case CRUD, status updates, batch review, driver actions |
| `test_cases.py` | Case listing, filtering, dashboard summary |
| `test_live_kpi_metrics.py` | Live KPI computation from reviewed cases |
| `test_live_simulator.py` | Digital twin trip generation, city distribution |
| `test_roi_api.py` | ROI calculator scenarios and validation |
| `test_reports_board_pack.py` | Board pack PDF generation |
| `test_demo_api.py` | Demo scenarios and reset endpoints |
| `test_model.py` | ML model loading, feature engineering, scoring |

---

## Running Tests

### Prerequisites

```bash
# Activate virtual environment:
source venv/bin/activate

# Install dependencies (includes pytest):
pip install -r requirements.txt
```

### Run all tests

```bash
pytest tests/ -v
```

### Run a specific test file

```bash
pytest tests/test_auth.py -v
```

### Run a specific test function

```bash
pytest tests/test_auth.py::test_login_success -v
```

### Run with coverage

```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

### Run tests in parallel (if pytest-xdist installed)

```bash
pytest tests/ -v -n auto
```

---

## Test Configuration

### `conftest.py`

The shared test configuration (`tests/conftest.py`) provides an `autouse` fixture that sets all required security environment variables for every test:

```python
@pytest.fixture(autouse=True)
def security_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-jwt-secret-...")
    monkeypatch.setenv("WEBHOOK_SECRET", "unit-test-webhook-secret-...")
    monkeypatch.setenv("API_ALLOWED_ORIGINS", "http://localhost:3000,...")
    monkeypatch.setenv("PORTER_AUTH_ADMIN_PASSWORD", "AdminPass!123")
    monkeypatch.setenv("PORTER_AUTH_OPS_MANAGER_PASSWORD", "OpsManagerPass!123")
    monkeypatch.setenv("PORTER_AUTH_ANALYST_PASSWORD", "AnalystPass!123")
    monkeypatch.setenv("PORTER_AUTH_VIEWER_PASSWORD", "ViewerPass!123")
    monkeypatch.setenv("ENCRYPTION_KEY", "EXBtipXs6jmJR5swf0tO06vd9cS4Nvt9fyjlX1gjz88=")
    monkeypatch.setenv("SHADOW_MODE", "false")
```

This means:
- Tests do not require a `.env` file
- Tests use known, deterministic secrets
- Tests do not interfere with production configuration
- Each test starts with a clean security state

### Database in tests

Most tests use FastAPI's `TestClient` with mocked database sessions. Tests that need a real database use the Docker PostgreSQL instance (must be running).

---

## What Each Test Category Covers

### Authentication tests (`test_auth.py`)

- Token creation with valid credentials returns JWT
- Token creation with invalid password returns 401
- Token creation with unknown user returns 401
- Token verification succeeds for valid tokens
- Token verification fails for expired tokens
- Token verification fails for tampered tokens
- Password hashing produces different hashes for same input (bcrypt salt)
- Password verification matches original plaintext

### Security tests (`test_security.py`)

- AES-256-GCM encryption produces different ciphertext for same input (random nonce)
- Decryption recovers original plaintext
- Invalid key raises configuration error
- Placeholder key is rejected in production mode
- Plaintext fallback only works when explicitly enabled in demo mode
- Key must decode to exactly 32 bytes

### Enforcement tests (`test_enforcement.py`)

- Webhook dispatched when URL configured and live mode
- Webhook suppressed in shadow mode
- Webhook logged (not sent) when URL not configured
- Dispatch timeout handling (5 second limit)
- Payload includes all required fields

### Shadow mode tests (`test_shadow_mode.py`, `test_shadow_api.py`)

- Shadow mode creates cases in `shadow_cases` table (not `fraud_cases`)
- Shadow mode suppresses enforcement dispatch
- Shadow status endpoint returns correct state
- Shadow mode toggle works via environment variable
- Live mode creates cases in `fraud_cases` table

### Ingestion tests (`test_ingestion_api.py`, `test_ingestion_queue.py`)

- Webhook endpoint accepts valid trip events
- HMAC signature verification works correctly
- Invalid signature returns 401
- Batch CSV upload parses and maps rows correctly
- Schema mapper resolves aliases correctly
- Redis Stream publishing succeeds
- PostgreSQL staging fallback works when Redis unavailable
- Staging drain recovers buffered trips

### Schema mapper tests (`test_schema_mapper.py`)

- Default alias map loads correctly
- All internal fields are mapped
- Payment mode normalisation (CASH→cash, UPI→upi, etc.)
- Vehicle type normalisation
- Timestamp parsing (ISO 8601, with/without timezone)
- Missing fields get sensible defaults
- Custom mapping files load correctly

### Case workflow tests (`test_case_workflow_api.py`, `test_cases.py`)

- Case creation from scored trip
- Case listing with status/tier/zone filters
- Case status update (open → under_review → confirmed)
- Override reason required for action-tier false alarm
- Batch review updates multiple cases
- Driver action creation (suspend, flag, monitor, clear)
- Audit log entries created for all decisions
- Analyst case isolation (cannot see others' cases)
- Dashboard summary aggregation

### KPI tests (`test_live_kpi_metrics.py`)

- Reviewed-case precision computed correctly
- False alarm rate computed correctly
- 24-hour throughput metrics
- 7-day precision trend

### Model tests (`test_model.py`)

- XGBoost model loads from saved weights
- Feature engineering produces 35 features
- No NaN values in feature matrix
- Scoring returns probability in [0, 1]
- Tier assignment matches threshold rules

### Digital twin tests (`test_live_simulator.py`)

- Trip generation produces valid trip dicts
- All required fields present
- City distribution matches configured weights
- Fraud patterns modify trip data correctly
- Simulator settings parse environment variables

### ROI tests (`test_roi_api.py`)

- Three scenarios computed (conservative, realistic, aggressive)
- Payback period is positive
- ROI percentage is positive
- Input validation (negative GMV rejected, etc.)

---

## Test Design Principles

1. **No external dependencies**: Tests mock Redis and PostgreSQL where possible. The `conftest.py` fixture provides all needed env vars.

2. **Deterministic**: Random seeds are fixed (`RANDOM_SEED=42`). Tests produce the same results on every run.

3. **Fast**: Most tests complete in under 1 second. ML model tests may take 2-3 seconds for feature engineering.

4. **Independent**: Each test cleans up after itself. No test depends on another test's output.

5. **Security-safe**: Test secrets are never production secrets. The `conftest.py` ensures this.

---

## Adding New Tests

1. Create `tests/test_your_feature.py`
2. The `security_env` fixture from `conftest.py` applies automatically
3. Use FastAPI's `TestClient` for API tests:
   ```python
   from fastapi.testclient import TestClient
   from api.main import app

   client = TestClient(app)

   def test_my_endpoint():
       response = client.get("/my/endpoint")
       assert response.status_code == 200
   ```
4. Mock external dependencies (Redis, PostgreSQL) where appropriate
5. Run: `pytest tests/test_your_feature.py -v`

---

## Next

- [Demo Guide](./10-demo-guide.md) — how to run the demo
- [Troubleshooting and FAQ](./11-troubleshooting-and-faq.md) — common issues
