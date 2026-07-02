# TODO - v2 Production Architecture Execution Plan (No WAF)

This plan implements the target architecture:
- CloudFront (CDN + TLS only, no WAF)
- S3 static frontend
- API Gateway path routing
- Lambda for read-heavy endpoints
- ECS/Fargate for compute-heavy endpoints
- S3 as source of truth for artifacts
- DynamoDB for manifest + selected API-ready cache items

## 0) Ground Rules

- [ ] Keep WAF out of Terraform/docs/diagrams for this phase.
- [ ] Keep existing v1 behavior available until v2 cutover checks pass.
- [ ] Make each phase deployable independently.
- [ ] Add rollback note for each phase.

---

## 1) Infra Routing and Edge (CloudFront + API Gateway, no WAF)

### Files
- [ ] `infra/terraform/modules/frontend-cdn/main.tf`
- [ ] `infra/terraform/modules/frontend-cdn/variables.tf`
- [ ] `infra/terraform/modules/frontend-cdn/outputs.tf`
- [ ] `infra/terraform/modules/api-gateway/main.tf`
- [ ] `infra/terraform/modules/api-gateway/variables.tf`
- [ ] `infra/terraform/modules/api-gateway/outputs.tf`
- [ ] `infra/terraform/envs/dev/main.tf`
- [ ] `infra/terraform/envs/dev/outputs.tf`

### Work
- [ ] Ensure CloudFront routes static paths to S3 origin.
- [ ] Ensure CloudFront routes `/api/*` to API Gateway origin.
- [ ] Ensure API Gateway routes:
  - [ ] read endpoints -> Lambda integration
  - [ ] `/api/predict` -> ECS integration
  - [ ] `/api/winner-probabilities` -> ECS integration
- [ ] Confirm no WAF resource/module associations.

### Validation
- [ ] `terraform validate` passes.
- [ ] `terraform plan` shows expected route-only changes.
- [ ] Smoke test static path + `/api/health` through CloudFront URL.

---

## 2) Service Boundary Enforcement (Lambda vs ECS)

### Files
- [ ] `services/analytics_api/analytics_api/main.py`
- [ ] `services/predict_api/predict_api/main.py`
- [ ] `services/shared/bootstrap.py`
- [ ] `tests/contract/test_split.py`
- [ ] `tests/contract/conftest.py`

### Work
- [ ] Keep analytics service read-only endpoints.
- [ ] Keep predict + winner-probabilities on ECS path/service.
- [ ] Remove accidental heavy startup compute from Lambda read service.
- [ ] Keep consistent response schemas across route split.

### Validation
- [ ] Contract tests cover route ownership and 404 on wrong service.
- [ ] Cold-start behavior checked for Lambda read service.

---

## 3) ETL Publish: Materialize DynamoDB API Cache

### Files
- [ ] `etl/publish/publish.py`
- [ ] `etl/publish/refresh.py`
- [ ] `etl/publish/__init__.py` (if needed)
- [ ] `etl/README.md`
- [ ] `packages/atwc26_core/atwc26_core/config.py`
- [ ] `packages/atwc26_core/atwc26_core/artifacts.py`

### New helper modules (to add)
- [ ] `packages/atwc26_core/atwc26_core/api_cache/keys.py`
- [ ] `packages/atwc26_core/atwc26_core/api_cache/store.py`
- [ ] `packages/atwc26_core/atwc26_core/api_cache/builders.py`

### Work
- [ ] Keep existing `LATEST` manifest behavior.
- [ ] Add publish-time API cache upserts for:
  - [ ] `API#standings`
  - [ ] `API#teams`
  - [ ] `API#team#{name}` players
  - [ ] `API#matches`
  - [ ] `API#match#{game_id}` detail
  - [ ] `API#player#{player_id}` detail
- [ ] Include source artifact hash metadata per cache item.
- [ ] Write local dry-run cache under `data/.etl/` when no S3 bucket.

### Validation
- [ ] Idempotent publish: unchanged artifact hashes skip unnecessary writes.
- [ ] Unit tests for each cache builder and item schema.
- [ ] Manual run: `make etl-publish` with and without AWS env vars.

