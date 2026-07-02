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
K6_BASELINE_URL ?= https://atwc26.com
K6_CANDIDATE_ANALYTICS_URL ?= http://localhost:8001
K6_CANDIDATE_PREDICT_URL ?= http://localhost:8000
BACKEND_VENV  := $(BACKEND_DIR)/.venv
BACKEND_PY    := $(BACKEND_VENV)/bin/python
BACKEND_PIP   := $(BACKEND_VENV)/bin/pip
PYTHON        ?= python3
PIP           ?= pip3

CORE_PKG      := $(ROOT)/packages/atwc26_core
SERVICES_DIR  := $(ROOT)/services
CONTRACT_DIR  := $(ROOT)/tests/contract
BUILD_SCRIPT  := $(ROOT)/infra/scripts/build_frontend_static.sh

.PHONY: help setup setup-backend setup-frontend setup-scraper setup-test setup-etl setup-services verify \
        backend analytics predict dev dev-v2 frontend schedule scrape scrape-force analyze events squads groups \
        test-e2e test-etl test-contract e2e-v2-local etl-local etl-simulate etl-publish \
        build-frontend-static build-frontend-static-v2 serve-frontend-static \
        k6-smoke k6-journey k6-load k6-stress k6-ab \
        up docker down restart-backend health

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

setup-etl: setup-scraper ## ETL pipeline deps (atwc26_core + pytest + boto3)
	$(PIP) install -e $(CORE_PKG)
	$(PIP) install pytest boto3
	@echo "etl: OK"

setup-test: setup-backend ## pytest + httpx in backend venv
	$(BACKEND_PIP) install -r $(E2E_DIR)/requirements-dev.txt
	@$(BACKEND_PY) -c "import pytest, httpx" 2>/dev/null \
		|| (echo "Test deps missing." && exit 1)
	@echo "e2e: OK"

setup-services: setup-backend ## v2 split API deps (analytics + predict)
	$(BACKEND_PIP) install -e $(CORE_PKG)
	$(BACKEND_PIP) install -r $(SERVICES_DIR)/analytics_api/requirements.txt
	$(BACKEND_PIP) install -r $(SERVICES_DIR)/predict_api/requirements.txt
	@echo "services: OK"

test-e2e: setup-test ## Run v1 API end-to-end tests (in-process, no server)
	$(BACKEND_PY) -m pytest $(E2E_DIR) -q -c $(E2E_DIR)/pytest.ini

test-contract: setup-services setup-test ## Contract tests for split analytics + predict APIs
	cd $(ROOT) && PYTHONPATH=$(ROOT) $(BACKEND_PY) -m pytest $(CONTRACT_DIR) -q

e2e-v2-local: setup-etl setup-services ## v2 smoke: ETL + QA + contract tests (no servers)
	@$(MAKE) verify
	$(MAKE) etl-local
	$(MAKE) test-etl
	$(MAKE) test-contract
	@echo ""
	@echo "v2 local E2E checks passed."
	@echo "Next — live stack:  make dev-v2"
	@echo "Next — static CDN:  make build-frontend-static-v2 && make serve-frontend-static"

build-frontend-static: ## Static export (v1 monolith API URL default)
	$(BUILD_SCRIPT)

