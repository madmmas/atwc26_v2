# ETL — data collection (v1)

Scrapers live under `etl/scrape/`. Post-scrape transforms live under `etl/`.
Outputs go to `data/` at the repo root.

## Install

```bash
pip install -r requirements.txt
# or from repo root: make setup-scraper
```

## Makefile targets

```bash
make schedule            # discover fixtures → data/schedule.json + game_links.csv
make scrape              # incremental — new links in etl/scrape/game_links.csv
make scrape-force        # re-scrape every game
make squads              # refresh data/squads_raw.json
make events              # rebuild data/match_events.json from data/raw/
make history             # backfill qualifier/friendly history (manual)
```

## Scripts

| Script | Purpose |
|--------|---------|
| `etl/scrape/fetch_schedule.py` | Discover WC26 fixtures from ESPN |
| `etl/scrape/scrape_wc26.py` | Per-player stats for each game |
| `etl/scrape/scrape_squads.py` | Full squad rosters |
| `etl/scrape/scrape_history.py` | Qualifier/friendly backfill for Predictor |
| `etl/build_match_events.py` | Match timelines + momentum from raw JSON |

Or run directly:

```bash
python etl/scrape/fetch_schedule.py
python etl/scrape/scrape_wc26.py
python etl/scrape/scrape_squads.py
python etl/scrape/scrape_history.py --help
python etl/build_match_events.py
```

See [docs/RUN.md](../docs/RUN.md) for the full refresh workflow.
