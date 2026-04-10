#!/usr/bin/env bash
# Porter Intelligence Platform — ECS deployment script.
#
# Reads environment-specific infrastructure IDs from the local state file
# written by setup.sh, renders the task definition, and creates or updates
# the ECS service.

set -euo pipefail

ACCOUNT_ID="${ACCOUNT_ID:?Set ACCOUNT_ID}"
REGION="${REGION:-ap-south-1}"
PROJECT="${PROJECT:-porter}"
ENV="${ENV:-prod}"
PREFIX="${PROJECT}-${ENV}"
CLUSTER="${CLUSTER:-${PREFIX}}"
SERVICE="${SERVICE:-${PROJECT}-api}"
TASK_FAMILY="${TASK_FAMILY:-${PROJECT}-api}"
ECR_REPO_NAME="${ECR_REPO_NAME:-porter-intelligence}"
IMAGE_TAG="${1:-$(git rev-parse --short HEAD)}"
IMAGE_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"
IMAGE_URI="${IMAGE_REPO}:${IMAGE_TAG}"
TASK_TEMPLATE="infrastructure/aws/ecs-task-definition.json"
EXECUTION_ROLE_NAME="${EXECUTION_ROLE_NAME:-ecsTaskExecutionRole}"
TASK_ROLE_NAME="${TASK_ROLE_NAME:-}"
SECRET_PREFIX="${SECRET_PREFIX:-${PROJECT}/${ENV}}"
LOG_GROUP_NAME="${LOG_GROUP_NAME:-/ecs/porter-intelligence}"
STATE_DIR="${STATE_DIR:-infrastructure/aws/state}"
STATE_FILE="${STATE_FILE:-${STATE_DIR}/${PROJECT}-${ENV}-${REGION}.json}"

log() {
  printf '==> %s\n' "$1"
}

is_missing() {
  [[ -z "${1:-}" || "${1}" == "None" || "${1}" == "null" ]]
}

state_get() {
  python3 - "${STATE_FILE}" "${1}" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
key = sys.argv[2]

if not path.exists() or path.stat().st_size == 0:
    print("")
    raise SystemExit

with path.open("r", encoding="utf-8") as handle:
    data = json.load(handle)

value = data.get(key, "")
if value is None:
    value = ""
print(value)
PY
}

resolve_secret_arn() {
  local secret_name="$1"
  aws secretsmanager describe-secret \
    --secret-id "${secret_name}" \
    --region "${REGION}" \
    --query 'ARN' \
    --output text
}

