# ETL — data collection and v2 publish pipeline

Scrapers live under `etl/scrape/`. Post-scrape transforms live under `etl/transform/`.
Monte Carlo + bracket path simulation live under `etl/simulate/`. QA checks live under
`etl/qa/`. AWS publish lives under `etl/publish/`.

Outputs go to `data/` at the repo root. Transform writes a manifest to `data/.etl/manifest.json`.

Shared logic (`DataStore`, prediction, tournament) is in `packages/atwc26_core/` (extracted from `backend/app/`).

## Install

```bash
pip install -r requirements.txt
pip install -e packages/atwc26_core
# or from repo root:
make setup-etl
```

## Makefile targets

### v1 scrape / refresh

```bash
make schedule            # discover fixtures → data/schedule.json + game_links.csv
make scrape              # incremental — new links in etl/scrape/game_links.csv
make scrape-force        # re-scrape every game
make squads              # refresh data/squads_raw.json
make events              # rebuild data/match_events.json from data/raw/
make history             # backfill qualifier/friendly history (manual)
make groups              # refresh standings + bracket
```

### v2 transform / QA / publish

```bash
make etl-local           # transform + simulate + train + QA (writes data/.etl/manifest.json)
make etl-scrape          # discover fixtures + scrape ESPN → data/raw + parquet
make etl-refresh         # scrape ESPN, then etl-local (full local refresh)
make etl-simulate        # Monte Carlo + bracket predictions → JSON artifacts
make etl-train           # Elo + Dixon-Coles (L2) + XGBoost + backtest summary
make etl-publish         # upload to S3 + DynamoDB + API cache (or local staging)
make test-etl            # pytest tests/etl etl/qa -q
```

`etl-local` runs transform, then **simulate ∥ train** where the Makefile parallelizes, then QA.
Transform rebuilds match timelines, precomputes player/team profiles, and records SHA-256
hashes. Simulate runs the tournament MC (10k locally / 1k in CI). Train writes model
artifacts and `backtest_summary.json`.

## Pipeline layout

| Stage | Module | Purpose |
|-------|--------|---------|
| Scrape | `etl/scrape/` | ESPN fixtures, per-game stats, squads, history |
| Transform | `etl/transform/` | Profiles, derived artifacts + manifest |
| Simulate | `etl/simulate/` | MC winner probs (+ stage_probabilities) + bracket path |
| Train | `etl/train/` + `etl/eval/` | Elo, Dixon-Coles, XGBoost + chronological backtest |
| QA | `etl/qa/` | Validate parquet/JSON + `DataStore` load |
| Publish | `etl/publish/` | S3 upload + DynamoDB manifest + API cache |

## Artifacts

| File | Required | Kind |
|------|----------|------|
| `data/all_players_stats.parquet` | yes | master player stats |
| `data/match_events.json` | yes | timelines + momentum |
| `data/historical_form.parquet` | no | predictor history |
| `data/squads_raw.json` | no | full squads |
| `data/standings.json` | no | group standings |
| `data/bracket.json` | no | knockout bracket |
| `data/glossary.csv` | no | column glossary |
| `data/team_flags.json` | no | flag URLs |
| `data/player_profiles.parquet` | no | precomputed per-90 player profiles |
| `data/team_profiles.parquet` | no | precomputed team aggregates |
| `data/winner_probabilities.json` | no | offline Monte Carlo (title + stage_probabilities) |
| `data/bracket_predictions.json` | no | deterministic bracket path |
| `data/elo_ratings.json` | no | Elo ratings (train) |
| `data/dc_params.json` | no | Dixon-Coles params, L2-fitted (train) |
| `data/xgb_model.ubj` / `xgb_features.json` | no | XGBoost model + feature list (train) |
| `data/backtest_summary.json` | no | Hold-out metrics for Track Record (train/eval; published via `ARTIFACTS`) |
| `data/schedule.json` | no | fixture schedule |

Canonical registry: `packages/atwc26_core/atwc26_core/artifacts.py` (`ARTIFACTS`).

## Useful env vars

| Var | Effect |
|-----|--------|
| `ATWC26_SKIP_TRAIN=1` | Skip train step (set by `etl.yml` when only bracket/standings changed) |
| `ATWC26_SKIP_MATCH_EVENTS=1` | Skip rebuilding match events inside transform (`etl-local` sets this) |
| `ATWC26_SIMULATE_TRIALS` | Monte Carlo trial count (CI often `1000`) |
| `ATWC26_S3_BUCKET` / `ATWC26_S3_PREFIX` | Publish target (unset → local staging) |
| `ATWC26_DYNAMODB_TABLE` | Manifest + API cache table |

