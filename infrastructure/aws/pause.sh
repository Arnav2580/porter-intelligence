#!/usr/bin/env bash
# Porter Intelligence Platform — Cost pause script
#
# Stops all billable AWS resources without destroying configuration or data.
# Safe to run before a demo break, overnight, or while iterating locally.
#
# Usage:
#   ACCOUNT_ID=767678952517 REGION=ap-southeast-2 bash infrastructure/aws/pause.sh
#
# What this does (in order of cost impact):
#   1. Sets ECS desired_count=0      → stops Fargate tasks     (~$42/month saved)
#   2. Stops RDS instance            → stops DB billing         (~$13/month saved)
#   3. Deletes ElastiCache cluster   → stops cache billing      (~$13/month saved)
#   4. Deletes ALB + target group    → stops LB billing         (~$18/month saved)
#
# Total saved: ~$86/month
#
# What is NOT deleted (costs < $1/month combined, worth keeping):
#   - ECR repository (image layers)
#   - ECS cluster definition
#   - VPC, subnets, security groups
#   - Secrets Manager secrets
#   - CloudWatch log group
#   - IAM roles
#
# To resume after pause, re-run:
#   ACCOUNT_ID=... REGION=... bash infrastructure/aws/setup.sh   # re-creates ALB + cache
#   ACCOUNT_ID=... REGION=... bash infrastructure/aws/deploy.sh  # redeploys ECS service
#
# NOTE: RDS 'stop' lasts 7 days maximum — AWS auto-starts it after that.
#       For a permanent pause, use teardown.sh instead.

set -euo pipefail

ACCOUNT_ID="${ACCOUNT_ID:?Set ACCOUNT_ID}"
REGION="${REGION:-ap-southeast-2}"
PROJECT="${PROJECT:-porter}"
ENV="${ENV:-buyer}"
STATE_FILE="${STATE_FILE:-infrastructure/aws/state/${PROJECT}-${ENV}-${REGION}.json}"

log() { printf '\n==> %s\n' "$1"; }
warn() { printf '[warn] %s\n' "$1"; }

state_get() {
  python3 - "${STATE_FILE}" "${1}" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
key  = sys.argv[2]
if not path.exists() or path.stat().st_size == 0:
    print(""); raise SystemExit
with path.open() as f:
    data = json.load(f)
print(data.get(key, "") or "")
PY
}

state_set() {
  python3 - "${STATE_FILE}" "${1}" "${2}" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
key, value = sys.argv[2], sys.argv[3]
data = json.load(path.open()) if path.exists() and path.stat().st_size > 0 else {}
data[key] = value
with path.open("w") as f:
    json.dump(data, f, indent=2, sort_keys=True); f.write("\n")
PY
}

is_missing() { [[ -z "${1:-}" || "${1}" == "None" || "${1}" == "null" ]]; }

# ── Load state ────────────────────────────────────────────────────────────────

if [[ ! -f "${STATE_FILE}" ]]; then
  printf 'State file not found: %s\n' "${STATE_FILE}"
  printf 'Run setup.sh first, or check PROJECT/ENV/REGION.\n'
  exit 1
fi

CLUSTER_NAME="$(state_get CLUSTER_NAME)"
SERVICE_NAME="$(state_get SERVICE_NAME)"
DB_INSTANCE_ID="$(state_get DB_INSTANCE_ID)"
CACHE_CLUSTER_ID="$(state_get CACHE_CLUSTER_ID)"
ALB_ARN="$(state_get ALB_ARN)"
TARGET_GROUP_ARN="$(state_get TARGET_GROUP_ARN)"

printf '\nPorter Intelligence Platform — Cost Pause\n'
printf '  Region:    %s\n' "${REGION}"
printf '  State:     %s\n' "${STATE_FILE}"
printf '  Cluster:   %s\n' "${CLUSTER_NAME}"
printf '  RDS:       %s\n' "${DB_INSTANCE_ID}"
printf '  Redis:     %s\n' "${CACHE_CLUSTER_ID}"
printf '\n'

