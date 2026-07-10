# Production cutover checklist (v2)

Use this before merging `refactor/v2-integration` → `main` (Issue 10). Background: [V1_TO_V2.md](../V1_TO_V2.md). Deployment: [DEPLOY.md](DEPLOY.md) · System map: [ARCHITECTURE.md](../ARCHITECTURE.md).

## Performance gate (Issue 8)

Run k6 A/B against the **v1 production baseline** and the **v2 candidate stack**:

```bash
make k6-ab \
  K6_BASELINE_URL=https://atwc26.com \
  ATWC26_PERF_CANDIDATE_ANALYTICS_URL=https://<api-gateway-url> \
  ATWC26_PERF_CANDIDATE_PREDICT_URL=https://<api-gateway-url>
```

Or trigger `.github/workflows/performance.yml` via **workflow_dispatch** with the
candidate API Gateway URLs.

### Pass criteria

The comparison writes `reports/ab-diff-<timestamp>.json`. Overall **PASS** requires:

| Check | Rule |
|-------|------|
| Error rate | Candidate `http_req_failed.rate` ≤ **10%** and ≤ baseline × **1.10** |
| Global p95 | Candidate `http_req_duration.p95` ≤ baseline × **1.25** |
| Key endpoints | `health`, `overview`, `teams`, `predict` p95 each ≤ baseline × **1.25** |

See [TESTING.md](TESTING.md) §6a for full k6 A/B documentation.

### Before cutover

- [ ] `make e2e-v2-local` passes on candidate data
- [ ] `make test-contract` passes
- [ ] k6 A/B **PASS** (artifact saved from CI or local run)
- [ ] Static frontend smoke on CloudFront URL (or `atwc26.com` after DNS)
- [ ] CloudFront routes static assets to S3 and `/api/*` to API Gateway
- [ ] Candidate stack runs **without WAF** (CloudFront CDN + TLS only)
- [ ] API Gateway split verified: read routes on **analytics Lambda**; `POST /api/predict` on **predict Lambda** (default) or **ECS/ALB** when `enable_ecs_compute=true`
- [ ] `GET /api/winner-probabilities` served by **analytics** (not predict)
- [ ] Frontend built with **same-origin** `/api/*` (`NEXT_PUBLIC_SAME_ORIGIN_API=true` or `deploy-frontend.yml`)
- [ ] DynamoDB API cache + S3 fallback behavior smoke-tested for read endpoints
- [ ] ETL publish + Lambda cold-start verified in AWS dev
- [ ] ETL publish bumps `ATWC26_DATA_VERSION`; compute refresh verified (Lambda and/or ECS per toggle)
- [ ] Rollback plan documented (revert DNS / CloudFront origin to v1)

## Tag v1 before merge

```bash
git tag v1-monolith <main-sha-before-merge>
git push origin v1-monolith
```
