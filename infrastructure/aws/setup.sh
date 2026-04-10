#!/usr/bin/env bash
# Idempotent AWS infrastructure provisioning for Porter Intelligence Platform.
#
# Notes:
# - Tracks EC2-only resource IDs in a local state file so the setup works even
#   when the caller cannot use ec2:CreateTags.
# - Safe to rerun for the same PROJECT / ENV / REGION tuple.

set -euo pipefail

ACCOUNT_ID="${ACCOUNT_ID:?Set ACCOUNT_ID}"
REGION="${REGION:-ap-south-1}"
PROJECT="${PROJECT:-porter}"
ENV="${ENV:-prod}"
PREFIX="${PROJECT}-${ENV}"
DB_NAME="${DB_NAME:-porter_intelligence}"
DB_USERNAME="${DB_USERNAME:-porteradmin}"
DB_INSTANCE_ID="${DB_INSTANCE_ID:-${PREFIX}-postgres}"
DB_INSTANCE_CLASS="${DB_INSTANCE_CLASS:-db.t3.medium}"
DB_ALLOCATED_STORAGE="${DB_ALLOCATED_STORAGE:-100}"
DB_BACKUP_RETENTION_DAYS="${DB_BACKUP_RETENTION_DAYS:-7}"
DB_MULTI_AZ="${DB_MULTI_AZ:-true}"
DB_ENGINE_VERSION="${DB_ENGINE_VERSION:-15.17}"
DB_FALLBACK_INSTANCE_CLASS="${DB_FALLBACK_INSTANCE_CLASS:-db.t3.micro}"
DB_FALLBACK_ALLOCATED_STORAGE="${DB_FALLBACK_ALLOCATED_STORAGE:-20}"
DB_FALLBACK_BACKUP_RETENTION_DAYS="${DB_FALLBACK_BACKUP_RETENTION_DAYS:-1}"
CACHE_CLUSTER_ID="${CACHE_CLUSTER_ID:-${PREFIX}-redis}"
CLUSTER_NAME="${CLUSTER_NAME:-${PREFIX}}"
SERVICE_NAME="${SERVICE_NAME:-${PROJECT}-api}"
ECR_REPO_NAME="${ECR_REPO_NAME:-porter-intelligence}"
ALB_NAME="${ALB_NAME:-${PREFIX}-alb}"
TARGET_GROUP_NAME="${TARGET_GROUP_NAME:-${PREFIX}-api-tg}"
EXECUTION_ROLE_NAME="${EXECUTION_ROLE_NAME:-${PREFIX}-ecs-execution-role}"
TASK_ROLE_NAME="${TASK_ROLE_NAME:-${PREFIX}-ecs-task-role}"
FALLBACK_EXECUTION_ROLE_NAME="${FALLBACK_EXECUTION_ROLE_NAME:-ecsTaskExecutionRole}"
SECRET_PREFIX="${SECRET_PREFIX:-${PROJECT}/${ENV}}"
LOG_GROUP_NAME="${LOG_GROUP_NAME:-/ecs/porter-intelligence}"
CERTIFICATE_ARN="${CERTIFICATE_ARN:-}"
HTTP_TO_HTTPS_REDIRECT="${HTTP_TO_HTTPS_REDIRECT:-true}"
VPC_ENDPOINTS_ENABLED="${VPC_ENDPOINTS_ENABLED:-true}"
STATE_DIR="${STATE_DIR:-infrastructure/aws/state}"
STATE_FILE="${STATE_FILE:-${STATE_DIR}/${PROJECT}-${ENV}-${REGION}.json}"

log() {
  printf '==> %s\n' "$1"
}

is_missing() {
  [[ -z "${1:-}" || "${1}" == "None" || "${1}" == "null" ]]
}

