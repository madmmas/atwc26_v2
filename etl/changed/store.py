"""Persist ETL fingerprints and scrape state in DynamoDB between CI runs."""
from __future__ import annotations

import json
from pathlib import Path

from atwc26_core import config

DATASET = "wc26"
PK = f"DATASET#{DATASET}"
FINGERPRINT_SK = "FINGERPRINT"
SCRAPE_STATE_SK = "SCRAPE_STATE"


def _processed_games_path() -> Path:
    return config.DATA_DIR / "processed_games.json"

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]


def _table():
    if boto3 is None or not config.DYNAMODB_TABLE:
        return None
    return boto3.resource("dynamodb", region_name=config.AWS_REGION).Table(config.DYNAMODB_TABLE)


def load_fingerprint() -> dict[str, str] | None:
    """Return the last published fingerprint, or None when unavailable."""
    table = _table()
    if table is None:
        return None
    try:
        resp = table.get_item(Key={"PK": PK, "SK": FINGERPRINT_SK})
    except Exception:
        return None
    item = resp.get("Item") or {}
    fp = item.get("fingerprint")
    if not isinstance(fp, dict):
        return None
    return {str(k): str(v) for k, v in fp.items()}


def save_fingerprint(fp: dict[str, str]) -> bool:
    """Upsert fingerprint after a successful publish."""
    table = _table()
    if table is None or not fp:
        return False
    try:
        table.put_item(
            Item={
                "PK": PK,
                "SK": FINGERPRINT_SK,
                "dataset": DATASET,
                "fingerprint": fp,
            }
        )
    except Exception:
        return False
    print(f"saved fingerprint ({len(fp)} file(s)) -> DynamoDB")
    return True


def load_scrape_state() -> dict | None:
    """Return processed_games.json content from DynamoDB, if stored."""
    table = _table()
    if table is None:
        return None
    try:
        resp = table.get_item(Key={"PK": PK, "SK": SCRAPE_STATE_SK})
    except Exception:
        return None
    state = (resp.get("Item") or {}).get("processed_games")
    return state if isinstance(state, dict) else None


def save_scrape_state(state: dict) -> bool:
    """Persist processed_games.json for the next CI run."""
    table = _table()
    if table is None or not state:
        return False
    try:
        table.put_item(
            Item={
                "PK": PK,
                "SK": SCRAPE_STATE_SK,
                "dataset": DATASET,
                "processed_games": state,
            }
        )
    except Exception:
        return False
    print(f"saved scrape state ({len(state)} game(s)) -> DynamoDB")
    return True


def restore_scrape_state() -> bool:
    """Write processed_games.json from DynamoDB when the repo copy is stale."""
    state = load_scrape_state()
    if not state:
        return False
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _processed_games_path()
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    print(f"restored scrape state -> {path} ({len(state)} game(s))")
    return True


def read_scrape_state() -> dict:
    path = _processed_games_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
