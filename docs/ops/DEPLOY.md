# Deployment & Operations

How to run and ship AnalyseThisWC26 locally and on AWS. This doc is the **ops entry point**; Terraform module detail lives in [`infra/README.md`](../../infra/README.md), and the full system map is in [`ARCHITECTURE.md`](../ARCHITECTURE.md).

| Doc | Read when… |
|-----|------------|
| [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) | What GHA workflows run automatically vs manually; bootstrap order; `production` environment |
| [V1_TO_V2.md](../V1_TO_V2.md) | v1 → v2 rationale, comparison, decision log |
| [ARCHITECTURE.md](../ARCHITECTURE.md) | C4 model + AWS deployment diagram |
| [`infra/README.md`](../../infra/README.md) | Terraform variables, outputs, GitHub secrets catalog, workflow file reference |
| [specs/PRODUCTION_SPEC.md](../specs/PRODUCTION_SPEC.md) | First-time AWS bootstrap (state bucket, OIDC, scheduler enablement order) |
| [TESTING.md](TESTING.md) | QA, k6 A/B, `make e2e-v2-local`, split-API smoke |
| [CUTOVER.md](CUTOVER.md) | v1 → v2 production go-live checklist |
| [etl/OVERVIEW.md](../etl/OVERVIEW.md) | ETL scheduler + pipeline (data freshness) |

---

## Table of Contents