# ── 1. Stop ECS tasks ─────────────────────────────────────────────────────────

log "Step 1/4 — Stopping ECS Fargate tasks (desired_count → 0)"

if ! is_missing "${CLUSTER_NAME}" && ! is_missing "${SERVICE_NAME}"; then
  SERVICE_STATUS="$(
    aws ecs describe-services \
      --cluster "${CLUSTER_NAME}" \
      --services "${SERVICE_NAME}" \
      --region "${REGION}" \
      --query 'services[0].status' \
      --output text 2>/dev/null || true
  )"
  if [[ "${SERVICE_STATUS}" == "ACTIVE" ]]; then
    aws ecs update-service \
      --cluster "${CLUSTER_NAME}" \
      --service "${SERVICE_NAME}" \
      --desired-count 0 \
      --region "${REGION}" >/dev/null
    printf '  ECS service set to desired_count=0. Tasks will drain.\n'
    printf '  Savings: ~$42/month\n'
  elif is_missing "${SERVICE_STATUS}" || [[ "${SERVICE_STATUS}" == "None" ]]; then
    printf '  ECS service not found — already stopped or not deployed.\n'
  else
    printf '  ECS service status: %s — skipping.\n' "${SERVICE_STATUS}"
  fi
else
  warn "CLUSTER_NAME or SERVICE_NAME missing from state — skipping ECS."
fi

# ── 2. Stop RDS instance ──────────────────────────────────────────────────────

log "Step 2/4 — Stopping RDS instance (preserves data, max 7 days)"

if ! is_missing "${DB_INSTANCE_ID}"; then
  DB_STATUS="$(
    aws rds describe-db-instances \
      --db-instance-identifier "${DB_INSTANCE_ID}" \
      --region "${REGION}" \
      --query 'DBInstances[0].DBInstanceStatus' \
      --output text 2>/dev/null || true
  )"
  if [[ "${DB_STATUS}" == "available" ]]; then
    aws rds stop-db-instance \
      --db-instance-identifier "${DB_INSTANCE_ID}" \
      --region "${REGION}" >/dev/null
    printf '  RDS instance stopping. This takes 2-5 minutes.\n'
    printf '  WARNING: AWS auto-restarts stopped RDS instances after 7 days.\n'
    printf '  If you need longer, run teardown.sh --rds-only to delete + snapshot.\n'
    printf '  Savings: ~$13/month\n'
  elif [[ "${DB_STATUS}" == "stopped" ]]; then
    printf '  RDS already stopped.\n'
  elif is_missing "${DB_STATUS}" || [[ "${DB_STATUS}" == "None" ]]; then
    printf '  RDS instance not found — already deleted or not provisioned.\n'
  else
    printf '  RDS status: %s — cannot stop now. Try again when status is "available".\n' "${DB_STATUS}"
  fi
else
  warn "DB_INSTANCE_ID missing from state — skipping RDS."
fi

# ── 3. Delete ElastiCache cluster ─────────────────────────────────────────────

log "Step 3/4 — Deleting ElastiCache cluster (no data to preserve)"

if ! is_missing "${CACHE_CLUSTER_ID}"; then
  CACHE_STATUS="$(
    aws elasticache describe-cache-clusters \
      --cache-cluster-id "${CACHE_CLUSTER_ID}" \
      --region "${REGION}" \
      --query 'CacheClusters[0].CacheClusterStatus' \
      --output text 2>/dev/null || true
  )"
  if [[ "${CACHE_STATUS}" == "available" ]]; then
    aws elasticache delete-cache-cluster \
      --cache-cluster-id "${CACHE_CLUSTER_ID}" \
      --region "${REGION}" >/dev/null
    printf '  ElastiCache cluster deletion initiated.\n'
    printf '  Recreate with: ACCOUNT_ID=... REGION=... bash infrastructure/aws/setup.sh\n'
    printf '  Savings: ~$13/month\n'
  elif is_missing "${CACHE_STATUS}" || [[ "${CACHE_STATUS}" == "None" ]]; then
    printf '  ElastiCache cluster not found — already deleted.\n'
  else
    printf '  ElastiCache status: %s — skipping.\n' "${CACHE_STATUS}"
  fi
