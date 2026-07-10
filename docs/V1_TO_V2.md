# v1 → v2 transition — architecture, deployment, and rationale

Why AnalyseThisWC26 moved from a **single-server monolith** to a **split, serverless-first AWS stack**, how the two versions coexist today, and how to cut over. For live diagrams see [ARCHITECTURE.md](ARCHITECTURE.md); for runbooks see [ops/DEPLOY.md](ops/DEPLOY.md) and [ops/CUTOVER.md](ops/CUTOVER.md).

| Doc | Read when… |
|-----|------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Current v2 C4 + AWS map |
| [ops/DEPLOY.md](ops/DEPLOY.md) | How to run/deploy v1 locally vs v2 locally and on AWS |
| [ops/CUTOVER.md](ops/CUTOVER.md) | Pre-launch checklist |
| [planning/REFACTOR_ISSUES.md](planning/REFACTOR_ISSUES.md) | Issue tracker & branch strategy |
| [specs/PRODUCTION_SPEC.md](specs/PRODUCTION_SPEC.md) | First-time AWS bootstrap |

---

## Table of Contents

1. [Summary](#1-summary)
2. [v1 — what we had](#2-v1--what-we-had)
3. [v2 — what we built](#3-v2--what-we-built)
4. [Why the migration was needed](#4-why-the-migration-was-needed)
5. [Side-by-side comparison](#5-side-by-side-comparison)
6. [Deployment transition](#6-deployment-transition)
7. [Repository layout changes](#7-repository-layout-changes)
8. [Decision log (retroactive)](#8-decision-log-retroactive)
9. [Do we need formal ADRs?](#9-do-we-need-formal-adrs)

---

## 1. Summary

| | **v1** | **v2** |
|---|--------|--------|
| **Production today** | `atwc26.com` — Nginx + FastAPI monolith + Next.js | Parallel **candidate** stack (`atwc26-v2` prefix) until Issue 10 cutover |
| **API shape** | One FastAPI app (`backend/`) — reads + predict + Monte Carlo | **Analytics** (read) + **Predict** (compute) — separate deploy units |
| **Frontend** | Docker `standalone` or dev server | **Static export** → S3 + CloudFront |
| **Data refresh** | Manual scrape + restart backend | **ETL pipeline** → S3 + DynamoDB → warm Lambdas/ECS |
| **Hosting target** | VM / Docker Compose | AWS serverless + optional ECS for predict |

v1 remains the **production baseline** until k6 A/B and [ops/CUTOVER.md](ops/CUTOVER.md) pass. v2 runs as an isolated candidate (separate Terraform `name_prefix`, no collision with v1).

---

## 2. v1 — what we had

### Architecture

```
Browser ──▶ Nginx (:443)
              ├─ /     ──▶ Next.js (standalone container)
              └─ /api/* ──▶ FastAPI monolith (Gunicorn/Uvicorn)
                              └─ loads data/*.parquet at startup into RAM
```

- **Single process** serves every endpoint: overview, teams, players, standings, bracket, winner probabilities, and `POST /api/predict`.
- **DataStore** in `backend/app/data.py` loads the full parquet dataset once; all aggregates live in memory.
- **Monte Carlo** tournament simulation (`get_winner_probabilities`) ran at **API startup** — ~6s before the first user request was acceptable on a long-lived server, but expensive on cold-start serverless.
- **Prediction** (Poisson / XGBoost) shares the same process and memory footprint as read-heavy analytics.

### Deployment

| Environment | How |
|-------------|-----|
| Local | `backend/` on `:8000` + `frontend/` on `:3000` |
| Docker | `docker compose` — Nginx on `:8080`, same-origin `/api` |
| Production | Single VM or PaaS — monolith + optional CDN for static assets |

Documented in [ops/DEPLOY.md §2–4](ops/DEPLOY.md#2-local--v1-monolith).

### What worked

- Simple mental model: one repo path, one API, one deploy.
- Fast reads after warm startup (everything in RAM).
- Easy local hackability for a demo / capability project.

### What broke down at WC scale

See [§4](#4-why-the-migration-was-needed).

---

## 3. v2 — what we built

### Architecture

```
Browser ──▶ CloudFront
              ├─ default ──▶ S3 (Next.js static export)
              └─ /api/*  ──▶ API Gateway
                                ├─ $default ──▶ analytics Lambda (reads)
                                └─ POST /api/predict ──▶ predict Lambda (default)
                                                         or ECS Fargate (optional)
```

- **ETL** (GitHub Actions + optional AWS scheduler) scrapes ESPN, transforms, simulates offline, publishes to **S3** + **DynamoDB** (manifest + API response cache).
- **Analytics Lambda** serves read endpoints from precomputed cache / S3-synced artifacts — no Monte Carlo at request time.
- **Predict** handles CPU-bound `POST /api/predict` — **Lambda by default**; **ECS Fargate** when `enable_ecs_compute=true` (longer runs, more memory).
- **Shared package** `packages/atwc26_core` holds DataStore, prediction engines, artifact registry — used by ETL, both APIs, and tests.

Full diagram: [ARCHITECTURE.md](ARCHITECTURE.md).

### Deployment

| Environment | How |
|-------------|-----|
| Local v2 | `make dev-v2` — analytics `:8001`, predict `:8000`, frontend `:3000` |
| AWS dev | `infra/terraform/envs/dev` — CloudFront URL, no custom domain |
| AWS prod | `infra/terraform/envs/prod` — `atwc26.com` + ACM + Route 53 |

Documented in [ops/DEPLOY.md §3–6](ops/DEPLOY.md).

---

## 4. Why the migration was needed

These were the concrete drivers — not abstract “microservices for microservices’ sake.”

### 4.1 Coupled read and compute workloads

v1 loaded **the entire dataset** and ran **Monte Carlo warmup** in the same process that serves `GET /api/overview`. Read traffic and prediction CPU fought for the same memory and CPU envelope.

v2 **separates by workload shape**:

| Workload | v2 placement | Rationale |
|----------|--------------|-----------|
| Read-heavy GETs | Analytics Lambda + DynamoDB cache | Millisecond reads; scale with concurrency; pay per invoke |
| Monte Carlo / bracket sim | ETL `etl/simulate` in GitHub Actions | ~30s batch job when data changes — not per HTTP request |
| `POST /api/predict` | Predict Lambda (default) or ECS | Interactive UI needs predictable latency; optional ECS when Lambda limits bite |

See also [TODO.md](../TODO.md) “Compute placement (core insight).”

### 4.2 Serverless cold start vs long-lived monolith

Moving reads to Lambda is viable only if **cold start does not parse parquet or run simulation**. v2 precomputes profiles, standings cache rows, and `winner_probabilities.json` in ETL publish — Lambda reads one DynamoDB item or small JSON from S3.

The monolith pattern (“load everything at startup”) does not transplant to Lambda without redesign.

### 4.3 Static frontend on CDN

v1 Next.js `standalone` needs a **Node runtime** container. v2 uses **static export** (`frontend/out/`) on S3 + CloudFront — cheaper, globally edge-cached, no server to patch for the UI layer.

### 4.4 ETL decoupled from the serving path

v1: scrape → restart backend. No manifest, no incremental publish, no match-timed automation.

v2:

- **S3** as artifact source of truth (sha256-gated publish).
- **DynamoDB** for publish manifest, API cache, ETL trigger dedup.
- **AWS scheduler** (optional) dispatches `etl.yml` after matches complete on ESPN.
- **GitHub Actions** as ETL worker runtime (no always-on scraper VM).

### 4.5 Cost and ops for a tournament spike

World Cup traffic is **bursty** (match days, predictor engagement) not steady-state SaaS. Serverless reads + static CDN align cost with usage. A single oversized VM running 24/7 for six weeks of peak interest is poor fit.

**Explicit non-goal in this phase:** CloudFront **without WAF** — CDN + TLS only; WAF deferred to reduce scope ([infra/README.md](../infra/README.md)).

### 4.6 Safe parallel migration

v2 uses `name_prefix = atwc26-v2` so candidate infrastructure never collides with production v1. Frontend can target v1 API cross-origin during development, then switch to same-origin `/api/*` through CloudFront at cutover ([ops/DEPLOY.md §8](ops/DEPLOY.md#8-frontend-build-modes)).

---

## 5. Side-by-side comparison

### Architecture

| Concern | v1 | v2 |
|---------|----|----|
| API processes | 1 (`backend/`) | 2 (`services/analytics_api`, `services/predict_api`) |
| Shared logic | In `backend/app/` | `packages/atwc26_core` |
| Winner probabilities | Computed at startup (MC) | Precomputed in ETL → analytics read |
| Data on serve path | Local parquet | S3 + DynamoDB manifest/cache |
| Edge | Nginx | CloudFront + API Gateway |
| ETL trigger | Manual | EventBridge → Lambda → `workflow_dispatch` (optional) + manual |

### Deployment

| Concern | v1 | v2 |
|---------|----|----|
| Local quick start | `uvicorn` + `npm run dev` | `make dev-v2` or v1 path still supported |
| Container prod | `docker compose` | Not the target path |
| AWS entry | None in repo | `make tf-apply TF_ENV=dev\|prod` |
| Frontend deploy | Rebuild container | `build_frontend_static.sh` → S3 sync |
| CI/CD | Basic tests | Path-filtered CI + Terraform + ETL + deploy workflows |
| Secrets | Env vars on host | GitHub OIDC → IAM role (preferred) |

### API routes (high level)

| Route | v1 | v2 |
|-------|----|----|
| `GET /api/*` (reads) | Monolith | Analytics Lambda |
| `GET /api/winner-probabilities` | Monolith (MC) | Analytics (precomputed) |
| `POST /api/predict` | Monolith | Predict Lambda or ECS |

Contract tests: `make test-contract` · [ops/TESTING.md §12](ops/TESTING.md#12-local-v2-e2e-smoke-path).

---

## 6. Deployment transition

Phases operators actually follow:

```text
1. v1 serves atwc26.com (unchanged on main production path)
2. Provision v2 candidate: terraform apply envs/dev (or prod with separate testing)
3. etl-publish → S3/DynamoDB; verify Lambdas serve fresh data
4. Build frontend:
     pre-cutover: NEXT_PUBLIC_API_URL → v1 (cross-origin + CORS)
     candidate:   split API Gateway URLs or same-origin when site_url exists
5. k6 A/B: v1 baseline vs v2 candidate ([ops/CUTOVER.md](ops/CUTOVER.md))
6. Cutover: DNS/CloudFront → v2, NEXT_PUBLIC_SAME_ORIGIN_API=true, disable v1 origin
7. Issue 10: merge refactor/v2-integration → main; retire v1 monolith deploy
```

**Do not** point CloudFront `/api/*` at the v1 monolith — v2 edge always forwards API traffic to API Gateway ([ARCHITECTURE.md](ARCHITECTURE.md)).

---

## 7. Repository layout changes

| v1 | v2 addition / change |
|----|----------------------|
| `backend/` | Kept for v1; v2 APIs in `services/analytics_api`, `services/predict_api` |
| `frontend/` | Same UI; static export path for AWS |
| `etl/scrape/` | Full pipeline: `etl/transform`, `simulate`, `train`, `publish`, `changed` |
| — | `packages/atwc26_core/` shared library |
| — | `infra/terraform/` modules + `envs/dev`, `envs/prod` |
| — | `services/shared/` bootstrap, cache reader, S3 sync |
| `docs/` (flat) | `docs/etl/`, `docs/ops/`, `docs/specs/`, `docs/models/`, `docs/planning/` |

Docs index: [README.md](README.md).

---

## 8. Decision log (retroactive)

No formal ADRs were written during the refactor. These are the **material decisions** inferred from code, [planning/REFACTOR_ISSUES.md](planning/REFACTOR_ISSUES.md), and [TODO.md](../TODO.md):

| # | Decision | Alternatives considered | Outcome | Why |
|---|----------|-------------------------|---------|-----|
| D1 | Split analytics vs predict APIs | Keep monolith; split only at route level in one Lambda | Two services + two Lambdas | Different scaling, memory, and cold-start profiles |
| D2 | Monte Carlo offline in ETL | Run MC at Lambda startup or on first request | `etl/simulate` → JSON artifacts | Eliminates 6s+ warmup on read path |
| D3 | DynamoDB API cache + S3 artifacts | Redis; always compute from parquet in Lambda | Single-table cache + S3 source of truth | Managed, fits publish manifest model, no extra cluster |
| D4 | Predict on Lambda default; ECS optional | ECS-only compute; Lambda-only for everything | `enable_ecs_compute` toggle | Lambda cheaper at low volume; ECS escape hatch for CPU/timeout |
| D5 | Static frontend on S3/CloudFront | Next.js standalone on ECS | `output: export` + OAC | Cheapest scale for UI; no Node at edge |
| D6 | ETL worker on GitHub Actions | Lambda-only ETL; always-on EC2 scraper | GHA + optional EventBridge dispatcher | Reuse CI runners; no scraper VM; PAT dispatch for workflow |
| D7 | No WAF in v2 candidate phase | Enable AWS WAF on CloudFront | Deferred | Scope control; TLS + CDN sufficient for candidate |
| D8 | Parallel candidate stack (`atwc26-v2`) | In-place replace v1 infrastructure | Separate Terraform prefix + cutover checklist | Rollback safety; k6 A/B against live v1 |
| D9 | `atwc26_core` shared package | Duplicate logic in ETL and services | Single pip-installable package | One artifact registry, one prediction implementation |
| D10 | GitHub OIDC for AWS deploy | Long-lived `AWS_ACCESS_KEY_ID` in secrets | `enable_github_oidc` module | Short-lived credentials; prod defaults on |

When you change one of these, update this table **and** [ARCHITECTURE.md](ARCHITECTURE.md) / [ops/DEPLOY.md](ops/DEPLOY.md).

---

## 9. Do we need formal ADRs?

**Short answer: not mandatory for this project at its current size; a living architecture doc + this transition doc is enough. Consider lightweight ADRs only if the team grows or AWS choices multiply.**

### What ADRs are good for

Architecture Decision Records capture **context, options, decision, and consequences** at the time a choice is made — before memory fades. They help when:

- Multiple developers need to understand *why* something is the way it is.
- Decisions are irreversible or expensive to undo (data model, public API shape, multi-account AWS).
- You revisit the same debate every six months.

### Why we didn't write ADRs during the refactor

- **Single maintainer / small team** — context lived in GitHub issues (#27–#33), [REFACTOR_ISSUES.md](planning/REFACTOR_ISSUES.md), and implementation PRs.
- **Exploratory refactor** — many decisions evolved together (ETL phases A–L in [TODO.md](../TODO.md)); freezing ADRs mid-flight would have churned constantly.
- **Substitutes emerged:**
  - [ARCHITECTURE.md](ARCHITECTURE.md) — current state (C4 + AWS)
  - This doc — v1/v2 delta + retroactive decision log (§8)
  - [specs/PRODUCTION_SPEC.md](specs/PRODUCTION_SPEC.md) — bootstrap runbook with verification steps
  - [planning/REFACTOR_GITHUB_ISSUES.md](planning/REFACTOR_GITHUB_ISSUES.md) — acceptance criteria per issue

That combination is **good enough** for onboarding and ops on a capability demo / small product.

### When ADRs *would* make sense here

Add `docs/adr/NNN-title.md` (or similar) **only if**:

1. **Predict path flips to ECS-only in production** and you need to document SLO/cost tradeoffs permanently.
2. **WAF, multi-region, or multi-account** production hardening begins — security/compliance choices deserve records.
3. **More than 2–3 contributors** debate infrastructure regularly without reading the full refactor thread.
4. **Public API contracts** freeze for external consumers (not just the owned frontend).

### Recommended practice going forward

| Change size | Document in |
|-------------|-------------|
| Bugfix / small feature | PR description only |
| New API route or ETL artifact | [etl/PIPELINE.md](etl/PIPELINE.md) or [models/ANALYTICS.md](models/ANALYTICS.md) |
| Infrastructure toggle or new AWS service | [ARCHITECTURE.md](ARCHITECTURE.md) + [infra/README.md](../infra/README.md) + row in §8 above |
| Irreversible cross-cutting choice | Optional one-page ADR in `docs/adr/` + link from [ARCHITECTURE.md](ARCHITECTURE.md) |

**Do not** retroactively write a dozen polished ADRs — the §8 table above captures the important ones. Invest documentation effort in **keeping ARCHITECTURE, DEPLOY, and ETL docs accurate** as the branch evolves.
