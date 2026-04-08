#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
API_PORT="${API_PORT:-8000}"
LOG_DIR="${ROOT_DIR}/logs"
API_LOG="${LOG_DIR}/local-api.log"

cd "${ROOT_DIR}"

mkdir -p "${LOG_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "[local-up] Creating virtual environment"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

echo "[local-up] Installing Python dependencies"
"${VENV_DIR}/bin/pip" install -r requirements.txt >/dev/null

if [[ ! -f ".env" ]]; then
  echo "[local-up] Copying .env.example to .env"
  cp .env.example .env
fi

if command -v docker >/dev/null 2>&1; then
  echo "[local-up] Starting PostgreSQL and Redis with docker compose"
  docker compose up -d >/dev/null
else
  echo "[local-up] Docker is not installed. Skipping infrastructure startup."
fi

if pgrep -f "uvicorn api.main:app --host 0.0.0.0 --port ${API_PORT}" >/dev/null 2>&1; then
  echo "[local-up] API already running on port ${API_PORT}"
else
  echo "[local-up] Starting API on port ${API_PORT}"
  nohup "${VENV_DIR}/bin/uvicorn" api.main:app \
    --host 0.0.0.0 \
    --port "${API_PORT}" \
    >"${API_LOG}" 2>&1 &
  sleep 3
fi

echo "[local-up] Health check"
if curl -sf "http://localhost:${API_PORT}/health" >/dev/null; then
  echo "[local-up] Backend healthy at http://localhost:${API_PORT}"
else
  echo "[local-up] Backend did not become healthy. Check ${API_LOG}"
  exit 1
fi

cat <<EOF

Local stack is ready.

API:
  http://localhost:${API_PORT}

Dashboard UI:
  cd dashboard-ui
  npm install
  npm run dev

Logs:
  tail -f ${API_LOG}
EOF