ensure_state_file() {
  mkdir -p "${STATE_DIR}"
  if [[ ! -f "${STATE_FILE}" ]]; then
    printf '{}\n' >"${STATE_FILE}"
  fi
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

state_set() {
  python3 - "${STATE_FILE}" "${1}" "${2}" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

if path.exists() and path.stat().st_size > 0:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
else:
    data = {}

data[key] = value

with path.open("w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

resource_exists() {
  local service="$1"
  shift
  aws "${service}" "$@" >/dev/null 2>&1
}

try_tag_resource() {
  local resource_id="$1"
  local resource_name="$2"
  aws ec2 create-tags \
    --resources "${resource_id}" \
    --tags "Key=Name,Value=${resource_name}" \
    --region "${REGION}" >/dev/null 2>&1 || true
}

get_secret_value() {
  local secret_name="$1"
  aws secretsmanager get-secret-value \
    --secret-id "${secret_name}" \
    --region "${REGION}" \
    --query 'SecretString' \
    --output text 2>/dev/null || true
}

put_secret_value() {
  local secret_name="$1"
  local description="$2"
  local secret_value="$3"
  if aws secretsmanager describe-secret \
    --secret-id "${secret_name}" \
    --region "${REGION}" >/dev/null 2>&1; then
    aws secretsmanager put-secret-value \
      --secret-id "${secret_name}" \
      --secret-string "${secret_value}" \
      --region "${REGION}" >/dev/null
  else
    aws secretsmanager create-secret \
      --name "${secret_name}" \
      --description "${description}" \
      --secret-string "${secret_value}" \
      --region "${REGION}" >/dev/null
  fi
}

ensure_random_secret() {
  local secret_name="$1"
  local description="$2"
  local generator="$3"
  local existing
  existing="$(get_secret_value "${secret_name}")"
  if ! is_missing "${existing}"; then
    printf '%s' "${existing}"
    return
  fi
  local generated
  generated="$(python3 -c "${generator}")"
  put_secret_value "${secret_name}" "${description}" "${generated}"
  printf '%s' "${generated}"
}

ensure_vpc() {
  local vpc_id
  vpc_id="$(state_get VPC_ID)"
  if ! is_missing "${vpc_id}" && resource_exists ec2 describe-vpcs --vpc-ids "${vpc_id}" --region "${REGION}"; then
    printf '%s' "${vpc_id}"
    return
  fi

  vpc_id="$(
    aws ec2 create-vpc \
      --cidr-block 10.20.0.0/16 \
      --region "${REGION}" \
      --query 'Vpc.VpcId' \
      --output text
  )"
  aws ec2 modify-vpc-attribute \
    --vpc-id "${vpc_id}" \
    --enable-dns-hostnames \
    --region "${REGION}" >/dev/null
  aws ec2 modify-vpc-attribute \
    --vpc-id "${vpc_id}" \
    --enable-dns-support \
    --region "${REGION}" >/dev/null
  try_tag_resource "${vpc_id}" "${PREFIX}-vpc"
  state_set VPC_ID "${vpc_id}"
  printf '%s' "${vpc_id}"
}

ensure_subnet() {
  local state_key="$1"
  local cidr="$2"
  local az="$3"
  local public_flag="$4"
  local subnet_id

  subnet_id="$(state_get "${state_key}")"
  if ! is_missing "${subnet_id}" && resource_exists ec2 describe-subnets --subnet-ids "${subnet_id}" --region "${REGION}"; then
    printf '%s' "${subnet_id}"
    return
  fi

  subnet_id="$(
    aws ec2 create-subnet \
      --vpc-id "${VPC_ID}" \
      --cidr-block "${cidr}" \
      --availability-zone "${az}" \
      --region "${REGION}" \
      --query 'Subnet.SubnetId' \
      --output text
  )"
  if [[ "${public_flag}" == "true" ]]; then
    aws ec2 modify-subnet-attribute \
      --subnet-id "${subnet_id}" \
      --map-public-ip-on-launch \
      --region "${REGION}" >/dev/null
  fi
  try_tag_resource "${subnet_id}" "${PREFIX}-${state_key}"
  state_set "${state_key}" "${subnet_id}"
  printf '%s' "${subnet_id}"
}

ensure_internet_gateway() {
  local igw_id
  igw_id="$(state_get INTERNET_GATEWAY_ID)"
  if ! is_missing "${igw_id}" && resource_exists ec2 describe-internet-gateways --internet-gateway-ids "${igw_id}" --region "${REGION}"; then
    printf '%s' "${igw_id}"
    return
  fi

  igw_id="$(
    aws ec2 create-internet-gateway \
      --region "${REGION}" \
      --query 'InternetGateway.InternetGatewayId' \
      --output text
  )"
  aws ec2 attach-internet-gateway \
    --vpc-id "${VPC_ID}" \
    --internet-gateway-id "${igw_id}" \
    --region "${REGION}" >/dev/null
  try_tag_resource "${igw_id}" "${PREFIX}-igw"
  state_set INTERNET_GATEWAY_ID "${igw_id}"
  printf '%s' "${igw_id}"
}

ensure_route_table() {
  local state_key="$1"
  local route_table_id
  route_table_id="$(state_get "${state_key}")"
  if ! is_missing "${route_table_id}" && resource_exists ec2 describe-route-tables --route-table-ids "${route_table_id}" --region "${REGION}"; then
    printf '%s' "${route_table_id}"
    return
  fi

  route_table_id="$(
    aws ec2 create-route-table \
      --vpc-id "${VPC_ID}" \
      --region "${REGION}" \
      --query 'RouteTable.RouteTableId' \
      --output text
  )"
  try_tag_resource "${route_table_id}" "${PREFIX}-${state_key}"
  state_set "${state_key}" "${route_table_id}"
  printf '%s' "${route_table_id}"
}

ensure_route() {
  local route_table_id="$1"
  local destination="$2"
  local target_arg="$3"
  local target_value="$4"
  aws ec2 create-route \
    --route-table-id "${route_table_id}" \
    --destination-cidr-block "${destination}" \
    "${target_arg}" "${target_value}" \
    --region "${REGION}" >/dev/null 2>&1 || true
}

associate_subnet_with_route_table() {
  local subnet_id="$1"
  local route_table_id="$2"
  local current
  current="$(
    aws ec2 describe-route-tables \
      --filters "Name=association.subnet-id,Values=${subnet_id}" \
      --region "${REGION}" \
      --query 'RouteTables[0].RouteTableId' \
      --output text 2>/dev/null || true
  )"
  if [[ "${current}" != "${route_table_id}" ]]; then
    aws ec2 associate-route-table \
      --subnet-id "${subnet_id}" \
      --route-table-id "${route_table_id}" \
      --region "${REGION}" >/dev/null 2>&1 || true
  fi
}

