"""Runtime configuration for the AnalyseThisWC26 backend."""
from __future__ import annotations

import os
from pathlib import Path

# The scraped dataset lives one level above the backend folder by default,
# but can be overridden for containerised deploys via ATWC26_DATA_DIR.
_DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data"
DATA_DIR = Path(os.getenv("ATWC26_DATA_DIR", str(_DEFAULT_DATA)))

MASTER_PARQUET = DATA_DIR / "all_players_stats.parquet"
GLOSSARY_CSV = DATA_DIR / "glossary.csv"
TEAM_FLAGS = DATA_DIR / "team_flags.json"
MATCH_EVENTS = DATA_DIR / "match_events.json"
SQUADS_RAW = DATA_DIR / "squads_raw.json"

# Comma-separated list of allowed CORS origins for the frontend.
CORS_ORIGINS = os.getenv(
    "ATWC26_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

APP_NAME = "AnalyseThisWC26"
APP_VERSION = "1.0.0"
