#!/usr/bin/env bash
# Porter Intelligence Platform — Full AWS teardown
#
# Deletes ALL provisioned resources in the correct dependency order.
# Use this when you no longer need the environment at all.
#
# Usage:
#   ACCOUNT_ID=767678952517 REGION=ap-southeast-2 bash infrastructure/aws/teardown.sh
#
# Safety: requires you to type "yes" before deleting anything.
# Use --force to skip the confirmation (CI/automated cleanup only).
#
# Deletion order (respects AWS dependency constraints):
#   1. ECS service (desired_count=0 → wait for drain → delete)
#   2. ECS cluster
#   3. ALB listeners → ALB → target group
#   4. ElastiCache cluster
#   5. RDS instance (with final snapshot unless --no-snapshot)
#   6. VPC endpoints
#   7. NAT gateway + EIP
#   8. Security group rules + security groups
#   9. Subnets
#  10. Internet gateway (detach + delete)
#  11. Route tables
#  12. VPC
#  13. CloudWatch log group
#  14. ECR repository images (repo itself is kept — cheap, avoids re-create)
#  15. Secrets Manager secrets (scheduled for 7-day deletion)
#
# What is NOT deleted:
#   - IAM roles (shared service, safe across environments)
#   - ECR repository (no cost without images, but avoids name collision)
#   - Secrets Manager secrets are scheduled for deletion, not immediate

set -euo pipefail

ACCOUNT_ID="${ACCOUNT_ID:?Set ACCOUNT_ID}"
REGION="${REGION:-ap-southeast-2}"
PROJECT="${PROJECT:-porter}"
ENV="${ENV:-buyer}"
STATE_FILE="${STATE_FILE:-infrastructure/aws/state/${PROJECT}-${ENV}-${REGION}.json}"
FORCE="${FORCE:-false}"
NO_SNAPSHOT="${NO_SNAPSHOT:-false}"
SKIP_SNAPSHOT_WAIT="${SKIP_SNAPSHOT_WAIT:-false}"

log()  { printf '\n==> %s\n' "$1"; }
warn() { printf '[warn] %s\n' "$1" >&2; }
ok()   { printf '  [ok] %s\n' "$1"; }
skip() { printf '  [--] %s\n' "$1"; }

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

state_clear() {
  python3 - "${STATE_FILE}" "${1}" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
if not path.exists() or path.stat().st_size == 0:
    raise SystemExit
data = json.load(path.open())
data[key] = ""
with path.open("w") as f:
    json.dump(data, f, indent=2, sort_keys=True); f.write("\n")
PY
}

is_missing() { [[ -z "${1:-}" || "${1}" == "None" || "${1}" == "null" ]]; }

# ── Load state ────────────────────────────────────────────────────────────────

if [[ ! -f "${STATE_FILE}" ]]; then
  printf 'State file not found: %s\n' "${STATE_FILE}"
  exit 1
fi

CLUSTER_NAME="$(state_get CLUSTER_NAME)"
SERVICE_NAME="$(state_get SERVICE_NAME)"
DB_INSTANCE_ID="$(state_get DB_INSTANCE_ID)"
CACHE_CLUSTER_ID="$(state_get CACHE_CLUSTER_ID)"
ALB_ARN="$(state_get ALB_ARN)"
TARGET_GROUP_ARN="$(state_get TARGET_GROUP_ARN)"
VPC_ID="$(state_get VPC_ID)"
INTERNET_GATEWAY_ID="$(state_get INTERNET_GATEWAY_ID)"
PUBLIC_ROUTE_TABLE_ID="$(state_get PUBLIC_ROUTE_TABLE_ID)"
PRIVATE_ROUTE_TABLE_ID="$(state_get PRIVATE_ROUTE_TABLE_ID)"
PUBLIC_SUBNET_A_ID="$(state_get PUBLIC_SUBNET_A_ID)"
PUBLIC_SUBNET_B_ID="$(state_get PUBLIC_SUBNET_B_ID)"
PRIVATE_SUBNET_A_ID="$(state_get PRIVATE_SUBNET_A_ID)"
PRIVATE_SUBNET_B_ID="$(state_get PRIVATE_SUBNET_B_ID)"
SG_ALB_ID="$(state_get SG_ALB_ID)"
SG_APP_ID="$(state_get SG_APP_ID)"
SG_DB_ID="$(state_get SG_DB_ID)"
SG_CACHE_ID="$(state_get SG_CACHE_ID)"
SG_ENDPOINTS_ID="$(state_get SG_ENDPOINTS_ID)"
NAT_GATEWAY_ID="$(state_get NAT_GATEWAY_ID)"
NAT_EIP_ALLOCATION_ID="$(state_get NAT_EIP_ALLOCATION_ID)"
SECRET_PREFIX="$(state_get SECRET_PREFIX)"
LOG_GROUP_NAME="$(state_get LOG_GROUP_NAME)"
ECR_REPO_NAME="${ECR_REPO_NAME:-porter-intelligence}"

