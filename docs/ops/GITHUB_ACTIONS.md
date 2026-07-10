# GitHub Actions — contributor & maintainer guide

Who runs what, when, and where secrets live. **Secret names and sources** stay in one place: [`infra/README.md` § GitHub secrets](../../infra/README.md#github-secrets--vars-issue-9). First-time AWS bootstrap steps: [specs/PRODUCTION_SPEC.md](../specs/PRODUCTION_SPEC.md) Part 1.

---

## Who are you?

| Role | Start here | You do **not** need |
|------|------------|---------------------|
| **App / API / frontend dev** | [CONTRIBUTING.md](../CONTRIBUTING.md), [DEPLOY.md §2–3](DEPLOY.md#3-local--v2-split-apis) | GitHub secrets, manual workflow runs, Terraform |
| **Infra / deploy maintainer** | This doc → [DEPLOY.md §5–6](DEPLOY.md#5-aws-dev-candidate-envsdev) → [`infra/README.md`](../../infra/README.md) → [PRODUCTION_SPEC.md](../specs/PRODUCTION_SPEC.md) Part 1 | Reading all of `PRODUCTION_SPEC` for every change |
| **ETL operator** | [etl/PIPELINE.md](../etl/PIPELINE.md), manual **ETL** workflow below | Terraform (usually) |

**Normal PRs:** push a branch and open a PR — **CI** runs automatically. No AWS setup required.

---

## What runs automatically

| Workflow | File | Trigger | Effect |
|----------|------|---------|--------|
| **CI** | [`ci.yml`](../../.github/workflows/ci.yml) | PR + push to `main` | Path-filtered tests (backend e2e, ETL, contract, frontend build, terraform validate, Lambda package) |
| **Deploy frontend** | [`deploy-frontend.yml`](../../.github/workflows/deploy-frontend.yml) | Push to `main` touching `frontend/**` or deploy scripts | Builds static site and syncs to **prod** stack (S3 + CloudFront invalidation) |
| **Terraform dev** (ECS only) | [`terraform.yml`](../../.github/workflows/terraform.yml) | Push to `main` on predict-related paths | Builds and pushes predict Docker image to ECR; rolls ECS if enabled — **not** a full `terraform apply` |

Nobody needs to click **Run workflow** for day-to-day app development.

---

## What maintainers run manually

All of these are under **GitHub → Actions → &lt;workflow name&gt; → Run workflow**.

| Workflow | Run when | Prerequisites |
|----------|----------|----------------|
| **Terraform dev** | New dev stack, infra/Lambda changes, `terraform plan` before apply | `ATWC26_TFVARS`, `ATWC26_TF_STATE_BUCKET`, `ATWC26_AWS_ROLE_ARN`, `AWS_REGION` — see [secrets table](../../infra/README.md#github-secrets--vars-issue-9) |
| **Terraform prod** | Prod infra change | GitHub **`production`** environment (below) + `ATWC26_TFVARS_PROD` + same OIDC/state secrets |
| **Deploy frontend** (dispatch) | Rebuild without a frontend commit; target dev or prod | `ATWC26_AWS_ROLE_ARN`; prod dispatch uses `production` environment |
| **ETL** | Manual data refresh, test publish, or debug pipeline | `ATWC26_AWS_ROLE_ARN`, `ATWC26_S3_BUCKET`, `ATWC26_DYNAMODB_TABLE`, etc. — [PIPELINE.md § env vars](../etl/PIPELINE.md#key-environment-variables) |
| **Performance** | k6 A/B after dev stack is up | Candidate URLs from **Terraform dev** job summary (`api_gateway_url`); baseline defaults to `https://atwc26.com` |

### Terraform dev actions

| Input | Use |
|-------|-----|
| `terraform-plan` | Dry-run — safe default |
| `terraform-apply` | Provision or update dev stack; job summary lists CloudFront + API Gateway URLs |
| `deploy-predict-ecs` | Image-only ECS redeploy (same as push trigger on predict paths) |

### Deploy frontend dispatch

| Input | Stack |
|-------|-------|
| `prod` (default) | `infra/terraform/envs/prod` — uses GitHub **`production`** environment |
| `dev` | `infra/terraform/envs/dev` |

### ETL dispatch

Usually **not** needed in production: AWS EventBridge → Lambda dispatches `etl.yml` when `enable_etl_scheduler=true`. Manual run: scrape → transform → simulate/train → QA → publish. See [PIPELINE.md](../etl/PIPELINE.md).

---

## First-time bootstrap order (maintainers)

Do this once per AWS account / repo. Detailed commands: [PRODUCTION_SPEC.md Part 1](../specs/PRODUCTION_SPEC.md).

1. Create Terraform **state bucket** → set `ATWC26_TF_STATE_BUCKET`.
2. Copy `infra/terraform/envs/dev/terraform.tfvars` → GitHub secret **`ATWC26_TFVARS`**.
3. **Terraform dev** → `terraform-apply` (first run may need temporary `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` until OIDC exists — see PRODUCTION_SPEC Step 1E).
4. Map Terraform **outputs** → repo secrets (`ATWC26_AWS_ROLE_ARN`, `ATWC26_S3_BUCKET`, `ATWC26_DYNAMODB_TABLE`, Lambda names, …) — [secrets table](../../infra/README.md#github-secrets--vars-issue-9).
5. Delete temporary AWS key secrets; confirm workflows use **OIDC** (`enable_github_oidc=true` in tfvars).
6. For **prod**: create GitHub **`production`** environment (below), copy `envs/prod/terraform.tfvars` → **`ATWC26_TFVARS_PROD`**, run **Terraform prod**.

Dev vs prod tfvars: **`ATWC26_TFVARS`** (dev) vs **`ATWC26_TFVARS_PROD`** (prod). Most other secrets are **repository-level** and shared.

---

## GitHub `production` environment

Required for **Terraform prod** and **Deploy frontend** when targeting prod.

1. Repo **Settings → Environments → New environment** → name: `production`.
2. Optional but recommended:
   - **Required reviewers** — gate prod applies and prod frontend deploys.
   - **Deployment branches** — limit to `main` if you use branch rules.
3. Workflows that use it:
   - [`terraform-prod.yml`](../../.github/workflows/terraform-prod.yml) — `environment: production`
   - [`deploy-frontend.yml`](../../.github/workflows/deploy-frontend.yml) — when dispatch input `environment: prod`

Environment-scoped secrets are **not** required today; prod tfvars live in repo secret `ATWC26_TFVARS_PROD`. You can add environment-only secrets later if you want stricter isolation.

---

## Fork or personal AWS stack

Contributors running their **own** fork + AWS account need a **separate** stack and secrets — not the org’s shared `ATWC26_*` values.

1. Override in `terraform.tfvars`: `github_org`, `github_repo`, `name_prefix`, `environment`.
2. Create your own state bucket and store `ATWC26_TF_STATE_BUCKET` in **your fork’s** Settings → Secrets.
3. Follow the bootstrap order above in your fork.
4. Run **Terraform dev** from your fork’s Actions tab.

See [DEPLOY.md §5](DEPLOY.md#5-aws-dev-candidate-envsdev) for dev vs prod tfvars defaults (`github_org` / `github_repo` differ between envs).

---

## Related docs

| Doc | Contents |
|-----|----------|
| [`infra/README.md`](../../infra/README.md) | Terraform variables, outputs, **secrets catalog**, CI path filters |
| [DEPLOY.md](DEPLOY.md) | Local, Docker, AWS dev/prod deployment paths |
| [PRODUCTION_SPEC.md](../specs/PRODUCTION_SPEC.md) | Full first-time bootstrap narrative |
| [etl/PIPELINE.md](../etl/PIPELINE.md) | ETL workflow stages and env vars |
| [TESTING.md](TESTING.md) | k6 locally (`make k6-ab`) and perf workflow inputs |
