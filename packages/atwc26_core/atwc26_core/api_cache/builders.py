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


def publish_standings(store: DataStore, manifest: dict, cache_store) -> bool:
    payload, source_sha, sources = build_standings(store, manifest)
    pk, sk = keys.dataset_pk(), keys.standings_sk()
    if cache_store.should_skip(pk, sk, source_sha):
        return False
    cache_store.put_item(
        pk=pk, sk=sk, payload=payload, source_sha256=source_sha, source_artifacts=sources
    )
    return True