printf '\n'
printf '=================================================================\n'
printf '  Porter Intelligence Platform — FULL TEARDOWN\n'
printf '=================================================================\n'
printf '  Region:    %s\n' "${REGION}"
printf '  Account:   %s\n' "${ACCOUNT_ID}"
printf '  State:     %s\n' "${STATE_FILE}"
printf '\n'
printf '  This will DELETE all AWS resources for this environment.\n'
printf '  Data will be preserved in an RDS snapshot (unless --no-snapshot).\n'
printf '\n'

# ── Confirmation ──────────────────────────────────────────────────────────────

if [[ "${FORCE}" != "true" ]]; then
  printf 'Type "yes" to confirm teardown: '
  read -r CONFIRM
  if [[ "${CONFIRM}" != "yes" ]]; then
    printf 'Aborted.\n'
    exit 0
  fi
fi

# ── 1. Stop + delete ECS service ──────────────────────────────────────────────

log "Step 1/15 — ECS service"

if ! is_missing "${CLUSTER_NAME}" && ! is_missing "${SERVICE_NAME}"; then
  SERVICE_STATUS="$(
    aws ecs describe-services \
      --cluster "${CLUSTER_NAME}" --services "${SERVICE_NAME}" \
      --region "${REGION}" --query 'services[0].status' --output text 2>/dev/null || true
  )"
  if [[ "${SERVICE_STATUS}" == "ACTIVE" ]]; then
    aws ecs update-service \
      --cluster "${CLUSTER_NAME}" --service "${SERVICE_NAME}" \
      --desired-count 0 --region "${REGION}" >/dev/null
    printf '  Draining tasks...\n'
    aws ecs wait services-stable \
      --cluster "${CLUSTER_NAME}" --services "${SERVICE_NAME}" \
      --region "${REGION}" 2>/dev/null || true
    aws ecs delete-service \
      --cluster "${CLUSTER_NAME}" --service "${SERVICE_NAME}" \
      --force --region "${REGION}" >/dev/null
    ok "ECS service deleted"
  else
    skip "ECS service not found or not active"
  fi
fi

# ── 2. Delete ECS cluster ─────────────────────────────────────────────────────

log "Step 2/15 — ECS cluster"

if ! is_missing "${CLUSTER_NAME}"; then
  aws ecs delete-cluster --cluster "${CLUSTER_NAME}" --region "${REGION}" >/dev/null 2>&1 || true
  ok "ECS cluster deleted"
fi

# ── 3. Delete ALB + listeners + target group ──────────────────────────────────

log "Step 3/15 — ALB"

if ! is_missing "${ALB_ARN}"; then
  LISTENER_ARNS="$(
    aws elbv2 describe-listeners \
      --load-balancer-arn "${ALB_ARN}" --region "${REGION}" \
      --query 'Listeners[*].ListenerArn' --output text 2>/dev/null || true
  )"
  for L_ARN in ${LISTENER_ARNS}; do
    aws elbv2 delete-listener --listener-arn "${L_ARN}" --region "${REGION}" >/dev/null 2>&1 || true
  done
  aws elbv2 delete-load-balancer --load-balancer-arn "${ALB_ARN}" --region "${REGION}" >/dev/null 2>&1 || true
  aws elbv2 wait load-balancers-deleted --load-balancer-arns "${ALB_ARN}" --region "${REGION}" 2>/dev/null || true
  state_clear ALB_ARN
  ok "ALB deleted"
