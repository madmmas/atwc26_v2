# Documentation index

Navigation hub for ATWC26 project docs. Diagrams live **inline** in each markdown file (Mermaid).

---

## Start here

| Role | Doc |
|------|-----|
| **v1 → v2 transition (why & how)** | [V1_TO_V2.md](V1_TO_V2.md) |
| System architecture (C4 + AWS) | [ARCHITECTURE.md](ARCHITECTURE.md) |
| New contributor | [CONTRIBUTING.md](CONTRIBUTING.md) |
| How analytics & prediction work | [models/ANALYTICS.md](models/ANALYTICS.md) |
| QA & automation | [ops/TESTING.md](ops/TESTING.md) |
| Deploy & ops | [ops/DEPLOY.md](ops/DEPLOY.md) (local, AWS dev/prod) · [`infra/README.md`](../infra/README.md) (Terraform) |
| Production cutover | [specs/PRODUCTION_SPEC.md](specs/PRODUCTION_SPEC.md) · [ops/CUTOVER.md](ops/CUTOVER.md) |
| Web app overview | [WEBAPP_README.md](WEBAPP_README.md) |

---

## By topic

| Folder | Index | Contents |
|--------|-------|----------|
| **[etl/](etl/README.md)** | ETL pipeline | Scheduler, pipeline, overview — full AWS map in [ARCHITECTURE.md](ARCHITECTURE.md) |
| **[ops/](ops/README.md)** | Operations | Deploy, testing, cutover, scrape runbook |
| **[specs/](specs/README.md)** | Specifications | Product, production, UX specs |
| **[models/](models/README.md)** | Models & analytics | Prediction methodology, training design |
| **[planning/](planning/README.md)** | Planning | Roadmap, refactor tracking |

---

## ETL & data pipeline

| Doc | Contents |
|-----|----------|
| [etl/OVERVIEW.md](etl/OVERVIEW.md) | End-to-end map, cross-boundary contract |
| [etl/SCHEDULER.md](etl/SCHEDULER.md) | EventBridge, Lambda dispatch, trigger windows |
| [etl/PIPELINE.md](etl/PIPELINE.md) | GitHub Actions, scrape → publish |
| [`etl/` runbook](../etl/README.md) | Makefile targets, artifacts, env vars |

---

## Root-level docs

| Doc | Contents |
|-----|----------|
| [V1_TO_V2.md](V1_TO_V2.md) | v1 monolith → v2 AWS: rationale, comparison, decision log |
| [ARCHITECTURE.md](ARCHITECTURE.md) | C4 model + full AWS deployment map |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development & code review guide |
| [WEBAPP_README.md](WEBAPP_README.md) | Frontend pages, API client modes, local dev |

---

## External

| Doc | Contents |
|-----|----------|
| [`infra/README.md`](../infra/README.md) | Terraform, GitHub Actions, AWS secrets |
| [`etl/README.md`](../etl/README.md) | ETL operator runbook (code) |
