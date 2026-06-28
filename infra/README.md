# AnalyseThisWC26 — v2 infrastructure

Terraform and deploy scripts for the **v2 candidate stack**. Production v1 (`atwc26.com`) stays on the monolith until Issue 10 cutover.

Use a distinct `name_prefix` (default `atwc26-v2`) so candidate resources never collide with production.

## Layout

```text
infra/
  scripts/
    build_frontend_static.sh   # Issue 4 — Next.js → frontend/out/
    deploy_frontend.sh         # aws s3 sync + optional CloudFront invalidation
    deploy_frontend_from_tf.sh   # reads bucket + distribution from Terraform outputs
  terraform/
    modules/frontend-cdn/      # Issue 5 — S3 + CloudFront (OAC)
    envs/dev/                  # dev/candidate wiring
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
terraform init
terraform plan
terraform apply
```

Note outputs:

```bash
terraform output cloudfront_url
terraform output cors_origin_hint      # add to v1 backend ATWC26_CORS_ORIGINS
terraform output backend_api_url        # use at static build time
```

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

### Validate (CI / local, no AWS apply)

```bash
terraform -chdir=infra/terraform/envs/dev init -backend=false
terraform -chdir=infra/terraform/envs/dev validate
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

## GitHub secrets / vars (Issue 9)

For CI deploy workflows, store:

| Name | Source |
|------|--------|
| `ATWC26_FRONTEND_BUCKET` | `terraform output bucket_name` |
| `ATWC26_CLOUDFRONT_DISTRIBUTION_ID` | `terraform output cloudfront_distribution_id` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | IAM user or OIDC role for sync |

## Related docs

- [docs/DEPLOY.md](../docs/DEPLOY.md) — full deployment guide
- [docs/REFACTOR_GITHUB_ISSUES.md](../docs/REFACTOR_GITHUB_ISSUES.md) — Issues 4–5 spec
