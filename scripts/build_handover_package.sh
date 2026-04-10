#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Porter Intelligence Platform — Handover Package Builder
# ──────────────────────────────────────────────────────────────────────────────
# Produces a single tarball that constitutes the full source handover package.
# Intended to be signed, hashed, and delivered under NDA after contract signing.
#
# Output: dist/handover/porter-handover-<YYYYMMDD>.tar.gz
#         dist/handover/porter-handover-<YYYYMMDD>.sha256
#         dist/handover/MANIFEST.txt
#
# Usage:
#   ./scripts/build_handover_package.sh
#
# The package contains ONLY files that should legitimately transfer. Model
# weights, private datasets, and internal docs are included. Local .venv,
# node_modules, logs, and secrets are excluded.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

STAMP=$(date +%Y%m%d)
DIST_DIR="${ROOT_DIR}/dist/handover"
STAGE_DIR="${DIST_DIR}/stage-${STAMP}"
TARBALL="${DIST_DIR}/porter-handover-${STAMP}.tar.gz"
SUMFILE="${DIST_DIR}/porter-handover-${STAMP}.sha256"
MANIFEST="${DIST_DIR}/MANIFEST.txt"

mkdir -p "${DIST_DIR}"
rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}"

say() { printf "\033[1;36m[handover]\033[0m %s\n" "$*"; }

# ── 1. Copy what belongs in the package ──────────────────────────────────────
say "Staging source"
SOURCE_PATHS=(
  api auth database enforcement generator ingestion ml model monitoring security
  dashboard dashboard-ui infrastructure scripts tests docs
  runtime_config.py requirements.txt docker-compose.yml
  README.md .env.example .gitignore .github
)

for p in "${SOURCE_PATHS[@]}"; do
  if [[ -e "${ROOT_DIR}/${p}" ]]; then
    mkdir -p "$(dirname "${STAGE_DIR}/${p}")"
    cp -R "${ROOT_DIR}/${p}" "${STAGE_DIR}/${p}"
    echo "  +  ${p}"
  else
    echo "  -  skipped (missing): ${p}"
  fi
done

# ── 2. Strip anything that must not ship ─────────────────────────────────────
say "Stripping venv/node_modules/cache/logs/secrets"
find "${STAGE_DIR}" -type d \( \
  -name "venv" -o -name ".venv" -o -name "node_modules" -o \
  -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o \
  -name ".ruff_cache" -o -name "logs" -o -name ".git" -o \
  -name "dist" -o -name "build" -o -name ".vite" -o -name ".netlify" -o \
  -name ".vercel" -o -name "state" \
\) -prune -exec rm -rf {} +

find "${STAGE_DIR}" -type f \( \
  -name ".env" -o -name ".env.local" -o -name "*.log" -o \
  -name ".DS_Store" -o -name "*.pyc" -o -name "*.pyo" \
\) -delete

# ── 3. Include model artifacts (weights live outside git) ────────────────────
say "Including model weights"
if [[ -d "${ROOT_DIR}/model/weights" ]]; then
  mkdir -p "${STAGE_DIR}/model/weights"
  cp -R "${ROOT_DIR}/model/weights/." "${STAGE_DIR}/model/weights/"
fi

# ── 4. Include sample datasets ───────────────────────────────────────────────
if [[ -d "${ROOT_DIR}/data/samples" ]]; then
  mkdir -p "${STAGE_DIR}/data/samples"
  cp -R "${ROOT_DIR}/data/samples/." "${STAGE_DIR}/data/samples/"
fi

# ── 5. Final manifest inside the package ─────────────────────────────────────
cat > "${STAGE_DIR}/HANDOVER.txt" <<EOF
Porter Intelligence Platform — Source Handover Package
Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Version:   $(git -C "${ROOT_DIR}" describe --always 2>/dev/null || echo "untagged")
Commit:    $(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || echo "unknown")
Branch:    $(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

Included
--------
  application code:  api/ auth/ database/ enforcement/ generator/ ingestion/
                     ml/ model/ monitoring/ security/
  dashboard:         dashboard/ dashboard-ui/
  infrastructure:    infrastructure/ docker-compose.yml
  scripts:           scripts/
  tests:             tests/
  docs (full):       docs/ (handover, runbooks, security, demo, deployment)
  model artifacts:   model/weights/ (weights, thresholds, feature names)
  sample data:       data/samples/
  config:            requirements.txt runtime_config.py .env.example

Excluded (by design)
--------------------
  venv/ node_modules/ __pycache__/ .pytest_cache/
  .env .env.local logs/ .git/
  dist/ build/ (regenerated)
  data/raw/ (regenerate via generator/)

Quickstart for the new owner
----------------------------
  1. Start          scripts/local_up.sh
  2. Verify         scripts/fallback_check.sh
  3. Rotate secrets docs/runbooks/rotate-secrets.md
  4. Retrain model  docs/runbooks/retrain-model.md
  5. Restore        docs/runbooks/restore-from-backup.md
EOF

# ── 6. Tar it ────────────────────────────────────────────────────────────────
say "Creating tarball"
tar -czf "${TARBALL}" -C "${DIST_DIR}" "stage-${STAMP}"
rm -rf "${STAGE_DIR}"

# ── 7. Hash ──────────────────────────────────────────────────────────────────
say "Hashing"
if command -v shasum >/dev/null; then
  shasum -a 256 "${TARBALL}" | awk '{print $1}' > "${SUMFILE}"
else
  sha256sum "${TARBALL}" | awk '{print $1}' > "${SUMFILE}"
fi

# ── 8. Top-level manifest ────────────────────────────────────────────────────
{
  echo "Porter Intelligence Platform — Handover Manifest"
  echo "Built:    $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Tarball:  $(basename "${TARBALL}")"
  echo "SHA-256:  $(cat "${SUMFILE}")"
  echo "Size:     $(du -h "${TARBALL}" | awk '{print $1}')"
} > "${MANIFEST}"

cat <<EOF

──────────────────────────────────────────────────────────
  HANDOVER PACKAGE BUILT
──────────────────────────────────────────────────────────
  Tarball   ${TARBALL}
  SHA-256   $(cat "${SUMFILE}")
  Size      $(du -h "${TARBALL}" | awk '{print $1}')
  Manifest  ${MANIFEST}

  Deliver under NDA. Do not upload to a public location.
──────────────────────────────────────────────────────────
EOF