ensure_eip() {
  local allocation_id
  allocation_id="$(state_get NAT_EIP_ALLOCATION_ID)"
  if ! is_missing "${allocation_id}" && resource_exists ec2 describe-addresses --allocation-ids "${allocation_id}" --region "${REGION}"; then
    printf '%s' "${allocation_id}"
    return
  fi

  allocation_id="$(
    aws ec2 allocate-address \
      --domain vpc \
      --region "${REGION}" \
      --query 'AllocationId' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${allocation_id}"; then
    printf ''
    return
  fi
  state_set NAT_EIP_ALLOCATION_ID "${allocation_id}"
  printf '%s' "${allocation_id}"
}

ensure_nat_gateway() {
  local nat_gateway_id
  if is_missing "${NAT_EIP_ALLOCATION_ID}"; then
    printf ''
    return
  fi
  nat_gateway_id="$(state_get NAT_GATEWAY_ID)"
  if ! is_missing "${nat_gateway_id}" && resource_exists ec2 describe-nat-gateways --nat-gateway-ids "${nat_gateway_id}" --region "${REGION}"; then
    aws ec2 wait nat-gateway-available \
      --nat-gateway-ids "${nat_gateway_id}" \
      --region "${REGION}" >/dev/null 2>&1 || true
    printf '%s' "${nat_gateway_id}"
    return
  fi

  nat_gateway_id="$(
    aws ec2 create-nat-gateway \
      --subnet-id "${PUBLIC_SUBNET_A_ID}" \
      --allocation-id "${NAT_EIP_ALLOCATION_ID}" \
      --region "${REGION}" \
      --query 'NatGateway.NatGatewayId' \
      --output text
  )"
  state_set NAT_GATEWAY_ID "${nat_gateway_id}"
  aws ec2 wait nat-gateway-available \
    --nat-gateway-ids "${nat_gateway_id}" \
    --region "${REGION}"
  printf '%s' "${nat_gateway_id}"
}

ensure_security_group() {
  local state_key="$1"
  local group_name="$2"
  local description="$3"
  local group_id

  group_id="$(state_get "${state_key}")"
  if ! is_missing "${group_id}" && resource_exists ec2 describe-security-groups --group-ids "${group_id}" --region "${REGION}"; then
    printf '%s' "${group_id}"
    return
  fi

  group_id="$(
    aws ec2 describe-security-groups \
      --filters \
        "Name=group-name,Values=${group_name}" \
        "Name=vpc-id,Values=${VPC_ID}" \
      --region "${REGION}" \
      --query 'SecurityGroups[0].GroupId' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${group_id}"; then
    group_id="$(
      aws ec2 create-security-group \
        --group-name "${group_name}" \
        --description "${description}" \
        --vpc-id "${VPC_ID}" \
        --region "${REGION}" \
        --query 'GroupId' \
        --output text
    )"
  fi
  state_set "${state_key}" "${group_id}"
  printf '%s' "${group_id}"
}

ensure_ingress_rule() {
  local group_id="$1"
  local protocol="$2"
  local port="$3"
  local source="$4"
  local source_type="$5"
  if [[ "${source_type}" == "cidr" ]]; then
    aws ec2 authorize-security-group-ingress \
      --group-id "${group_id}" \
      --protocol "${protocol}" \
      --port "${port}" \
      --cidr "${source}" \
      --region "${REGION}" >/dev/null 2>&1 || true
  else
    aws ec2 authorize-security-group-ingress \
      --group-id "${group_id}" \
      --protocol "${protocol}" \
      --port "${port}" \
      --source-group "${source}" \
      --region "${REGION}" >/dev/null 2>&1 || true
  fi
}

find_vpc_endpoint() {
  local state_key="$1"
  local service_name="$2"
  local endpoint_type="$3"
  local endpoint_id

  endpoint_id="$(state_get "${state_key}")"
  if ! is_missing "${endpoint_id}" && resource_exists ec2 describe-vpc-endpoints --vpc-endpoint-ids "${endpoint_id}" --region "${REGION}"; then
    printf '%s' "${endpoint_id}"
    return
  fi

  endpoint_id="$(
    aws ec2 describe-vpc-endpoints \
      --filters \
        "Name=vpc-id,Values=${VPC_ID}" \
        "Name=service-name,Values=com.amazonaws.${REGION}.${service_name}" \
        "Name=vpc-endpoint-type,Values=${endpoint_type}" \
      --region "${REGION}" \
      --query 'VpcEndpoints[0].VpcEndpointId' \
      --output text 2>/dev/null || true
  )"
  if ! is_missing "${endpoint_id}"; then
    state_set "${state_key}" "${endpoint_id}"
  fi
  printf '%s' "${endpoint_id}"
}

ensure_interface_vpc_endpoint() {
  local state_key="$1"
  local service_name="$2"
  local endpoint_id

  endpoint_id="$(find_vpc_endpoint "${state_key}" "${service_name}" "Interface")"
  if ! is_missing "${endpoint_id}"; then
    aws ec2 wait vpc-endpoint-available \
      --vpc-endpoint-ids "${endpoint_id}" \
      --region "${REGION}" >/dev/null 2>&1 || true
    printf '%s' "${endpoint_id}"
    return
  fi

  endpoint_id="$(
    aws ec2 create-vpc-endpoint \
      --vpc-id "${VPC_ID}" \
      --vpc-endpoint-type Interface \
      --service-name "com.amazonaws.${REGION}.${service_name}" \
      --subnet-ids "${PRIVATE_SUBNET_A_ID}" "${PRIVATE_SUBNET_B_ID}" \
      --security-group-ids "${SG_ENDPOINTS_ID}" \
      --private-dns-enabled \
      --region "${REGION}" \
      --query 'VpcEndpoint.VpcEndpointId' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${endpoint_id}"; then
    printf ''
    return
  fi

  state_set "${state_key}" "${endpoint_id}"
  aws ec2 wait vpc-endpoint-available \
    --vpc-endpoint-ids "${endpoint_id}" \
    --region "${REGION}" >/dev/null 2>&1 || true
  printf '%s' "${endpoint_id}"
}

