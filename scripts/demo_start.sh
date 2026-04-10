#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Porter Intelligence Platform — Demo Start
# ──────────────────────────────────────────────────────────────────────────────
# Boots the full demo environment (API + frontend) and validates readiness.
# Run 15–30 minutes before a buyer meeting.
#
# Usage:
#   ./scripts/demo_start.sh
#
# Idempotent: safe to re-run. If services are already up, it only validates.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/venv"
LOG_DIR="${ROOT_DIR}/logs"
API_LOG="${LOG_DIR}/demo-api.log"
UI_LOG="${LOG_DIR}/demo-ui.log"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-5173}"

cd "${ROOT_DIR}"
mkdir -p "${LOG_DIR}"

say() { printf "\033[1;36m[demo-start]\033[0m %s\n" "$*"; }
ok()  { printf "\033[1;32m  ✓\033[0m %s\n" "$*"; }
bad() { printf "\033[1;31m  ✗\033[0m %s\n" "$*" >&2; }

# ── 1. venv + deps ────────────────────────────────────────────────────────────
if [[ ! -d "${VENV_DIR}" ]]; then
  say "Creating virtualenv"
  python3 -m venv "${VENV_DIR}"
fi
say "Installing Python dependencies (quiet)"
"${VENV_DIR}/bin/pip" install -q -r requirements.txt
ok "dependencies installed"

# ── 2. .env guard ─────────────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  say ".env not found — copying from .env.example"
  cp .env.example .env
fi
ok ".env present"

# ── 3. Infrastructure (Redis + Postgres) via docker compose ───────────────────
if command -v docker >/dev/null 2>&1; then
  say "Starting Postgres + Redis (docker compose up -d)"
  docker compose up -d >/dev/null
  ok "infra containers up"
else
  bad "docker not installed — Redis/Postgres must be running externally"
fi

# ── 4. API ────────────────────────────────────────────────────────────────────
if pgrep -f "uvicorn api.main:app.*--port ${API_PORT}" >/dev/null 2>&1; then
  ok "API already running on :${API_PORT}"
else
  say "Starting API on :${API_PORT}"
  nohup "${VENV_DIR}/bin/uvicorn" api.main:app \
    --host 0.0.0.0 --port "${API_PORT}" \
    >"${API_LOG}" 2>&1 &
  sleep 4
fi

# ── 5. API health ─────────────────────────────────────────────────────────────
say "Health check → /health"
HEALTH_JSON=$(curl -sf "http://localhost:${API_PORT}/health" || true)
if [[ -z "${HEALTH_JSON}" ]]; then
  bad "API did not respond. Tail: ${API_LOG}"
  tail -n 30 "${API_LOG}" >&2 || true
  exit 1
fi

MODEL_LOADED=$(printf "%s" "${HEALTH_JSON}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('model_loaded',False))")
DB_OK=$(printf "%s" "${HEALTH_JSON}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('database',''))")
REDIS_OK=$(printf "%s" "${HEALTH_JSON}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('redis',''))")
SHADOW=$(printf "%s" "${HEALTH_JSON}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('shadow_mode',False))")

[[ "${MODEL_LOADED}" == "True" ]]  && ok "model loaded"      || { bad "model NOT loaded"; exit 1; }
[[ "${DB_OK}" == "ok" ]]           && ok "database ok"        || bad "database: ${DB_OK}"
[[ "${REDIS_OK}" == "ok" ]]        && ok "redis ok"           || bad "redis: ${REDIS_OK}"
[[ "${SHADOW}" == "False" ]]       && ok "shadow_mode: OFF"   || say "shadow_mode: ON (will suppress enforcement)"

# ── 6. Pre-seed demo database with reviewed cases ─────────────────────────────
say "Seeding demo database (idempotent)"
"${VENV_DIR}/bin/python" scripts/seed_demo_db.py || bad "DB seed failed (KPI panel may show zero metrics)"

# ── 8. Frontend dev server ────────────────────────────────────────────────────
if pgrep -f "vite.*--port ${UI_PORT}" >/dev/null 2>&1 || pgrep -f "dashboard-ui.*vite" >/dev/null 2>&1; then
  ok "UI dev server already running on :${UI_PORT}"
else
  say "Starting frontend dev server on :${UI_PORT}"
  (cd dashboard-ui && nohup npm run dev -- --port "${UI_PORT}" >"${UI_LOG}" 2>&1 &)
  sleep 4
fi

if curl -sf "http://localhost:${UI_PORT}" >/dev/null 2>&1; then
  ok "UI reachable at http://localhost:${UI_PORT}"
else
  bad "UI not reachable yet — check ${UI_LOG}"
fi

# ── 9. Final readiness summary ────────────────────────────────────────────────
cat <<EOF

──────────────────────────────────────────────────────────
  DEMO ENVIRONMENT READY
──────────────────────────────────────────────────────────
  Dashboard        http://localhost:${UI_PORT}
  Analyst          http://localhost:${UI_PORT}/login
  OpenAPI          http://localhost:${API_PORT}/docs
  Health           http://localhost:${API_PORT}/health

  Logs
    API  tail -f ${API_LOG}
    UI   tail -f ${UI_LOG}

  Pre-meeting checklist → docs/demo/day-13-final-checklist.md
──────────────────────────────────────────────────────────
EOF
