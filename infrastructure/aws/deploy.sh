#!/usr/bin/env bash
# Porter Intelligence Platform — ECS rolling deployment
# Usage: ./infrastructure/aws/deploy.sh [IMAGE_TAG]
#
# Prerequisites: aws CLI configured, ECR login active, jq installed.
# Set ACCOUNT_ID and REGION before running (or export from CI env).

set -euo pipefail

ACCOUNT_ID="${ACCOUNT_ID:?Set ACCOUNT_ID}"
REGION="${REGION:-ap-south-1}"
CLUSTER="${CLUSTER:-porter-prod}"
SERVICE="${SERVICE:-porter-api}"
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/porter-intelligence"
IMAGE_TAG="${1:-$(git rev-parse --short HEAD)}"
IMAGE="${ECR_REPO}:${IMAGE_TAG}"
TASK_FAMILY="porter-intelligence"

echo "==> Deploying Porter Intelligence Platform"
echo "    Image : ${IMAGE}"
echo "    Cluster: ${CLUSTER} / Service: ${SERVICE}"

# 1. ECR login
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REPO}"

# 2. Build + push
docker build --platform linux/amd64 -t "${IMAGE}" .
docker tag  "${IMAGE}" "${ECR_REPO}:latest"
docker push "${IMAGE}"
docker push "${ECR_REPO}:latest"
echo "==> Image pushed: ${IMAGE}"

# 3. Register new task definition revision with updated image
TASK_DEF=$(aws ecs describe-task-definition \
  --task-definition "${TASK_FAMILY}" \
  --region "${REGION}" \
  --query "taskDefinition" \
  --output json)

NEW_TASK_DEF=$(echo "${TASK_DEF}" | jq \
  --arg IMAGE "${IMAGE}" \
  '.containerDefinitions[0].image = $IMAGE
   | del(.taskDefinitionArn, .revision, .status,
         .requiresAttributes, .compatibilities,
         .registeredAt, .registeredBy)')

NEW_REVISION=$(aws ecs register-task-definition \
  --region "${REGION}" \
  --cli-input-json "${NEW_TASK_DEF}" \
  --query "taskDefinition.revision" \
  --output text)
echo "==> Task definition revision: ${NEW_REVISION}"

# 4. Update service — rolling deployment (min 100%, max 200%)
aws ecs update-service \
  --cluster "${CLUSTER}" \
  --service "${SERVICE}" \
  --task-definition "${TASK_FAMILY}:${NEW_REVISION}" \
  --region "${REGION}" \
  --force-new-deployment \
  --output json | jq '.service | {status, desiredCount, runningCount}'

# 5. Wait for stable
echo "==> Waiting for service to stabilise (up to 10 min)…"
aws ecs wait services-stable \
  --cluster "${CLUSTER}" \
  --services "${SERVICE}" \
  --region "${REGION}"

echo "==> Deployment complete: ${IMAGE}"