1. [Choose your deployment path](#1-choose-your-deployment-path)
2. [Local — v1 monolith](#2-local--v1-monolith)
3. [Local — v2 split APIs](#3-local--v2-split-apis)
4. [Docker Compose — v1 monolith](#4-docker-compose--v1-monolith)
5. [AWS dev candidate (`envs/dev`)](#5-aws-dev-candidate-envsdev)
6. [AWS prod (`envs/prod`)](#6-aws-prod-envsprod)
7. [v2 edge routing (reference)](#7-v2-edge-routing-reference)
8. [Frontend build modes](#8-frontend-build-modes)
9. [Environment variables](#9-environment-variables)
10. [Security checklist](#10-security-checklist)
11. [Health & observability](#11-health--observability)
12. [Scaling notes](#12-scaling-notes)
13. [Alternative hosting (non-AWS)](#13-alternative-hosting-non-aws)

---

## 1. Choose your deployment path

| Goal | Stack | Section |
|------|-------|---------|
| Hack on the **legacy monolith** locally | `backend/` + `frontend/` | [§2](#2-local--v1-monolith) |
| Hack on the **v2 split APIs** locally | `services/analytics_api` + `services/predict_api` | [§3](#3-local--v2-split-apis) |
| Run **v1 behind Nginx** in Docker | `docker compose` | [§4](#4-docker-compose--v1-monolith) |
| Provision **AWS candidate** (CloudFront URL, no custom domain) | `infra/terraform/envs/dev` | [§5](#5-aws-dev-candidate-envsdev) |
| Provision **AWS prod** (`atwc26.com`) | `infra/terraform/envs/prod` | [§6](#6-aws-prod-envsprod) |

**v2 AWS shape (both envs):** CloudFront → S3 (static) + API Gateway (`/api/*`) → analytics Lambda (`$default`) + predict Lambda **or** ECS Fargate (`enable_ecs_compute`). See [§7](#7-v2-edge-routing-reference) and [ARCHITECTURE.md](../ARCHITECTURE.md).

---

## 2. Local — v1 monolith

Single FastAPI app (`backend/`) + Next.js dev server. Matches production v1 at `atwc26.com` today.

> Use a **virtualenv** for the backend. See [README.md §4](../../README.md#4-setup--one-time-vs-repeated-commands).

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # one-time
pip install -r requirements.txt                     # one-time (re-run on change)
python -m uvicorn app.main:app --reload --port 8000
```

**Frontend** (new terminal)

```bash
cd frontend
cp .env.example .env.local        # one-time — NEXT_PUBLIC_API_URL=http://localhost:8000
npm install                       # one-time
npm run dev                        # http://localhost:3000
```

---

## 3. Local — v2 split APIs

Read-heavy **analytics** (`:8001`) and CPU-bound **predict** (`:8000`) run as separate FastAPI services under `services/`.

```bash
make setup-services    # one-time
make dev-v2            # analytics :8001 + predict :8000 + frontend :3000
```

Or run services individually:

```bash
make analytics   # http://localhost:8001
make predict     # http://localhost:8000
```

`frontend/.env.local` should set:

```bash
NEXT_PUBLIC_ANALYTICS_API_URL=http://localhost:8001
NEXT_PUBLIC_PREDICT_API_URL=http://localhost:8000
```

**Automated gate (no servers):** `make e2e-v2-local` · **Contract tests:** `make test-contract` · Full QA path: [TESTING.md §12](TESTING.md#12-local-v2-e2e-smoke-path).

---

## 4. Docker Compose — v1 monolith

```bash
docker compose up --build
# open http://localhost:8080
```

Nginx routes `/api/*` → backend, everything else → frontend (`NEXT_PUBLIC_API_URL=""` for same-origin).

**Refresh data after scrape:**

```bash
make scrape
docker compose restart backend
```

---

## 5. AWS dev candidate (`envs/dev`)

Provisions the v2 stack with a **CloudFront URL** (no custom domain by default). Same modules as prod; different defaults — see [toggle table](#feature-toggles-dev-vs-prod) below.

### Prerequisites

- Terraform ≥ 1.5, AWS CLI configured
- Node.js 18+ (frontend static build)
- For Lambda APIs: `./infra/scripts/package_lambdas.sh` (or `make tf-package` — runs automatically before `make tf-apply`)

### 5.1 Provision infrastructure

```bash
cd infra/terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
# optional: cp backend.hcl.example backend.hcl

make tf-plan TF_ENV=dev      # from repo root — packages Lambdas + plan
make tf-apply TF_ENV=dev     # apply
make tf-output TF_ENV=dev    # CloudFront URL, API Gateway URL, buckets, etc.
```

Or manually:

```bash
./infra/scripts/package_lambdas.sh
cd infra/terraform/envs/dev && terraform init && terraform apply
```

Key outputs: `cloudfront_url`, `site_url`, `api_gateway_url`, `data_bucket_name`, `dynamodb_table_name`, `cors_origin_hint`.

CI: **Actions → Terraform dev → Run workflow** (`terraform.yml`).

### 5.2 Publish data

```bash
ATWC26_S3_BUCKET="$(terraform -chdir=infra/terraform/envs/dev output -raw data_bucket_name)" \
ATWC26_DYNAMODB_TABLE="$(terraform -chdir=infra/terraform/envs/dev output -raw dynamodb_table_name)" \
  make etl-publish
```

Requires AWS credentials or `ATWC26_AWS_ROLE_ARN` (after `enable_github_oidc=true`). See [specs/PRODUCTION_SPEC.md](../specs/PRODUCTION_SPEC.md) Part 1.

### 5.3 Build & deploy frontend

```bash
# Auto-detects API mode from Terraform outputs (site_url → same-origin, else API Gateway URLs):
./infra/scripts/build_frontend_static.sh

# Or via Makefile (split local defaults):
make build-frontend-static-v2

ATWC26_TF_DIR=infra/terraform/envs/dev ./infra/scripts/deploy_frontend_from_tf.sh
```

See [§8 Frontend build modes](#8-frontend-build-modes).

**Pre-cutover / v1 API cross-origin:** if the static bundle still targets the v1 monolith, add `terraform output cors_origin_hint` to **`ATWC26_CORS_ORIGINS`** on the v1 host and build with:

```bash
NEXT_PUBLIC_API_URL="$(terraform -chdir=infra/terraform/envs/dev output -raw backend_api_url)" \
  ./infra/scripts/build_frontend_static.sh
```

### 5.4 Smoke-test

```bash
CF="$(terraform -chdir=infra/terraform/envs/dev output -raw cloudfront_url)"
curl -fsS "$CF/" >/dev/null
curl -fsS "$CF/api/health"
curl -fsS "$CF/api/standings" | head -c 200
```

More checks: [TESTING.md §7](TESTING.md#7-route-split--cache-validation-v2-target).

### 5.5 Optional features (dev)

Enable in `terraform.tfvars`, then `terraform apply`:

| Toggle | Default (dev) | Effect |
|--------|---------------|--------|
| `enable_github_oidc` | `false` | GitHub Actions OIDC role → `ATWC26_AWS_ROLE_ARN` |
| `enable_etl_scheduler` | `false` | EventBridge + Lambda → `etl.yml` dispatch |
| `enable_ecs_compute` | `false` | Route `POST /api/predict` to ECS/ALB instead of predict Lambda |

When `enable_ecs_compute=true` and `build_ecs_image=true` (default), `terraform apply` also docker-builds and pushes the predict image to ECR.

Scheduler detail: [etl/SCHEDULER.md](../etl/SCHEDULER.md). Bootstrap order: [specs/PRODUCTION_SPEC.md](../specs/PRODUCTION_SPEC.md).

### Feature toggles (dev vs prod)

| Toggle | `envs/dev` default | `envs/prod` default |
|--------|-------------------|---------------------|
| `enable_github_oidc` | `false` | `true` |
| `enable_etl_scheduler` | `false` | `false` |
| `enable_ecs_compute` | `false` | `false` |
| Custom domain (ACM + Route 53) | off (`aliases = []`) | on (`enable_custom_domain = true`) |

Prod also defaults `github_org` / `github_repo` to `madmmas` / `atwc26_v2` (dev tfvars still default to `neunov` / `AnalyseThisWC26` — override in `terraform.tfvars` for your fork).

Full variable tables: [`infra/README.md`](../../infra/README.md).

---

## 6. AWS prod (`envs/prod`)

Provisions v2 APIs + static frontend on **`atwc26.com`** / **`www`** with ACM (us-east-1) and Route 53 alias records.

### 6.1 Configure & apply

```bash
cd infra/terraform/envs/prod
cp terraform.tfvars.example terraform.tfvars
cp backend.hcl.example backend.hcl   # state key: atwc26-v2/prod/terraform.tfstate
# edit terraform.tfvars (github_dispatch_token when enabling scheduler, etc.)
```

**Import existing DNS** before first apply if apex/www A records already exist — [infra/terraform/envs/prod/IMPORT.md](../../infra/terraform/envs/prod/IMPORT.md).

```bash
make tf-plan TF_ENV=prod
make tf-apply TF_ENV=prod
```

CI: **Actions → Terraform prod → Run workflow** (`terraform-prod.yml`) — requires GitHub `production` environment + `ATWC26_TFVARS_PROD` secret.

### 6.2 Publish data & deploy frontend

```bash
ATWC26_S3_BUCKET="$(terraform -chdir=infra/terraform/envs/prod output -raw data_bucket_name)" \
ATWC26_DYNAMODB_TABLE="$(terraform -chdir=infra/terraform/envs/prod output -raw dynamodb_table_name)" \
  make etl-publish

ATWC26_TF_DIR=infra/terraform/envs/prod ./infra/scripts/build_frontend_static.sh
ATWC26_TF_DIR=infra/terraform/envs/prod ./infra/scripts/deploy_frontend_from_tf.sh
```

After cutover, `build_frontend_static.sh` auto-sets `NEXT_PUBLIC_SAME_ORIGIN_API=true` when `site_url` is available (browser calls `/api/*` via CloudFront — no CORS to a separate API host). CI uses the same flag in [`deploy-frontend.yml`](../../.github/workflows/deploy-frontend.yml).

### 6.3 Go-live

Run the checklist in [CUTOVER.md](CUTOVER.md) (k6 A/B, contract tests, edge routing verification) before switching production traffic.

---

## 7. v2 edge routing (reference)

```
Browser ──HTTPS──▶ CloudFront (no WAF in this phase)
                      ├─ default behavior ──▶ S3 (Next.js static export)
                      └─ /api/* behavior ──▶ API Gateway HTTP API
                                              ├─ $default ──▶ analytics Lambda
                                              ├─ GET /api/predict/health ──▶ predict (Lambda or ECS)
                                              └─ POST /api/predict ──▶ predict Lambda (default)
                                                                   or ECS/ALB (enable_ecs_compute=true)
```

**Route ownership**

| Path | Service | Notes |
|------|---------|-------|
| `GET /api/health`, overview, teams, players, matches, standings, bracket, leaderboard, **winner-probabilities** | **analytics Lambda** | Precomputed JSON / DynamoDB API cache |
| `POST /api/predict`, `GET /api/predict/health` | **predict Lambda** (default) or **ECS Fargate** | Toggle via `enable_ecs_compute` |

CloudFront does **not** proxy `/api/*` to the v1 monolith. Pre-cutover static builds may call v1 **cross-origin** via `NEXT_PUBLIC_API_URL`; post-cutover builds use same-origin `/api/*` through CloudFront.

Diagram: [ARCHITECTURE.md §4](../ARCHITECTURE.md#4-aws-deployment-architecture).

---

## 8. Frontend build modes

`./infra/scripts/build_frontend_static.sh` writes `frontend/out/` for S3 upload.

| Mode | When | Env vars | Browser calls |
|------|------|----------|---------------|
| **v1 monolith cross-origin** | Pre-cutover candidate on CloudFront URL | `NEXT_PUBLIC_API_URL=https://atwc26.com` | v1 API directly (CORS required on v1) |
| **v2 split APIs** | Local dev or direct API Gateway debugging | `NEXT_PUBLIC_ANALYTICS_API_URL`, `NEXT_PUBLIC_PREDICT_API_URL` | Two API bases |
| **v2 same-origin (target)** | After cutover / when `site_url` output exists | `NEXT_PUBLIC_SAME_ORIGIN_API=true` (auto when Terraform `site_url` is set) | `https://<cloudfront-or-domain>/api/*` |

```bash
# v1 monolith API (default when no Terraform context):
./infra/scripts/build_frontend_static.sh

# Split APIs (local):
make build-frontend-static-v2

# Same-origin v2 (typical post-apply prod/dev with unified site_url):
ATWC26_TF_DIR=infra/terraform/envs/dev ./infra/scripts/build_frontend_static.sh

# Manual deploy:
export ATWC26_FRONTEND_BUCKET=...
export ATWC26_CLOUDFRONT_DISTRIBUTION_ID=...
./infra/scripts/deploy_frontend.sh
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `https://atwc26.com` | v1 monolith API baked into bundle |
| `NEXT_PUBLIC_ANALYTICS_API_URL` | — | v2 analytics base |
| `NEXT_PUBLIC_PREDICT_API_URL` | — | v2 predict base |
| `NEXT_PUBLIC_SAME_ORIGIN_API` | auto from `site_url` | Relative `/api/*` via CloudFront |
| `ATWC26_TF_DIR` | `infra/terraform/envs/dev` | Terraform env for output auto-detect |
| `ATWC26_FRONTEND_BUCKET` | — | Required for `deploy_frontend.sh` |
| `ATWC26_CLOUDFRONT_DISTRIBUTION_ID` | — | Optional invalidation after S3 sync |

Docker Compose continues to use `output: "standalone"` — static export is a separate path for AWS.

**Preview static build locally:** `make serve-frontend-static` or `npx serve frontend/out`.

---

## 9. Environment variables

### v1 monolith (`backend/`)

| Var | Default | Purpose |
|-----|---------|---------|
| `ATWC26_DATA_DIR` | `../data` | Parquet dataset directory |
| `ATWC26_CORS_ORIGINS` | `localhost:3000` | Comma-separated allowed origins |
| `WEB_CONCURRENCY` | `4` | Gunicorn/Uvicorn workers (Docker prod) |

### v2 split services (`services/`)

| Var | Default | Purpose |
|-----|---------|---------|
| `ATWC26_S3_BUCKET` | — | ETL artifact bucket (AWS runtime) |
| `ATWC26_DYNAMODB_TABLE` | — | Manifest + API cache table |
| `ATWC26_DATA_VERSION` | — | Bumped by ETL publish to warm Lambda/ECS |
| `ATWC26_CORS_ORIGINS` | `*` in dev Makefile targets | Allowed browser origins |

### Frontend

| Var | Default | Purpose |
|-----|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | v1 monolith API; `""` for same-origin behind Nginx |
| `NEXT_OUTPUT_MODE` | `export` (static script) / `standalone` (Docker) | Next.js output mode |

GitHub Actions: [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) (what/when). Secrets catalog: [`infra/README.md` § GitHub secrets](../../infra/README.md#github-secrets--vars-issue-9).

---

## 10. Security checklist

**v1 Docker / VM**

- [x] Backend non-root; data mounted read-only
- [x] Nginx security headers + rate limiting on `/api`
- [x] CORS locked to known origins
- [ ] TLS + HSTS at proxy or load balancer

**v2 AWS candidate**

- [x] S3 frontend bucket private (CloudFront OAC only)
- [x] CloudFront + TLS **without WAF** in this phase (by design)
- [ ] Enable GitHub OIDC (`enable_github_oidc`) — prefer over long-lived AWS keys in GHA
- [ ] Rotate `github_dispatch_token` (Secrets Manager) if scheduler enabled
- [ ] Pin and scan container images (`docker scout` / Trivy) before ECS deploy

---

## 11. Health & observability

| Stack | Endpoint | Notes |
|-------|----------|-------|
| v1 monolith | `GET /api/health` | Dataset counts in one service |
| v2 analytics | `GET /api/health` on analytics origin | Read API readiness |
| v2 predict | `GET /api/health` or `GET /api/predict/health` | Model availability |
| v2 via CloudFront | `GET /api/health` | Hits analytics (`$default` route) |

Gunicorn/Uvicorn logs go to stdout (Docker / ECS). Optional: `prometheus-fastapi-instrumentator`.

---

## 12. Scaling notes

**v1 monolith:** vertical (`WEB_CONCURRENCY`) or horizontal replicas behind Nginx — each holds an in-memory copy of aggregates (~tens of MB).

**v2 AWS:**

- **Frontend:** static on S3 + CloudFront — scales with CDN.
- **Analytics Lambda:** read-heavy; DynamoDB API cache reduces cold-path compute; scales with Lambda concurrency.
- **Predict:** CPU-bound; default **Lambda** scales per invoke; optional **ECS** behind ALB for longer runs / more memory (`enable_ecs_compute=true`).
- **ETL:** GitHub Actions worker; AWS scheduler dispatches — not user-facing scale path.

---

## 13. Alternative hosting (non-AWS)

For experiments outside the v2 Terraform path:

| Option | Frontend | Backend | Notes |
|--------|----------|---------|-------|
| Managed PaaS | Vercel / Netlify | Render / Railway / Fly.io | Set `NEXT_PUBLIC_API_URL` to backend URL |
| Single VM | Docker Compose | same | `docker compose up -d` + Let's Encrypt on Nginx |
| Kubernetes | Deployment + Service | Deployment + HPA | Readiness: `GET /api/health` |

The **target production path** for WC26 is AWS v2 (§5–§6), not generic PaaS.
