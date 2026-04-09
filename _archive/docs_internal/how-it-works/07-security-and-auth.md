# 07 — Security And Auth

[Index](./README.md) | [Prev: Frontend](./06-frontend-and-dashboard.md) | [Next: Deployment](./08-deployment-and-infrastructure.md)

This document covers every security mechanism in the platform: encryption, authentication, authorization, audit logging, and hardening.

---

## Security Architecture Overview

```
Request arrives
    │
    ▼
┌────────────────────────────────┐
│  Security Headers Middleware    │  X-Content-Type-Options, X-Frame-Options,
│                                │  X-XSS-Protection, Referrer-Policy
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  CORS Middleware               │  API_ALLOWED_ORIGINS whitelist
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  Rate Limiting (slowapi)       │  Per-endpoint limits
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  JWT Authentication            │  HS256, 8-hour expiry
│  OAuth2 Bearer token           │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  RBAC Permission Check         │  Role → permission matrix
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  PII Encryption (AES-256-GCM) │  Encrypt before DB write
│                                │  Decrypt on read
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  Audit Logging                 │  Every decision logged
│                                │  Immutable audit trail
└────────────────────────────────┘
```

---

## 1. PII Encryption

**Source:** `security/encryption.py`

### Algorithm

- **AES-256-GCM** (Authenticated Encryption with Associated Data)
- 256-bit key (32 bytes, base64-encoded in `ENCRYPTION_KEY` env var)
- 96-bit random nonce per encryption operation
- Output: base64-encoded `nonce + ciphertext + authentication_tag`

### What is encrypted

| Field | Where | When |
|---|---|---|
| `trip_id` | FraudCase table | Before database write |
| `driver_id` | FraudCase table | Before database write |

PII is encrypted before persisting to PostgreSQL and decrypted when reading for API responses.

### Key management

```bash
# Generate a valid encryption key:
python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Set as `ENCRYPTION_KEY` in `.env`. The key must decode to exactly 32 bytes.

### Plaintext fallback

In demo mode only (`APP_RUNTIME_MODE=demo` + `ALLOW_PLAINTEXT_PII=true`), encryption can be disabled. This is for development convenience. In production mode, `ENCRYPTION_KEY` must be properly configured or the API will refuse to persist PII.

### Implementation details

```python
def encrypt_pii(value: str) -> str:
    nonce = secrets.token_bytes(12)          # 96-bit random nonce
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, value.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

def decrypt_pii(value: str) -> str:
    raw = base64.urlsafe_b64decode(value)
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
```

---

## 2. JWT Authentication

**Source:** `auth/jwt.py`

### Configuration

| Setting | Value |
|---|---|
| Algorithm | HS256 |
| Signing key | `JWT_SECRET_KEY` env var |
| Token expiry | 480 minutes (8 hours) |
| Password hashing | bcrypt (via passlib) |

### Token creation

```python
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=480)
    return jwt.encode(to_encode, secret_key, "HS256")
```

Token payload contains: `sub` (username), `role`, `name`, `exp` (expiry).

### Token verification

```python
def verify_token(token: str) -> Optional[dict]:
    return jwt.decode(token, secret_key, algorithms=["HS256"])
```

Returns the decoded payload or `None` if invalid/expired.

### Key generation

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set as `JWT_SECRET_KEY` in `.env`.

---

## 3. Role-Based Access Control (RBAC)

**Source:** `auth/dependencies.py`, `auth/models.py`

### Roles

| Role | Username | Purpose |
|---|---|---|
| `admin` | `admin` | Full platform access |
| `ops_manager` | `ops_manager` | Read cases, manage status, view reports |
| `ops_analyst` | `analyst_1` | Review assigned/unassigned cases, take driver actions |
| `read_only` | `viewer` | Read-only access to all data |

### Permission matrix

| Permission | admin | ops_manager | ops_analyst | read_only |
|---|---|---|---|---|
| `read:all` | Yes | — | — | — |
| `write:all` | Yes | — | — | — |
| `read:cases` | Yes | Yes | Yes | Yes |
| `write:case_status` | Yes | Yes | Yes | — |
| `write:driver_actions` | Yes | Yes | Yes | — |
| `read:reports` | Yes | Yes | — | Yes |
| `read:kpi` | Yes | Yes | Yes | Yes |

### How permissions are checked

```python
@router.get("/cases/")
async def list_cases(
    user=Depends(require_permission("read:cases")),
):
    # user dict contains: sub, role, name