else
  warn "CACHE_CLUSTER_ID missing from state — skipping ElastiCache."
fi

# ── 4. Delete ALB + target group ──────────────────────────────────────────────

log "Step 4/4 — Deleting ALB and target group"

if ! is_missing "${ALB_ARN}"; then
  ALB_EXISTS="$(
    aws elbv2 describe-load-balancers \
      --load-balancer-arns "${ALB_ARN}" \
      --region "${REGION}" \
      --query 'LoadBalancers[0].LoadBalancerArn' \
      --output text 2>/dev/null || true
  )"
  if ! is_missing "${ALB_EXISTS}"; then
    # Delete listeners first
    LISTENER_ARNS="$(
      aws elbv2 describe-listeners \
        --load-balancer-arn "${ALB_ARN}" \
        --region "${REGION}" \
        --query 'Listeners[*].ListenerArn' \
        --output text 2>/dev/null || true
    )"
    for LISTENER_ARN in ${LISTENER_ARNS}; do
      aws elbv2 delete-listener \
        --listener-arn "${LISTENER_ARN}" \
        --region "${REGION}" >/dev/null 2>&1 || true
    done
    aws elbv2 delete-load-balancer \
      --load-balancer-arn "${ALB_ARN}" \
      --region "${REGION}" >/dev/null
    state_set ALB_ARN ""
    printf '  ALB deleted.\n'
    printf '  Savings: ~$18/month\n'
  else
    printf '  ALB not found — already deleted.\n'
    state_set ALB_ARN ""
  fi
fi

if ! is_missing "${TARGET_GROUP_ARN}"; then
  TG_EXISTS="$(
    aws elbv2 describe-target-groups \
      --target-group-arns "${TARGET_GROUP_ARN}" \
      --region "${REGION}" \
      --query 'TargetGroups[0].TargetGroupArn' \
      --output text 2>/dev/null || true
  )"
  if ! is_missing "${TG_EXISTS}"; then
    aws elbv2 delete-target-group \
      --target-group-arn "${TARGET_GROUP_ARN}" \
      --region "${REGION}" >/dev/null 2>&1 || true
    state_set TARGET_GROUP_ARN ""
    printf '  Target group deleted.\n'
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────

printf '\n'
printf '=================================================================\n'
printf ' Pause complete — estimated monthly savings: ~$86/month\n'
printf '=================================================================\n'
printf '\n'
printf ' Remaining costs (near-zero):\n'
printf '   ECR image storage     ~$1-2/month\n'
printf '   Secrets Manager       ~$2/month\n'
printf '   CloudWatch log group  ~$0 (no new log ingest)\n'
printf '\n'
printf ' To RESUME deployment:\n'
printf '   ACCOUNT_ID=%s REGION=%s PROJECT=%s ENV=%s \\\n' \
  "${ACCOUNT_ID}" "${REGION}" "${PROJECT}" "${ENV}"
printf '     bash infrastructure/aws/setup.sh\n'
printf '   ACCOUNT_ID=%s REGION=%s PROJECT=%s ENV=%s \\\n' \
  "${ACCOUNT_ID}" "${REGION}" "${PROJECT}" "${ENV}"
printf '     bash infrastructure/aws/deploy.sh\n'
printf '\n'
printf ' For demo WITHOUT AWS (free, works now):\n'
printf '   docker compose up\n'
printf '   # API on http://localhost:8000 — full benchmark mode, no DB needed\n'
printf '\n'
