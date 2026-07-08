# AnalyseThisWC26 — common dev & ops commands.
# Run `make` or `make help` to list targets.

.DEFAULT_GOAL := help

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT         := $(CURDIR)
BACKEND_DIR  := $(ROOT)/backend
FRONTEND_DIR := $(ROOT)/frontend
ETL_DIR      := $(ROOT)/etl
SCRAPER_DIR  := $(ETL_DIR)/scrape
E2E_DIR      := $(ROOT)/e2e
K6_DIR       := $(ROOT)/k6
CORE_PKG     := $(ROOT)/packages/atwc26_core
SERVICES_DIR := $(ROOT)/services
CONTRACT_DIR := $(ROOT)/tests/contract
BUILD_SCRIPT := $(ROOT)/infra/scripts/build_frontend_static.sh
TF_DIR       := $(ROOT)/infra/terraform/envs/dev
PACKAGE_LAMBDAS := $(ROOT)/infra/scripts/package_lambdas.sh

# ── Python / backend venv ──────────────────────────────────────────────────────
PYTHON       ?= python3
PIP          ?= pip3
BACKEND_VENV := $(BACKEND_DIR)/.venv
BACKEND_PY   := $(BACKEND_VENV)/bin/python
BACKEND_PIP  := $(BACKEND_VENV)/bin/pip

# ── Local dev defaults ─────────────────────────────────────────────────────────
CORS         := http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001
V2_ANALYTICS ?= http://localhost:8001
V2_PREDICT   ?= http://localhost:8000

# ── k6 ─────────────────────────────────────────────────────────────────────────
K6_BASE_URL                  ?= https://atwc26.com
K6_BASELINE_URL              ?= https://atwc26.com
K6_CANDIDATE_ANALYTICS_URL   ?= $(V2_ANALYTICS)
K6_CANDIDATE_PREDICT_URL      ?= $(V2_PREDICT)

# ── Terraform ──────────────────────────────────────────────────────────────────
TF         ?= terraform
TF_AWS_ENV = $(if $(AWS_PROFILE),AWS_PROFILE=$(AWS_PROFILE))

.PHONY: help \
	setup setup-backend setup-frontend setup-scraper setup-etl setup-test setup-services verify \
	backend analytics predict frontend dev dev-v2 \
	test-e2e test-etl test-contract e2e-v2-local \
	etl-scrape etl-local etl-refresh etl-simulate etl-train etl-publish \
	schedule scrape scrape-force analyze events squads groups history \
	build-frontend-static build-frontend-static-v2 serve-frontend-static \
	k6-smoke k6-journey k6-load k6-stress k6-ab \
	tf-init tf-init-local tf-validate tf-package tf-plan tf-apply tf-destroy tf-output \
	up docker down restart-backend health refresh refresh-full deploy

##@ Help

help: ## List targets (grouped)
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make <target>\n"} \
		/^##@/ { printf "\n%s\n", substr($$0, 5) } \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

##@ Setup

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

verify: ## Check whether one-time setup steps are done
	@echo "venv:      $$([ -d $(BACKEND_VENV) ] && echo OK || echo MISSING)"
	@echo "backend:   $$($(BACKEND_PY) -c 'import fastapi,pyarrow,pandas' 2>/dev/null && echo OK || echo MISSING)"
	@echo "frontend:  $$([ -d $(FRONTEND_DIR)/node_modules ] && echo OK || echo MISSING)"
	@echo "env file:  $$([ -f $(FRONTEND_DIR)/.env.local ] && echo OK || echo MISSING)"
	@echo "data:      $$([ -f data/all_players_stats.parquet ] && echo OK || echo MISSING)"
	@echo "timelines: $$([ -f data/match_events.json ] && echo OK || echo MISSING)"

##@ Development

backend: setup-backend ## v1 monolith API (http://localhost:8000)
	cd $(BACKEND_DIR) && ATWC26_CORS_ORIGINS="$(CORS)" \
		$(BACKEND_PY) -m uvicorn app.main:app --reload --port 8000

analytics: setup-services ## v2 analytics API (http://localhost:8001)
	cd $(ROOT) && ATWC26_CORS_ORIGINS="$(CORS)" PYTHONPATH=$(ROOT) \
		$(BACKEND_PY) -m uvicorn analytics_api.main:app --reload --port 8001 \
		--app-dir $(SERVICES_DIR)/analytics_api

predict: setup-services ## v2 predict API (http://localhost:8000)
	cd $(ROOT) && ATWC26_CORS_ORIGINS="$(CORS)" PYTHONPATH=$(ROOT) \
		$(BACKEND_PY) -m uvicorn predict_api.main:app --reload --port 8000 \
		--app-dir $(SERVICES_DIR)/predict_api

