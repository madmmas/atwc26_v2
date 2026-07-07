"""Precompute player and team profile parquets during transform."""
from __future__ import annotations

from pathlib import Path

from atwc26_core import config
from atwc26_core.data import DataStore


def build_profiles(*, store: DataStore | None = None) -> tuple[Path, Path]:
    """Write player_profiles.parquet and team_profiles.parquet under data/."""
    store = store or DataStore()
    # Always derive from the master parquet — never round-trip stale profile files.
    store.load(force=True, rebuild_profiles=True)

    player_path = config.PLAYER_PROFILES
    team_path = config.TEAM_PROFILES
    player_path.parent.mkdir(parents=True, exist_ok=True)
    store.players.to_parquet(player_path, index=False)
    store.teams.to_parquet(team_path, index=False)
    return player_path, team_path
