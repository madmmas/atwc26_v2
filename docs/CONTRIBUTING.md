# CONTRIBUTING.md — Developer & reviewer guide

Welcome 👋 This guide gets you from a fresh clone to making a reviewed change.
Read [README.md](../README.md) first for the big picture,
[models/ANALYTICS.md](models/ANALYTICS.md) for how the model works, and
[V1_TO_V2.md](V1_TO_V2.md) if you are working on the v2 split stack.

---

## 1. Get set up

Follow the **one-time setup** in [README.md §4](../README.md#4-setup--one-time-vs-repeated-commands).
Short version:

```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# frontend
cd ../frontend && cp .env.example .env.local && npm install
```

Run both in dev (two terminals) — **v1 monolith**:
```bash
# backend/  →  python -m uvicorn app.main:app --reload --port 8000
# frontend/ →  npm run dev
```

**v2 split APIs** (analytics + predict): `make dev-v2` — see [ops/DEPLOY.md §3](ops/DEPLOY.md#3-local--v2-split-apis).

### CI and AWS (most contributors can skip this)

- **Normal PRs:** push your branch and open a PR — the **CI** workflow runs automatically (tests, build, validate). You do not need GitHub secrets or AWS access.
- **AWS / deploy setup** is for **repo maintainers** only: [ops/GITHUB_ACTIONS.md](ops/GITHUB_ACTIONS.md) (what to run and when), [`infra/README.md`](../infra/README.md) (secret names), [specs/PRODUCTION_SPEC.md](specs/PRODUCTION_SPEC.md) Part 1 (first-time bootstrap).

---

## 2. Project structure (what lives where)

```
backend/                    # v1 monolith API (production v1)
services/
  analytics_api/            # v2 read API
  predict_api/              # v2 predict API
  shared/                   # bootstrap, cache reader, S3 sync
packages/atwc26_core/       # shared DataStore, engines, artifacts (v2 + ETL)

frontend/
  app/
    layout.tsx      root layout, nav, footer, metadata
    page.tsx        Overview (KPIs, team chart, leaderboards)
    explore/page.tsx   Player explorer (filter/sort table)
    predict/page.tsx   Match Predictor (XI builder)  ← the marquee feature
    globals.css     Tailwind layers + theme helpers (.card, .btn, role chips)
  components/
    Nav.tsx, Logo.tsx, ui.tsx, PredictionResult.tsx
  lib/api.ts        typed API client + all response types
  tailwind.config.ts, next.config.js, tsconfig.json

deploy/nginx.conf   reverse proxy (routes /api → backend, / → frontend)
docker-compose.yml  full stack
data/               generated dataset (do not hand-edit)
etl/scrape/         data pipeline scrapers (see [ops/RUN.md](ops/RUN.md))
notebooks/          analysis and data QA notebooks
docs/               project documentation
```

**Data flow (v1):** `etl/scrape/scrape_wc26.py` → `data/*.parquet` → `backend/app/data.py` → `main.py` → `lib/api.ts` → React pages.

**Data flow (v2):** ETL publish → S3/DynamoDB → `services/*_api` (+ `atwc26_core`) → `lib/api.ts` → React pages. See [V1_TO_V2.md](V1_TO_V2.md).

---

## 3. Conventions

### Python (backend)
- **Type hints + short docstrings** on public functions (match the existing style).
- Keep heavy work **out of request handlers** — precompute in `DataStore` at
  startup and cache. Endpoints should be thin.
- All stat columns must be coerced numeric; never trust raw dtypes.
- Tunable model numbers belong in **named constants** at the top of
  `prediction.py`, never inline magic numbers.
- Run/format: the code targets standard PEP 8; keep functions small.

### TypeScript / React (frontend)
- **Server components by default**; add `"use client"` only when you need state or
  effects (the data pages need it because they fetch in the browser).
- All API calls go through **`lib/api.ts`** (typed). Don't `fetch` ad-hoc in
  components.
- Styling is **Tailwind utility classes** + the shared helpers in `globals.css`
  (`.card`, `.btn-primary`, `.chip`, `role-*`). Reuse them; avoid one-off CSS.
- Keep components small and presentational; data-shaping lives in the page or the
  API client.
- Add a **`data-testid`** to any new interactive element (buttons, selects,
  result containers) so QA automation stays stable — see existing ones in
  `predict/page.tsx`.

---

## 4. Common tasks (recipes)

### Add a new analytics metric to the API
1. Ensure the stat column exists in the parquet (it's one of the ~140 scraped
   fields). If it needs per-90, add its name to the relevant list in
   `data.py` (`ATTACK_STATS` / `DEFENSE_STATS` / …).
2. It's now available on player profiles automatically (`<stat>_p90`).
3. Surface it: it already works via `GET /api/leaderboard?metric=<stat>_p90` and
   `GET /api/players?sort=<stat>_p90`.

### Add a new API endpoint
1. Add the route in `main.py` (use `get_store()` for data).
2. Wrap the return in `_clean(...)` so `NaN/inf` become `null`.
3. Add a typed method + types in `frontend/lib/api.ts`.

### Add a new frontend page
1. Create `frontend/app/<name>/page.tsx` (App Router = folder-based).
2. Add a link in `components/Nav.tsx` (`links` array) with a `data-testid`.
3. Fetch via `lib/api.ts`.

### Change the prediction model
- **Poisson XI weights:** edit named constants in
  `packages/atwc26_core/atwc26_core/prediction.py` (or v1 `backend/app/prediction.py`) —
  documented in [models/ANALYTICS.md §8](models/ANALYTICS.md#8-tuning-guide-for-contributors).
- **Dixon-Coles / Elo / XGBoost:** change training in `etl/train/`, then `make etl-train`.
  Primary API/UI order is `PRIMARY_MODEL_ORDER` in `services/predict_api`.
- Re-run prediction + train tests (probabilities must sum to 1.0; see
  [models/V2_PARITY_TEST_PLAN.md](models/V2_PARITY_TEST_PLAN.md)).

### Frontend surfaces worth knowing
- Homepage: `TodaysMatchesWidget` (today's fixtures + quick-predict).
- Predict: `PredictTabs`, `TrackRecordPanel`, model select (`predict-model-select`).
- Standings: `StandingsAnchorBar` section anchors.

---

## 5. Git workflow

- Branch from `main`:
  `feature/<short-name>`, `fix/<short-name>`, or `docs/<short-name>`.
- **Conventional Commits**: `feat: …`, `fix: …`, `docs: …`, `refactor: …`,
  `test: …`, `chore: …`.
- Keep PRs focused and small. Include **what** and **why** in the description.
- Before opening a PR, run the **PR checklist** below.

### PR checklist (author)
- [ ] `cd frontend && npm run build` passes (type-check + build).
- [ ] Backend imports & serves: `python -m uvicorn app.main:app --port 8000` and
      `GET /api/health` is `200`.
- [ ] New endpoints have types in `lib/api.ts`.
- [ ] New interactive UI has `data-testid`s.
- [ ] Docs updated if behavior/model/API changed (`docs/`, README).
- [ ] No secrets, no large data files committed (`data/` is generated).

### Review checklist (reviewer)
- [ ] Logic matches [models/ANALYTICS.md](models/ANALYTICS.md); model constants are named, not
      inline.
- [ ] Request handlers stay thin; expensive work is cached in `DataStore`.
- [ ] Frontend uses `lib/api.ts` and shared Tailwind helpers.
- [ ] Naming/readability consistent with surrounding code.
- [ ] Error/edge cases handled (empty selection, unknown team, NaN values).

---

## 6. Gotchas

- **Multiple Pythons on macOS.** `pip`/packages are per-interpreter. Always work
  inside `backend/.venv` so uvicorn and your packages match. (The original "no
  module named pyarrow" error was exactly this.)
- **Parquet needs `pyarrow`** — it's in `requirements.txt`; if the API can't read
  data, that's usually a wrong/!activated env.
- **`NEXT_PUBLIC_API_URL`** is baked at **build** time into the client bundle.
  Empty string = same-origin (behind Nginx); a URL = direct to the backend.
- **The backend caches the parquet at startup** — after re-scraping, **restart**
  the backend to see new data.
- Python 3.9 needs `eval_type_backport`; 3.10+ does not.