ensure_gateway_vpc_endpoint() {
  local state_key="$1"
  local service_name="$2"
  local endpoint_id

  endpoint_id="$(find_vpc_endpoint "${state_key}" "${service_name}" "Gateway")"
  if ! is_missing "${endpoint_id}"; then
    aws ec2 wait vpc-endpoint-available \
      --vpc-endpoint-ids "${endpoint_id}" \
      --region "${REGION}" >/dev/null 2>&1 || true
    printf '%s' "${endpoint_id}"
    return
  fi

  endpoint_id="$(
    aws ec2 create-vpc-endpoint \
      --vpc-id "${VPC_ID}" \
      --vpc-endpoint-type Gateway \
      --service-name "com.amazonaws.${REGION}.${service_name}" \
      --route-table-ids "${PRIVATE_ROUTE_TABLE_ID}" \
      --region "${REGION}" \
      --query 'VpcEndpoint.VpcEndpointId' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${endpoint_id}"; then
    printf ''
    return
  fi

  state_set "${state_key}" "${endpoint_id}"
  aws ec2 wait vpc-endpoint-available \
    --vpc-endpoint-ids "${endpoint_id}" \
    --region "${REGION}" >/dev/null 2>&1 || true
  printf '%s' "${endpoint_id}"
}

ensure_private_service_endpoints() {
  local s3_gateway_endpoint_id
  local ecr_api_endpoint_id
  local ecr_dkr_endpoint_id
  local logs_endpoint_id
  local secrets_endpoint_id
  local ssm_endpoint_id

  s3_gateway_endpoint_id="$(ensure_gateway_vpc_endpoint VPCE_S3_ID s3)"
  ecr_api_endpoint_id="$(ensure_interface_vpc_endpoint VPCE_ECR_API_ID ecr.api)"
  ecr_dkr_endpoint_id="$(ensure_interface_vpc_endpoint VPCE_ECR_DKR_ID ecr.dkr)"
  logs_endpoint_id="$(ensure_interface_vpc_endpoint VPCE_LOGS_ID logs)"
  secrets_endpoint_id="$(ensure_interface_vpc_endpoint VPCE_SECRETSMANAGER_ID secretsmanager)"
  ssm_endpoint_id="$(ensure_interface_vpc_endpoint VPCE_SSM_ID ssm)"

  if is_missing "${s3_gateway_endpoint_id}" \
    || is_missing "${ecr_api_endpoint_id}" \
    || is_missing "${ecr_dkr_endpoint_id}" \
    || is_missing "${logs_endpoint_id}" \
    || is_missing "${secrets_endpoint_id}" \
    || is_missing "${ssm_endpoint_id}"; then
    return 1
  fi

  return 0
}

ensure_named_resource() {
  local describe_cmd="$1"
  local create_cmd="$2"
  if ! eval "${describe_cmd}" >/dev/null 2>&1; then
    eval "${create_cmd}" >/dev/null
  fi
}

ensure_ecr_repository() {
  ensure_named_resource \
    "aws ecr describe-repositories --repository-names \"${ECR_REPO_NAME}\" --region \"${REGION}\"" \
    "aws ecr create-repository --repository-name \"${ECR_REPO_NAME}\" --image-scanning-configuration scanOnPush=true --region \"${REGION}\""
}

ensure_ecs_cluster() {
  local status
  status="$(
    aws ecs describe-clusters \
      --clusters "${CLUSTER_NAME}" \
      --region "${REGION}" \
      --query 'clusters[0].status' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${status}" || [[ "${status}" == "MISSING" ]]; then
    aws ecs create-cluster \
      --cluster-name "${CLUSTER_NAME}" \
      --capacity-providers FARGATE FARGATE_SPOT \
      --region "${REGION}" >/dev/null
  fi
}

ensure_log_group() {
  aws logs create-log-group \
    --log-group-name "${LOG_GROUP_NAME}" \
    --region "${REGION}" >/dev/null 2>&1 || true
  aws logs put-retention-policy \
    --log-group-name "${LOG_GROUP_NAME}" \
    --retention-in-days 30 \
    --region "${REGION}" >/dev/null
}

