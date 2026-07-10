# Web application overview

Next.js 14 frontend for AnalyseThisWC26 — Overview, Explore, Match Predictor, and Standings. Shares the UI between **v1 monolith** and **v2 split API** builds; API wiring is controlled at **build time** via env vars.

| Doc | Read when… |
|-----|------------|
| [V1_TO_V2.md](V1_TO_V2.md) | Why v1 and v2 exist; migration path |
| [ops/DEPLOY.md](ops/DEPLOY.md) | Local dev, static export, AWS deploy |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Frontend conventions, `data-testid`, `lib/api.ts` |

---

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Overview — KPIs, team chart, leaderboards |
| `/explore` | Player explorer (filter, sort, pagination) |
| `/predict` | Match Predictor — build two XIs, run prediction |
| `/standings` | Group / knockout standings |

App Router: `frontend/app/<route>/page.tsx`. Navigation: `frontend/components/Nav.tsx`.

---

## API client (`frontend/lib/api.ts`)

The client supports three deployment modes:

| Mode | Env vars | Behavior |
|------|----------|----------|
| **v1 monolith** | `NEXT_PUBLIC_API_URL` | All calls to one base (e.g. `http://localhost:8000`) |
| **v2 split** | `NEXT_PUBLIC_ANALYTICS_API_URL`, `NEXT_PUBLIC_PREDICT_API_URL` | Reads → analytics; predict → predict service |
| **v2 same-origin** | `NEXT_PUBLIC_SAME_ORIGIN_API=true` | Relative `/api/*` via CloudFront (post-cutover) |

Local v2 defaults: analytics `:8001`, predict `:8000` — see `make dev-v2` and `frontend/.env.example`.

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
