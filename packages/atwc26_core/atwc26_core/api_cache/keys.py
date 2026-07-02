"""DynamoDB API cache key helpers."""
from __future__ import annotations

DATASET = "wc26"


def dataset_pk(dataset: str = DATASET) -> str:
    return f"DATASET#{dataset}"


def standings_sk() -> str:
    return "API#standings"


def teams_sk() -> str:
    return "API#teams"


def team_players_sk(team_name: str) -> str:
    return f"API#team#{team_name}"


def matches_sk() -> str:
    return "API#matches"


def match_detail_sk(game_id: str) -> str:
    return f"API#match#{game_id}"


def player_detail_sk(player_id: int | str) -> str:
    return f"API#player#{player_id}"


def winner_probabilities_sk() -> str:
    return "API#winner-probabilities"


def bracket_sk() -> str:
    return "API#bracket"


def overview_sk() -> str:
    return "API#overview"