ensure_iam_roles() {
  local trust_policy_file execution_policy_file task_policy_file
  local effective_execution_role effective_task_role
  local execution_ready="false"
  local task_ready="false"

  effective_execution_role="${EXECUTION_ROLE_NAME}"
  effective_task_role="${TASK_ROLE_NAME}"
  trust_policy_file="$(mktemp)"
  execution_policy_file="$(mktemp)"
  task_policy_file="$(mktemp)"

  cat >"${trust_policy_file}" <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

  cat >"${execution_policy_file}" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:${SECRET_PREFIX}*"
    },
    {
      "Effect": "Allow",
      "Action": "kms:Decrypt",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "secretsmanager.${REGION}.amazonaws.com"
        }
      }
    }
  ]
}
EOF

  cat >"${task_policy_file}" <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": []
}
EOF

  if aws iam get-role --role-name "${EXECUTION_ROLE_NAME}" >/dev/null 2>&1; then
    execution_ready="true"
  elif aws iam create-role \
    --role-name "${EXECUTION_ROLE_NAME}" \
    --assume-role-policy-document "file://${trust_policy_file}" >/dev/null 2>&1; then
    execution_ready="true"
  elif aws ecs describe-task-definition \
    --task-definition porter-intelligence-api \
    --region "${REGION}" \
    --query 'taskDefinition.executionRoleArn' \
    --output text >/dev/null 2>&1; then
    effective_execution_role="${FALLBACK_EXECUTION_ROLE_NAME}"
    log "IAM role management unavailable; reusing execution role name ${effective_execution_role}"
    execution_ready="true"
  else
    log "IAM role management unavailable and no reusable execution role discovered"
  fi

  if [[ "${execution_ready}" == "true" ]]; then
    aws iam attach-role-policy \
      --role-name "${effective_execution_role}" \
      --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" >/dev/null 2>&1 || true
    aws iam put-role-policy \
      --role-name "${effective_execution_role}" \
      --policy-name porterSecretsAccess \
      --policy-document "file://${execution_policy_file}" >/dev/null 2>&1 || true
  fi

  if ! is_missing "${effective_task_role}"; then
    if aws iam get-role --role-name "${effective_task_role}" >/dev/null 2>&1; then
      task_ready="true"
    elif aws iam create-role \
      --role-name "${effective_task_role}" \
      --assume-role-policy-document "file://${trust_policy_file}" >/dev/null 2>&1; then
      task_ready="true"
    else
      log "IAM role management unavailable; deploying without a task role"
      effective_task_role=""
    fi
  fi

  if [[ "${task_ready}" == "true" && -n "${effective_task_role}" ]]; then
    aws iam put-role-policy \
      --role-name "${effective_task_role}" \
      --policy-name porterTaskRuntime \
      --policy-document "file://${task_policy_file}" >/dev/null 2>&1 || true
  fi

  rm -f "${trust_policy_file}" "${execution_policy_file}" "${task_policy_file}"

  EXECUTION_ROLE_NAME="${effective_execution_role}"
  TASK_ROLE_NAME="${effective_task_role}"
  state_set EXECUTION_ROLE_NAME "${EXECUTION_ROLE_NAME}"
  state_set TASK_ROLE_NAME "${TASK_ROLE_NAME}"
}

ensure_db_subnet_group() {
  ensure_named_resource \
    "aws rds describe-db-subnet-groups --db-subnet-group-name \"${PREFIX}-db-subnet\" --region \"${REGION}\"" \
    "aws rds create-db-subnet-group --db-subnet-group-name \"${PREFIX}-db-subnet\" --db-subnet-group-description \"${PREFIX} RDS subnet group\" --subnet-ids \"${PRIVATE_SUBNET_A_ID}\" \"${PRIVATE_SUBNET_B_ID}\" --region \"${REGION}\""
}

ensure_rds_instance() {
  local status
  local create_error_file
  local multi_az_flag=()

  if [[ "${DB_MULTI_AZ}" == "true" ]]; then
    multi_az_flag+=(--multi-az)
  fi

  status="$(
    aws rds describe-db-instances \
      --db-instance-identifier "${DB_INSTANCE_ID}" \
      --region "${REGION}" \
      --query 'DBInstances[0].DBInstanceStatus' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${status}" || [[ "${status}" == "None" ]]; then
    create_error_file="$(mktemp)"
    if aws rds create-db-instance \
      --db-instance-identifier "${DB_INSTANCE_ID}" \
      --db-instance-class "${DB_INSTANCE_CLASS}" \
      --engine postgres \
      --engine-version "${DB_ENGINE_VERSION}" \
      --allocated-storage "${DB_ALLOCATED_STORAGE}" \
      --storage-type gp3 \
      --storage-encrypted \
      --master-username "${DB_USERNAME}" \
      --master-user-password "${DB_PASS}" \
      --db-name "${DB_NAME}" \
      --vpc-security-group-ids "${SG_DB_ID}" \
      --db-subnet-group-name "${PREFIX}-db-subnet" \
      "${multi_az_flag[@]}" \
      --backup-retention-period "${DB_BACKUP_RETENTION_DAYS}" \
      --no-publicly-accessible \
      --region "${REGION}" >/dev/null 2>"${create_error_file}"; then
      state_set RDS_DEPLOYMENT_PROFILE buyer_safe
    else
      log "RDS buyer-safe profile unavailable; retrying with isolated staging profile"
      if ! aws rds create-db-instance \
        --db-instance-identifier "${DB_INSTANCE_ID}" \
        --db-instance-class "${DB_FALLBACK_INSTANCE_CLASS}" \
        --engine postgres \
        --engine-version "${DB_ENGINE_VERSION}" \
        --allocated-storage "${DB_FALLBACK_ALLOCATED_STORAGE}" \
        --storage-type gp3 \
        --storage-encrypted \
        --master-username "${DB_USERNAME}" \
        --master-user-password "${DB_PASS}" \
        --db-name "${DB_NAME}" \
        --vpc-security-group-ids "${SG_DB_ID}" \
        --db-subnet-group-name "${PREFIX}-db-subnet" \
        --backup-retention-period "${DB_FALLBACK_BACKUP_RETENTION_DAYS}" \
        --no-publicly-accessible \
        --region "${REGION}" >/dev/null 2>>"${create_error_file}"; then
        cat "${create_error_file}" >&2
        rm -f "${create_error_file}"
        return 1
      fi
      state_set RDS_DEPLOYMENT_PROFILE isolated_staging
    fi
    rm -f "${create_error_file}"
  fi
  aws rds wait db-instance-available \
    --db-instance-identifier "${DB_INSTANCE_ID}" \
    --region "${REGION}"
}

