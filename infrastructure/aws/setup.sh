#!/usr/bin/env bash
# One-time setup — already executed. Do not re-run.
# Porter Intelligence Platform — One-time AWS infrastructure provisioning
#
# Provisions: VPC, ECS Fargate cluster, RDS PostgreSQL Multi-AZ,
#             ElastiCache Redis, ECR, ALB, Secrets Manager secrets,
#             CloudWatch log group.
#
# Usage: ACCOUNT_ID=<id> ./infrastructure/aws/setup.sh
# Prerequisites: aws CLI >= 2.x, jq, sufficient IAM permissions.

set -euo pipefail

ACCOUNT_ID="${ACCOUNT_ID:?Set ACCOUNT_ID}"
REGION="${REGION:-ap-south-1}"
PROJECT="porter"
ENV="prod"
PREFIX="${PROJECT}-${ENV}"
AZ_A="${REGION}a"
AZ_B="${REGION}b"

echo "==> Provisioning Porter Intelligence Platform on AWS (${REGION})"

# ── 1. VPC ──────────────────────────────────────────────────────────────────
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --region "${REGION}" \
  --query "Vpc.VpcId" --output text)
aws ec2 create-tags --resources "${VPC_ID}" \
  --tags "Key=Name,Value=${PREFIX}-vpc" --region "${REGION}"
aws ec2 modify-vpc-attribute --vpc-id "${VPC_ID}" \
  --enable-dns-hostnames --region "${REGION}"
echo "   VPC: ${VPC_ID}"

# Public subnets (ALB)
PUB_A=$(aws ec2 create-subnet --vpc-id "${VPC_ID}" \
  --cidr-block 10.0.1.0/24 --availability-zone "${AZ_A}" \
  --region "${REGION}" --query "Subnet.SubnetId" --output text)
PUB_B=$(aws ec2 create-subnet --vpc-id "${VPC_ID}" \
  --cidr-block 10.0.2.0/24 --availability-zone "${AZ_B}" \
  --region "${REGION}" --query "Subnet.SubnetId" --output text)

# Private subnets (ECS tasks, RDS, ElastiCache)
PRIV_A=$(aws ec2 create-subnet --vpc-id "${VPC_ID}" \
  --cidr-block 10.0.10.0/24 --availability-zone "${AZ_A}" \
  --region "${REGION}" --query "Subnet.SubnetId" --output text)
PRIV_B=$(aws ec2 create-subnet --vpc-id "${VPC_ID}" \
  --cidr-block 10.0.11.0/24 --availability-zone "${AZ_B}" \
  --region "${REGION}" --query "Subnet.SubnetId" --output text)

# Internet Gateway
IGW=$(aws ec2 create-internet-gateway --region "${REGION}" \
  --query "InternetGateway.InternetGatewayId" --output text)
aws ec2 attach-internet-gateway --vpc-id "${VPC_ID}" \
  --internet-gateway-id "${IGW}" --region "${REGION}"

# Route table for public subnets
RTB=$(aws ec2 create-route-table --vpc-id "${VPC_ID}" \
  --region "${REGION}" --query "RouteTable.RouteTableId" --output text)
aws ec2 create-route --route-table-id "${RTB}" \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id "${IGW}" --region "${REGION}"
for SN in "${PUB_A}" "${PUB_B}"; do
  aws ec2 associate-route-table --subnet-id "${SN}" \
    --route-table-id "${RTB}" --region "${REGION}"
done
echo "   Subnets: ${PUB_A} ${PUB_B} (public) | ${PRIV_A} ${PRIV_B} (private)"

# ── 2. Security Groups ───────────────────────────────────────────────────────
SG_ALB=$(aws ec2 create-security-group \
  --group-name "${PREFIX}-alb-sg" --description "ALB SG" \
  --vpc-id "${VPC_ID}" --region "${REGION}" \
  --query "GroupId" --output text)
aws ec2 authorize-security-group-ingress \
  --group-id "${SG_ALB}" --protocol tcp --port 443 \
  --cidr 0.0.0.0/0 --region "${REGION}"

SG_APP=$(aws ec2 create-security-group \
  --group-name "${PREFIX}-app-sg" --description "ECS Task SG" \
  --vpc-id "${VPC_ID}" --region "${REGION}" \
  --query "GroupId" --output text)
aws ec2 authorize-security-group-ingress \
  --group-id "${SG_APP}" --protocol tcp --port 8000 \
  --source-group "${SG_ALB}" --region "${REGION}"

SG_DB=$(aws ec2 create-security-group \
  --group-name "${PREFIX}-db-sg" --description "RDS SG" \
  --vpc-id "${VPC_ID}" --region "${REGION}" \
  --query "GroupId" --output text)