frontend: setup-frontend ## Next.js dev server (http://localhost:3000)
	cd $(FRONTEND_DIR) && npm run dev

dev: setup ## v1 backend + frontend (Ctrl-C stops both)
	@trap 'kill 0' INT TERM; \
	$(MAKE) backend & \
	cd $(FRONTEND_DIR) && NEXT_PUBLIC_ANALYTICS_API_URL=http://localhost:8000 \
		NEXT_PUBLIC_PREDICT_API_URL=http://localhost:8000 npm run dev & \
	wait

dev-v2: setup-services setup-frontend ## Split APIs + frontend (analytics :8001, predict :8000)
	@trap 'kill 0' INT TERM; \
	$(MAKE) analytics & \
	$(MAKE) predict & \
	cd $(FRONTEND_DIR) && NEXT_PUBLIC_ANALYTICS_API_URL=$(V2_ANALYTICS) \
		NEXT_PUBLIC_PREDICT_API_URL=$(V2_PREDICT) npm run dev & \
	wait

health: ## Poll API health endpoint
	@curl -fs http://localhost:8000/api/health && echo

##@ Tests

test-e2e: setup-test ## v1 API end-to-end tests (in-process, no server)
	$(BACKEND_PY) -m pytest $(E2E_DIR) -q -c $(E2E_DIR)/pytest.ini

test-contract: setup-services setup-test ## Contract tests for split analytics + predict APIs
	cd $(ROOT) && PYTHONPATH=$(ROOT) $(BACKEND_PY) -m pytest $(CONTRACT_DIR) -q

test-etl: setup-etl ## ETL unit + QA tests
	cd $(ROOT) && PYTHONPATH=$(ROOT) $(PYTHON) -m pytest tests/etl etl/qa -q

e2e-v2-local: setup-etl setup-services ## v2 smoke: ETL + QA + contract tests (no servers)
	@$(MAKE) verify
	$(MAKE) etl-local
	$(MAKE) test-etl
	$(MAKE) test-contract
	@echo ""
	@echo "v2 local E2E checks passed."
	@echo "Next — live stack:  make dev-v2"
	@echo "Next — static CDN:  make build-frontend-static-v2 && make serve-frontend-static"

##@ ETL & scrape

schedule: ## Discover WC26 fixtures (gameId + kickoff time) from ESPN
	$(PYTHON) $(SCRAPER_DIR)/fetch_schedule.py

scrape: ## Incremental scrape from game_links.csv
	$(PYTHON) $(SCRAPER_DIR)/scrape_wc26.py

scrape-force: ## Re-scrape all games from scratch
	$(PYTHON) $(SCRAPER_DIR)/scrape_wc26.py --force

squads: ## Refresh full WC26 squad rosters
	$(PYTHON) $(SCRAPER_DIR)/scrape_squads.py

history: ## Backfill ~1yr of qualifier/friendly history (Predictor ratings only)
	$(PYTHON) $(SCRAPER_DIR)/scrape_history.py

events: ## Rebuild match timelines/momentum from data/raw/*.json
	$(PYTHON) $(ETL_DIR)/build_match_events.py

groups: ## Refresh group standings + remaining group-stage fixtures
	$(PYTHON) $(SCRAPER_DIR)/fetch_groups.py

analyze: ## Re-execute notebooks/analysis.ipynb in place
	jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb

etl-scrape: setup-scraper ## Discover fixtures + scrape ESPN → data/raw + parquet
	$(MAKE) schedule scrape events squads groups

etl-local: setup-etl ## Transform + simulate + train + QA (local manifest)
	cd $(ROOT) && $(PYTHON) -m etl.transform
	cd $(ROOT) && $(PYTHON) -m etl.simulate
ifeq ($(ATWC26_SKIP_TRAIN),1)
	@echo "etl-train: skipped (match data unchanged)"
else
	cd $(ROOT) && $(PYTHON) -m etl.train
endif
	cd $(ROOT) && $(PYTHON) -m etl.qa

etl-refresh: etl-scrape etl-local ## Scrape ESPN, then transform + simulate + train + QA

etl-simulate: setup-etl ## Offline Monte Carlo + bracket predictions → data/*.json
	cd $(ROOT) && $(PYTHON) -m etl.simulate

etl-train: setup-etl ## Train Elo, Dixon-Coles, XGBoost models
	cd $(ROOT) && $(PYTHON) -m etl.train

etl-publish: setup-etl ## Publish artifacts to S3/DynamoDB (or local staging)
	cd $(ROOT) && $(PYTHON) -m etl.publish