---

## 4) Lambda Read Path: DynamoDB First, S3 Fallback

### Files
- [ ] `services/analytics_api/analytics_api/main.py`
- [ ] `services/shared/data_sync.py`
- [ ] `services/shared/json_util.py`
- [ ] `packages/atwc26_core/atwc26_core/data.py`
- [ ] `packages/atwc26_core/atwc26_core/reload.py`

### Work
- [ ] Add read abstraction:
  - [ ] in-memory cache (warm container)
  - [ ] DynamoDB API cache item
  - [ ] S3/local artifact fallback
- [ ] Incrementally migrate endpoints:
  - [ ] `/api/standings`
  - [ ] `/api/teams`
  - [ ] `/api/teams/{team}/players`
  - [ ] `/api/matches`
  - [ ] `/api/matches/{game_id}`
  - [ ] `/api/players/{player_id}`
- [ ] Keep response shape backward-compatible.

### Validation
- [ ] Contract tests unchanged.
- [ ] Endpoint-level tests for cache hit/miss paths.
- [ ] Confirm no full parquet read for migrated simple endpoints.

---

## 5) ECS Refresh and Data Versioning

### Files
- [ ] `etl/publish/refresh.py`
- [ ] `.github/workflows/etl.yml`
- [ ] `.github/workflows/deploy.yml`
- [ ] `infra/terraform/modules/*` (task/service env vars if needed)

### Work
- [ ] Keep Lambda refresh via `ATWC26_DATA_VERSION`.
- [ ] Re-introduce ECS refresh only if required for compute freshness:
  - [ ] workflow-driven rolling deploy, or
  - [ ] EventBridge-triggered rollout
- [ ] Ensure ECS and Lambda both receive same publish version stamp.

### Validation
- [ ] ETL publish updates running compute to new data version.
- [ ] No stale winner-probability/predict responses after publish.

---

## 6) CI/CD Hardening

### Files
- [ ] `.github/workflows/ci.yml`
- [ ] `.github/workflows/etl.yml`
- [ ] `.github/workflows/deploy.yml`
- [ ] `.github/workflows/performance.yml`

### Work
- [ ] Add tests for API cache schema + fallback behavior.
- [ ] Add route-split smoke test (read route vs compute route).
- [ ] Keep path-filter optimization accurate.
- [ ] Ensure deploy workflow reports:
  - [ ] CloudFront URL
  - [ ] API Gateway URL
  - [ ] data version / publish id

### Validation
- [ ] CI green for ETL, contract, and route smoke checks.
- [ ] Manual deploy run with `plan` and `apply`.

---

## 7) Docs and Showcase Readiness

### Files
- [ ] `docs/DEPLOY.md`
- [ ] `docs/TESTING.md`
- [ ] `docs/CUTOVER.md`
- [ ] `infra/README.md`
- [ ] `etl/README.md`
- [ ] `docs/REFACTOR_ISSUES.md`

### Work
- [ ] Ensure architecture docs match implementation exactly.
- [ ] Explicitly state "no WAF" for this phase.
- [ ] Add troubleshooting notes for cache misses and stale version.
- [ ] Add client-friendly architecture diagram and request flow.

### Validation
- [ ] End-to-end walkthrough from deploy to perf test is reproducible.

---

## Suggested Execution Sequence

- [ ] Phase A: Infra route split (CloudFront/API Gateway)
- [ ] Phase B: Standings cache slice (baseline pattern)
- [ ] Phase C: Teams + team players cache slices
- [ ] Phase D: Matches + match detail + player detail cache slices
- [ ] Phase E: ECS refresh/versioning finalization
- [ ] Phase F: CI/doc hardening and cutover rehearsal

---

## Exit Criteria (Production-Grade Demo)

- [ ] CloudFront serves frontend + `/api/*` correctly (no WAF).
- [ ] Read endpoints served by Lambda with DynamoDB/S3-backed data path.
- [ ] Compute endpoints served by ECS with fresh data after ETL publish.
- [ ] ETL publish is idempotent and versioned.
- [ ] CI and performance checks pass.
- [ ] Docs fully aligned with deployed architecture.