ensure_cache_subnet_group() {
  ensure_named_resource \
    "aws elasticache describe-cache-subnet-groups --cache-subnet-group-name \"${PREFIX}-cache-subnet\" --region \"${REGION}\"" \
    "aws elasticache create-cache-subnet-group --cache-subnet-group-name \"${PREFIX}-cache-subnet\" --cache-subnet-group-description \"${PREFIX} cache subnet group\" --subnet-ids \"${PRIVATE_SUBNET_A_ID}\" \"${PRIVATE_SUBNET_B_ID}\" --region \"${REGION}\""
}

ensure_cache_cluster() {
  local status
  status="$(
    aws elasticache describe-cache-clusters \
      --cache-cluster-id "${CACHE_CLUSTER_ID}" \
      --region "${REGION}" \
      --query 'CacheClusters[0].CacheClusterStatus' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${status}" || [[ "${status}" == "None" ]]; then
    aws elasticache create-cache-cluster \
      --cache-cluster-id "${CACHE_CLUSTER_ID}" \
      --cache-node-type cache.t3.micro \
      --engine redis \
      --engine-version "7.0" \
      --num-cache-nodes 1 \
      --cache-subnet-group-name "${PREFIX}-cache-subnet" \
      --security-group-ids "${SG_CACHE_ID}" \
      --region "${REGION}" >/dev/null
  fi
  aws elasticache wait cache-cluster-available \
    --cache-cluster-id "${CACHE_CLUSTER_ID}" \
    --region "${REGION}"
}

ensure_load_balancer() {
  local alb_arn
  alb_arn="$(state_get ALB_ARN)"
  if ! is_missing "${alb_arn}" && resource_exists elbv2 describe-load-balancers --load-balancer-arns "${alb_arn}" --region "${REGION}"; then
    printf '%s' "${alb_arn}"
    return
  fi

  alb_arn="$(
    aws elbv2 describe-load-balancers \
      --names "${ALB_NAME}" \
      --region "${REGION}" \
      --query 'LoadBalancers[0].LoadBalancerArn' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${alb_arn}"; then
    alb_arn="$(
      aws elbv2 create-load-balancer \
        --name "${ALB_NAME}" \
        --subnets "${PUBLIC_SUBNET_A_ID}" "${PUBLIC_SUBNET_B_ID}" \
        --security-groups "${SG_ALB_ID}" \
        --scheme internet-facing \
        --type application \
        --region "${REGION}" \
        --query 'LoadBalancers[0].LoadBalancerArn' \
        --output text
    )"
  fi
  state_set ALB_ARN "${alb_arn}"
  aws elbv2 wait load-balancer-available \
    --load-balancer-arns "${alb_arn}" \
    --region "${REGION}"
  printf '%s' "${alb_arn}"
}

ensure_target_group() {
  local target_group_arn
  target_group_arn="$(state_get TARGET_GROUP_ARN)"
  if ! is_missing "${target_group_arn}" && resource_exists elbv2 describe-target-groups --target-group-arns "${target_group_arn}" --region "${REGION}"; then
    printf '%s' "${target_group_arn}"
    return
  fi

  target_group_arn="$(
    aws elbv2 describe-target-groups \
      --names "${TARGET_GROUP_NAME}" \
      --region "${REGION}" \
      --query 'TargetGroups[0].TargetGroupArn' \
      --output text 2>/dev/null || true
  )"
  if is_missing "${target_group_arn}"; then
    target_group_arn="$(
      aws elbv2 create-target-group \
        --name "${TARGET_GROUP_NAME}" \
        --protocol HTTP \
        --port 8000 \
        --target-type ip \
        --health-check-path /health \
        --health-check-protocol HTTP \
        --matcher HttpCode=200 \
        --vpc-id "${VPC_ID}" \
        --region "${REGION}" \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text
    )"
  fi
  state_set TARGET_GROUP_ARN "${target_group_arn}"
  printf '%s' "${target_group_arn}"
}

listener_arn_for_port() {
  local port="$1"
  aws elbv2 describe-listeners \
    --load-balancer-arn "${ALB_ARN}" \
    --region "${REGION}" \
    --query "Listeners[?Port==\`${port}\`].ListenerArn | [0]" \
    --output text 2>/dev/null || true
}

ensure_http_listener() {
  local target_group_arn="$1"
  local listener_arn
  local http_action

  if [[ -n "${CERTIFICATE_ARN}" && "${HTTP_TO_HTTPS_REDIRECT}" == "true" ]]; then
    http_action='Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}'
  else
    http_action="Type=forward,TargetGroupArn=${target_group_arn}"
  fi

  listener_arn="$(listener_arn_for_port 80)"
  if ! is_missing "${listener_arn}"; then
    aws elbv2 modify-listener \
      --listener-arn "${listener_arn}" \
      --default-actions "${http_action}" \
      --region "${REGION}" >/dev/null
    return
  fi

  aws elbv2 create-listener \
    --load-balancer-arn "${ALB_ARN}" \
    --protocol HTTP \
    --port 80 \
    --default-actions "${http_action}" \
    --region "${REGION}" >/dev/null
}

