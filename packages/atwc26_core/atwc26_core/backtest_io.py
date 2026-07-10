"""Read/write ``backtest_summary.json`` (safe for predict Lambda/ECS — no ETL deps)."""
from __future__ import annotations

import json
from pathlib import Path

from . import config


def save_backtest_summary(summary: dict, path: Path | None = None) -> Path:
    path = path or config.BACKTEST_SUMMARY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2))
    return path


def load_backtest_summary(path: Path | None = None) -> dict | None:
    path = path or config.BACKTEST_SUMMARY
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None
