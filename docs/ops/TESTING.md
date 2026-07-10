# TESTING.md — QA & automation guide

Everything a QA engineer needs to test **AnalyseThisWC26**: how to run it, the
full API contract with sample payloads, the frontend `data-testid` map, model
invariants worth asserting, and copy-paste starting points for **pytest** (API)
and **Playwright** (E2E).

---

## 1. Bring the app up for testing

**Option A — local processes**
```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000        # API at :8000

# frontend (another terminal)
cd frontend && cp .env.example .env.local && npm install
npm run dev                                        # UI at :3000
```

**Option B — full stack via Docker** (single origin, like prod)
```bash
docker compose up --build                          # everything at :8080
```

**Readiness gate** (poll before running a suite):
```bash
curl -fs http://localhost:8000/api/health > /dev/null && echo "API ready"
```

---

## 2. API contract (for API automation)

> **v1 monolith** — single origin on `:8000` (or `:8080` behind Nginx). Contract below matches `backend/app/main.py`.
>
> **v2 split stack** — analytics on **`:8001`**, predict on **`:8000`**. Run `make test-contract` for split boundaries; live smoke: [§12](#12-local-v2-e2e-smoke-path). Deploy routing: [DEPLOY.md §7](DEPLOY.md#7-v2-edge-routing-reference).

Base URL: `http://localhost:8000` (v1 monolith or v2 predict). For v2 read endpoints use `http://localhost:8001`.
All responses are JSON; `NaN/inf` are converted to `null`.

### `GET /api/health`
```json
{ "status": "ok", "app": "AnalyseThisWC26", "version": "1.0.0",
  "avg_team_goals": 1.583, "games": 12, "teams": 24, "players": 376,
  "data_updated_at": "2026-07-10T12:00:00+00:00" }
```

`data_updated_at` is the newest artifact timestamp among key data files
(parquet mtimes / JSON `generated_at`).

### `GET /api/backtest` (predict service)
Returns the latest hold-out summary written by `make etl-train`
(`data/backtest_summary.json`). **404** if missing. Same-origin prod routes this
to the predict Lambda/ECS via API Gateway (`GET /api/backtest`).

```json
{ "generated_at": "...", "holdout_n": 85, "train_n": 343,
  "models": { "elo": { "accuracy": 0.48, "log_loss": 1.02, "brier": 0.64 },
              "dixon_coles": { "accuracy": 0.51, "log_loss": 0.98, "brier": 0.61,
                               "train_converged": true } } }
```

See also [models/V2_PARITY_TEST_PLAN.md](../models/V2_PARITY_TEST_PLAN.md).

### `GET /api/overview`
Keys: `league`, `teams[]`, `top_scorers[]`, `top_xg_per90[]`, `top_creators_per90[]`.
Each team: `{team_name, games, goals_for, goals_against, goals_per_game,
conceded_per_game, xg_per_game, xga_per_game, shots_per_game, sot_per_game,
big_chances_per_game}`.

### `GET /api/teams`
`{ "teams": [ {team_name, …}, … ] }`

### `GET /api/teams/{team_name}/players`
`{ "team_name": "...", "players": [ {player_id, player_name, role, minutes,
expectedGoals_p90, …}, … ] }` — **404** if the team is unknown.

### `GET /api/players`
Query: `team`, `role` (GK/DEF/MID/FWD), `sort` (any player column),
`limit` (≤ 500).
`{ "count": N, "players": [...] }` — **400** on an unknown `sort` field.

### `GET /api/leaderboard`
Query: `metric` (default `expectedGoals_p90`), `role`, `min_minutes` (default 90),
`limit` (default 20).
`{ "metric": "...", "leaders": [...] }` — **400** on an unknown `metric`.

### `POST /api/predict`
Request:
```json
{
  "team_a": { "team_name": "Brazil", "home": true,
    "players": [ {"player_id": 12345, "role": "GK"},
                 {"player_id": 23456, "role": "DEF"} ] },
  "team_b": { "team_name": "Germany", "home": false,
    "players": [ {"player_id": 34567, "role": "FWD"} ] }
}
```
Response (abridged):
```json
{
  "team_a": { "team_name": "Brazil", "attack_rating": 0.76, "defense_rating": 0.97,
    "gk_rating": 0.96, "expected_goals": 2.60, "win_probability": 0.19,
    "key_players": [ {"player_name": "...", "attack": 1.57, "defense": 0.27} ] },
  "team_b": { "...": "..." },
  "draw_prob": 0.13,
  "most_likely_score": { "a": 2, "b": 4, "prob": 0.05 },
  "top_scorelines": [ {"a": 2, "b": 4, "prob": 0.05}, … ],
  "radar": { "dimensions": ["Attack","Creativity","Possession","Defense","Goalkeeping"],
             "Brazil": {...}, "Germany": {...} },
  "narrative": "The model gives Germany a strong edge …",
  "model": { "type": "...", "avg_team_goals_baseline": 1.583, "assumptions": "..." }
}
```
**400** if either team has zero selected players.

> **Tip:** an easy way to build a valid `predict` body is to call
> `GET /api/teams/{team}/players`, take the first GK + some DEF/MID/FWD, and map
> each to `{player_id, role}`.

---

## 3. Model invariants worth asserting

These should hold for **any** valid prediction — great automated checks:

1. `team_a.win_probability + team_b.win_probability + draw_prob ≈ 1.0` (±0.001).
2. Every probability ∈ [0, 1]; every `expected_goals` ∈ [0.2, 5.0] (the clamp).
3. `most_likely_score` equals the highest-prob entry in `top_scorelines`.
4. `radar.dimensions` has 5 entries; each team vector has all 5 keys, values 5–100.
5. **Symmetry/sanity:** identical XIs for both teams on neutral ground →
   `win_a ≈ win_b` and `expected_goals_a ≈ expected_goals_b ≈ ~1.58`.
6. Home advantage: flipping `home` to team A (others equal) must **not decrease**
   team A's win probability.
7. A clearly stronger XI (top scorers) vs. a weak XI should give the stronger side
   the higher win probability.

---

## 4. Frontend `data-testid` map (for E2E)

Stable selectors are already wired in:

| testid | Element | Page |
|---|---|---|
| `logo` | brand wordmark | all |
| `nav`, `nav-overview`, `nav-explore`, `nav-predict` | nav + links | all |
| `team-select-a`, `team-select-b` | team dropdowns | /predict |
| `autopick-a`, `autopick-b` | "Auto-pick XI" buttons | /predict |
| `team-col-a`, `team-col-b` | each team's column | /predict |
| `predict-button` | "Predict result" | /predict |
| `prediction-result` | result container (appears after predict) | /predict |
| `predict-error` | error banner (negative paths) | /predict |

If you need more, add `data-testid`s in the component and note them here (see
[CONTRIBUTING.md](../CONTRIBUTING.md)).

---

## 5. Automated API tests (pytest)

In-process tests against the v1 FastAPI app — **no running server required**.

```bash
make test-e2e
# or: pip install -r e2e/requirements-dev.txt && pytest e2e -q -c e2e/pytest.ini
```

Implemented in `e2e/test_api_e2e.py` (health, overview, teams, players, matches,
predict probabilities sum to 1.0, empty XI returns 400).

CI runs the same suite on pull requests via `.github/workflows/ci.yml`.

---

## 6. Performance baseline (k6)

Establish **v1 production baselines** before the v2 refactor. Scripts live under
`k6/`; see [k6/README.md](../k6/README.md) for install steps.

**Prerequisites:** [k6](https://grafana.com/docs/k6/latest/set-up/install-k6/)
(`brew install k6` on macOS).

| Target | Command |
|--------|---------|
| Smoke (health + overview) | `make k6-smoke` |
| Full API journey + JSON report | `make k6-journey` |

Default target is production (`https://atwc26.com`). Override for local Docker:

```bash
ATWC26_BASE_URL=http://localhost:8080 make k6-smoke
ATWC26_BASE_URL=http://localhost:8080 make k6-journey
```

**Environment variables**

| Variable | Default | Purpose |
|----------|---------|---------|
| `ATWC26_BASE_URL` | `https://atwc26.com` | API origin (Makefile: `K6_BASE_URL`) |
| `ATWC26_REPORT_DIR` | `reports/` | Journey baseline JSON output directory |
| `ATWC26_K6_PAUSE_SEC` | `0.15` | Pause between API calls (production rate limit) |

`make k6-journey` writes `reports/baseline-<timestamp>.json` with aggregate
latency (`p95`), error rate, and per-endpoint timings. That file is the v1
reference for v2 A/B comparison (refactor Issue 8). Reports are gitignored.

**Typical baseline run (against production):**

```bash
make k6-smoke
make k6-journey
ls reports/baseline-*.json
```

### 6a. k6 A/B — v1 baseline vs v2 candidate (Issue 8)

Compare production (or any v1 URL) against the v2 split API stack:

```bash
make k6-ab \
  K6_BASELINE_URL=https://atwc26.com \
  K6_CANDIDATE_ANALYTICS_URL=https://xxxx.execute-api.us-east-1.amazonaws.com \
  K6_CANDIDATE_PREDICT_URL=https://xxxx.execute-api.us-east-1.amazonaws.com
```

Local candidate (split APIs on laptop — **both must be running**):

```bash
make analytics   # terminal 1 — :8001
make predict     # terminal 2 — :8000
make k6-ab \
  K6_BASELINE_URL=https://atwc26.com \
  K6_CANDIDATE_ANALYTICS_URL=http://localhost:8001 \
  K6_CANDIDATE_PREDICT_URL=http://localhost:8000
```

`compare_ab.sh` isolates env per run so v1 always hits `K6_BASELINE_URL`
(not localhost). k6 thresholds are disabled during A/B; pass/fail is
`compare_summaries.py`.

Writes:

- `reports/journey-v1-<timestamp>.json` — baseline run
- `reports/journey-v2-<timestamp>.json` — candidate run
- `reports/ab-diff-<timestamp>.json` — comparison result

**Load / stress** (single stack, no A/B):

```bash
make k6-load    # ramp to 5 VUs
make k6-stress  # ramp to 10 VUs
```

**A/B pass thresholds** (enforced by `k6/compare_summaries.py`):

| Metric | Pass rule |
|--------|-----------|
| `http_req_failed.rate` | ≤ 10% and ≤ baseline × 1.10 |
| `http_req_duration.p95` (global) | ≤ baseline × 1.25 |
| Endpoint p95 (`health`, `overview`, `teams`, `predict`) | ≤ baseline × 1.25 |

Cutover checklist: [CUTOVER.md](CUTOVER.md). CI: `.github/workflows/performance.yml` (manual dispatch).

**Environment variables (A/B)**

| Variable | Default | Purpose |
|----------|---------|---------|
| `K6_BASELINE_URL` | `https://atwc26.com` | v1 monolith for baseline journey |
| `K6_CANDIDATE_ANALYTICS_URL` | `http://localhost:8001` | v2 analytics API |
| `K6_CANDIDATE_PREDICT_URL` | `http://localhost:8000` | v2 predict API |
| `ATWC26_ANALYTICS_URL` | *(falls back to `ATWC26_BASE_URL`)* | Analytics origin in k6 scripts |
| `ATWC26_PREDICT_URL` | *(falls back to `ATWC26_BASE_URL`)* | Predict origin in k6 scripts |
| `ATWC26_K6_STACK` | `baseline` | Report filename prefix (`v1`, `v2`, …) |

---

## 7. Route-split + cache validation (v2 target)

Use this checklist to verify the TODO execution plan in a deployed candidate:

- [x] **Edge pathing:** CloudFront serves static pages and forwards `/api/*` to API Gateway (Terraform wired; smoke on deploy).
- [x] **No WAF:** candidate distribution has no attached WAF ACL.
- [x] **Service ownership:** `GET /api/winner-probabilities` on analytics (precomputed JSON); `POST /api/predict` on compute path (`tests/contract/test_split.py`).
- [x] **Data freshness:** ETL publish bumps `ATWC26_DATA_VERSION` and can trigger ECS rolling deploy when configured.
- [x] **Cache behavior:** DynamoDB API cache with local dry-run and `DataStore` fallback (`tests/etl/test_api_cache.py`).

Quick smoke commands (replace URLs as needed):

```bash
curl -fsS "$CLOUDFRONT_URL/" >/dev/null
curl -fsS "$CLOUDFRONT_URL/api/health"
curl -fsS "$CLOUDFRONT_URL/api/standings" | jq '.groups | length'
curl -fsS "$CLOUDFRONT_URL/api/winner-probabilities" | jq '.teams | length'
```

---

## 8. Suggested automation stack

| Layer | Tool | Why |
|---|---|---|
| API tests | **pytest + httpx** (or `requests`) | fast, asserts the contract above |
| Component/E2E | **Playwright** (TS or Python) | drives the real UI via `data-testid` |
| Load/perf | **k6** or **Locust** | the API is CPU-bound & cacheable; easy to load |
| CI | GitHub Actions | `ci.yml` — path-filtered on `refactor/v2-integration`; `etl.yml` / `deploy.yml` manual dispatch |

### Example: API test (pytest + httpx)
```python
# tests/test_api.py   →   pip install pytest httpx
import httpx

BASE = "http://localhost:8000"

def test_health():
    r = httpx.get(f"{BASE}/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_unknown_team_404():
    assert httpx.get(f"{BASE}/api/teams/Nowhere/players").status_code == 404

def _xi(team):
    players = httpx.get(f"{BASE}/api/teams/{team}/players").json()["players"]
    picks, need = [], {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3}
    for role, n in need.items():
        for p in [p for p in players if p["role"] == role][:n]:
            picks.append({"player_id": p["player_id"], "role": role})
    return {"team_name": team, "players": picks, "home": False}

def test_predict_probabilities_sum_to_one():
    body = {"team_a": _xi("Brazil"), "team_b": _xi("Germany")}
    d = httpx.post(f"{BASE}/api/predict", json=body).json()
    total = d["team_a"]["win_probability"] + d["team_b"]["win_probability"] + d["draw_prob"]
    assert abs(total - 1.0) < 1e-3

def test_predict_requires_players():
    body = {"team_a": {"team_name": "Brazil", "players": []},
            "team_b": {"team_name": "Germany", "players": []}}
    assert httpx.post(f"{BASE}/api/predict", json=body).status_code == 400
```

### Example: E2E test (Playwright, TypeScript)
```ts
// e2e/predict.spec.ts   →   npm i -D @playwright/test && npx playwright install
import { test, expect } from "@playwright/test";

test("build two XIs and predict a result", async ({ page }) => {
  await page.goto("http://localhost:3000/predict");

  await page.getByTestId("team-select-a").selectOption({ label: "Brazil" });
  await page.getByTestId("team-select-b").selectOption({ label: "Germany" });

  await page.getByTestId("autopick-a").click();
  await page.getByTestId("autopick-b").click();

  await page.getByTestId("predict-button").click();

  const result = page.getByTestId("prediction-result");
  await expect(result).toBeVisible();
  await expect(result).toContainText("Most likely scoreline");
});
```

---

## 9. Negative & edge cases to cover

- `POST /api/predict` with **empty** players → 400.
- Same team on both sides (UI disables Predict when `teamA === teamB`).
- Unknown `sort`/`metric` query → 400.
- Unknown team in path → 404.
- Players with **very low minutes** (cameo XI) — prediction should still return
  valid, clamped numbers (no NaN/inf in JSON).
- Switching formation (4-3-3 ↔ 3-5-2) re-shapes the XI slots without errors.
- Backend cold start: first request after boot triggers data load — health may
  lag a second; poll it.

---

## 10. Smoke checklist (manual, ~2 min)

- [ ] `/api/health` returns `200` with non-zero `players`/`teams`.
- [ ] Overview page shows KPIs, the team chart, and three leaderboards.
- [ ] Explore: filter by team + role and change sort → table updates.
- [ ] Predictor: pick two teams → Auto-pick both → Predict → result + radar show.
- [ ] Toggle home advantage → win probabilities shift accordingly.
- [ ] Footer "NeuNov Technologies" links to neunov.com.

---

## 11. Notes for reliable runs

- The dataset is **read-only** and deterministic, so tests are reproducible for a
  given `data/` snapshot. If `data/` is refreshed, exact numbers change but the
  **invariants in §3 still hold** — assert on invariants, not hard-coded values.
- Run API and E2E suites against the **same** running stack (Docker `:8080` is
  closest to production).

---

## 12. Local v2 E2E smoke path

End-to-end check for the **v2 candidate stack** on your laptop: ETL → `data/` →
split APIs → frontend (dev or static). No AWS required for the automated part.

### Automated gate (no running servers)

```bash
make e2e-v2-local
```

Runs, in order:

1. `make verify` — data artifacts present
2. `make etl-local` — transform + QA manifest
3. `make test-etl` — ETL unit tests
4. `make test-contract` — analytics/predict split boundaries

### Live UI + split APIs

```bash
# frontend/.env.local should set:
#   NEXT_PUBLIC_ANALYTICS_API_URL=http://localhost:8001
#   NEXT_PUBLIC_PREDICT_API_URL=http://localhost:8000
make dev-v2
```

Open **http://localhost:3000** — overview/matches use analytics (`:8001`);
predict page uses predict API (`:8000`).

Readiness:

```bash
curl -fs http://localhost:8001/api/health && echo "analytics OK"
curl -fs http://localhost:8000/api/health && echo "predict OK"
```

### Static frontend (mimics S3 + CloudFront)

With split APIs running (`make analytics` + `make predict` in other terminals):

```bash
make build-frontend-static-v2
make serve-frontend-static    # http://localhost:3000
```

Or override API origins (e.g. API Gateway URL after `terraform apply`):

```bash
NEXT_PUBLIC_ANALYTICS_API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com \
NEXT_PUBLIC_PREDICT_API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com \
make build-frontend-static-v2
```

**CORS:** APIs must allow the static preview origin (`http://localhost:3000`).
`make analytics` / `make predict` set `ATWC26_CORS_ORIGINS` accordingly.

### Optional: dry-run S3 publish

```bash
make etl-publish
# without ATWC26_S3_BUCKET → stages to data/.etl/publish-staging/
```

Local split APIs still read **`data/`** directly (not staging). Real S3 publish +
Lambda bootstrap is covered in [infra/README.md](../infra/README.md).

### v2 local checklist (~5 min)

- [ ] `make e2e-v2-local` passes
- [ ] `make dev-v2` — overview and matches load
- [ ] Predict page returns a result (probabilities sum ≈ 1)
- [ ] `make build-frontend-static-v2 && make serve-frontend-static` — same flows work from static bundle
- [ ] *(optional AWS)* `make etl-publish` with `ATWC26_S3_BUCKET` + `terraform apply`
