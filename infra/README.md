# AnalyseThisWC26 — v2 infrastructure

Terraform and deploy scripts for the **v2 candidate stack**. Production v1 (`atwc26.com`) stays on the monolith until Issue 10 cutover.

Use a distinct `name_prefix` (default `atwc26-v2`) so candidate resources never collide with production.

> Scope note: this v2 candidate path intentionally uses **CloudFront without WAF** for now (CDN + TLS only).

**Architecture diagram:** [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) (C4 model + full AWS map). ETL scheduler detail: [docs/etl/SCHEDULER.md](../docs/etl/SCHEDULER.md).

## Layout

```text
infra/
  scripts/
    build_frontend_static.sh   # Issue 4 — Next.js → frontend/out/
    deploy_frontend.sh         # aws s3 sync + optional CloudFront invalidation
    deploy_frontend_from_tf.sh # reads bucket + distribution from Terraform outputs
    package_lambdas.sh         # Issue 7 — layer + analytics/predict zip artifacts
  lambda-layer/
    requirements.txt           # shared Lambda layer dependencies
  terraform/
    modules/frontend-cdn/      # Issue 5 — S3 + CloudFront (OAC)
    modules/s3-data/           # Issue 7 — ETL data bucket
    modules/dynamodb/          # Issue 7 — publish manifest table
    modules/lambda-analytics/  # Issue 7
    modules/lambda-predict/    # Issue 7
    modules/api-gateway/       # Issue 7 — HTTP API routes
    modules/ecs-compute/       # Fargate for POST /api/predict only
    modules/ecs-predict-image/ # Docker build + ECR push (terraform apply)
    modules/acm-certificate/   # ACM + Route53 DNS validation (us-east-1)
    envs/dev/                  # dev/candidate wiring
    envs/prod/                 # production — atwc26.com + Route53 aliases
services/
  analytics_api/               # Issue 7 — read-only tournament API
  predict_api/                 # Issue 7 — POST /api/predict
```

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [AWS CLI](https://aws.amazon.com/cli/) configured (`aws sts get-caller-identity`)
- Node.js 18+ (static frontend build)

## Issue 5 — S3 + CloudFront (dev)

### 1. Configure

```bash
cd infra/terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars if needed
```

### 2. Plan / apply

```bash
# Validate only (no remote state):
terraform init -backend=false

# Apply with remote state (recommended for CI and shared dev):
cp backend.hcl.example backend.hcl   # edit bucket/key
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

Note outputs:

```bash
terraform output cloudfront_url
terraform output site_url              # unified URL (static + /api/* via CloudFront)
terraform output api_gateway_url       # direct API Gateway (debug)
terraform output cors_origin_hint
```

### Edge routing (Phase A)

CloudFront serves:

- default behavior → S3 static frontend (`frontend/out/`)
- `/api/*` → API Gateway HTTP API (no WAF)

API Gateway routes:

- `POST /api/predict` → compute (ECS when `enable_ecs_compute=true`, else predict Lambda)
- all other paths (including `GET /api/winner-probabilities`) → analytics Lambda

Set `enable_ecs_compute = true` in `terraform.tfvars` to route `POST /api/predict` to Fargate.
With `build_ecs_image = true` (default), `terraform apply` also **docker builds**, **pushes to ECR**, and rolls the ECS task definition to the content-hash tag — no separate deploy step.

Requires **Docker** and **AWS CLI** on the machine running `terraform apply` when ECS is enabled.

### 3. CORS on v1 backend

The static site runs on CloudFront and calls the **v1 API** cross-origin. Add the CloudFront URL to the backend allow list:

```bash
# Example — append to existing origins on the v1 host:
export ATWC26_CORS_ORIGINS="http://localhost:3000,...,https://d111111abcdef8.cloudfront.net"
```

Rebuild/restart the v1 backend after updating CORS.

### 4. Build static frontend

Bake the v1 API URL into the bundle **at build time**:

```bash
# From repo root — API URL from terraform output:
NEXT_PUBLIC_API_URL="$(terraform -chdir=infra/terraform/envs/dev output -raw backend_api_url)" \
  ./infra/scripts/build_frontend_static.sh
```

### 5. Deploy to S3

```bash
./infra/scripts/deploy_frontend_from_tf.sh
```

Or manually:

```bash
export ATWC26_FRONTEND_BUCKET="$(terraform -chdir=infra/terraform/envs/dev output -raw bucket_name)"
export ATWC26_CLOUDFRONT_DISTRIBUTION_ID="$(terraform -chdir=infra/terraform/envs/dev output -raw cloudfront_distribution_id)"
./infra/scripts/deploy_frontend.sh
```

Open `terraform output cloudfront_url` and verify pages load; API calls should reach `backend_api_url`.

## Production — `atwc26.com` (envs/prod)

Prod stack provisions the full v2 API + static frontend with **managed ACM**, **CloudFront aliases**, and **Route53 A/AAAA alias records** for `atwc26.com` and `www.atwc26.com`.

### 1. Configure

```bash
cd infra/terraform/envs/prod
cp terraform.tfvars.example terraform.tfvars
cp backend.hcl.example backend.hcl   # state key: atwc26-v2/prod/terraform.tfstate
# edit terraform.tfvars (github_dispatch_token, etc.)
```

Import existing apex/www A records before first apply if they already exist — see [envs/prod/IMPORT.md](terraform/envs/prod/IMPORT.md).

### 2. Plan / apply

```bash
# From repo root:
make tf-plan TF_ENV=prod
make tf-apply TF_ENV=prod

# Or:
ATWC26_TF_DIR=infra/terraform/envs/prod ./infra/scripts/build_frontend_static.sh
ATWC26_TF_DIR=infra/terraform/envs/prod ./infra/scripts/deploy_frontend_from_tf.sh
```

### 3. Publish data

```bash
ATWC26_S3_BUCKET="$(terraform -chdir=infra/terraform/envs/prod output -raw data_bucket_name)" \
ATWC26_DYNAMODB_TABLE="$(terraform -chdir=infra/terraform/envs/prod output -raw dynamodb_table_name)" \
  make etl-publish
```

### Prod variables (highlights)

| Variable | Default | Purpose |
|----------|---------|---------|
| `enable_custom_domain` | `true` | Issue ACM cert + attach to CloudFront |
| `manage_dns_alias_records` | `true` | Route53 apex/www → CloudFront |
| `domain_name` | `atwc26.com` | Primary custom domain |
| `cors_allow_origins` | `https://atwc26.com`, `https://www.atwc26.com` | API CORS |

CI: **Actions → Terraform prod → Run workflow** (requires GitHub `production` environment + `ATWC26_TFVARS_PROD` secret).

---

## Validate (CI / local, no AWS apply)

```bash
terraform -chdir=infra/terraform/envs/dev init -backend=false
terraform -chdir=infra/terraform/envs/dev validate
terraform -chdir=infra/terraform/envs/prod init -backend=false
terraform -chdir=infra/terraform/envs/prod validate
```

## Issue 7 — Split analytics + predict Lambdas

### Local services

```bash
make setup-services
make analytics    # http://localhost:8001
make predict      # http://localhost:8000
make dev-v2       # split APIs + frontend
make test-contract
```

Frontend uses `NEXT_PUBLIC_ANALYTICS_API_URL` and `NEXT_PUBLIC_PREDICT_API_URL` (see `frontend/.env.example`).

### Package Lambdas

```bash
./infra/scripts/package_lambdas.sh
# writes infra/build/lambdas/{layer,analytics,predict}.zip
```

Builds **Linux arm64** wheels (Lambda architecture), strips tests/boto3, and prunes
pyarrow headers. If `layer.zip` is large, Terraform uploads it via S3 automatically
(see `aws_s3_object.lambda_layer` in `envs/dev/main.tf`).

### Terraform apply (candidate API stack)

After packaging:

```bash
cd infra/terraform/envs/dev
terraform apply
```

Outputs:

```bash
terraform output api_gateway_url          # both analytics + predict routes
terraform output data_bucket_name         # sync ETL artifacts here
terraform output dynamodb_table_name
```

### Route ownership (target state)

- `analytics_api` (Lambda): all read endpoints including `GET /api/winner-probabilities` (precomputed JSON / DynamoDB cache — no Monte Carlo at request time).
- `predict` compute path (ECS/Fargate): `POST /api/predict` only.
- API Gateway performs route split; CloudFront forwards `/api/*` to API Gateway.

### Execution phases (from `TODO.md`)

Phases A–F (infra + API cache) are done. Remaining:

1. **G** — `etl/simulate` (offline Monte Carlo → S3 JSON)
2. **H** — winner-probs on analytics read path
3. **I** — per-90 profiles in transform
4. **J** — full read cache + light Lambda startup
5. **K** — path-filtered GHA jobs
6. **L** — GitHub OIDC

Publish data before invoking Lambdas in AWS:

```bash
ATWC26_S3_BUCKET="$(terraform output -raw data_bucket_name)" make etl-publish
```

## Variables (dev)

| Variable | Default | Purpose |
|----------|---------|---------|
| `aws_region` | `us-east-1` | S3 bucket region |
| `name_prefix` | `atwc26-v2` | Resource naming prefix |
| `environment` | `dev` | Environment label |
| `backend_api_url` | `https://atwc26.com` | v1 API for static build + docs |
| `aliases` | `[]` | Optional custom CloudFront domain |
| `acm_certificate_arn` | — | ACM cert in **us-east-1** if using aliases |

## Outputs (dev)

| Output | Used by |
|--------|---------|
| `bucket_name` | `deploy_frontend.sh` |
| `cloudfront_distribution_id` | `deploy_frontend.sh` invalidation |
| `cloudfront_url` | Smoke-test candidate frontend |
| `cors_origin_hint` | v1 `ATWC26_CORS_ORIGINS` |
| `backend_api_url` | `build_frontend_static.sh` |

## GitHub Actions (Issue 9)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | PR/push to `main` or `refactor/v2-integration` | Path-filtered tests (e2e, ETL, contract, frontend build, terraform validate, Lambda package) |
| [`.github/workflows/etl.yml`](../.github/workflows/etl.yml) | Daily cron + `workflow_dispatch` | Transform + QA; optional ESPN scrape + S3 publish on manual run |
| [`.github/workflows/terraform.yml`](../.github/workflows/terraform.yml) | `workflow_dispatch` | Package Lambdas → Terraform plan/apply; writes stack URLs for k6 A/B |
| [`.github/workflows/deploy-frontend.yml`](../.github/workflows/deploy-frontend.yml) | Push to `main` (frontend paths) + `workflow_dispatch` | Build and sync static frontend to S3/CloudFront |
| [`.github/workflows/performance.yml`](../.github/workflows/performance.yml) | `workflow_dispatch` | k6 A/B v1 vs v2 |

### CI path filters (`refactor/v2-integration`)

| Job | Paths |
|-----|-------|
| `api-e2e` | `backend/**`, `e2e/**` (always on PRs to `main`) |
| `etl` | `etl/**`, `packages/atwc26_core/**`, `tests/etl/**` |
| `contract` | `services/**`, `packages/atwc26_core/**`, `tests/contract/**` |
| `v2-smoke` | ETL or services paths → `make e2e-v2-local` |
| `frontend-build` | `frontend/**` |
| `terraform-validate` / `lambda-package` | `infra/**` |
| `k6-compare` | `k6/**`, `tests/k6/**` |

### Terraform workflow

1. **Actions → Terraform dev → Run workflow**
2. Choose `plan` (dry-run) or `apply` (provision/update stack).
3. After **apply**, the job summary lists **CloudFront URL** and **API Gateway URL** — use the latter as `K6_CANDIDATE_ANALYTICS_URL` / `K6_CANDIDATE_PREDICT_URL` in the Performance workflow or `make k6-ab`.

Frontend deploy and ETL publish are separate workflows (`deploy-frontend.yml`, `etl.yml`).

Remote Terraform state is **required** for `apply` in CI. Set `ATWC26_TF_STATE_BUCKET` (see secrets table below).

### ETL workflow

- **Scheduled** (06:00 UTC): transform + QA + tests on committed `data/` artifacts.
- **Manual** with **Run scrape** enabled: `schedule` → `scrape` → `events` → `squads` → `groups` → transform → QA → tests → publish.

## GitHub secrets / vars (Issue 9)

Configure under **Settings → Secrets and variables → Actions**.

| Name | Required for | Source |
|------|----------------|--------|
| `AWS_ACCESS_KEY_ID` | ETL publish, deploy (legacy) | IAM user — prefer OIDC |
| `AWS_SECRET_ACCESS_KEY` | ETL publish, deploy (legacy) | IAM credentials |
| `ATWC26_AWS_ROLE_ARN` | ETL publish, deploy (preferred) | `terraform output github_actions_role_arn` when `enable_github_oidc=true` |
| `AWS_REGION` | All AWS jobs | e.g. `us-east-1` |
| `ATWC26_S3_BUCKET` | ETL publish | `terraform output data_bucket_name` |
| `ATWC26_DYNAMODB_TABLE` | ETL publish | `terraform output dynamodb_table_name` |
| `ATWC26_TF_STATE_BUCKET` | Deploy `apply` | S3 bucket for Terraform state |
| `ATWC26_TFVARS` | Deploy dev (optional) | Multiline HCL — copy of `envs/dev/terraform.tfvars` |
| `ATWC26_TFVARS_PROD` | Deploy prod | Multiline HCL — copy of `envs/prod/terraform.tfvars` |
| `ATWC26_FRONTEND_BUCKET` | Manual `deploy_frontend.sh` only | `terraform output bucket_name` |
| `ATWC26_CLOUDFRONT_DISTRIBUTION_ID` | Manual deploy / invalidation | `terraform output cloudfront_distribution_id` |

Deploy workflow reads frontend bucket and distribution from Terraform outputs when `deploy_frontend` is enabled — separate frontend secrets are only needed for manual `deploy_frontend.sh` outside CI.

### IAM permissions (deploy role)

- S3: data bucket, frontend bucket, Lambda layer upload prefix
- DynamoDB: manifest table
- Lambda, API Gateway, CloudFront, IAM (for Lambda execution roles)
- ECS (predict service refresh path)
- Optional: S3 state bucket for `ATWC26_TF_STATE_BUCKET`

## Related docs

- [docs/ops/DEPLOY.md](../docs/ops/DEPLOY.md) — full deployment guide
- [docs/planning/REFACTOR_GITHUB_ISSUES.md](../docs/planning/REFACTOR_GITHUB_ISSUES.md) — Issues 4–5 spec