render_task_definition() {
  local output_file="$1"
  python3 - "${TASK_TEMPLATE}" "${output_file}" "${ACCOUNT_ID}" "${REGION}" "${IMAGE_URI}" "${EXECUTION_ROLE_NAME}" "${TASK_ROLE_NAME}" "${TASK_FAMILY}" "${LOG_GROUP_NAME}" "${DATABASE_URL_SECRET_ARN}" "${REDIS_URL_SECRET_ARN}" "${JWT_SECRET_KEY_SECRET_ARN}" "${ENCRYPTION_KEY_SECRET_ARN}" "${WEBHOOK_SECRET_SECRET_ARN}" <<'PY'
import json
import sys

(
    template_path,
    output_path,
    account_id,
    region,
    image_uri,
    execution_role_name,
    task_role_name,
    task_family,
    log_group_name,
    database_url_secret_arn,
    redis_url_secret_arn,
    jwt_secret_key_secret_arn,
    encryption_key_secret_arn,
    webhook_secret_secret_arn,
) = sys.argv[1:15]

with open(template_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

payload["family"] = task_family
payload["executionRoleArn"] = f"arn:aws:iam::{account_id}:role/{execution_role_name}"
if task_role_name:
    payload["taskRoleArn"] = f"arn:aws:iam::{account_id}:role/{task_role_name}"
else:
    payload.pop("taskRoleArn", None)

container = payload["containerDefinitions"][0]
container["image"] = image_uri
container["logConfiguration"]["options"]["awslogs-region"] = region
container["logConfiguration"]["options"]["awslogs-group"] = log_group_name

secret_arns = {
    "DATABASE_URL": database_url_secret_arn,
    "REDIS_URL": redis_url_secret_arn,
    "JWT_SECRET_KEY": jwt_secret_key_secret_arn,
    "ENCRYPTION_KEY": encryption_key_secret_arn,
    "WEBHOOK_SECRET": webhook_secret_secret_arn,
}
for secret in container.get("secrets", []):
    secret["valueFrom"] = secret_arns[secret["name"]]

with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
}

if [[ ! -f "${STATE_FILE}" ]]; then
  printf 'Missing state file: %s\nRun setup.sh first.\n' "${STATE_FILE}" >&2
  exit 1
fi

APP_SG_ID="$(state_get SG_APP_ID)"
ECS_SUBNET_A_ID="$(state_get ECS_SUBNET_A_ID)"
ECS_SUBNET_B_ID="$(state_get ECS_SUBNET_B_ID)"
ECS_ASSIGN_PUBLIC_IP="$(state_get ECS_ASSIGN_PUBLIC_IP)"
PRIVATE_SUBNET_A_ID="$(state_get PRIVATE_SUBNET_A_ID)"
PRIVATE_SUBNET_B_ID="$(state_get PRIVATE_SUBNET_B_ID)"
TARGET_GROUP_ARN="$(state_get TARGET_GROUP_ARN)"
STATE_CLUSTER="$(state_get CLUSTER_NAME)"
STATE_SERVICE="$(state_get SERVICE_NAME)"
STATE_SECRET_PREFIX="$(state_get SECRET_PREFIX)"
STATE_EXECUTION_ROLE_NAME="$(state_get EXECUTION_ROLE_NAME)"
STATE_TASK_ROLE_NAME="$(state_get TASK_ROLE_NAME)"
STATE_LOG_GROUP_NAME="$(state_get LOG_GROUP_NAME)"

if ! is_missing "${STATE_CLUSTER}"; then
  CLUSTER="${STATE_CLUSTER}"
fi
if ! is_missing "${STATE_SERVICE}"; then
  SERVICE="${STATE_SERVICE}"
fi
if ! is_missing "${STATE_SECRET_PREFIX}"; then
  SECRET_PREFIX="${STATE_SECRET_PREFIX}"
fi
if ! is_missing "${STATE_EXECUTION_ROLE_NAME}"; then
  EXECUTION_ROLE_NAME="${STATE_EXECUTION_ROLE_NAME}"
fi
TASK_ROLE_NAME="${STATE_TASK_ROLE_NAME}"
if ! is_missing "${STATE_LOG_GROUP_NAME}"; then
  LOG_GROUP_NAME="${STATE_LOG_GROUP_NAME}"
fi

if is_missing "${ECS_SUBNET_A_ID}"; then
  ECS_SUBNET_A_ID="${PRIVATE_SUBNET_A_ID}"
fi
if is_missing "${ECS_SUBNET_B_ID}"; then
  ECS_SUBNET_B_ID="${PRIVATE_SUBNET_B_ID}"
fi
if is_missing "${ECS_ASSIGN_PUBLIC_IP}"; then
  ECS_ASSIGN_PUBLIC_IP="DISABLED"
fi

DATABASE_URL_SECRET_ARN="$(resolve_secret_arn "${SECRET_PREFIX}/DATABASE_URL")"
REDIS_URL_SECRET_ARN="$(resolve_secret_arn "${SECRET_PREFIX}/REDIS_URL")"
JWT_SECRET_KEY_SECRET_ARN="$(resolve_secret_arn "${SECRET_PREFIX}/JWT_SECRET_KEY")"
ENCRYPTION_KEY_SECRET_ARN="$(resolve_secret_arn "${SECRET_PREFIX}/ENCRYPTION_KEY")"
WEBHOOK_SECRET_SECRET_ARN="$(resolve_secret_arn "${SECRET_PREFIX}/WEBHOOK_SECRET")"

for value in "${APP_SG_ID}" "${ECS_SUBNET_A_ID}" "${ECS_SUBNET_B_ID}" "${TARGET_GROUP_ARN}"; do
  if is_missing "${value}"; then
    printf 'State file %s is missing required infrastructure IDs.\n' "${STATE_FILE}" >&2
    exit 1
  fi
done

log "Deploying Porter Intelligence Platform"
log "Image: ${IMAGE_URI}"

NETWORK_CONFIGURATION="awsvpcConfiguration={subnets=[${ECS_SUBNET_A_ID},${ECS_SUBNET_B_ID}],securityGroups=[${APP_SG_ID}],assignPublicIp=${ECS_ASSIGN_PUBLIC_IP}}"

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${IMAGE_REPO}"

docker build --platform linux/amd64 -t "${IMAGE_URI}" .
docker tag "${IMAGE_URI}" "${IMAGE_REPO}:latest"
docker push "${IMAGE_URI}"
docker push "${IMAGE_REPO}:latest"

TEMP_TASK_DEF="$(mktemp)"
render_task_definition "${TEMP_TASK_DEF}"

NEW_REVISION="$(
  aws ecs register-task-definition \
    --region "${REGION}" \
    --cli-input-json "file://${TEMP_TASK_DEF}" \
    --query 'taskDefinition.revision' \
    --output text
)"
rm -f "${TEMP_TASK_DEF}"

log "Task definition revision: ${NEW_REVISION}"

SERVICE_STATUS="$(
  aws ecs describe-services \
    --cluster "${CLUSTER}" \
    --services "${SERVICE}" \
    --region "${REGION}" \
    --query 'services[0].status' \
    --output text 2>/dev/null || true
)"

if is_missing "${SERVICE_STATUS}" || [[ "${SERVICE_STATUS}" == "MISSING" ]]; then
  log "Creating ECS service ${SERVICE}"
  aws ecs create-service \
    --cluster "${CLUSTER}" \
    --service-name "${SERVICE}" \
    --task-definition "${TASK_FAMILY}:${NEW_REVISION}" \
    --desired-count 1 \
    --launch-type FARGATE \
    --deployment-configuration maximumPercent=200,minimumHealthyPercent=100 \
    --health-check-grace-period-seconds 180 \
    --network-configuration "${NETWORK_CONFIGURATION}" \
    --load-balancers "targetGroupArn=${TARGET_GROUP_ARN},containerName=porter-api,containerPort=8000" \
    --region "${REGION}" >/dev/null
else
  log "Updating ECS service ${SERVICE}"
  aws ecs update-service \
    --cluster "${CLUSTER}" \
    --service "${SERVICE}" \
    --task-definition "${TASK_FAMILY}:${NEW_REVISION}" \
    --network-configuration "${NETWORK_CONFIGURATION}" \
    --region "${REGION}" \
    --force-new-deployment \
    --output json | jq '.service | {status, desiredCount, runningCount}'
fi

log "Waiting for service to stabilise"
aws ecs wait services-stable \
  --cluster "${CLUSTER}" \
  --services "${SERVICE}" \
  --region "${REGION}"

log "Deployment complete: ${IMAGE_URI}"