ensure_https_listener() {
  local target_group_arn="$1"
  local listener_arn

  if [[ -z "${CERTIFICATE_ARN}" ]]; then
    return
  fi

  listener_arn="$(listener_arn_for_port 443)"
  if ! is_missing "${listener_arn}"; then
    aws elbv2 modify-listener \
      --listener-arn "${listener_arn}" \
      --certificates "CertificateArn=${CERTIFICATE_ARN}" \
      --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 \
      --default-actions "Type=forward,TargetGroupArn=${target_group_arn}" \
      --region "${REGION}" >/dev/null
    return
  fi

    aws elbv2 create-listener \
      --load-balancer-arn "${ALB_ARN}" \
      --protocol HTTPS \
      --port 443 \
      --certificates "CertificateArn=${CERTIFICATE_ARN}" \
      --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 \
      --default-actions "Type=forward,TargetGroupArn=${target_group_arn}" \
      --region "${REGION}" >/dev/null
}

ensure_state_file
log "Provisioning AWS foundation for Porter Intelligence Platform (${REGION})"

VPC_ID="$(ensure_vpc)"
PUBLIC_SUBNET_A_ID="$(ensure_subnet PUBLIC_SUBNET_A_ID 10.20.1.0/24 "${REGION}a" true)"
PUBLIC_SUBNET_B_ID="$(ensure_subnet PUBLIC_SUBNET_B_ID 10.20.2.0/24 "${REGION}b" true)"
PRIVATE_SUBNET_A_ID="$(ensure_subnet PRIVATE_SUBNET_A_ID 10.20.10.0/24 "${REGION}a" false)"
PRIVATE_SUBNET_B_ID="$(ensure_subnet PRIVATE_SUBNET_B_ID 10.20.11.0/24 "${REGION}b" false)"
INTERNET_GATEWAY_ID="$(ensure_internet_gateway)"
PUBLIC_ROUTE_TABLE_ID="$(ensure_route_table PUBLIC_ROUTE_TABLE_ID)"
PRIVATE_ROUTE_TABLE_ID="$(ensure_route_table PRIVATE_ROUTE_TABLE_ID)"
NAT_EIP_ALLOCATION_ID="$(ensure_eip)"
NAT_GATEWAY_ID="$(ensure_nat_gateway)"

ensure_route "${PUBLIC_ROUTE_TABLE_ID}" "0.0.0.0/0" "--gateway-id" "${INTERNET_GATEWAY_ID}"
associate_subnet_with_route_table "${PUBLIC_SUBNET_A_ID}" "${PUBLIC_ROUTE_TABLE_ID}"
associate_subnet_with_route_table "${PUBLIC_SUBNET_B_ID}" "${PUBLIC_ROUTE_TABLE_ID}"
associate_subnet_with_route_table "${PRIVATE_SUBNET_A_ID}" "${PRIVATE_ROUTE_TABLE_ID}"
associate_subnet_with_route_table "${PRIVATE_SUBNET_B_ID}" "${PRIVATE_ROUTE_TABLE_ID}"
log "Base networking ready"

SG_ALB_ID="$(ensure_security_group SG_ALB_ID "${PREFIX}-alb-sg" "Porter ALB security group")"
SG_APP_ID="$(ensure_security_group SG_APP_ID "${PREFIX}-app-sg" "Porter ECS task security group")"
SG_DB_ID="$(ensure_security_group SG_DB_ID "${PREFIX}-db-sg" "Porter RDS security group")"
SG_CACHE_ID="$(ensure_security_group SG_CACHE_ID "${PREFIX}-cache-sg" "Porter Redis security group")"
SG_ENDPOINTS_ID="$(ensure_security_group SG_ENDPOINTS_ID "${PREFIX}-endpoints-sg" "Porter VPC interface endpoints security group")"

ensure_ingress_rule "${SG_ALB_ID}" tcp 80 "0.0.0.0/0" cidr
ensure_ingress_rule "${SG_ALB_ID}" tcp 443 "0.0.0.0/0" cidr
ensure_ingress_rule "${SG_APP_ID}" tcp 8000 "${SG_ALB_ID}" group
ensure_ingress_rule "${SG_DB_ID}" tcp 5432 "${SG_APP_ID}" group
ensure_ingress_rule "${SG_CACHE_ID}" tcp 6379 "${SG_APP_ID}" group
ensure_ingress_rule "${SG_ENDPOINTS_ID}" tcp 443 "${SG_APP_ID}" group

PRIVATE_CONNECTIVITY_MODE="public_subnets"
if ! is_missing "${NAT_GATEWAY_ID}"; then
  ensure_route "${PRIVATE_ROUTE_TABLE_ID}" "0.0.0.0/0" "--nat-gateway-id" "${NAT_GATEWAY_ID}"
  PRIVATE_CONNECTIVITY_MODE="nat_gateway"
elif [[ "${VPC_ENDPOINTS_ENABLED}" == "true" ]] && ensure_private_service_endpoints; then
  PRIVATE_CONNECTIVITY_MODE="vpc_endpoints"
