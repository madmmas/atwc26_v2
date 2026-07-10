"""Shared helpers for API health / freshness metadata."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from atwc26_core import config


def _iso_from_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _iso_from_json_generated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        value = data.get("generated_at")
        return str(value) if value else None
    except Exception:
        return None


def data_updated_at() -> str | None:
    """Newest known data timestamp across key artifacts."""
    candidates: list[str] = []
    for path, reader in (
        (config.DC_PARAMS, _iso_from_json_generated_at),
        (config.ELO_RATINGS, _iso_from_json_generated_at),
        (config.BACKTEST_SUMMARY, _iso_from_json_generated_at),
        (config.WINNER_PROBABILITIES, _iso_from_json_generated_at),
        (config.MASTER_PARQUET, _iso_from_mtime),
        (config.PLAYER_PROFILES, _iso_from_mtime),
    ):
        stamp = reader(path)
        if stamp:
            candidates.append(stamp)
    if not candidates:
        return None
    return max(candidates)
