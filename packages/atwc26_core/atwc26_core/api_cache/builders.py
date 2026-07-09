"""Build API-ready cache payloads from an in-memory DataStore."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from atwc26_core.data import DataStore

from . import keys


def _hash_payload(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _artifact_hash(manifest: dict, *names: str) -> str:
    parts: list[str] = []
    artifacts = manifest.get("artifacts", {})
    for name in names:
        entry = artifacts.get(name, {})
        parts.append(entry.get("sha256", ""))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def build_standings(store: DataStore, manifest: dict) -> tuple[dict, str, list[str]]:
    payload = {"groups": store.standings}
    source_sha = _artifact_hash(manifest, "standings")
    return payload, source_sha, ["standings"]


def build_teams(store: DataStore, manifest: dict) -> tuple[dict, str, list[str]]:
    payload = {"teams": store.teams.to_dict("records")}
    source_sha = _artifact_hash(manifest, "all_players_stats")
    return payload, source_sha, ["all_players_stats"]


def build_team_players(
    store: DataStore, team_name: str, manifest: dict
) -> tuple[dict | None, str, list[str]]:
    sub = store.players[store.players["team_name"] == team_name]
    if sub.empty:
        return None, "", []
    payload = {
        "team_name": team_name,
        "players": sub.sort_values(["role", "minutes"], ascending=[True, False]).to_dict(
            "records"
        ),
    }
    source_sha = _hash_payload(payload)
    return payload, source_sha, ["all_players_stats"]


def build_matches(store: DataStore, manifest: dict) -> tuple[dict, str, list[str]]:
    payload = {"matches": store.matches}
    source_sha = _artifact_hash(manifest, "all_players_stats", "match_events")
    return payload, source_sha, ["all_players_stats", "match_events"]


def build_match_detail(
    store: DataStore, game_id: str, manifest: dict
) -> tuple[dict | None, str, list[str]]:
    detail = store.match_detail(game_id)
    if detail is None:
        return None, "", []
    source_sha = _hash_payload(detail)
    return detail, source_sha, ["all_players_stats", "match_events"]


def build_player_detail(
    store: DataStore, player_id: int, manifest: dict
) -> tuple[dict | None, str, list[str]]:
    detail = store.player_detail(player_id)
    if detail is None:
        return None, "", []
    source_sha = _hash_payload(detail)
    return detail, source_sha, ["all_players_stats"]


def build_overview(store: DataStore, manifest: dict) -> tuple[dict, str, list[str]]:
    players = store.players
    top_scorers = (
        players.sort_values("totalGoals_total", ascending=False)
        .head(8)[
            [
                "player_id",
                "player_name",
                "team_name",
                "flag_url",
                "role",
                "totalGoals_total",
                "expectedGoals_total",
                "minutes",
            ]
        ]
        .to_dict("records")
    )
    top_xg = (
        players.sort_values("expectedGoals_p90", ascending=False)
        .query("minutes >= 90")
        .head(8)[
            [
                "player_id",
                "player_name",
                "team_name",
                "flag_url",
                "role",
                "expectedGoals_p90",
                "minutes",
            ]
        ]
        .to_dict("records")
    )
    top_creators = (
        players.sort_values("expectedAssists_p90", ascending=False)
        .query("minutes >= 90")
        .head(8)[
            [
                "player_id",
                "player_name",
                "team_name",
                "flag_url",
                "role",
                "expectedAssists_p90",
                "minutes",
            ]
        ]
        .to_dict("records")
    )
    payload = {
        "league": store.league,
        "teams": store.teams.to_dict("records"),
        "top_scorers": top_scorers,
        "top_xg_per90": top_xg,
        "top_creators_per90": top_creators,
    }
    source_sha = _artifact_hash(
        manifest, "player_profiles", "team_profiles", "all_players_stats"
    )
    return payload, source_sha, ["player_profiles", "team_profiles", "all_players_stats"]


def build_winner_probabilities(
    store: DataStore, manifest: dict
) -> tuple[dict | None, str, list[str]]:
    from ..simulation_artifacts import (
        load_stage_probabilities,
        load_winner_probabilities,
        winner_probabilities_api_payload,
    )
    from ..tournament import get_winner_probabilities

    probs = load_winner_probabilities()
    if probs is None:
        probs = get_winner_probabilities(store)
    stage_probs = load_stage_probabilities()
    payload = winner_probabilities_api_payload(
        probs,
        flag_lookup=store.flag,
        stage_probabilities=stage_probs,
    )
    source_sha = _artifact_hash(manifest, "winner_probabilities")
    return payload, source_sha, ["winner_probabilities"]


def build_bracket(store: DataStore, manifest: dict) -> tuple[dict, str, list[str]]:
    from ..tournament import get_bracket_predictions

    preds = get_bracket_predictions(store)
    payload = {
        "rounds": [
            {
                **round_def,
                "matches": [
                    {**m, "prediction": preds.get(str(m["game_id"]))}
                    for m in round_def["matches"]
                ],
            }
            for round_def in store.bracket.get("rounds", [])
        ]
    }
    source_sha = _artifact_hash(manifest, "bracket", "bracket_predictions")
    return payload, source_sha, ["bracket", "bracket_predictions"]


DEFAULT_LEADERBOARD_COMBOS = [
    ("expectedGoals_p90", None, 90),
    ("expectedAssists_p90", None, 90),
    ("totalGoals_total", None, 0),
    ("defensiveInterventions_p90", "DEF", 90),
    ("saves_p90", "GK", 90),
    ("expectedGoals_p90", "FWD", 90),
    ("expectedGoals_p90", "MID", 90),
]


def build_players_all(store: DataStore, manifest: dict) -> tuple[dict, str, list[str]]:
    """Cache /api/players (default sort=minutes, no filter)."""
    df = store.players.sort_values("minutes", ascending=False)
    payload = {"count": int(len(df)), "players": df.to_dict("records")}
    source_sha = _hash_payload(payload)
    return payload, source_sha, ["player_profiles"]


def build_leaderboard(
    store: DataStore,
    metric: str,
    role: str | None,
    min_minutes: int,
    manifest: dict,
    limit: int = 20,
) -> tuple[dict | None, str, list[str]]:
    df = store.players
    if metric not in df.columns:
        return None, "", []
    df = df[df["minutes"] >= min_minutes]
    if role:
        df = df[df["role"] == role.upper()]
    df = df.sort_values(metric, ascending=False).head(limit)
    cols = [
        "player_id",
        "player_name",
        "team_name",
        "flag_url",
        "role",
        "minutes",
        metric,
    ]
    cols = [c for c in cols if c in df.columns]
    payload = {"metric": metric, "leaders": df[cols].to_dict("records")}
    source_sha = _hash_payload(payload)
    return payload, source_sha, ["player_profiles"]


def publish_standings(store: DataStore, manifest: dict, cache_store) -> bool:
    payload, source_sha, sources = build_standings(store, manifest)
    pk, sk = keys.dataset_pk(), keys.standings_sk()
    if cache_store.should_skip(pk, sk, source_sha):
        return False
    cache_store.put_item(
        pk=pk, sk=sk, payload=payload, source_sha256=source_sha, source_artifacts=sources
    )
    return True
