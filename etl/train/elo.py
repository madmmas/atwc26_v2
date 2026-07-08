"""Compute Elo ratings from match history."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from atwc26_core import config

ELO_START = 1500.0
K = 32
HOME_ADVANTAGE = 100


def train_elo(match_matrix: pd.DataFrame) -> dict[str, float]:
    """Iterate matches chronologically and return final team ratings."""
    ratings: dict[str, float] = {}

    def get(team: str) -> float:
        return ratings.setdefault(team, ELO_START)

    for _, row in match_matrix.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        r_a = get(home)
        r_b = get(away)
        expected_a = 1.0 / (1.0 + 10.0 ** ((r_b - r_a - HOME_ADVANTAGE) / 400.0))
        outcome = int(row["outcome"])
        if outcome == 2:
            actual_a = 1.0
        elif outcome == 1:
            actual_a = 0.5
        else:
            actual_a = 0.0
        ratings[home] = r_a + K * (actual_a - expected_a)
        ratings[away] = r_b + K * ((1.0 - actual_a) - (1.0 - expected_a))

    return ratings


def save_elo(ratings: dict[str, float], path: Path | None = None) -> Path:
    """Write ratings to config.ELO_RATINGS."""
    path = path or config.ELO_RATINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ratings": {k: round(v, 2) for k, v in ratings.items()},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2))
    return path
