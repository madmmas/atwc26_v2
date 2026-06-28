# v2 refactor — GitHub issues (copy-paste)

**Status *(June 2026)*:** Track A (plan Issues 1–3 + #25 ETL follow-up) is **complete** on `main`. Track B issues are **open** on GitHub as #27–#33. Branch `refactor/v2-integration` exists.

Labels (created):

- **`refactor-v1`** — Issues 1–3 *(complete)*
- **`refactor-v2`** — Issues 4–10 (merge to `refactor/v2-integration`)
- **`ops`** — Issue 10 cutover
- **`blocked`** — waiting on upstream issue

For branch rules, plan # → GitHub # mapping, and dependency graph see [REFACTOR_ISSUES.md](REFACTOR_ISSUES.md).  
Cutover checklist: [CUTOVER.md](CUTOVER.md) *(create before Issue 10)*.

Production baseline: [atwc26.com](https://atwc26.com) (v1 monolith on `main`).

---

## Track A — v1 prep (Issues 1–3 → `main`) ✓ COMPLETE

Shipped on the **v1 monolith** before v2 integration work.

---

### Issue 1 — Reorganize repo layout (docs, notebooks, scrapers) ✓

**Title:** `refactor: reorganize docs, notebooks, and scrapers`  
**Labels:** `refactor-v1`  
**Branch:** `feat/reorganize-layout` → **`main`**  
**Depends on:** —  
**Status:** **Merged to `main`**

#### Body

Low-risk file moves on v1. Keep `backend/` and `frontend/` unchanged.

**Moves (original Issue 1):**

| From (repo root) | To |
|------------------|-----|
| `ANALYTICS.md`, `CONTRIBUTING.md`, `DEPLOY.md`, `RUN.md`, `TESTING.md`, `WEBAPP_README.md` | `docs/` |
| `analysis.ipynb`, `verify_data.ipynb` | `notebooks/` |
| `scrape_wc26.py`, `scrape_squads.py`, `game_links.csv` | `etl/scrape/` |

**Moves (follow-up [#25](https://github.com/neunov/AnalyseThisWC26/issues/25), merged PR #26):**

| From (repo root) | To |
|------------------|-----|
| `fetch_schedule.py` | `etl/scrape/fetch_schedule.py` |
| `scrape_history.py` | `etl/scrape/scrape_history.py` |
| `build_match_events.py` | `etl/build_match_events.py` |
| `history_analysis.ipynb` | `notebooks/history_analysis.ipynb` |

**Also shipped outside this issue (feature PRs, now on `main`):**

| Script | Location | Purpose |
|--------|----------|---------|
| `fetch_groups.py` | `etl/scrape/` | Group standings + remaining fixtures (`make groups`) |

**ETL layout on `main`:**

```text
etl/
  scrape/          fetch_schedule, scrape_wc26, scrape_squads, scrape_history, fetch_groups
  build_match_events.py
  requirements.txt
  README.md
requirements.txt   # root: -r etl/requirements.txt + matplotlib (notebooks)
```

**Also:**

- Scraper deps in `etl/requirements.txt`; root `requirements.txt` for notebooks.
- `Makefile` targets: `schedule`, `scrape`, `events`, `history`, `groups`.
- `README.md` at repo root with pointers to `docs/`.

**Out of scope:** API split, Terraform, deleting `backend/`.

#### Acceptance criteria

- [x] No duplicate markdown at repo root (except `README.md`).
- [x] No `.ipynb` at repo root; all under `notebooks/`.
- [x] No `scrape*.py` at repo root; scrapers run from `etl/scrape/`.
- [x] `make scrape` and `make dev` work against v1 monolith.
- [x] Merged to **`main`**.

#### Test plan

```bash
make setup
make scrape
make dev
```

---

### Issue 2 — End-to-end API tests (v1 monolith) ✓

**Title:** `test: add end-to-end tests for v1 API`  
**Labels:** `refactor-v1`  
**Branch:** `feat/e2e-tests-v1` → **`main`**  
**Depends on:** Issue 1  
**Status:** **Merged to `main`**

#### Body

Automated end-to-end tests against the **v1 FastAPI monolith** (`backend/`) before any v2 work.

**Add:**

- `e2e/` harness (`pytest`, in-process `TestClient`) — not `tests/` (v2 adds `tests/etl/`, `tests/contract/` later).
- Coverage: `GET /api/health`, `GET /api/overview`, teams/players/matches, `POST /api/predict` (valid XI + `400` on empty XI).
- `make test-e2e` and notes in `docs/TESTING.md`.
- CI job in `.github/workflows/ci.yml`.

**Follow-up (not yet covered):** expand e2e for tournament endpoints added after Issue 2:

- `GET /api/standings`, `GET /api/bracket`, `GET /api/winner-probabilities`, `GET /api/players/{id}`

**Out of scope:** Split-service contract tests (v2 Issue 7), k6 A/B (v2 Issue 8).

#### Acceptance criteria

- [x] `make test-e2e` passes on v1 layout.
- [x] Predict assertions include probability sum ≈ 1.0.
- [x] Merged to **`main`**.

#### Test plan

```bash
make setup && make test-e2e
```

---

### Issue 3 — k6 baseline performance (v1 / production) ✓

**Title:** `perf: k6 baseline against v1 production`  
**Labels:** `refactor-v1`  
**Branch:** `feat/k6-baseline` → **`main`**  
**Depends on:** Issue 2  
**Status:** **Merged to `main`**

#### Body

Establish **baseline latency and error rates** for the current deployment. Default target: [atwc26.com](https://atwc26.com).

**Add under `k6/`:**

- `scripts/smoke.js`, `scripts/journey.js`
- `k6/lib/` (config, scenarios, thresholds, summary)
- `k6/run.sh`, `k6/README.md`
- Makefile targets: `k6-smoke`, `k6-journey`
- `reports/` gitignored for baseline JSON summaries

**Out of scope:** A/B comparison (v2 Issue 8 / GitHub #31).

#### Acceptance criteria

- [x] `make k6-smoke` succeeds against production (or documented override).
- [x] `make k6-journey` writes baseline summary JSON.
- [x] `docs/TESTING.md` documents env vars and baseline run steps.
- [x] Merged to **`main`**.

#### Test plan

```bash
make k6-smoke
make k6-journey
```

**Checkpoint:** After Issue 3, tag `main` if desired (`v1-baseline`) and create `refactor/v2-integration` from `main` for Issues 4–10. Integration branch **already exists**.

---

## Track B — v2 refactor (Issues 4–10 → `refactor/v2-integration`)

All PRs below target **`refactor/v2-integration`**, not `main`, until Issue 10 cutover.

---

### Issue 4 — Static frontend build for S3

**GitHub:** [#30](https://github.com/neunov/AnalyseThisWC26/issues/30)  
**Title:** `feat(v2): static export frontend for S3`  
**Labels:** `refactor-v2`  
**Branch:** `feat/frontend-static-export` → **`refactor/v2-integration`**  
**Depends on:** Issue 1 *(on `main`)*

#### Body

Configure Next.js (`frontend/`) for **static export** and manual S3 upload. Use the **v1 backend URL** for API env vars until Issue 7.

**Current state:** `frontend/next.config.js` uses `output: "standalone"` (Docker). Static export not yet configured.

**Add:**

- Static export in `frontend/next.config.js`
- `infra/scripts/build_frontend_static.sh` → `frontend/out/`
- `infra/scripts/deploy_frontend.sh` — manual `aws s3 sync`
- `frontend/.env.example` for static deploy API URL

#### Acceptance criteria

- [ ] `./infra/scripts/build_frontend_static.sh` produces `frontend/out/`.
- [ ] Static site works locally (`npx serve frontend/out`) against v1 API.
- [ ] Documented in `docs/DEPLOY.md`.

#### Test plan

```bash
./infra/scripts/build_frontend_static.sh
npx serve frontend/out
```

---

### Issue 5 — Terraform: S3 + CloudFront static site (v1 backend)

**GitHub:** [#27](https://github.com/neunov/AnalyseThisWC26/issues/27)  
**Title:** `infra(v2): S3 and CloudFront for static frontend`  
**Labels:** `refactor-v2`  
**Branch:** `feat/frontend-cdn-infra` → **`refactor/v2-integration`**  
**Depends on:** Issue 4

#### Body

Terraform for **S3 + CloudFront** static frontend, wired to the **existing v1 backend** API URL.

**Add:**

- `infra/terraform/modules/frontend-cdn/`
- `infra/terraform/envs/dev/` wiring
- `infra/README.md` — apply, deploy, variables

#### Acceptance criteria

- [ ] `terraform validate` passes.
- [ ] Deploy script syncs `frontend/out/` to bucket; CloudFront serves app.
- [ ] API calls reach v1 backend (CORS OK).

#### Test plan

```bash
terraform -chdir=infra/terraform/envs/dev validate
./infra/scripts/build_frontend_static.sh
# After apply: deploy_frontend.sh with bucket + distribution IDs
```

---

### Issue 6 — ETL transform, publish, QA, shared package, and ETL workflow

**GitHub:** [#28](https://github.com/neunov/AnalyseThisWC26/issues/28)  
**Title:** `feat(v2): ETL pipeline with S3, DynamoDB, and QA`  
**Labels:** `refactor-v2`  
**Branch:** `feat/etl-pipeline-aws` → **`refactor/v2-integration`**  
**Depends on:** Issue 1 *(on `main`)*

#### Body

Full ETL: scrape (`etl/scrape/` from Issue 1) → transform → QA → publish.

**Existing v1 ETL on `main` (inputs to v2 pipeline):**

- Scrapers: `fetch_schedule`, `scrape_wc26`, `scrape_squads`, `scrape_history`, `fetch_groups`
- Transform: `etl/build_match_events.py` (match timelines → `data/match_events.json`)
- Data artifacts: `all_players_stats.parquet`, `historical_form.parquet`, `standings.json`, `bracket.json`, `squads_raw.json`, `data/history_*`

**Add:**

- `packages/atwc26_core/` (from `backend/app/` — include `data.py`, `prediction.py`, `tournament.py`, schemas)
- `etl/transform/`, `etl/qa/`, `etl/publish/` (may subsume or wrap `build_match_events.py`)
- `tests/etl/`, `Makefile` targets `etl-local`, `etl-publish`
- `.github/workflows/etl.yml` — scrape → transform → QA → publish

#### Acceptance criteria

- [ ] `make etl-local` produces expected parquet/JSON artifacts.
- [ ] `pytest tests/etl etl/qa -q` passes.
- [ ] `make etl-publish` idempotent with AWS creds.
- [ ] `etl/README.md` documents S3 keys and DynamoDB schema.

#### Test plan

```bash
pip install -e packages
make etl-local && pytest tests/etl etl/qa -q
```

---

### Issue 7 — Split backend into analytics + predict Lambdas

**GitHub:** [#29](https://github.com/neunov/AnalyseThisWC26/issues/29)  
**Title:** `feat(v2): split APIs into analytics and predict Lambdas`  
**Labels:** `refactor-v2`  
**Branch:** `feat/split-lambda-apis` → **`refactor/v2-integration`**  
**Depends on:** Issue 6

#### Body

Split `backend/` into `services/analytics_api/` and `services/predict_api/` as Lambda functions using S3 + DynamoDB.

**Current v1 API surface to split:**

- Analytics: overview, teams, players, matches, leaderboard, standings, bracket, winner-probabilities, player detail
- Predict: `POST /api/predict` (uses `prediction.py` + historical form from ETL)

**Add:**

- Mangum handlers, `package_lambdas.sh`, shared Lambda layer
- Terraform: `lambda-analytics`, `lambda-predict`, `api-gateway`, `dynamodb`, `s3-data`
- `tests/contract/`, split `NEXT_PUBLIC_ANALYTICS_API_URL` / `NEXT_PUBLIC_PREDICT_API_URL`, `docker-compose.yml` on `:8001`/`:8000`

**Note:** `.env.local` may already comment split URLs; `frontend/lib/api.ts` still uses single `NEXT_PUBLIC_API_URL` until this issue lands.

#### Acceptance criteria

- [ ] `make predict` / `make analytics` locally.
- [ ] Contract tests pass; predict returns 404 on analytics service.
- [ ] `terraform apply` deploys working candidate stack.

#### Test plan

```bash
make dev && pytest tests/contract -q
./infra/scripts/package_lambdas.sh
```

---

### Issue 8 — k6 A/B: v1 vs v2 deployments

**GitHub:** [#31](https://github.com/neunov/AnalyseThisWC26/issues/31)  
**Title:** `perf(v2): k6 A/B compare v1 and v2`  
**Labels:** `refactor-v2`  
**Branch:** `feat/k6-ab-compare` → **`refactor/v2-integration`**  
**Depends on:** Issues 3 *(on `main`)*, 5, 7

#### Body

Compare **v1 baseline** (Issue 3 on `main`) against the v2 candidate stack.

**Add:**

- `k6/compare_ab.sh`, `k6/compare_summaries.py`
- `k6/scripts/load.js`, `k6/scripts/stress.js`
- Makefile: `k6-ab`, `k6-load`, `k6-stress`
- `.github/workflows/performance.yml` (manual dispatch)

#### Acceptance criteria

- [ ] `make k6-ab` compares baseline vs candidate; writes `reports/` diff.
- [ ] Thresholds documented in `docs/TESTING.md` and cutover doc.

#### Test plan

```bash
make k6-ab ATWC26_PERF_CANDIDATE_ANALYTICS_URL=... ATWC26_PERF_CANDIDATE_PREDICT_URL=...
```

---

### Issue 9 — Full CI/CD: scrape, transform, publish, deploy

**GitHub:** [#32](https://github.com/neunov/AnalyseThisWC26/issues/32)  
**Title:** `ci(v2): complete CI/CD pipeline`  
**Labels:** `refactor-v2`  
**Branch:** `feat/full-cicd` → **`refactor/v2-integration`**  
**Depends on:** Issues 6, 7, 8

#### Body

End-to-end GitHub Actions: test → package → deploy → optional perf gate.

**Existing on `main`:** `.github/workflows/ci.yml` runs `e2e/` on PRs to `main`.

**Add / finalize:**

- `.github/workflows/ci.yml` — path-filtered jobs on `refactor/v2-integration`
- `.github/workflows/etl.yml` — scheduled/manual ETL
- Deploy jobs for Lambdas + frontend + terraform plan/apply
- Secrets/vars in `infra/README.md`

#### Acceptance criteria

- [ ] Path-filtered CI on PRs to `refactor/v2-integration`.
- [ ] Manual ETL workflow_dispatch runs scrape → publish.
- [ ] Deploy workflow yields candidate URL for k6 A/B.

#### Test plan

Draft PR + `workflow_dispatch` for ETL and deploy.

---

### Issue 10 — Cut over to v2 and remove v1 layout

**GitHub:** [#33](https://github.com/neunov/AnalyseThisWC26/issues/33)  
**Title:** `chore(v2): cut over to v2 and remove v1 monolith`  
**Labels:** `refactor-v2`, `ops`  
**Branch:** `chore/remove-v1-monolith` → **`refactor/v2-integration`** → then **`main`**  
**Depends on:** Issues 1–9

#### Body

Final PR: **`refactor/v2-integration` → `main`** after candidate validation.

**Remove:** `backend/`, legacy root duplicates, nginx if present.  
**Keep:** `frontend/`, `docs/`, `notebooks/`, `etl/`, `services/`, `packages/`, `infra/`, `k6/`, `e2e/`, `tests/`.

**Data artifacts to preserve:** `standings.json`, `bracket.json`, `historical_form.parquet`, `match_events.json`, `squads_raw.json`, `data/history_*`, tournament parquet/JSON outputs from ETL publish.

**Ops:** Tag `main` before merge: `v1-monolith`. Run k6 A/B per cutover checklist. DNS/CloudFront cutover. Create/follow `docs/CUTOVER.md`.

#### Acceptance criteria

- [ ] No `backend/` in tree.
- [ ] `make test-e2e`, contract tests pass on merged `main`.
- [ ] k6 A/B within threshold.
- [ ] Maintainer approves integration → `main` PR.

#### Test plan

Follow cutover checklist (Phases A–H) in `docs/CUTOVER.md`.
