#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Porter Intelligence Platform — Fallback Validation
# ──────────────────────────────────────────────────────────────────────────────
# Verifies the fallback demo path is viable when the live environment fails.
# Checks (in order):
#   A. Model artifacts present locally (can score offline)
#   B. Sample CSV datasets present (can run batch demo)
#   C. Stateless scorer imports cleanly (no Redis/Postgres needed)
#   D. ROI calculator module loads
#   E. Board pack PDF available (or noted missing if archived)
#   F. Demo fallback markdown present
#
# Exit codes
#   0 — fallback is safe to use
#   1 — fallback cannot be trusted; investigate before the meeting
# ──────────────────────────────────────────────────────────────────────────────

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PY="${ROOT_DIR}/venv/bin/python"
[[ -x "${PY}" ]] || PY="python3"

FAIL=0
pass()    { printf "\033[1;32m  ✓\033[0m %s\n" "$*"; }
warn()    { printf "\033[1;33m  !\033[0m %s\n" "$*"; }
fail()    { printf "\033[1;31m  ✗\033[0m %s\n" "$*"; FAIL=1; }
section() { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }

# ── A. Model artifacts ────────────────────────────────────────────────────────
section "A. Model artifacts"
MODEL_DIR="${ROOT_DIR}/model/weights"
for f in "two_stage_config.json" "feature_names.json"; do
  if [[ -f "${MODEL_DIR}/${f}" ]]; then
    pass "${f}"
  else
    fail "missing: ${MODEL_DIR}/${f}"
  fi
done
if ls "${MODEL_DIR}"/*.json >/dev/null 2>&1 || ls "${MODEL_DIR}"/*.pkl >/dev/null 2>&1; then
  pass "model weight files present"
else
  fail "no weight files in ${MODEL_DIR}"
fi

# ── B. Sample datasets ────────────────────────────────────────────────────────
section "B. Sample datasets"
SAMPLES_DIR="${ROOT_DIR}/data/samples"
if [[ -d "${SAMPLES_DIR}" ]] && [[ -n "$(ls -A "${SAMPLES_DIR}" 2>/dev/null)" ]]; then
  SAMPLE_COUNT=$(ls -1 "${SAMPLES_DIR}" 2>/dev/null | wc -l | tr -d ' ')
  pass "data/samples/ populated (${SAMPLE_COUNT} files)"
  ls -1 "${SAMPLES_DIR}" 2>/dev/null | awk 'NR<=5 {print "    · " $0}'
else
  fail "data/samples/ empty or missing — batch demo will fail"
fi

# ── C. Stateless scorer import ────────────────────────────────────────────────
section "C. Stateless scorer (offline path)"
if "${PY}" -c "from ml.stateless_scorer import score_trip_stateless, build_feature_vector; print('ok')" 2>/dev/null | grep -q ok; then
  pass "ml.stateless_scorer imports"
else
  fail "ml.stateless_scorer import failed — run: ${PY} -c 'from ml.stateless_scorer import score_trip_stateless'"
fi

# ── D. ROI calculator ─────────────────────────────────────────────────────────
section "D. ROI calculator"
if "${PY}" -c "from api.routes.roi import build_roi_response; print('ok')" 2>/dev/null | grep -q ok; then
  pass "ROI module loads"
else
  fail "ROI module failed to import"
fi

# ── E. Board pack / fallback assets ───────────────────────────────────────────
section "E. Fallback assets"
BOARD_PACK_CANDIDATES=(
  "_archive/docs_sales/founders-work/artifacts/porter-intelligence-board-pack.pdf"
  "founders work/artifacts/porter-intelligence-board-pack.pdf"
)
FOUND_BOARD=0
for p in "${BOARD_PACK_CANDIDATES[@]}"; do
  if [[ -f "${ROOT_DIR}/${p}" ]]; then
    pass "board pack: ${p}"
    FOUND_BOARD=1
    break
  fi
done
[[ "${FOUND_BOARD}" == 0 ]] && warn "board pack PDF not found at expected paths — regenerate before meeting"

if [[ -f "${ROOT_DIR}/docs/demo/fail-safe-demo.md" ]]; then
  pass "docs/demo/fail-safe-demo.md present"
else
  warn "docs/demo/fail-safe-demo.md missing — script walk-through unavailable"
fi

if [[ -f "${ROOT_DIR}/docs/demo/day-13-final-checklist.md" ]]; then
  pass "day-13 checklist present"
else
  warn "day-13 checklist missing"
fi

# ── F. Offline scoring smoke test ─────────────────────────────────────────────
section "F. Offline scoring smoke test"
SMOKE=$("${PY}" - <<'PY' 2>&1
import json, sys
try:
    import xgboost as xgb
    from pathlib import Path
    w = Path("model/weights")
    names = json.loads((w / "feature_names.json").read_text())
    cfg   = json.loads((w / "two_stage_config.json").read_text())
    action = cfg.get("action_threshold")
    watch  = cfg.get("watchlist_threshold")
    assert isinstance(names, list) and len(names) == 31, f"expected 31 features, got {len(names)}"
    assert action and watch and action > watch, "thresholds invalid"
    print("OK")
except Exception as e:
    print(f"ERR {e}")
    sys.exit(1)
PY
)
if [[ "${SMOKE}" == "OK" ]]; then
  pass "offline scoring artifacts valid (31 features, thresholds ok)"
else
  fail "offline smoke test failed: ${SMOKE}"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
if [[ "${FAIL}" == 0 ]]; then
  printf "\033[1;32m────── FALLBACK READY ──────\033[0m\n"
  printf "  All offline paths validated. You can run the demo without the live stack.\n"
  exit 0
else
  printf "\033[1;31m────── FALLBACK NOT SAFE ──────\033[0m\n"
  printf "  Fix the failures above before relying on the fallback path.\n"
  exit 1
fi
