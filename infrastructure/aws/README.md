# AWS Deployment

Idempotent AWS provisioning and deployment scripts for Porter Intelligence Platform.

## What `setup.sh` provisions

- VPC with public and private subnets
- NAT gateway for private-subnet egress when the caller has EIP/NAT permissions
- VPC endpoints for private ECS operation when NAT is unavailable but endpoint permissions exist
- Security groups for ALB, ECS, RDS, and Redis
- ECR repository
- ECS cluster
- CloudWatch log group
- environment-scoped IAM roles for ECS execution and task runtime when IAM permissions allow
- RDS PostgreSQL
- ElastiCache Redis
- Secrets Manager entries
- Application Load Balancer and target group

## Required Environment Variables

```bash
export ACCOUNT_ID=<aws-account-id>
export REGION=ap-southeast-2
```

Optional:

```bash
export CERTIFICATE_ARN=<acm-certificate-arn>
export DB_NAME=porter_intelligence
export DB_USERNAME=porteradmin
export EXECUTION_ROLE_NAME=<optional-precreated-execution-role>
export TASK_ROLE_NAME=<optional-precreated-task-role>
```

## Provision Infrastructure

```bash
ACCOUNT_ID=<aws-account-id> REGION=ap-southeast-2 \
  ./infrastructure/aws/setup.sh
```

If the caller cannot allocate an Elastic IP or create a NAT gateway, the script
first tries to keep ECS private by creating the required VPC endpoints
(`ecr.api`, `ecr.dkr`, `logs`, `secretsmanager`, `ssm`, and `s3`). If endpoint
creation is also unavailable, it falls back to placing ECS tasks in the public
subnets and records that choice in
`infrastructure/aws/state/<project>-<env>-<region>.json`. This keeps the buyer
environment reproducible under reduced IAM privileges while still preserving the
private-subnet design when full networking permissions are available.

If `CERTIFICATE_ARN` is provided, `setup.sh` creates:

- an HTTPS listener on `443`
- an HTTP listener on `80` that redirects to HTTPS

If no certificate is supplied, the ALB remains HTTP-only until a certificate ARN
is passed on a later rerun.

The script persists secrets under the environment-specific prefix
`<project>/<env>/`:

- `DATABASE_MASTER_PASSWORD`
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `ENCRYPTION_KEY`
- `WEBHOOK_SECRET`

## Deploy Application

```bash
ACCOUNT_ID=<aws-account-id> REGION=ap-southeast-2 \
  ./infrastructure/aws/deploy.sh
```

`deploy.sh` will:

- build and push the Docker image to ECR
- render the ECS task definition from the repo template
- register a new task definition revision
- create the ECS service if it does not already exist
- otherwise perform a rolling update
- reconcile the ECS service network configuration with the current state file

## Pausing to Stop Costs

If you are between demos or iterating locally, run the pause script to stop all
billable resources without destroying configuration or data:

```bash
ACCOUNT_ID=767678952517 REGION=ap-southeast-2 \
  bash infrastructure/aws/pause.sh
```

What it stops and estimated monthly savings:

| Action | Saves |
|---|---|
| ECS desired_count → 0 | ~$42/month |
| RDS instance stopped | ~$13/month |
| ElastiCache deleted | ~$13/month |
| ALB + target group deleted | ~$18/month |
| **Total** | **~$86/month** |

> **Note:** AWS auto-restarts stopped RDS instances after 7 days. For
> a permanent stop, use `teardown.sh` instead.

To resume after a pause:

```bash
ACCOUNT_ID=767678952517 REGION=ap-southeast-2 \
  bash infrastructure/aws/setup.sh
ACCOUNT_ID=767678952517 REGION=ap-southeast-2 \
  bash infrastructure/aws/deploy.sh
```

## Running Demo Without AWS (Free)

The platform runs fully in benchmark mode with no cloud services needed.
`docker compose up` is sufficient for a sales demo:

```bash
docker compose up          # postgres + redis + api + prometheus, all local
# API available at http://localhost:8000
# All 14 endpoints return 200 with benchmark data
```

Set `ENABLE_SYNTHETIC_FEED=true` in `.env` for a live-updating fraud feed.

## Full Teardown

When you no longer need the AWS environment at all:

```bash
ACCOUNT_ID=767678952517 REGION=ap-southeast-2 \
  bash infrastructure/aws/teardown.sh
```

This deletes all resources in dependency order (ECS → ALB → ElastiCache →
RDS → VPC). It takes a final RDS snapshot by default. Pass `--no-snapshot`
to skip it:

```bash
NO_SNAPSHOT=true ACCOUNT_ID=767678952517 REGION=ap-southeast-2 \
  bash infrastructure/aws/teardown.sh
```

## Frontend Hosting

The dashboard is intentionally decoupled from raw ALB hostnames.

- If Netlify is used, set `VITE_API_BASE_URL` in the site environment.
- If the dashboard and API share the same origin behind a reverse proxy,
  `VITE_API_BASE_URL` can remain blank.