fi

if ! is_missing "${TARGET_GROUP_ARN}"; then
  aws elbv2 delete-target-group --target-group-arn "${TARGET_GROUP_ARN}" --region "${REGION}" >/dev/null 2>&1 || true
  state_clear TARGET_GROUP_ARN
  ok "Target group deleted"
fi

# ── 4. Delete ElastiCache cluster ─────────────────────────────────────────────

log "Step 4/15 — ElastiCache"

if ! is_missing "${CACHE_CLUSTER_ID}"; then
  CACHE_STATUS="$(
    aws elasticache describe-cache-clusters \
      --cache-cluster-id "${CACHE_CLUSTER_ID}" --region "${REGION}" \
      --query 'CacheClusters[0].CacheClusterStatus' --output text 2>/dev/null || true
  )"
  if ! is_missing "${CACHE_STATUS}" && [[ "${CACHE_STATUS}" != "None" ]]; then
    aws elasticache delete-cache-cluster \
      --cache-cluster-id "${CACHE_CLUSTER_ID}" --region "${REGION}" >/dev/null 2>&1 || true
    printf '  Waiting for ElastiCache deletion...\n'
    aws elasticache wait cache-cluster-deleted \
      --cache-cluster-id "${CACHE_CLUSTER_ID}" --region "${REGION}" 2>/dev/null || true
    ok "ElastiCache cluster deleted"
  else
    skip "ElastiCache cluster not found"
  fi
fi

# ── 5. Delete RDS instance (with snapshot) ────────────────────────────────────

log "Step 5/15 — RDS instance"

if ! is_missing "${DB_INSTANCE_ID}"; then
  DB_STATUS="$(
    aws rds describe-db-instances \
      --db-instance-identifier "${DB_INSTANCE_ID}" --region "${REGION}" \
      --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || true
  )"
  if ! is_missing "${DB_STATUS}" && [[ "${DB_STATUS}" != "None" ]]; then
    SNAPSHOT_ID="${DB_INSTANCE_ID}-final-$(date +%Y%m%d%H%M)"
    if [[ "${NO_SNAPSHOT}" == "true" ]]; then
      aws rds delete-db-instance \
        --db-instance-identifier "${DB_INSTANCE_ID}" \
        --skip-final-snapshot \
        --region "${REGION}" >/dev/null
      printf '  RDS deletion initiated (no snapshot).\n'
    else
      aws rds delete-db-instance \
        --db-instance-identifier "${DB_INSTANCE_ID}" \
        --final-db-snapshot-identifier "${SNAPSHOT_ID}" \
        --region "${REGION}" >/dev/null
      printf '  RDS deletion initiated. Final snapshot: %s\n' "${SNAPSHOT_ID}"
      printf '  Snapshots are free for 1 month, then ~$0.095/GB/month.\n'
    fi
    if [[ "${SKIP_SNAPSHOT_WAIT}" != "true" ]]; then
      printf '  Waiting for RDS deletion (takes 5-10 minutes)...\n'
      aws rds wait db-instance-deleted \
        --db-instance-identifier "${DB_INSTANCE_ID}" --region "${REGION}" 2>/dev/null || true
    fi
    ok "RDS instance deleted"
  else
    skip "RDS instance not found"
  fi
fi

# ── 6. Delete VPC endpoints ───────────────────────────────────────────────────

log "Step 6/15 — VPC endpoints"

for KEY in VPCE_S3_ID VPCE_ECR_API_ID VPCE_ECR_DKR_ID VPCE_LOGS_ID VPCE_SECRETSMANAGER_ID VPCE_SSM_ID; do
  ENDPOINT_ID="$(state_get "${KEY}" 2>/dev/null || true)"
  if ! is_missing "${ENDPOINT_ID}"; then
    aws ec2 delete-vpc-endpoints \
      --vpc-endpoint-ids "${ENDPOINT_ID}" --region "${REGION}" >/dev/null 2>&1 || true
    state_clear "${KEY}" 2>/dev/null || true
    ok "VPC endpoint ${KEY} deleted"
  fi