else
  log "Private ECS prerequisites unavailable with current permissions; using public ECS subnets"
fi

if [[ "${PRIVATE_CONNECTIVITY_MODE}" == "nat_gateway" || "${PRIVATE_CONNECTIVITY_MODE}" == "vpc_endpoints" ]]; then
  state_set ECS_SUBNET_A_ID "${PRIVATE_SUBNET_A_ID}"
  state_set ECS_SUBNET_B_ID "${PRIVATE_SUBNET_B_ID}"
  state_set ECS_ASSIGN_PUBLIC_IP DISABLED
else
  state_set ECS_SUBNET_A_ID "${PUBLIC_SUBNET_A_ID}"
  state_set ECS_SUBNET_B_ID "${PUBLIC_SUBNET_B_ID}"
  state_set ECS_ASSIGN_PUBLIC_IP ENABLED
fi
state_set PRIVATE_CONNECTIVITY_MODE "${PRIVATE_CONNECTIVITY_MODE}"

log "Networking ready (${PRIVATE_CONNECTIVITY_MODE})"

ensure_ecr_repository
ensure_ecs_cluster
ensure_log_group
ensure_iam_roles

DB_PASS="$(
  ensure_random_secret \
    "${SECRET_PREFIX}/DATABASE_MASTER_PASSWORD" \
    "Porter Intelligence Platform database master password" \
    "import secrets; print(secrets.token_urlsafe(24))"
)"
ensure_random_secret \
  "${SECRET_PREFIX}/JWT_SECRET_KEY" \
  "Porter Intelligence Platform JWT signing key" \
  "import secrets; print(secrets.token_urlsafe(48))" >/dev/null
ensure_random_secret \
  "${SECRET_PREFIX}/WEBHOOK_SECRET" \
  "Porter Intelligence Platform webhook verification secret" \
  "import secrets; print(secrets.token_urlsafe(48))" >/dev/null
ensure_random_secret \
  "${SECRET_PREFIX}/ENCRYPTION_KEY" \
  "Porter Intelligence Platform field encryption key" \
  "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())" >/dev/null

ensure_db_subnet_group
ensure_rds_instance
RDS_ENDPOINT="$(
  aws rds describe-db-instances \
    --db-instance-identifier "${DB_INSTANCE_ID}" \
    --region "${REGION}" \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text
)"
put_secret_value \
  "${SECRET_PREFIX}/DATABASE_URL" \
  "Porter Intelligence Platform SQLAlchemy database URL" \
  "postgresql+asyncpg://${DB_USERNAME}:${DB_PASS}@${RDS_ENDPOINT}:5432/${DB_NAME}"

ensure_cache_subnet_group
ensure_cache_cluster
REDIS_ENDPOINT="$(
  aws elasticache describe-cache-clusters \
    --cache-cluster-id "${CACHE_CLUSTER_ID}" \
    --show-cache-node-info \
    --region "${REGION}" \
    --query 'CacheClusters[0].CacheNodes[0].Endpoint.Address' \
    --output text
)"
put_secret_value \
  "${SECRET_PREFIX}/REDIS_URL" \
  "Porter Intelligence Platform Redis connection URL" \
  "redis://${REDIS_ENDPOINT}:6379"

STATE_CERTIFICATE_ARN="$(state_get CERTIFICATE_ARN)"
if [[ -z "${CERTIFICATE_ARN}" ]] && ! is_missing "${STATE_CERTIFICATE_ARN}"; then
  CERTIFICATE_ARN="${STATE_CERTIFICATE_ARN}"
fi

ALB_ARN="$(ensure_load_balancer)"
TARGET_GROUP_ARN="$(ensure_target_group)"
ensure_https_listener "${TARGET_GROUP_ARN}"
ensure_http_listener "${TARGET_GROUP_ARN}"

ALB_DNS_NAME="$(
  aws elbv2 describe-load-balancers \
    --load-balancer-arns "${ALB_ARN}" \
    --region "${REGION}" \
    --query 'LoadBalancers[0].DNSName' \
    --output text
)"

state_set CLUSTER_NAME "${CLUSTER_NAME}"
state_set SERVICE_NAME "${SERVICE_NAME}"
state_set DB_INSTANCE_ID "${DB_INSTANCE_ID}"
state_set CACHE_CLUSTER_ID "${CACHE_CLUSTER_ID}"
state_set ALB_DNS_NAME "${ALB_DNS_NAME}"
state_set SECRET_PREFIX "${SECRET_PREFIX}"
state_set LOG_GROUP_NAME "${LOG_GROUP_NAME}"
state_set CERTIFICATE_ARN "${CERTIFICATE_ARN}"

log "Provisioning complete"
printf 'State file:        %s\n' "${STATE_FILE}"
printf 'Cluster:           %s\n' "${CLUSTER_NAME}"
printf 'Service:           %s\n' "${SERVICE_NAME}"
printf 'ALB DNS:           %s\n' "${ALB_DNS_NAME}"
printf 'Secrets prefix:    %s/\n' "${SECRET_PREFIX}"
printf '\n'
printf 'Next step:\n'
printf '  ACCOUNT_ID=%s REGION=%s PROJECT=%s ENV=%s bash infrastructure/aws/deploy.sh\n' \
  "${ACCOUNT_ID}" "${REGION}" "${PROJECT}" "${ENV}"
