# Web application overview

Next.js 14 frontend for AnalyseThisWC26 — Overview, Explore, Match Predictor, and Standings. Shares the UI between **v1 monolith** and **v2 split API** builds; API wiring is controlled at **build time** via env vars.

| Doc | Read when… |
|-----|------------|
| [V1_TO_V2.md](V1_TO_V2.md) | Why v1 and v2 exist; migration path |
| [ops/DEPLOY.md](ops/DEPLOY.md) | Local dev, static export, AWS deploy |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Frontend conventions, `data-testid`, `lib/api.ts` |
| [models/ANALYTICS.md](models/ANALYTICS.md) | Prediction engines & defaults |
| [specs/UXSPEC2.md](specs/UXSPEC2.md) | Section-nav / page-tab UX (shipped) |

---

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Overview — KPIs, **today's matches** (win probs via quick-predict), team chart, leaderboards |
| `/explore` | Player explorer (filter, sort, pagination) |
| `/predict` | Match Predictor — section tabs, build two XIs, multi-model predict (**Dixon-Coles** default), **TrackRecordPanel** |
| `/standings` | Groups + knockout — **StandingsAnchorBar** section nav (`#groups` / `#bracket`) |

App Router: `frontend/app/<route>/page.tsx`. Navigation: `frontend/components/Nav.tsx`.

### Notable UI pieces

| Component | Role |
|-----------|------|
| `TodaysMatchesWidget` | Homepage fixtures for today + quick win-probability chips (`dixon_coles` when available) |
| `PredictTabs` | In-page tabs on `/predict` (predictor / winner chart / track record) |
| `TrackRecordPanel` | Out-of-sample backtest metrics from `GET /api/backtest` (`data-testid="track-record-panel"`) |
| `StandingsAnchorBar` | Sticky section anchors on `/standings` |
| `WinnerProbabilityChart` | Title + stage reach probabilities from analytics |

Model selector default: `dixon_coles` when listed in `models_available`, else Poisson. Same rule in `frontend/lib/quickPredict.ts`.

---

## API client (`frontend/lib/api.ts`)

The client supports three deployment modes:

| Mode | Env vars | Behavior |
|------|----------|----------|
| **v1 monolith** | `NEXT_PUBLIC_API_URL` | All calls to one base (e.g. `http://localhost:8000`) |
| **v2 split** | `NEXT_PUBLIC_ANALYTICS_API_URL`, `NEXT_PUBLIC_PREDICT_API_URL` | Reads → analytics; predict / backtest / predict health → predict service |
| **v2 same-origin** | `NEXT_PUBLIC_SAME_ORIGIN_API=true` | Relative `/api/*` via CloudFront (post-cutover) |

Local v2 defaults: analytics `:8001`, predict `:8000` — see `make dev-v2` and `frontend/.env.example`.

Same-origin builds call relative `/api/backtest`, which API Gateway routes to the predict service (with `/api/predict` and `/api/predict/health`). See [ops/DEPLOY.md §7](ops/DEPLOY.md#7-v2-edge-routing-reference).

---

## Local development

**v1 (monolith API):**

```bash
# backend on :8000, then:
cd frontend && cp .env.example .env.local && npm run dev
```

**v2 (split APIs):**

```bash
make dev-v2   # starts analytics, predict, and frontend
```

**Static export preview (mimics S3 + CloudFront):**

```bash
make build-frontend-static-v2
make serve-frontend-static
```

---

## Build output

| Target | `next.config.js` mode | Output |
|--------|----------------------|--------|
| Docker Compose (v1) | `standalone` | Node server in container |
| AWS / static | `export` (via `build_frontend_static.sh`) | `frontend/out/` → S3 |

---

## Testing

- E2E selectors: [ops/TESTING.md](ops/TESTING.md) §4 (`data-testid` map)
- v2 smoke: [ops/TESTING.md §12](ops/TESTING.md#12-local-v2-e2e-smoke-path)
- Model parity / backtest: [models/V2_PARITY_TEST_PLAN.md](models/V2_PARITY_TEST_PLAN.md)
