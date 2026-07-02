# TODO — v2 Production Architecture (No WAF)

Target: **zero AWS compute for reads and Monte Carlo**; **one small ECS task for predict only** (~$7/mo Spot).

## Compute placement (core insight)

| Workload | Where | Why |
|----------|-------|-----|
| 10k Monte Carlo (`tournament.py`) | GHA `etl/simulate` after publish | ~30s, once per data change, tiny JSON output |
| Bracket path predictions | GHA `etl/simulate` (same step) | Needs Predictor but not per-request |
| Per-90 player/team profiles | GHA `etl/transform` | Never parse parquet at Lambda cold start |
| Standings, matches, players, overview, leaderboard | GHA `etl/publish` → DynamoDB API cache + S3 | Lambda reads one item per request |
| `GET /api/winner-probabilities` | Analytics Lambda (read precomputed JSON/cache) | Not compute — no MC at request time |
| `POST /api/predict` | ECS Fargate (warm Predictor) | 2–3s cold start unacceptable for interactive UI |

**Only recurring AWS compute:** ECS Fargate `0.25 vCPU / 512 MB` for predict.

## Ground rules

- [x] Keep WAF out of Terraform/docs/diagrams for this phase.
- [x] Keep v1 monolith available until v2 cutover checks pass.
- [ ] Each phase deployable independently with rollback note.
- [ ] GitHub Actions OIDC (no long-lived `AWS_ACCESS_KEY_ID` secrets).

---

## Completed — Phases A–F (infra + API cache foundation)

- [x] **A** CloudFront `/api/*` → API Gateway; static → S3
- [x] **B–D** DynamoDB API cache (`API#standings`, teams, matches, players)
- [x] **E** Lambda/ECS refresh via `ATWC26_DATA_VERSION` on publish
- [x] **F** CI path filters, deploy workflow, docs skeleton

Rollback: revert Terraform module flags; analytics falls back to `DataStore` + S3 sync.

---

## Phase G — `etl/simulate` (Monte Carlo offline)

### Files
- [ ] `etl/simulate/run.py`
- [ ] `packages/atwc26_core/atwc26_core/config.py` — `WINNER_PROBABILITIES`, `BRACKET_PREDICTIONS`
- [ ] `packages/atwc26_core/atwc26_core/artifacts.py`
- [ ] `Makefile` — `etl-simulate`; wire into `etl-local`
- [ ] `tests/etl/test_simulate.py`

### Work
- [ ] Run 10k-trial MC + bracket path after transform; write JSON artifacts to `data/`.
- [ ] Register artifacts in manifest for S3 publish.
- [ ] `ATWC26_SIMULATE_TRIALS` env for fast local/CI runs (default 10_000).

### Validation
- [ ] `make etl-simulate` produces `winner_probabilities.json` + `bracket_predictions.json`.
- [ ] Unit test with `trials=50`.

Rollback: delete JSON files; endpoints fall back to runtime sim (dev only until Phase H).

---

## Phase H — Winner probabilities on read path

### Files
- [ ] `services/analytics_api/analytics_api/main.py`
- [ ] `services/predict_api/predict_api/main.py`
- [ ] `infra/terraform/modules/api-gateway/main.tf`
- [ ] `tests/contract/test_split.py`

### Work
- [ ] Serve `GET /api/winner-probabilities` from analytics (precomputed JSON / API cache).
- [ ] Remove endpoint + MC warmup from predict service.
- [ ] API Gateway: only `POST /api/predict` → compute; winner-probs → analytics `$default`.

### Validation
- [ ] Contract tests: winner-probs on analytics, 404 on predict.
- [ ] Predict startup no longer runs Monte Carlo.

Rollback: restore predict route in API Gateway + predict handler.

---

## Phase I — Per-90 profiles in transform

### Files
- [ ] `etl/transform/profiles.py`
- [ ] `etl/transform/run.py`
- [ ] `packages/atwc26_core/atwc26_core/data.py`
- [ ] `packages/atwc26_core/atwc26_core/config.py` — `PLAYER_PROFILES`, `TEAM_PROFILES`

### Work
- [ ] Transform writes `player_profiles.parquet` + `team_profiles.parquet`.
- [ ] `DataStore.load()` reads precomputed profiles when present (skip `_build_*` on hot path).

### Validation
- [ ] Transform regenerates profiles when master parquet changes.
- [ ] QA + contract tests pass.

Rollback: delete profile parquets; DataStore rebuilds from master parquet.

---

## Phase J — Full read cache + light Lambda startup

### Files
- [ ] `packages/atwc26_core/atwc26_core/api_cache/{keys,builders}.py`
- [ ] `etl/publish/api_cache.py`
- [ ] `services/analytics_api/analytics_api/main.py`

### Work
- [ ] Publish API cache: `API#overview`, `API#bracket`, `API#winner-probabilities`.
- [ ] Analytics endpoints: overview, bracket, leaderboard, winner-probs → `read_cached`.
- [ ] Remove `get_bracket_predictions` from analytics startup; health uses minimal load.

### Validation
- [ ] No parquet parse on migrated read endpoints (cache hit path).
- [ ] `make e2e-v2-local` green.

Rollback: endpoints fall back to `DataStore` computation.

---

## Phase K — GHA pipeline (path-filtered jobs)

### Files
- [ ] `.github/workflows/etl.yml`
- [ ] `.github/workflows/deploy.yml` (split or path-filter jobs)
- [ ] `etl/publish/refresh.py`

### Work
- [ ] ETL job: scrape (optional) → transform → simulate → publish → warm ECS predict only.
- [ ] Separate deploy triggers: analytics Lambda, predict ECS image, frontend static.
- [ ] Data-only commits do not redeploy code.

### Validation
- [ ] Scheduled ETL runs simulate + tests.
- [ ] Publish bumps analytics Lambda + ECS predict data version.

Rollback: revert workflow YAML; manual `make etl-publish`.

---

## Phase L — GitHub OIDC

### Files
- [ ] `infra/terraform/modules/github-oidc/`
- [ ] `.github/workflows/etl.yml`, `deploy.yml` — `aws-actions/configure-aws-credentials` with `role-to-assume`

### Work
- [ ] IAM role trusts `token.actions.githubusercontent.com` for this repo only.
- [ ] Replace `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` with `ATWC26_AWS_ROLE_ARN` secret.

### Validation
- [ ] ETL publish + deploy plan succeed via OIDC in GHA.

Rollback: re-enable access-key secrets in workflows.

---

## Exit criteria

- [ ] CloudFront serves frontend + `/api/*` (no WAF).
- [ ] Read endpoints: DynamoDB cache or S3 JSON only — no Monte Carlo, no parquet on Lambda.
- [ ] `POST /api/predict` on warm ECS only.
- [ ] ETL: transform → simulate → publish idempotent and versioned.
- [ ] GHA OIDC; path-filtered deploy jobs.
- [ ] Docs match deployed architecture.