```

The `require_permission()` dependency:
1. Extracts and verifies the JWT token
2. Maps the user's role to permissions
3. Checks if the required permission is in the role's permission set
4. Returns 403 if denied

### Analyst case isolation

Analysts (`ops_analyst` role) can only see:
- Cases assigned to them
- Unassigned cases

They cannot see cases assigned to other analysts. This is enforced at the query level in the cases router.

---

## 4. Seed Users

**Source:** `auth/config.py`

Four users are created at startup from environment variables:

| Username | Env Variable for Password | Role |
|---|---|---|
| `admin` | `PORTER_AUTH_ADMIN_PASSWORD` | admin |
| `ops_manager` | `PORTER_AUTH_OPS_MANAGER_PASSWORD` | ops_manager |
| `analyst_1` | `PORTER_AUTH_ANALYST_PASSWORD` | ops_analyst |
| `viewer` | `PORTER_AUTH_VIEWER_PASSWORD` | read_only |

Passwords are hashed with bcrypt at startup. The platform will not start if any seed user password is missing or uses a placeholder value.

---

## 5. Rate Limiting

**Source:** `api/limiting.py`

Rate limiting is implemented via `slowapi` (Redis-backed if available, in-memory fallback).

| Endpoint Group | Limit | Env Override |
|---|---|---|
| Auth (`/auth/token`) | 10/minute | `AUTH_TOKEN_RATE_LIMIT` |
| Fraud scoring (`/fraud/score`) | 100/minute | `FRAUD_SCORE_RATE_LIMIT` |
| Ingestion (`/ingest/*`) | 300/minute | `INGEST_RATE_LIMIT` |

Rate limits are per-client (IP-based).

---

## 6. Security Headers

**Source:** `api/main.py` (SecurityHeadersMiddleware)

Every response includes:

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |

---

## 7. CORS

**Source:** `api/main.py` (CORSMiddleware)

Configured via `API_ALLOWED_ORIGINS` environment variable:

```bash
API_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,https://your-domain.com
```

Only listed origins can make cross-origin requests.

---

## 8. HMAC Webhook Verification

**Source:** `ingestion/webhook.py`

Incoming webhook requests can include an `X-Porter-Signature` header:

```
X-Porter-Signature: sha256=<hex_digest>
```

Verification:
1. Compute `HMAC-SHA256(WEBHOOK_SECRET, request_body)`
2. Compare with incoming signature using `hmac.compare_digest()` (timing-safe)
3. Reject with 401 if mismatch

In production mode, webhook signature verification is required.

---

## 9. Audit Logging

**Source:** `database/models.py` (AuditLog table)

Every analyst decision is logged to an immutable audit table:

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique log entry ID |
| `user_id` | string | Who performed the action |
| `action` | string | What they did (case_status_change, driver_suspend, etc.) |
| `resource` | string | What they acted on (fraud_case, driver) |
| `resource_id` | string | ID of the resource |
| `details` | JSONB | Full details (old status, new status, notes, reason) |
| `ip_address` | string | Request IP address |
| `created_at` | timestamp | When it happened |

### What is logged

- Every case status change (open → under_review → confirmed/false_alarm)
- Every driver action (suspend, flag, monitor, clear)
- Override reasons (required when dismissing action-tier cases)
- Batch review operations

### Immutability

Audit logs are append-only. There is no update or delete endpoint. The `AuditLog` model has no update methods.

---

## 10. Security Configuration Validation

**Source:** `security/settings.py`

At startup, the platform validates all security-critical environment variables:

1. `JWT_SECRET_KEY` — must not be a placeholder
2. `ENCRYPTION_KEY` — must decode to 32 bytes
3. `WEBHOOK_SECRET` — must not be a placeholder (in prod mode)
4. `PORTER_AUTH_*_PASSWORD` — all four must be set and non-placeholder

If any validation fails:
- In demo mode: logs a warning, continues with reduced security
- In production mode: raises `SecurityConfigurationError`, API returns 503

### Placeholder detection

The system recognises these as placeholder values that must be replaced:
- `change-me-*`
- `your-*`
- `placeholder-*`
- `CHANGE_ME_*`
- Empty strings

---

## Security Checklist For Production

- [ ] Generate strong random `JWT_SECRET_KEY` (48+ characters)
- [ ] Generate valid `ENCRYPTION_KEY` (32-byte base64)
- [ ] Generate strong `WEBHOOK_SECRET`
- [ ] Set strong passwords for all seed users
- [ ] Set `API_ALLOWED_ORIGINS` to exact production domains
- [ ] Set `APP_RUNTIME_MODE=prod`
- [ ] Verify `ALLOW_PLAINTEXT_PII` is NOT set
- [ ] Verify webhook signature verification is active
- [ ] Review rate limits for expected traffic
- [ ] Enable HTTPS (via load balancer or reverse proxy)

---

## Next

- [Deployment and Infrastructure](./08-deployment-and-infrastructure.md) — Docker, AWS, monitoring, scaling
- [Testing and Quality](./09-testing-and-quality.md) — test suite documentation
