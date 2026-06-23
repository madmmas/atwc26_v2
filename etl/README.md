# ETL — data collection (v1)

Scrapers live under `etl/scrape/`. Outputs go to `data/` at the repo root.

## Install

```bash
pip install -r etl/requirements.txt
# or: make setup-scraper
```

## Scrape

```bash
make scrape              # incremental — new links in etl/scrape/game_links.csv
make scrape-force        # re-scrape every game
make squads              # refresh data/squads_raw.json
make schedule            # discover fixtures → append new game links
```

Or directly:

```bash
python etl/scrape/scrape_wc26.py
python etl/scrape/scrape_squads.py
```

See [docs/RUN.md](../docs/RUN.md) for the full refresh workflow.