done

# ── 7. NAT gateway + EIP ──────────────────────────────────────────────────────

log "Step 7/15 — NAT gateway and EIP"

if ! is_missing "${NAT_GATEWAY_ID}"; then
  aws ec2 delete-nat-gateway --nat-gateway-id "${NAT_GATEWAY_ID}" --region "${REGION}" >/dev/null 2>&1 || true
  printf '  Waiting for NAT gateway deletion...\n'
  aws ec2 wait nat-gateway-deleted --nat-gateway-ids "${NAT_GATEWAY_ID}" --region "${REGION}" 2>/dev/null || true
  state_clear NAT_GATEWAY_ID
  ok "NAT gateway deleted"
fi

if ! is_missing "${NAT_EIP_ALLOCATION_ID}"; then
  aws ec2 release-address --allocation-id "${NAT_EIP_ALLOCATION_ID}" --region "${REGION}" >/dev/null 2>&1 || true
  state_clear NAT_EIP_ALLOCATION_ID
  ok "EIP released"
fi

# ── 8. Security group rules ───────────────────────────────────────────────────

log "Step 8/15 — Security group ingress rules"

revoke_sg_ingress() {
  local group_id="$1"
  [[ -z "${group_id}" ]] && return
  RULES="$(
    aws ec2 describe-security-groups \
      --group-ids "${group_id}" --region "${REGION}" \
      --query 'SecurityGroups[0].IpPermissions' --output json 2>/dev/null || true
  )"
  if [[ -n "${RULES}" && "${RULES}" != "[]" && "${RULES}" != "null" ]]; then
    aws ec2 revoke-security-group-ingress \
      --group-id "${group_id}" \
      --ip-permissions "${RULES}" \
      --region "${REGION}" >/dev/null 2>&1 || true
  fi
}

for SG_ID in "${SG_ALB_ID}" "${SG_APP_ID}" "${SG_DB_ID}" "${SG_CACHE_ID}" "${SG_ENDPOINTS_ID}"; do
  is_missing "${SG_ID}" && continue
  revoke_sg_ingress "${SG_ID}"
done
ok "Security group rules revoked"

# ── 9. Subnets ────────────────────────────────────────────────────────────────

log "Step 9/15 — Subnets"

for SUBNET_ID in "${PUBLIC_SUBNET_A_ID}" "${PUBLIC_SUBNET_B_ID}" \
                 "${PRIVATE_SUBNET_A_ID}" "${PRIVATE_SUBNET_B_ID}"; do
  is_missing "${SUBNET_ID}" && continue
  aws ec2 delete-subnet --subnet-id "${SUBNET_ID}" --region "${REGION}" >/dev/null 2>&1 || true
done
ok "Subnets deleted"

# ── 10. Security groups ───────────────────────────────────────────────────────

log "Step 10/15 — Security groups"

for SG_ID in "${SG_ALB_ID}" "${SG_APP_ID}" "${SG_DB_ID}" "${SG_CACHE_ID}" "${SG_ENDPOINTS_ID}"; do
  is_missing "${SG_ID}" && continue
  aws ec2 delete-security-group --group-id "${SG_ID}" --region "${REGION}" >/dev/null 2>&1 || true
done
ok "Security groups deleted"

# ── 11. Internet gateway ──────────────────────────────────────────────────────

log "Step 11/15 — Internet gateway"

if ! is_missing "${INTERNET_GATEWAY_ID}" && ! is_missing "${VPC_ID}"; then
  aws ec2 detach-internet-gateway \
    --internet-gateway-id "${INTERNET_GATEWAY_ID}" \
    --vpc-id "${VPC_ID}" --region "${REGION}" >/dev/null 2>&1 || true
  aws ec2 delete-internet-gateway \
    --internet-gateway-id "${INTERNET_GATEWAY_ID}" --region "${REGION}" >/dev/null 2>&1 || true
  state_clear INTERNET_GATEWAY_ID
  ok "Internet gateway deleted"
fi

# ── 12. Route tables ──────────────────────────────────────────────────────────

log "Step 12/15 — Route tables"