aws ec2 authorize-security-group-ingress \
  --group-id "${SG_DB}" --protocol tcp --port 5432 \
  --source-group "${SG_APP}" --region "${REGION}"

SG_CACHE=$(aws ec2 create-security-group \
  --group-name "${PREFIX}-cache-sg" --description "ElastiCache SG" \
  --vpc-id "${VPC_ID}" --region "${REGION}" \
  --query "GroupId" --output text)
aws ec2 authorize-security-group-ingress \
  --group-id "${SG_CACHE}" --protocol tcp --port 6379 \
  --source-group "${SG_APP}" --region "${REGION}"
echo "   Security groups created"

# ── 3. ECR ───────────────────────────────────────────────────────────────────
aws ecr create-repository \
  --repository-name porter-intelligence \
  --image-scanning-configuration scanOnPush=true \
  --region "${REGION}" > /dev/null
echo "   ECR repo: ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/porter-intelligence"

# ── 4. ECS Cluster ───────────────────────────────────────────────────────────
aws ecs create-cluster \
  --cluster-name "${PREFIX}" \
  --capacity-providers FARGATE FARGATE_SPOT \
  --region "${REGION}" > /dev/null
echo "   ECS cluster: ${PREFIX}"

# ── 5. CloudWatch Log Group ──────────────────────────────────────────────────
aws logs create-log-group \
  --log-group-name "/ecs/porter-intelligence" \
  --region "${REGION}" || true
aws logs put-retention-policy \
  --log-group-name "/ecs/porter-intelligence" \
  --retention-in-days 30 \
  --region "${REGION}"
echo "   CloudWatch log group: /ecs/porter-intelligence (30-day retention)"

# ── 6. RDS PostgreSQL Multi-AZ ───────────────────────────────────────────────
DB_SUBNET_GROUP="${PREFIX}-db-subnet"
aws rds create-db-subnet-group \
  --db-subnet-group-name "${DB_SUBNET_GROUP}" \
  --db-subnet-group-description "Porter RDS subnet group" \
  --subnet-ids "${PRIV_A}" "${PRIV_B}" \
  --region "${REGION}" > /dev/null

DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
aws rds create-db-instance \
  --db-instance-identifier "${PREFIX}-postgres" \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version "15.4" \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --master-username porteradmin \
  --master-user-password "${DB_PASS}" \
  --db-name porter \
  --vpc-security-group-ids "${SG_DB}" \
  --db-subnet-group-name "${DB_SUBNET_GROUP}" \
  --multi-az \
  --backup-retention-period 7 \
  --no-publicly-accessible \
  --region "${REGION}" > /dev/null
echo "   RDS PostgreSQL Multi-AZ provisioning (takes ~10 min)"

# ── 7. ElastiCache Redis ─────────────────────────────────────────────────────
CACHE_SUBNET_GROUP="${PREFIX}-cache-subnet"
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name "${CACHE_SUBNET_GROUP}" \
  --cache-subnet-group-description "Porter ElastiCache subnet group" \
  --subnet-ids "${PRIV_A}" "${PRIV_B}" \
  --region "${REGION}" > /dev/null

aws elasticache create-cache-cluster \
  --cache-cluster-id "${PREFIX}-redis" \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --engine-version "7.0" \
  --num-cache-nodes 1 \
  --cache-subnet-group-name "${CACHE_SUBNET_GROUP}" \
  --security-group-ids "${SG_CACHE}" \
  --region "${REGION}" > /dev/null
echo "   ElastiCache Redis provisioning"

# ── 8. Secrets Manager ───────────────────────────────────────────────────────
ENCRYPTION_KEY=$(python3 -c \
  "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")

for SECRET_NAME in DATABASE_URL REDIS_URL JWT_SECRET_KEY ENCRYPTION_KEY WEBHOOK_SECRET; do
  aws secretsmanager create-secret \
    --name "porter/prod/${SECRET_NAME}" \
    --description "Porter Intelligence Platform — ${SECRET_NAME}" \
    --region "${REGION}" > /dev/null || true
done

# Pre-fill ENCRYPTION_KEY (others must be set after RDS/Redis are ready)
aws secretsmanager put-secret-value \
  --secret-id "porter/prod/ENCRYPTION_KEY" \
  --secret-string "${ENCRYPTION_KEY}" \
  --region "${REGION}" > /dev/null
echo "   Secrets Manager secrets created"
echo "   ENCRYPTION_KEY stored: ${ENCRYPTION_KEY}"
echo "   !! Set DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, WEBHOOK_SECRET manually !!"

echo ""
echo "==> Infrastructure provisioning initiated."
echo "    Wait ~10 min for RDS, then run: ./infrastructure/aws/deploy.sh"
