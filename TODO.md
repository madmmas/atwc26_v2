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

### Phase G — `etl/simulate` (Monte Carlo offline)

### Files
- [x] `etl/simulate/run.py`
- [x] `packages/atwc26_core/atwc26_core/config.py` — `WINNER_PROBABILITIES`, `BRACKET_PREDICTIONS`
- [x] `packages/atwc26_core/atwc26_core/artifacts.py`
- [x] `Makefile` — `etl-simulate`; wire into `etl-local`
- [x] `tests/etl/test_simulate.py`

### Work
- [x] Run 10k-trial MC + bracket path after transform; write JSON artifacts to `data/`.
- [x] Register artifacts in manifest for S3 publish.
- [x] `ATWC26_SIMULATE_TRIALS` env for fast local/CI runs (default 10_000).

### Validation
- [x] `make etl-simulate` produces `winner_probabilities.json` + `bracket_predictions.json`.
- [x] Unit test with `trials=50`.

---

## Phase H — Winner probabilities on read path

### Files
- [x] `services/analytics_api/analytics_api/main.py`
- [x] `services/predict_api/predict_api/main.py`
- [x] `infra/terraform/modules/api-gateway/main.tf`
- [x] `tests/contract/test_split.py`

### Work
- [x] Serve `GET /api/winner-probabilities` from analytics (precomputed JSON / API cache).
- [x] Remove endpoint + MC warmup from predict service.
- [x] API Gateway: only `POST /api/predict` → compute; winner-probs → analytics `$default`.

### Validation
- [x] Contract tests: winner-probs on analytics, 404 on predict.
- [x] Predict startup no longer runs Monte Carlo.

---

## Phase I — Per-90 profiles in transform

### Files
- [x] `etl/transform/profiles.py`
- [x] `etl/transform/run.py`
- [x] `packages/atwc26_core/atwc26_core/data.py`
- [x] `packages/atwc26_core/atwc26_core/config.py` — `PLAYER_PROFILES`, `TEAM_PROFILES`

### Work
- [x] Transform writes `player_profiles.parquet` + `team_profiles.parquet`.
- [x] `DataStore.load()` reads precomputed profiles when present (skip `_build_*` on hot path).

### Validation
- [x] Transform regenerates profiles when master parquet changes.
- [x] QA + contract tests pass.

---

## Phase J — Full read cache + light Lambda startup

### Files
- [x] `packages/atwc26_core/atwc26_core/api_cache/{keys,builders}.py`
- [x] `etl/publish/api_cache.py`
- [x] `services/analytics_api/analytics_api/main.py`

### Work
- [x] Publish API cache: `API#overview`, `API#bracket`, `API#winner-probabilities`.
- [x] Analytics endpoints: overview, bracket, winner-probs → `read_cached`.
- [x] Remove `get_bracket_predictions` from analytics startup; health uses minimal load.

### Validation
- [x] No parquet parse on migrated read endpoints (cache hit path).
- [x] `make e2e-v2-local` green.

---

## Phase K — GHA pipeline (path-filtered jobs)

### Files
- [x] `.github/workflows/etl.yml`
- [x] `.github/workflows/pipeline.yml`
- [x] `.github/workflows/ci.yml`
- [x] `etl/publish/refresh.py`

### Work
- [x] ETL job: transform → simulate → publish → warm ECS predict.
- [x] Path-filtered pipeline on push (`etl`, analytics Lambda package, `frontend` build).
- [ ] Full auto-deploy of Lambda/ECS images on path change (manual deploy workflow remains).

### Validation
- [x] Scheduled ETL runs simulate with `ATWC26_SIMULATE_TRIALS=100` in CI.
- [x] Publish bumps analytics Lambda + ECS predict data version.

---

## Phase L — GitHub OIDC

### Files
- [x] `infra/terraform/modules/github-oidc/`
- [x] `.github/workflows/etl.yml`, `deploy.yml` — `role-to-assume` support

### Work
- [x] IAM role trusts `token.actions.githubusercontent.com` for this repo.
- [x] Workflows accept `ATWC26_AWS_ROLE_ARN` (falls back to access keys when unset).

### Validation
- [ ] `terraform apply` with `enable_github_oidc=true`; ETL publish via OIDC in GHA.

---

## Exit criteria

- [ ] CloudFront serves frontend + `/api/*` (no WAF).
- [x] Read endpoints: DynamoDB cache or S3 JSON only — no Monte Carlo on Lambda.
- [ ] `POST /api/predict` on warm ECS only.
- [x] ETL: transform → simulate → publish idempotent and versioned.
- [x] GHA path-filtered jobs; OIDC module ready.
- [x] Docs match deployed architecture.
