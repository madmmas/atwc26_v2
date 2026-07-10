# AnalyseThisWC26 🏟️

An interactive **FIFA World Cup 2026 analytics** web app — a capability demo for
**[NeuNov Technologies](https://neunov.com)**. Fans explore every player and team
of the tournament and build two custom XIs to get an **AI match-result
prediction** from real per-90 performance.

Built on the dataset produced by [`etl/scrape/scrape_wc26.py`](../etl/scrape/scrape_wc26.py).

> 📚 **This is the web-app reference.** For the whole project start at
> **[README.md](../README.md)**. Deep dives: **[models/ANALYTICS.md](models/ANALYTICS.md)** (the
> model), **[CONTRIBUTING.md](CONTRIBUTING.md)** (dev/review),
> **[ops/TESTING.md](ops/TESTING.md)** (QA), **[ops/DEPLOY.md](ops/DEPLOY.md)** (ops).

## Features

- **Overview** — tournament KPIs, team xG/xGA chart, and live leaderboards
  (top scorers, sharpest finishers by xG/90, top creators by xA/90).
- **Explore** — filter the full player pool by team & role, sort by any of
  ~9 headline metrics.
- **Match Predictor** (the marquee) — pick two teams, choose a formation
  (4-3-3 / 4-4-2 / 3-5-2 / 4-2-3-1), build an XI per slot (or **Auto-pick XI**),
  toggle home advantage, and get:
  - win / draw / win probabilities,
  - most-likely scoreline + expected goals,
  - a 5-axis team **radar** (attack, creativity, possession, defense, GK),
  - key contributing players, and a plain-English narrative.

## How the prediction engine works

A transparent, player-driven **Poisson goals model** (the football-analytics
standard):

1. Each selected XI is aggregated into **role-weighted attack and defense
   ratings** plus a **goalkeeping** factor, from per-90 xG/xA and defensive
   actions. Ratings are normalised so an average tournament XI ≈ 1.0.
2. Expected goals for each side:
   `λ = avg_goals × attack_self / defense_opp / gk_opp × home`.
3. The independent-Poisson score matrix gives win/draw/loss, the most-likely
   score, and the scoreline distribution.

It reflects **this tournament's** form because every input is a player's per-90
output from the scraped data. See [`backend/app/prediction.py`](backend/app/prediction.py).

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, Recharts |
| Backend | FastAPI, Gunicorn + Uvicorn workers, pandas/pyarrow |
| Data | Parquet (from `etl/scrape/scrape_wc26.py`), cached in memory |
| Delivery | Docker, docker-compose, Nginx reverse proxy |

## Quick start

```bash
# Backend (virtualenv recommended — see README §4)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend && cp .env.example .env.local && npm install && npm run dev
# open http://localhost:3000
```

Or the whole stack via Docker (see **[ops/DEPLOY.md](ops/DEPLOY.md)**):
```bash
docker compose up --build      # http://localhost:8080
```

## API surface

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | liveness + dataset counts |
| `GET /api/overview` | KPIs, teams, leaderboards |
| `GET /api/teams` | team table |
| `GET /api/teams/{team}/players` | roster with per-90 stats |
| `GET /api/players?team=&role=&sort=&limit=` | filtered players |
| `GET /api/leaderboard?metric=&role=&min_minutes=` | metric leaders |
| `POST /api/predict` | match prediction from two XIs |

## Project layout

```
backend/   FastAPI app (data layer, prediction engine, API)
frontend/  Next.js app (overview, explore, predict)
deploy/    nginx.conf
docker-compose.yml, [ops/DEPLOY.md](ops/DEPLOY.md)
data/      parquet dataset (from etl/scrape/scrape_wc26.py)
```

> **Demo disclaimer:** predictions are a statistical model for illustration, not
> betting advice. Data is from public tournament sources for demonstration only.
