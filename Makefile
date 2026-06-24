# AnalyseThisWC26 — common dev & ops commands.
# Run `make` or `make help` to list targets.

.DEFAULT_GOAL := help

ROOT          := $(CURDIR)
BACKEND_DIR   := $(ROOT)/backend
FRONTEND_DIR  := $(ROOT)/frontend
ETL_DIR       := $(ROOT)/etl
SCRAPER_DIR   := $(ETL_DIR)/scrape
E2E_DIR       := $(ROOT)/e2e
K6_DIR        := $(ROOT)/k6
K6_BASE_URL   ?= https://atwc26.com
BACKEND_VENV  := $(BACKEND_DIR)/.venv
BACKEND_PY    := $(BACKEND_VENV)/bin/python
BACKEND_PIP   := $(BACKEND_VENV)/bin/pip
PYTHON        ?= python3
PIP           ?= pip3

.PHONY: help setup setup-backend setup-frontend setup-scraper setup-test verify \
        backend frontend dev schedule scrape scrape-force analyze events squads groups \
        test-e2e k6-smoke k6-journey up docker down restart-backend health

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make <target>\n\nTargets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: setup-backend setup-frontend setup-scraper ## One-time install (venv, deps, env)
	@echo "Setup complete. Run 'make dev' or 'make docker'."

setup-backend: $(BACKEND_VENV)/bin/activate ## Backend venv + pip packages
	$(BACKEND_PIP) install -r $(BACKEND_DIR)/requirements.txt
	@$(BACKEND_PY) -c "import fastapi, pyarrow, pandas" 2>/dev/null \
		|| (echo "Backend deps missing." && exit 1)
	@echo "backend: OK"

$(BACKEND_VENV)/bin/activate:
	$(PYTHON) -m venv $(BACKEND_VENV)

setup-frontend: ## Frontend npm packages + .env.local
	@test -f $(FRONTEND_DIR)/.env.local \
		|| cp $(FRONTEND_DIR)/.env.example $(FRONTEND_DIR)/.env.local
	cd $(FRONTEND_DIR) && npm install
	@echo "frontend: OK"

setup-scraper: ## Root Python deps (scraper + notebook)
	$(PIP) install -r $(ROOT)/requirements.txt
	@$(PYTHON) -c "import pandas, pyarrow" 2>/dev/null \
		|| (echo "Scraper deps missing." && exit 1)
	@echo "scraper: OK"

setup-test: setup-backend ## pytest + httpx in backend venv
	$(BACKEND_PIP) install -r $(E2E_DIR)/requirements-dev.txt
	@$(BACKEND_PY) -c "import pytest, httpx" 2>/dev/null \
		|| (echo "Test deps missing." && exit 1)
	@echo "e2e: OK"

test-e2e: setup-test ## Run v1 API end-to-end tests (in-process, no server)
	$(BACKEND_PY) -m pytest $(E2E_DIR) -q -c $(E2E_DIR)/pytest.ini

k6-smoke: ## k6 smoke test against v1 API (default: production)
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh smoke

k6-journey: ## k6 user journey + baseline JSON in reports/
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh journey

verify: ## Check whether one-time setup steps are done
	@echo "venv:      $$([ -d $(BACKEND_VENV) ] && echo OK || echo MISSING)"
	@echo "backend:   $$($(BACKEND_PY) -c 'import fastapi,pyarrow,pandas' 2>/dev/null && echo OK || echo MISSING)"
	@echo "frontend:  $$([ -d $(FRONTEND_DIR)/node_modules ] && echo OK || echo MISSING)"
	@echo "env file:  $$([ -f $(FRONTEND_DIR)/.env.local ] && echo OK || echo MISSING)"
	@echo "data:      $$([ -f data/all_players_stats.parquet ] && echo OK || echo MISSING)"
	@echo "timelines: $$([ -f data/match_events.json ] && echo OK || echo MISSING)"

backend: setup-backend ## Run FastAPI dev server (http://localhost:8000)
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m uvicorn app.main:app --reload --port 8000

frontend: setup-frontend ## Run Next.js dev server (http://localhost:3000)
	cd $(FRONTEND_DIR) && npm run dev

dev: setup ## Run backend + frontend together (Ctrl-C stops both)
	@trap 'kill 0' INT TERM; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	wait

schedule: ## Discover WC26 fixtures (gameId + kickoff time) from ESPN
	$(PYTHON) $(SCRAPER_DIR)/fetch_schedule.py

scrape: ## Incremental scrape from game_links.csv
	$(PYTHON) $(SCRAPER_DIR)/scrape_wc26.py

scrape-force: ## Re-scrape all games from scratch
	$(PYTHON) $(SCRAPER_DIR)/scrape_wc26.py --force

analyze: ## Re-execute notebooks/analysis.ipynb in place
	jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb

events: ## Rebuild match timelines/momentum from data/raw/*.json
	$(PYTHON) $(ETL_DIR)/build_match_events.py

squads: ## Refresh full WC26 squad rosters (incl. players who haven't played)
	$(PYTHON) $(SCRAPER_DIR)/scrape_squads.py

history: ## Backfill ~1yr of qualifier/friendly history (Predictor ratings only)
	$(PYTHON) $(SCRAPER_DIR)/scrape_history.py

groups: ## Refresh group standings + remaining group-stage fixtures
	$(PYTHON) $(SCRAPER_DIR)/fetch_groups.py

up: ## Build and run full stack via Docker (http://localhost:8080)
	docker compose up --build

docker: up

down: ## Stop Docker stack
	docker compose down

restart-backend: ## Reload backend after a data refresh (Docker)
	docker compose restart backend

health: ## Poll API health endpoint
	@curl -fs http://localhost:8000/api/health && echo

refresh: scrape events restart-backend ## Scrape new games, rebuild timelines, restart Docker backend

refresh-full: schedule scrape events squads groups restart-backend ## Discover new fixtures/squads/groups, then refresh