build-frontend-static-v2: ## Static export with split API URLs (local :8001/:8000 defaults)
	NEXT_PUBLIC_ANALYTICS_API_URL=$${NEXT_PUBLIC_ANALYTICS_API_URL:-http://localhost:8001} \
	NEXT_PUBLIC_PREDICT_API_URL=$${NEXT_PUBLIC_PREDICT_API_URL:-http://localhost:8000} \
	$(BUILD_SCRIPT)

serve-frontend-static: ## Serve frontend/out/ on http://localhost:3000 (preview static export)
	@test -d $(FRONTEND_DIR)/out || (echo "Run make build-frontend-static-v2 first" && exit 1)
	npx --yes serve $(FRONTEND_DIR)/out -p 3000

test-etl: setup-etl ## Run ETL unit + QA tests
	cd $(ROOT) && PYTHONPATH=$(ROOT) $(PYTHON) -m pytest tests/etl etl/qa -q

etl-local: setup-etl ## Transform + simulate + QA (local manifest)
	cd $(ROOT) && $(PYTHON) -m etl.transform
	cd $(ROOT) && $(PYTHON) -m etl.simulate
	cd $(ROOT) && $(PYTHON) -m etl.qa

etl-simulate: setup-etl ## Offline Monte Carlo + bracket predictions → data/*.json
	cd $(ROOT) && $(PYTHON) -m etl.simulate

etl-publish: setup-etl ## Publish artifacts to S3/DynamoDB (or local staging)
	cd $(ROOT) && $(PYTHON) -m etl.publish

k6-smoke: ## k6 smoke test against v1 API (default: production)
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh smoke

k6-journey: ## k6 user journey + baseline JSON in reports/
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh journey

k6-load: ## k6 ramped load test (5 VUs) + JSON report
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh load

k6-stress: ## k6 stress test (10 VUs) + JSON report
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh stress

k6-ab: ## A/B compare v1 baseline vs v2 candidate; writes reports/ab-diff-*.json
	ATWC26_PERF_BASELINE_URL=$(K6_BASELINE_URL) \
	ATWC26_PERF_CANDIDATE_ANALYTICS_URL=$(K6_CANDIDATE_ANALYTICS_URL) \
	ATWC26_PERF_CANDIDATE_PREDICT_URL=$(K6_CANDIDATE_PREDICT_URL) \
	$(K6_DIR)/compare_ab.sh

verify: ## Check whether one-time setup steps are done
	@echo "venv:      $$([ -d $(BACKEND_VENV) ] && echo OK || echo MISSING)"
	@echo "backend:   $$($(BACKEND_PY) -c 'import fastapi,pyarrow,pandas' 2>/dev/null && echo OK || echo MISSING)"
	@echo "frontend:  $$([ -d $(FRONTEND_DIR)/node_modules ] && echo OK || echo MISSING)"
	@echo "env file:  $$([ -f $(FRONTEND_DIR)/.env.local ] && echo OK || echo MISSING)"
	@echo "data:      $$([ -f data/all_players_stats.parquet ] && echo OK || echo MISSING)"
	@echo "timelines: $$([ -f data/match_events.json ] && echo OK || echo MISSING)"

backend: setup-backend ## Run v1 FastAPI monolith (http://localhost:8000)
	cd $(BACKEND_DIR) && ATWC26_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001" \
		$(BACKEND_PY) -m uvicorn app.main:app --reload --port 8000

analytics: setup-services ## Run v2 analytics API (http://localhost:8001)
	cd $(ROOT) && ATWC26_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001" \
		PYTHONPATH=$(ROOT) $(BACKEND_PY) -m uvicorn analytics_api.main:app --reload --port 8001 --app-dir $(SERVICES_DIR)/analytics_api

predict: setup-services ## Run v2 predict API (http://localhost:8000)
	cd $(ROOT) && ATWC26_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001" \
		PYTHONPATH=$(ROOT) $(BACKEND_PY) -m uvicorn predict_api.main:app --reload --port 8000 --app-dir $(SERVICES_DIR)/predict_api

frontend: setup-frontend ## Run Next.js dev server (http://localhost:3000)
	cd $(FRONTEND_DIR) && npm run dev

dev: setup ## Run v1 backend + frontend together (Ctrl-C stops both)
	@trap 'kill 0' INT TERM; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	wait

dev-v2: setup-services setup-frontend ## Run split APIs + frontend (analytics :8001, predict :8000)
	@trap 'kill 0' INT TERM; \
	$(MAKE) analytics & \
	$(MAKE) predict & \
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

refresh: scrape events groups restart-backend ## Scrape new games, rebuild timelines/standings/bracket, restart Docker backend

deploy: ## Rebuild + restart the stack, then immediately refresh data (instead of waiting for the next cron tick)
	docker compose up -d --build
	$(MAKE) refresh

refresh-full: schedule scrape events squads groups restart-backend ## Discover new fixtures/squads, then refresh