for RT_ID in "${PUBLIC_ROUTE_TABLE_ID}" "${PRIVATE_ROUTE_TABLE_ID}"; do
  is_missing "${RT_ID}" && continue
  # Disassociate non-main associations first
  ASSOC_IDS="$(
    aws ec2 describe-route-tables --route-table-ids "${RT_ID}" --region "${REGION}" \
      --query 'RouteTables[0].Associations[?Main==`false`].RouteTableAssociationId' \
      --output text 2>/dev/null || true
  )"
  for ASSOC_ID in ${ASSOC_IDS}; do
    aws ec2 disassociate-route-table --association-id "${ASSOC_ID}" --region "${REGION}" >/dev/null 2>&1 || true
  done
  aws ec2 delete-route-table --route-table-id "${RT_ID}" --region "${REGION}" >/dev/null 2>&1 || true
done
ok "Route tables deleted"

# ── 13. VPC ───────────────────────────────────────────────────────────────────

log "Step 13/15 — VPC"

if ! is_missing "${VPC_ID}"; then
  aws ec2 delete-vpc --vpc-id "${VPC_ID}" --region "${REGION}" >/dev/null 2>&1 || true
  state_clear VPC_ID
  ok "VPC deleted"
fi

# ── 14. CloudWatch log group ──────────────────────────────────────────────────

log "Step 14/15 — CloudWatch log group"

if ! is_missing "${LOG_GROUP_NAME}"; then
  aws logs delete-log-group \
    --log-group-name "${LOG_GROUP_NAME}" --region "${REGION}" >/dev/null 2>&1 || true
  ok "Log group deleted"
fi

# ── 15. ECR images + Secrets Manager ─────────────────────────────────────────

log "Step 15/15 — ECR images and Secrets Manager"

# Delete all ECR images (keeps repo to avoid name collision on re-provision)
IMAGE_IDS="$(
  aws ecr list-images \
    --repository-name "${ECR_REPO_NAME}" --region "${REGION}" \
    --query 'imageIds[*]' --output json 2>/dev/null || true
)"
if [[ -n "${IMAGE_IDS}" && "${IMAGE_IDS}" != "[]" ]]; then
  aws ecr batch-delete-image \
    --repository-name "${ECR_REPO_NAME}" \
    --image-ids "${IMAGE_IDS}" \
    --region "${REGION}" >/dev/null 2>&1 || true
  ok "ECR images deleted (repository kept)"
fi

# Schedule Secrets Manager secrets for deletion (7-day recovery window)
if ! is_missing "${SECRET_PREFIX}"; then
  for SECRET_SUFFIX in DATABASE_MASTER_PASSWORD DATABASE_URL REDIS_URL JWT_SECRET_KEY ENCRYPTION_KEY WEBHOOK_SECRET; do
    SECRET_NAME="${SECRET_PREFIX}/${SECRET_SUFFIX}"
    aws secretsmanager delete-secret \
      --secret-id "${SECRET_NAME}" \
      --recovery-window-in-days 7 \
      --region "${REGION}" >/dev/null 2>&1 || true
  done
  ok "Secrets scheduled for deletion (7-day recovery window)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

printf '\n'
printf '=================================================================\n'
printf ' Teardown complete — all billable resources deleted.\n'
printf '=================================================================\n'
printf '\n'
printf ' Remaining (near-zero cost):\n'
printf '   ECR repository (empty)  — no cost\n'
printf '   IAM roles               — no cost\n'
printf '   Secrets Manager secrets — 7-day deletion window, ~$0.40/secret\n'
printf '\n'
printf ' RDS snapshot (if taken) will be free for 1 month,\n'
printf ' then ~$0.095/GB/month. Delete from AWS Console > RDS > Snapshots.\n'
printf '\n'
printf ' State file preserved at: %s\n' "${STATE_FILE}"
printf ' Re-provision from scratch:\n'
printf '   ACCOUNT_ID=%s REGION=%s PROJECT=%s ENV=%s \\\n' \
  "${ACCOUNT_ID}" "${REGION}" "${PROJECT}" "${ENV}"
printf '     bash infrastructure/aws/setup.sh\n'
printf '\n'
