# Operations documentation

Deploy, test, cutover, and data-collection runbooks.

## Who are you?

| Role | Start here | You do **not** need |
|------|------------|---------------------|
| **App / API / frontend dev** | [CONTRIBUTING.md](../CONTRIBUTING.md), [DEPLOY.md §2–3](DEPLOY.md#3-local--v2-split-apis) | GitHub secrets, manual workflow runs |
| **Infra / deploy maintainer** | [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) → [DEPLOY.md §5–6](DEPLOY.md#5-aws-dev-candidate-envsdev) → [`infra/README.md`](../../infra/README.md) | Full [PRODUCTION_SPEC.md](../specs/PRODUCTION_SPEC.md) for every change |
| **ETL operator** | [etl/PIPELINE.md](../etl/PIPELINE.md) | Terraform (usually) |

---

| Doc | Contents |
|-----|----------|
| [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) | **GHA runbook** — auto vs manual workflows, bootstrap order, `production` environment |
| [V1_TO_V2.md](../V1_TO_V2.md) | v1 → v2 rationale, comparison, decision log |
| [ARCHITECTURE.md](../ARCHITECTURE.md) | System C4 model + AWS deployment map |
| [DEPLOY.md](DEPLOY.md) | **Deployment hub** — local, Docker, AWS dev/prod, frontend build modes |
| [TESTING.md](TESTING.md) | QA, E2E, k6 performance, env vars |
| [CUTOVER.md](CUTOVER.md) | Production go-live checklist |
| [RUN.md](RUN.md) | v1 incremental ESPN scrape workflow |

**Secrets catalog:** [`infra/README.md` § GitHub secrets](../../infra/README.md#github-secrets--vars-issue-9) (single source of truth — not duplicated here).

**Parent index:** [docs/README.md](../README.md)
