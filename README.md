# AnalyseThisWC26 🌈⚽

**Interactive FIFA World Cup 2026 player & team analytics, with an AI match
predictor.** A capability demo by **[NeuNov Technologies](https://neunov.com)**.

Fans explore every player and team of the tournament, then build two custom XIs
and get a statistical match-result prediction driven by real per-90 performance.

> **New here?** Read this file top-to-bottom once. Then jump to the deep-dive doc
> for your role:
> - 🧠 **How the numbers & prediction work** → [docs/ANALYTICS.md](docs/ANALYTICS.md)
> - 👩‍💻 **Contributing / code review** → [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
> - 🧪 **QA & automation testing** → [docs/TESTING.md](docs/TESTING.md)
> - 🚀 **Deployment & ops** → [docs/DEPLOY.md](docs/DEPLOY.md)

---

## 1. What's in this repo

The project is two halves that share one dataset:

```
                 ┌──────────────────────────────────────────────┐
   ESPN JSON ──▶ │  etl/scrape/scrape_wc26.py (data pipeline)   │
   APIs          │  → data/all_players_stats.parquet           │
                 └───────────────┬──────────────────────────────┘
                                 │ reads
              ┌──────────────────┴───────────────────┐
              ▼                                       ▼
   ┌────────────────────┐                 ┌────────────────────────┐
   │ notebooks/         │                 │  Web app               │
   │ notebooks/analysis.ipynb │                 │  backend/  (FastAPI)   │
   └────────────────────┘                 │  frontend/ (Next.js)   │
                                          └────────────────────────┘
```

| Part | Folder / file | What it does |
|---|---|---|
| **Scraper** | [etl/scrape/scrape_wc26.py](etl/scrape/scrape_wc26.py) | Pulls per-player stats for each game from ESPN's JSON APIs into Parquet. |
| **Notebook** | [notebooks/analysis.ipynb](notebooks/analysis.ipynb) | Pandas starter: per-90 normalization, leaderboards. |
| **Backend** | [backend/](backend/) | FastAPI service: analytics endpoints + the prediction engine. |
| **Frontend** | [frontend/](frontend/) | Next.js UI: Overview, Explore, Match Predictor. |
| **Deploy** | [docker-compose.yml](docker-compose.yml), [deploy/](deploy/) | Containerized stack behind Nginx. |
| **Data** | [data/](data/) | Generated Parquet/CSV/JSON (the single source of truth). |

The full data-collection design (and its legal/ethical notes) lives in
[docs/RUN.md](docs/RUN.md) and [docs/ANALYTICS.md](docs/ANALYTICS.md).

---

## 2. Tech stack

| Layer | Tech | Why |
|---|---|---|
| Data pipeline | Python, pandas, pyarrow | Fast, typed columnar data (Parquet). |
| Backend API | FastAPI, Gunicorn + Uvicorn | Async, scales horizontally; reuses the pandas data. |
| Prediction | NumPy + a Poisson goals model | Transparent, explainable football analytics. |
| Frontend | Next.js 14, TypeScript, Tailwind, Recharts | Modern, fast, CDN-deployable, attractive. |
| Delivery | Docker, docker-compose, Nginx | One public origin, secure, reproducible. |

---

## 3. Prerequisites

- **Python 3.10+** (3.11 recommended; works on 3.9 with one extra package — see below)
- **Node.js 18+** (tested on 22) and npm
- **Docker** (only if you want the containerized stack)

---

## 4. Setup — one-time vs. repeated commands

> ⚠️ **Key idea:** a few commands are **run once** (or only when dependencies
> change). Everything else is a normal repeated command. The table tells you
> which is which **and how to check whether the one-time step is already done.**

### One-time (or "only when X changes") commands

| # | Command | Run it… | Already done if… (verification) |
|---|---|---|---|
| 1 | `python -m venv backend/.venv` | once | `test -d backend/.venv && echo yes` prints `yes` |
| 2 | `pip install -r backend/requirements.txt` | once, then whenever `requirements.txt` changes | `backend/.venv/bin/python -c "import fastapi, pyarrow, pandas; print('ok')"` prints `ok` |
| 3 | `pip install -r etl/requirements.txt` (scraper + notebook) | once, then on change | `python -c "import pandas, pyarrow; print('ok')"` prints `ok` |
| 4 | `npm install` (in `frontend/`) | once, then whenever `package.json` changes | `test -d frontend/node_modules && echo yes` prints `yes` |
| 5 | `cp frontend/.env.example frontend/.env.local` | once | `test -f frontend/.env.local && echo yes` prints `yes` |
| 6 | First data scrape: `make scrape` | once to bootstrap data | `ls data/all_players_stats.parquet` lists the file |

**One-shot verification of the whole setup** (copy-paste):

```bash
echo "venv:      $([ -d backend/.venv ] && echo OK || echo MISSING)"
echo "backend:   $(backend/.venv/bin/python -c 'import fastapi,pyarrow,pandas' 2>/dev/null && echo OK || echo MISSING)"
echo "frontend:  $([ -d frontend/node_modules ] && echo OK || echo MISSING)"
echo "env file:  $([ -f frontend/.env.local ] && echo OK || echo MISSING)"
echo "data:      $([ -f data/all_players_stats.parquet ] && echo OK || echo MISSING)"
```
If every line says `OK`, skip setup and go straight to **Run** below.

### Repeated commands (run any time)

| Command | Purpose |
|---|---|
| `source backend/.venv/bin/activate` | activate the backend env in a shell |
| `python -m uvicorn app.main:app --reload --port 8000` (in `backend/`) | run the API (dev) |
| `npm run dev` (in `frontend/`) | run the UI (dev) |
| `make scrape` | refresh data with newly-added game links |
| `docker compose up --build` | run the whole stack in containers |

---

## 5. Run it (local dev, two terminals)

**Terminal A — backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # one-time
pip install -r requirements.txt                     # one-time
python -m uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/api/health
```

> **Python 3.9 only:** also run `pip install eval_type_backport` once. Not needed
> on 3.10+.

**Terminal B — frontend**
```bash
cd frontend
cp .env.example .env.local      # one-time
npm install                     # one-time
npm run dev
# → http://localhost:3000
```

Open **http://localhost:3000** and try the **Match Predictor**: pick two teams,
hit **Auto-pick XI** on each, then **Predict result**.

### Or run everything with Docker
```bash
docker compose up --build       # → http://localhost:8080
```

---

## 6. Refreshing the data

The dataset grows as the tournament progresses. Add new game links and re-scrape;
the scraper is incremental (only fetches new games). Full step-by-step:
**[docs/RUN.md](docs/RUN.md)**.

```bash
make scrape                     # picks up new links in etl/scrape/game_links.csv
# restart the backend so it reloads the parquet
```

---

## 7. Branding

- Product name: **AnalyseThisWC26** (colorful typographic wordmark in
  [frontend/components/Logo.tsx](frontend/components/Logo.tsx)).
- Built by **[NeuNov Technologies](https://neunov.com)** — every "NeuNov" mention
  links to neunov.com.

---

## 8. Disclaimer

Predictions are an illustrative statistical model, **not betting advice**. Data is
collected from public tournament sources for demonstration purposes only; see the
data-source notes in [docs/RUN.md](docs/RUN.md) and [docs/ANALYTICS.md](docs/ANALYTICS.md).
