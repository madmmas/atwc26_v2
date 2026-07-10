# AnalyseThisWC26 v2 — Architecture (C4 model + AWS deployment)

System-wide architecture for the ATWC26 v2 candidate stack: C4 context/container/component views plus a full AWS deployment map. For operational detail, follow the links below rather than duplicating runbooks here.

| Doc | Read when… |
|-----|------------|
| **[etl/OVERVIEW.md](etl/OVERVIEW.md)** | ETL cross-boundary contract, scheduler ↔ pipeline handoff |
| **[etl/SCHEDULER.md](etl/SCHEDULER.md)** | EventBridge/Lambda dispatch, trigger windows, DynamoDB dedup |
| **[etl/PIPELINE.md](etl/PIPELINE.md)** | `etl.yml` steps, scrape → publish, fingerprints |
| **[ops/DEPLOY.md](ops/DEPLOY.md)** | How to build and deploy (Docker, AWS, frontend) |
| **[ops/CUTOVER.md](ops/CUTOVER.md)** | v1 → v2 production cutover checklist |
| **[specs/PRODUCTION_SPEC.md](specs/PRODUCTION_SPEC.md)** | Production toggles, secrets, enablement order |
| **[`infra/README.md`](../infra/README.md)** | Terraform modules, outputs, GitHub Actions wiring |

**Sources:** `infra/terraform/**`, `.github/workflows/` (`ci.yml`, `etl.yml`, `terraform.yml`, `terraform-prod.yml`, `deploy-frontend.yml`), `services/`, `etl/`, `packages/atwc26_core/`.

> **Diagram colors.** §4 extends the AWS-service palette used in [etl/SCHEDULER.md](etl/SCHEDULER.md) (compute, storage, database, security, integration, logs) with additional **edge** (purple) classes for Route 53, CloudFront, and API Gateway.

---

## Table of Contents