Transform also **early-exits** when the scrape fingerprint matches the last published remote fingerprint (`etl/changed/detect.py`) — no separate skip-transform env.

## S3 keys

Published objects use prefix `ATWC26_S3_PREFIX` (default `data`). Examples of keys that **are** in `ARTIFACTS` (uploaded when present and changed):

```
s3://<bucket>/data/all_players_stats.parquet
s3://<bucket>/data/match_events.json
s3://<bucket>/data/player_profiles.parquet
s3://<bucket>/data/team_profiles.parquet
s3://<bucket>/data/winner_probabilities.json
s3://<bucket>/data/bracket_predictions.json
s3://<bucket>/data/elo_ratings.json
s3://<bucket>/data/dc_params.json
s3://<bucket>/data/xgb_model.ubj
s3://<bucket>/data/xgb_features.json
s3://<bucket>/data/backtest_summary.json
s3://<bucket>/data/standings.json
s3://<bucket>/data/bracket.json
s3://<bucket>/data/schedule.json
…
```

`backtest_summary.json` is written by train and published via `ARTIFACTS`.

Set `ATWC26_S3_BUCKET` and AWS credentials before `make etl-publish`. Without a bucket, publish stages files under `data/.etl/publish-staging/`.

## DynamoDB manifest schema

Table: `ATWC26_DYNAMODB_TABLE` (default `atwc26-data-manifest`).

| Attribute | Type | Description |
|-----------|------|-------------|
| `PK` | String | `DATASET#wc26` |
| `SK` | String | `PUBLISH#<timestamp>` or `LATEST` |
| `dataset` | String | `wc26` |
| `published_at` | String | ISO-8601 UTC |
| `s3_bucket` | String | target bucket |
| `s3_prefix` | String | key prefix (default `data`) |
| `artifacts` | Map | per-artifact `{ s3_key, sha256, bytes, kind }` |
| `git_sha` | String | optional CI commit |
| `latest_publish_sk` | String | on `LATEST` row only |

Publish is **idempotent**: artifacts whose `sha256` matches the `LATEST` record are skipped on upload.

When new artifacts are uploaded:

- With `ATWC26_LAMBDA_ANALYTICS_NAME` / `ATWC26_LAMBDA_PREDICT_NAME` set, publish bumps `ATWC26_DATA_VERSION` on those Lambdas to force fresh containers.
- With `ATWC26_ECS_CLUSTER` + `ATWC26_ECS_SERVICES` set, publish triggers a rolling ECS deployment on those services.

## DynamoDB API cache schema

Table: same as manifest (`ATWC26_DYNAMODB_TABLE`).

| SK | Payload |
|----|---------|
| `API#standings` | `{ "groups": ... }` |
| `API#teams` | `{ "teams": [...] }` |
| `API#team#{name}` | `{ "team_name", "players": [...] }` |
| `API#matches` | `{ "matches": [...] }` |
| `API#match#{game_id}` | match detail object |
| `API#player#{player_id}` | player detail object |

Each item includes `published_at`, `source_artifacts`, `source_sha256`, and `payload`.
Local dry-run writes JSON files under `data/.etl/api-cache/` when `ATWC26_S3_BUCKET` is unset.

Read path (analytics Lambda):

1. in-memory cache (warm container)
2. DynamoDB API item
3. S3/local artifact fallback via `DataStore`

## Scripts (direct)

```bash
python -m etl.transform
python -m etl.qa
python -m etl.publish
python etl/build_match_events.py
```

## CI

`.github/workflows/etl.yml` is triggered by `workflow_dispatch` (manual or AWS Lambda scheduler). It runs scrape → transform → **simulate ∥ train** → QA → publish with fingerprint-based skip logic (`ATWC26_SKIP_TRAIN=1` when only bracket/standings changed). Manual runs can opt out with **skip_scrape** or **skip_publish**.

**Docs:** [docs/etl/OVERVIEW.md](../docs/etl/OVERVIEW.md) · [docs/etl/SCHEDULER.md](../docs/etl/SCHEDULER.md) · [docs/etl/PIPELINE.md](../docs/etl/PIPELINE.md)

See [docs/ops/RUN.md](../docs/ops/RUN.md) for the full v1 refresh workflow.