##@ Frontend

build-frontend-static: ## Static export (v1 monolith API URL default)
	$(BUILD_SCRIPT)

build-frontend-static-v2: ## Static export with split API URLs (local :8001/:8000 defaults)
	NEXT_PUBLIC_ANALYTICS_API_URL=$${NEXT_PUBLIC_ANALYTICS_API_URL:-$(V2_ANALYTICS)} \
	NEXT_PUBLIC_PREDICT_API_URL=$${NEXT_PUBLIC_PREDICT_API_URL:-$(V2_PREDICT)} \
	$(BUILD_SCRIPT)

serve-frontend-static: ## Serve frontend/out/ on http://localhost:3000
	@test -d $(FRONTEND_DIR)/out || (echo "Run make build-frontend-static-v2 first" && exit 1)
	npx --yes serve $(FRONTEND_DIR)/out -p 3000

##@ Performance (k6)

k6-smoke: ## Smoke test against v1 API (default: production)
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh smoke

k6-journey: ## User journey + baseline JSON in reports/
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh journey

k6-load: ## Ramped load test (5 VUs) + JSON report
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh load

k6-stress: ## Stress test (10 VUs) + JSON report
	ATWC26_BASE_URL=$(K6_BASE_URL) $(K6_DIR)/run.sh stress

k6-ab: ## A/B compare v1 baseline vs v2 candidate; writes reports/ab-diff-*.json
	ATWC26_PERF_BASELINE_URL=$(K6_BASELINE_URL) \
	ATWC26_PERF_CANDIDATE_ANALYTICS_URL=$(K6_CANDIDATE_ANALYTICS_URL) \
	ATWC26_PERF_CANDIDATE_PREDICT_URL=$(K6_CANDIDATE_PREDICT_URL) \
	$(K6_DIR)/compare_ab.sh

##@ Terraform

tf-init: ## Init (remote state when backend.hcl exists)
	@if [ -f $(TF_DIR)/backend.hcl ]; then \
		$(TF_AWS_ENV) $(TF) -chdir=$(TF_DIR) init -input=false -reconfigure -backend-config=backend.hcl; \
	else \
		echo "No $(TF_DIR)/backend.hcl — run: cp backend.hcl.example backend.hcl"; \
		$(TF) -chdir=$(TF_DIR) init -input=false -backend=false; \
	fi

tf-init-local: ## Init without remote state (validate only; resets .terraform)
	@rm -rf $(TF_DIR)/.terraform
	$(TF) -chdir=$(TF_DIR) init -input=false -backend=false

tf-validate: tf-init-local ## Validate (no AWS credentials required)
	$(TF) -chdir=$(TF_DIR) validate

tf-package: ## Package Lambda layer + analytics/predict zips
	$(PACKAGE_LAMBDAS)

tf-plan: tf-package tf-init ## Plan (packages Lambdas first)
	@test -f $(TF_DIR)/terraform.tfvars \
		|| (echo "Copy $(TF_DIR)/terraform.tfvars.example to terraform.tfvars" && exit 1)
	$(TF_AWS_ENV) $(TF) -chdir=$(TF_DIR) plan -input=false

tf-apply: tf-package tf-init ## Apply (packages Lambdas first)
	@test -f $(TF_DIR)/terraform.tfvars \
		|| (echo "Copy $(TF_DIR)/terraform.tfvars.example to terraform.tfvars" && exit 1)
	$(TF_AWS_ENV) $(TF) -chdir=$(TF_DIR) apply -input=false -auto-approve

tf-destroy: tf-init ## Tear down dev stack (prompts for confirmation)
	@test -f $(TF_DIR)/terraform.tfvars \
		|| (echo "Copy $(TF_DIR)/terraform.tfvars.example to terraform.tfvars" && exit 1)
	$(TF_AWS_ENV) $(TF) -chdir=$(TF_DIR) destroy -input=false

tf-output: tf-init ## Show stack outputs
	$(TF_AWS_ENV) $(TF) -chdir=$(TF_DIR) output

##@ Docker

up: ## Build and run full stack (http://localhost:8080)
	docker compose up --build

docker: up ## Alias for up

down: ## Stop Docker stack
	docker compose down

restart-backend: ## Reload backend after a data refresh (Docker)
	docker compose restart backend

refresh: scrape events groups restart-backend ## Scrape, rebuild timelines/standings, restart backend

refresh-full: schedule scrape events squads groups restart-backend ## Discover fixtures/squads, then refresh

deploy: ## Rebuild stack, then refresh data immediately
	docker compose up -d --build
	$(MAKE) refresh
