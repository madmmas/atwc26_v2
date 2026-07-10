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
make etl-local           # transform + simulate + QA (writes data/.etl/manifest.json)
make etl-scrape          # discover fixtures + scrape ESPN → data/raw + parquet
make etl-refresh         # scrape ESPN, then etl-local (full local refresh)
make etl-simulate        # Monte Carlo + bracket predictions → JSON artifacts
make etl-publish         # upload to S3 + DynamoDB + API cache (or local staging)
make test-etl            # pytest tests/etl etl/qa -q
```

`etl-local` runs `python -m etl.transform`, `python -m etl.simulate`, then `python -m etl.qa`.
Transform rebuilds match timelines, precomputes player/team profiles, and records SHA-256
hashes. Simulate runs the 10k-trial tournament MC in GHA (not in Lambda/ECS).

## Pipeline layout

| Stage | Module | Purpose |
|-------|--------|---------|
| Scrape | `etl/scrape/` | ESPN fixtures, per-game stats, squads, history |
| Transform | `etl/transform/` | Profiles, derived artifacts + manifest |
| Simulate | `etl/simulate/` | 10k MC winner probs + bracket predictions (GHA) |
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
| `data/winner_probabilities.json` | no | offline Monte Carlo output |
| `data/bracket_predictions.json` | no | deterministic bracket path |
| `data/elo_ratings.json` | no | Elo ratings |
| `data/dc_params.json` | no | Dixon-Coles params |
| `data/xgb_model.ubj` / `xgb_features.json` | no | XGBoost model |
| `data/backtest_summary.json` | no | hold-out track-record metrics |

## S3 keys

Published objects use prefix `ATWC26_S3_PREFIX` (default `data`):

```
s3://<bucket>/data/all_players_stats.parquet
s3://<bucket>/data/match_events.json
s3://<bucket>/data/historical_form.parquet
s3://<bucket>/data/squads_raw.json
s3://<bucket>/data/standings.json
s3://<bucket>/data/bracket.json
s3://<bucket>/data/glossary.csv
s3://<bucket>/data/team_flags.json
```

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

`.github/workflows/etl.yml` is triggered by `workflow_dispatch` (manual or AWS Lambda scheduler). It runs scrape → transform → publish with fingerprint-based skip logic. Manual runs can opt out with **skip_scrape** or **skip_publish**.

**Docs:** [docs/etl/OVERVIEW.md](../docs/etl/OVERVIEW.md) · [docs/etl/SCHEDULER.md](../docs/etl/SCHEDULER.md) · [docs/etl/PIPELINE.md](../docs/etl/PIPELINE.md)

See [docs/ops/RUN.md](../docs/ops/RUN.md) for the full v1 refresh workflow.
