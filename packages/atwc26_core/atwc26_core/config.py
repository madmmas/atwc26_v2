"""Runtime configuration shared by ETL, backend, and Lambda services."""
from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DATA = _REPO_ROOT / "data"
DATA_DIR = Path(os.getenv("ATWC26_DATA_DIR", str(_DEFAULT_DATA)))

MASTER_PARQUET = DATA_DIR / "all_players_stats.parquet"
GLOSSARY_CSV = DATA_DIR / "glossary.csv"
TEAM_FLAGS = DATA_DIR / "team_flags.json"
MATCH_EVENTS = DATA_DIR / "match_events.json"
SQUADS_RAW = DATA_DIR / "squads_raw.json"
HISTORICAL_FORM = DATA_DIR / "historical_form.parquet"
STANDINGS = DATA_DIR / "standings.json"
BRACKET = DATA_DIR / "bracket.json"
PLAYER_PROFILES = DATA_DIR / "player_profiles.parquet"
TEAM_PROFILES = DATA_DIR / "team_profiles.parquet"
WINNER_PROBABILITIES = DATA_DIR / "winner_probabilities.json"
BRACKET_PREDICTIONS = DATA_DIR / "bracket_predictions.json"
ELO_RATINGS = DATA_DIR / "elo_ratings.json"
DC_PARAMS = DATA_DIR / "dc_params.json"
XGB_MODEL = DATA_DIR / "xgb_model.ubj"
XGB_FEATURES = DATA_DIR / "xgb_features.json"
BACKTEST_SUMMARY = DATA_DIR / "backtest_summary.json"
SCHEDULE = DATA_DIR / "schedule.json"
RELOAD_SECRET = os.getenv("ATWC26_RELOAD_SECRET", "")

# S3 publish targets (v2 ETL)
S3_BUCKET = os.getenv("ATWC26_S3_BUCKET", "")
S3_PREFIX = os.getenv("ATWC26_S3_PREFIX", "data").strip("/")
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

# DynamoDB manifest table for published artifact metadata
DYNAMODB_TABLE = os.getenv("ATWC26_DYNAMODB_TABLE", "atwc26-data-manifest")

# Comma-separated list of allowed CORS origins for the frontend API.
CORS_ORIGINS = os.getenv(
    "ATWC26_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")


def use_cors_middleware() -> bool:
    """Use FastAPI CORS locally; skip on Lambda where API Gateway already adds ACAO headers."""
    flag = os.getenv("ATWC26_CORS_MIDDLEWARE", "auto").lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    return not bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

APP_NAME = "AnalyseThisWC26"
APP_VERSION = "1.0.0"