1. [C4 Model — Level 1: System Context](#1-c4-model--level-1-system-context)
2. [C4 Model — Level 2: Container Diagram](#2-c4-model--level-2-container-diagram)
3. [C4 Model — Level 3: Component Diagram (ETL Pipeline)](#3-c4-model--level-3-component-diagram-etl-pipeline)
4. [AWS Deployment Architecture](#4-aws-deployment-architecture)
5. [Source map](#source-map)

---

## 1. C4 Model — Level 1: System Context

```mermaid
C4Context
    title System Context — AnalyseThisWC26 (ATWC26 v2)

    Person(fan, "Fan", "Explores WC26 player/team stats, builds two custom XIs, gets a match prediction")
    Person(operator, "Maintainer / Operator", "Runs Terraform, manages GitHub secrets/tfvars, triggers manual ETL runs")

    System(atwc26, "ATWC26 v2", "FIFA World Cup 2026 analytics + AI match predictor: static frontend, split read/compute APIs, serverless ETL")

    System_Ext(espn, "ESPN APIs", "Scoreboard / summary / roster / standings JSON — the only external data source")
    System_Ext(ghactions, "GitHub Actions", "CI/CD + ETL worker runtime: ci.yml, etl.yml, terraform.yml, terraform-prod.yml, deploy-frontend.yml")
    System_Ext(v1, "atwc26.com — v1 monolith", "Existing production stack (Nginx + FastAPI + Next.js). v2 runs as a parallel candidate until Issue 10 cutover")

    Rel(fan, atwc26, "Views stats, submits predictions", "HTTPS")
    Rel(ghactions, espn, "Scrapes fixtures & stats")
    Rel(operator, ghactions, "Dispatches workflows, sets secrets / tfvars")
    Rel(ghactions, atwc26, "Builds, tests, packages Lambdas, applies Terraform, publishes data, deploys frontend")
```

**Reading this:** the fan only ever talks to the v2 system over HTTPS. Everything else — scraping ESPN, building/testing/deploying, applying infrastructure — is GitHub Actions acting as the system's CI/CD and ETL runtime.

The v1 monolith (`atwc26.com`) is a separate existing system that v2 is meant to eventually replace ([ops/CUTOVER.md](ops/CUTOVER.md)). **Pre-cutover**, the static frontend may call the v1 API **cross-origin** via `NEXT_PUBLIC_API_URL` / `backend_api_url` baked at build time — CloudFront does **not** proxy `/api/*` to v1; it routes `/api/*` to v2 API Gateway. After cutover, the frontend uses same-origin `/api` via CloudFront ([ops/DEPLOY.md](ops/DEPLOY.md), [`infra/README.md`](../infra/README.md)).

---

## 2. C4 Model — Level 2: Container Diagram

```mermaid
C4Container
    title Container Diagram — ATWC26 v2 (AWS candidate stack)

    Person(fan, "Fan", "Browser user")

    System_Boundary(atwc26, "ATWC26 v2") {
        Container(frontend, "Static Frontend", "Next.js 14, static export", "Overview / Explore / Predict / Standings — build-time env vars set API base URL(s)")
        Container(cdn, "CloudFront + API Gateway", "CDN (OAC) + HTTP API", "Single public origin: default behavior → S3, /api/* behavior → API Gateway")
        Container(analytics, "Analytics API", "AWS Lambda, Python 3.11 / FastAPI, arm64", "Read endpoints: health, overview, teams, players, matches, standings, bracket, leaderboard, winner-probabilities")
        Container(predict, "Predict API", "AWS Lambda (default) or ECS Fargate + ALB (enable_ecs_compute=true)", "POST /api/predict — Poisson / XGBoost compute, CPU-bound")
        ContainerDb(datastore, "Data Bucket", "Amazon S3", "Published parquet/JSON artifacts — single source of truth for both APIs")
        ContainerDb(manifest, "Manifest & Cache Table", "Amazon DynamoDB, single table", "Publish manifest, precomputed API-response cache, ETL trigger dedup state")
        Container(scheduler, "ETL Scheduler", "Amazon EventBridge + AWS Lambda", "Polls schedule.json every 5 min; dispatches ETL once a match is confirmed complete on ESPN")
        Container(etl, "ETL Pipeline", "GitHub Actions (.github/workflows/etl.yml)", "Scrape → transform → simulate/train → QA → publish")
    }

    System_Ext(espn, "ESPN APIs", "Data source")
    System_Ext(gha_cicd, "GitHub Actions — CI/CD", "ci.yml, terraform.yml, terraform-prod.yml, deploy-frontend.yml")
    System_Ext(v1, "atwc26.com — v1 monolith", "Pre-cutover API target for static frontend")

    Rel(fan, cdn, "HTTPS")
    Rel(cdn, frontend, "Serves static assets", "S3 origin via OAC")
    Rel(cdn, analytics, "GET /api/* via API Gateway ($default route)", "HTTPS")
    Rel(cdn, predict, "POST /api/predict, GET /api/predict/health via API Gateway", "HTTPS")
    Rel(frontend, v1, "Pre-cutover: may call v1 API cross-origin", "HTTPS")
    Rel(analytics, datastore, "Reads artifacts (S3 sync via manifest)")
    Rel(analytics, manifest, "Reads precomputed API cache")
    Rel(predict, datastore, "Reads artifacts (S3 sync via manifest)")
    Rel(predict, manifest, "Reads publish manifest (LATEST)")
    Rel(scheduler, manifest, "Reads/writes trigger dedup state")
    Rel(scheduler, etl, "POST workflow_dispatch", "GitHub REST API")
    Rel(etl, espn, "Scrapes fixtures & stats")
    Rel(etl, datastore, "Publishes changed artifacts (sha256-gated)")
    Rel(etl, manifest, "Publishes manifest + precomputed API cache")
    Rel(etl, predict, "Bumps data version / rolling ECS deploy + /reload")
    Rel(etl, analytics, "Bumps ATWC26_DATA_VERSION")
    Rel(gha_cicd, cdn, "Provisions via Terraform — infra/terraform/envs/dev and envs/prod")
    Rel(gha_cicd, frontend, "Builds static export, syncs to S3, invalidates CloudFront")
```

**Reading this:** the API is deliberately split by workload shape — `analytics` is read-heavy and stateless (Lambda is a natural fit), `predict` is CPU-bound and can outgrow a Lambda's timeout/memory envelope, so the stack lets you flip it onto Fargate behind an ALB without changing the route contract. Both compute containers share one S3 bucket and one DynamoDB table as their only shared state. API cache rows are **written by ETL publish**; analytics **reads** them at request time (with in-memory fallback compute). Predict reads the **publish manifest** to know which S3 artifacts to sync — it does not use the API response cache.

---

## 3. C4 Model — Level 3: Component Diagram (ETL Pipeline)

This level maps `.github/workflows/etl.yml` and the `etl/` package. For step-by-step workflow detail, see [etl/PIPELINE.md](etl/PIPELINE.md). For the AWS scheduler that dispatches the workflow, see [etl/SCHEDULER.md](etl/SCHEDULER.md).

```mermaid
C4Component
    title Component Diagram — ETL Pipeline (.github/workflows/etl.yml)

    Container_Boundary(etlpipeline, "ETL Pipeline — GitHub Actions runner") {
        Component(changed, "etl.changed", "Python module", "Fingerprint compare, trigger dedup, scrape-state restore/save — detect.py, store.py, triggers.py")
        Component(scrape, "etl.scrape", "Python scripts", "fetch_schedule, scrape_wc26, scrape_squads, fetch_groups")
        Component(transform, "etl.transform", "Python module", "Profiles, manifest, match events — run.py, profiles.py; invokes etl/build_match_events.py")
        Component(simulate, "etl.simulate", "Python module", "Monte Carlo (1,000 trials in CI) winner probabilities + bracket path")
        Component(train, "etl.train", "Python module", "Elo, Dixon-Coles, XGBoost model training")
        Component(qa, "etl.qa", "Python module", "Validates artifacts + DataStore load — checks.py")
        Component(publish, "etl.publish", "Python module", "S3 upload, DynamoDB manifest/cache, compute refresh — publish.py, refresh.py, api_cache.py")
        Component(core, "atwc26_core", "Shared package", "DataStore, artifact registry, tournament/prediction logic — packages/atwc26_core")
    }

    System_Ext(espn, "ESPN APIs", "Scoreboard / summary / roster JSON")
    ContainerDb(s3, "S3 Data Bucket", "Amazon S3")
    ContainerDb(ddb, "DynamoDB", "Manifest + cache + trigger table")
    Container(lam, "Analytics / Predict Lambdas", "AWS Lambda")
    Container(ecs, "Predict ECS Service", "AWS Fargate (optional)")

    Rel(changed, ddb, "check-trigger / restore-state / load-remote fingerprint")
    Rel(scrape, espn, "HTTP GET")
    Rel(scrape, core, "Writes data/*.parquet, data/*.json")
    Rel(transform, core, "Reads raw artifacts, writes profiles + manifest + match_events.json")
    Rel(simulate, core, "Reads features, writes winner_probabilities.json / bracket_predictions.json")
    Rel(train, core, "Writes elo_ratings.json, dc_params.json, xgb_model.ubj")
    Rel(qa, core, "Validates artifacts + DataStore load")
    Rel(publish, s3, "Uploads changed artifacts, sha256-gated against DynamoDB LATEST")
    Rel(publish, ddb, "PutItem: manifest, API cache rows, {game_id}#DONE trigger markers")
    Rel(publish, lam, "update_function_configuration — bumps ATWC26_DATA_VERSION")
    Rel(publish, ecs, "force-new-deployment + POST /api/predict/reload (when enable_ecs_compute=true)")
```

**Reading this:** `etl.changed` is the gatekeeper on both ends — it can skip an entire GHA run if the scheduler already marked a game `#DONE`, and it can skip transform/publish if ESPN's data hasn't actually changed since the fingerprint was last saved. Everything downstream of `publish` is idempotent (S3 uploads and Lambda/ECS refreshes only fire when a SHA-256 actually differs).

---

## 4. AWS Deployment Architecture

Full-stack AWS map. The ETL scheduler slice is expanded operationally in [etl/SCHEDULER.md](etl/SCHEDULER.md); Terraform module wiring is in [`infra/README.md`](../infra/README.md).

```mermaid
flowchart TB
    classDef edge fill:#8C4FFF,stroke:#232F3E,color:#fff
    classDef compute fill:#FF9900,stroke:#232F3E,color:#fff
    classDef storage fill:#569A31,stroke:#232F3E,color:#fff
    classDef database fill:#4053D6,stroke:#232F3E,color:#fff
    classDef security fill:#DD344C,stroke:#232F3E,color:#fff
    classDef integration fill:#E7157B,stroke:#232F3E,color:#fff
    classDef monitor fill:#FF4F8B,stroke:#232F3E,color:#fff
    classDef external fill:#6B7280,stroke:#232F3E,color:#fff

    FAN["Fan / Browser"]:::external
    ESPN["ESPN APIs"]:::external
    GH["GitHub Actions<br/>ci.yml · etl.yml · terraform.yml<br/>terraform-prod.yml · deploy-frontend.yml"]:::external

    subgraph EDGE["Edge & DNS — envs/prod only for custom domain"]
        R53["Route 53<br/>atwc26.com / www A+AAAA alias"]:::edge
        ACM["ACM Certificate (us-east-1)<br/>DNS-validated"]:::security
        CF["CloudFront Distribution<br/>OAC · pretty-urls function<br/>no WAF (v2 scope)"]:::edge
    end

    subgraph FRONTEND["Static Frontend — module: frontend-cdn"]
        S3F["S3 — frontend bucket<br/>Next.js static export<br/>private, OAC-only access"]:::storage
    end

    subgraph APILAYER["API Layer — module: api-gateway"]
        APIGW["API Gateway HTTP API<br/>$default → analytics<br/>POST /api/predict → predict<br/>GET /api/predict/health → predict"]:::edge
    end

    subgraph COMPUTE["Compute"]
        LAM_A["Lambda: analytics<br/>module: lambda-analytics<br/>python3.11 · arm64"]:::compute
        LAM_P["Lambda: predict (default path)<br/>module: lambda-predict<br/>route inactive when enable_ecs_compute=true"]:::compute
        subgraph ECSVPC["Default VPC — module: ecs-compute (optional, enable_ecs_compute=true)"]
            ALB["ALB :80 → :8000<br/>health check /api/health"]:::compute
            ECS["ECS Fargate service: predict<br/>FastAPI, health-check grace 300s"]:::compute
        end
        ECR["ECR repo: predict<br/>content-hash tagged<br/>module: ecs-predict-image"]:::compute
    end

    subgraph DATA["Data Layer"]
        S3D["S3 — data bucket<br/>module: s3-data<br/>parquet/json artifacts"]:::storage
        DDB["DynamoDB — single table<br/>module: dynamodb<br/>manifest + API cache + ETL trigger state"]:::database
    end

    subgraph SCHED["ETL Scheduler — module: etl-scheduler (optional, enable_etl_scheduler=true)"]
        EB["EventBridge rule<br/>cron(*/5 * * * ? *)"]:::integration
        LAM_D["Lambda: etl-dispatch"]:::compute
        SM["Secrets Manager<br/>GitHub PAT (actions:write)"]:::security
        LOGS["CloudWatch Logs<br/>14-day retention"]:::monitor
    end

    subgraph IAMOIDC["IAM — module: github-oidc (optional, enable_github_oidc)"]
        OIDC["OIDC provider: token.actions.githubusercontent.com<br/>+ github-actions role (PowerUserAccess-scoped)"]:::security
    end

    FAN -->|HTTPS| CF
    R53 -->|alias A/AAAA| CF
    ACM -. attaches cert .-> CF
    CF -->|default behavior| S3F
    CF -->|"/api/* behavior, origin-request policy"| APIGW

    APIGW -->|"$default route, AWS_PROXY"| LAM_A
    APIGW -->|"POST /api/predict, AWS_PROXY (enable_ecs_compute=false)"| LAM_P
    APIGW -.->|"POST /api/predict, HTTP_PROXY (enable_ecs_compute=true)"| ALB
    ALB --> ECS
    ECS -.->|pulls content-hash tagged image| ECR

    LAM_A -->|GetObject/ListBucket| S3D
    LAM_A -->|Get/Query/Scan| DDB
    LAM_P -->|GetObject/ListBucket| S3D
    LAM_P -->|Get/Query/Scan| DDB
    ECS -->|GetObject/ListBucket| S3D
    ECS -->|GetItem/Query| DDB

    EB -->|invoke every 5 min| LAM_D
    LAM_D -->|GetObject data/schedule.json| S3D
    LAM_D -->|Get/PutItem ETL_TRIGGER#wc26| DDB
    LAM_D -->|GetSecretValue| SM
    LAM_D -.->|completion probe| ESPN
    LAM_D -->|POST workflow_dispatch etl.yml| GH
    LAM_D --> LOGS

    GH -->|scrape| ESPN
    GH -->|AssumeRoleWithWebIdentity| OIDC
    GH -->|publish artifacts, sha256-gated| S3D
    GH -->|publish manifest + API cache + DONE markers| DDB
    GH -->|update_function_configuration| LAM_A
    GH -.->|"update_function_configuration (enable_ecs_compute=false)"| LAM_P
    GH -.->|"force-new-deployment + POST /reload (enable_ecs_compute=true)"| ECS
    GH -.->|"docker build + push (enable_ecs_compute=true, build_ecs_image=true)"| ECR
    GH -->|build static export, S3 sync| S3F
    GH -.->|CloudFront invalidation| CF
```

**Legend**

| Color | AWS category | Services in this diagram |
|---|---|---|
| Purple `#8C4FFF` | Networking & content delivery | Route 53, CloudFront, API Gateway |
| Orange `#FF9900` | Compute | Lambda ×3, ALB, ECS Fargate, ECR |
| Green `#569A31` | Storage | S3 (frontend bucket, data bucket) |
| Blue `#4053D6` | Database | DynamoDB |
| Red `#DD344C` | Security, identity & compliance | ACM, Secrets Manager, IAM/OIDC |
| Pink `#E7157B` | Application integration | EventBridge |
| Magenta `#FF4F8B` | Management & governance | CloudWatch Logs |
| Gray `#6B7280` | External | Browser, ESPN, GitHub Actions |

**Key deployment facts** (confirmed in `infra/terraform/**`):

- The predict route is a **runtime toggle, not two parallel paths**: `enable_ecs_compute` (default `false`) decides whether `POST /api/predict` hits `lambda-predict` or the ECS/ALB path — API Gateway swaps the integration with `create_before_destroy` so the route survives the switch.
- **Feature toggles differ by environment** (`infra/terraform/envs/dev/variables.tf` vs `envs/prod/variables.tf`):

  | Toggle | `envs/dev` default | `envs/prod` default |
  |--------|-------------------|---------------------|
  | `enable_github_oidc` | `false` | `true` |
  | `enable_etl_scheduler` | `false` | `false` |
  | `enable_ecs_compute` | `false` | `false` |

  A fresh **dev** `terraform apply` provisions the data/API/CDN stack but not the OIDC role or AWS-side ETL scheduler until explicitly turned on. See [specs/PRODUCTION_SPEC.md](specs/PRODUCTION_SPEC.md) Part 1 for enablement order.

- **GitHub OIDC trust** defaults also differ: dev tfvars default to `github_org = "neunov"` / `github_repo = "AnalyseThisWC26"`; prod defaults to `madmmas` / `atwc26_v2`. Override in `terraform.tfvars` for your fork.
- `envs/prod` adds **ACM (us-east-1) + Route 53 alias records** for `atwc26.com`/`www` on top of the same module set `envs/dev` uses — `envs/dev` has no custom domain by default.
- CloudFront intentionally ships **without WAF** in this phase (CDN + TLS only) — called out in [`infra/README.md`](../infra/README.md).
- **ECS image builds** (only when `enable_ecs_compute=true` and `build_ecs_image=true`): `ecs-predict-image` hashes `services/predict_api/`, `services/shared/`, and `packages/atwc26_core/atwc26_core/`, then `terraform apply` runs `docker build && push` via `local-exec`. The default predict path is Lambda and needs no ECR image. `deploy-predict-ecs` in `terraform.yml` exists for image-only redeploys without a full apply.

---

## Source map

| Diagram element | Source file(s) |
|---|---|
| Frontend / CDN | `infra/terraform/modules/frontend-cdn/main.tf`, [`infra/README.md`](../infra/README.md) |
| API Gateway routing | `infra/terraform/modules/api-gateway/main.tf` |
| Analytics / Predict Lambdas | `infra/terraform/modules/lambda-analytics/main.tf`, `infra/terraform/modules/lambda-predict/main.tf` |
| ECS Fargate + ALB | `infra/terraform/modules/ecs-compute/main.tf` |
| ECR content-hash build | `infra/terraform/modules/ecs-predict-image/main.tf` |
| S3 data + DynamoDB | `infra/terraform/modules/s3-data/main.tf`, `infra/terraform/modules/dynamodb/main.tf` |
| ETL scheduler (EventBridge/Lambda/Secrets) | `infra/terraform/modules/etl-scheduler/main.tf`, [etl/SCHEDULER.md](etl/SCHEDULER.md) |
| ACM + Route 53 (prod) | `infra/terraform/modules/acm-certificate/main.tf`, `infra/terraform/envs/prod/dns.tf` |
| GitHub OIDC role | `infra/terraform/modules/github-oidc/main.tf` |
| ETL GitHub Action | `.github/workflows/etl.yml`, [`etl/README.md`](../etl/README.md), [etl/PIPELINE.md](etl/PIPELINE.md) |
| CI / Terraform / deploy workflows | `.github/workflows/ci.yml`, `terraform.yml`, `terraform-prod.yml`, `deploy-frontend.yml` |
| Env toggles & defaults | `infra/terraform/envs/dev/variables.tf`, `infra/terraform/envs/prod/variables.tf` |
| System purpose / v1 vs v2 | root `README.md`, [ops/DEPLOY.md](ops/DEPLOY.md), [specs/PRODUCTION_SPEC.md](specs/PRODUCTION_SPEC.md) |
