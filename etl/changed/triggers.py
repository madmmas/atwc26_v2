"""DynamoDB records for match-based ETL scheduler state."""
from __future__ import annotations

from datetime import datetime, timezone

from atwc26_core import config

ETL_TRIGGER_PK = "ETL_TRIGGER#wc26"


def game_done_key(game_id: str) -> str:
    return f"{game_id}#DONE"


try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]


def _table():
    if boto3 is None or not config.DYNAMODB_TABLE:
        return None
    return boto3.resource("dynamodb", region_name=config.AWS_REGION).Table(config.DYNAMODB_TABLE)


def mark_games_finished(game_ids: set[str] | frozenset[str]) -> bool:
    """Stop future scheduler slots for games whose match data was published."""
    table = _table()
    if table is None or not game_ids:
        return False
    now = datetime.now(timezone.utc).isoformat()
    try:
        for game_id in sorted(game_ids):
            table.put_item(
                Item={
                    "PK": ETL_TRIGGER_PK,
                    "SK": game_done_key(str(game_id)),
                    "game_id": str(game_id),
                    "finished_at": now,
                }
            )
    except Exception:
        return False
    print(f"marked {len(game_ids)} game trigger(s) finished -> DynamoDB")
    return True


def is_game_finished(game_id: str) -> bool:
    table = _table()
    if table is None:
        return False
    try:
        resp = table.get_item(Key={"PK": ETL_TRIGGER_PK, "SK": game_done_key(str(game_id))})
    except Exception:
        return False
    return bool(resp.get("Item"))


def trigger_still_needed(game_id: str) -> bool:
    """Return False when the scheduler should not run ETL for this game."""
    if not str(game_id).strip():
        return True
    return not is_game_finished(str(game_id))
