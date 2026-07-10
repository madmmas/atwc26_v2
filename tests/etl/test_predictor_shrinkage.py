"""Tests for per-90 minutes shrinkage in the Poisson Predictor."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from atwc26_core.prediction import MINUTES_SHRINK_K, Predictor


def _mid(pid: int, name: str, minutes: float, xg: float) -> dict:
    return {
        "player_id": pid,
        "player_name": name,
        "team_name": "Alpha",
        "role": "MID",
        "minutes": minutes,
        "expectedGoals_p90": xg,
        "expectedAssists_p90": 0.10,
        "bigChanceCreated_p90": 0.05,
        "shotsOnTarget_p90": 0.5,
        "touchesInOppBox_p90": 1.0,
        "interceptions_p90": 1.0,
        "duelsWon_p90": 2.0,
        "totalClearance_p90": 0.5,
        "totalTackles_p90": 1.0,
        "ballRecovery_p90": 2.0,
        "defensiveInterventions_p90": 1.0,
        "touches_p90": 50.0,
        "passPct": 80.0,
    }


def _store_with_players(players: list[dict]) -> MagicMock:
    store = MagicMock()
    store.predictor_players = pd.DataFrame(players)
    store.predictor_avg_goals = 1.3
    store.league = {"avg_team_goals": 1.3}
    return store


def test_low_minute_player_shrinks_toward_ref():
    # Stable MID reference from several average starters; two copies of the
    # same absurd xG rate — one with 20 minutes, one with 900.
    players = [
        _mid(10, "AvgA", 900, 0.20),
        _mid(11, "AvgB", 900, 0.18),
        _mid(12, "AvgC", 900, 0.22),
        _mid(2, "HotSub", 20, 2.0),
        _mid(4, "HotStarter", 900, 2.0),
        {
            "player_id": 3,
            "player_name": "Keeper",
            "team_name": "Alpha",
            "role": "GK",
            "minutes": 900,
            "goalsPrevented_p90": 0.0,
            "saves_p90": 2.0,
        },
    ]
    pred = Predictor(_store_with_players(players))

    rated_sub = pred._rate_team([
        {"player_id": 3, "role": "GK"},
        {"player_id": 2, "role": "MID"},
    ])
    rated_full = pred._rate_team([
        {"player_id": 3, "role": "GK"},
        {"player_id": 4, "role": "MID"},
    ])
    rated_avg = pred._rate_team([
        {"player_id": 3, "role": "GK"},
        {"player_id": 10, "role": "MID"},
    ])

    assert MINUTES_SHRINK_K == 45.0
    # Same raw rates: low-minute player must rate closer to average than the
    # full-minute clone.
    assert rated_sub.attack < rated_full.attack
    assert abs(rated_sub.attack - rated_avg.attack) < abs(rated_full.attack - rated_avg.attack)
