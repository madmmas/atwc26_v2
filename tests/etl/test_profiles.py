"""Tests for transform profile precomputation."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from atwc26_core import config
from etl.transform.profiles import build_profiles


def test_build_profiles_writes_parquets(tmp_path, monkeypatch):
    repo_data = Path(__file__).resolve().parents[2] / "data"
    if not (repo_data / "all_players_stats.parquet").exists():
        import pytest

        pytest.skip("committed data required")

    for path in repo_data.iterdir():
        if path.is_file():
            (tmp_path / path.name).write_bytes(path.read_bytes())

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "MASTER_PARQUET", tmp_path / "all_players_stats.parquet")
    monkeypatch.setattr(config, "MATCH_EVENTS", tmp_path / "match_events.json")
    monkeypatch.setattr(config, "GLOSSARY_CSV", tmp_path / "glossary.csv")
    monkeypatch.setattr(config, "TEAM_FLAGS", tmp_path / "team_flags.json")
    monkeypatch.setattr(config, "STANDINGS", tmp_path / "standings.json")
    monkeypatch.setattr(config, "BRACKET", tmp_path / "bracket.json")
    monkeypatch.setattr(config, "SQUADS_RAW", tmp_path / "squads_raw.json")
    monkeypatch.setattr(config, "HISTORICAL_FORM", tmp_path / "historical_form.parquet")
    monkeypatch.setattr(config, "PLAYER_PROFILES", tmp_path / "player_profiles.parquet")
    monkeypatch.setattr(config, "TEAM_PROFILES", tmp_path / "team_profiles.parquet")

    player_path, team_path = build_profiles()
    assert player_path.exists()
    assert team_path.exists()

    players = pd.read_parquet(player_path)
    teams = pd.read_parquet(team_path)
    assert "expectedGoals_p90" in players.columns
    assert len(teams) > 0


def test_build_profiles_rebuilds_from_master_when_stale(tmp_path, monkeypatch):
    repo_data = Path(__file__).resolve().parents[2] / "data"
    if not (repo_data / "all_players_stats.parquet").exists():
        import pytest

        pytest.skip("committed data required")

    for path in repo_data.iterdir():
        if path.is_file():
            (tmp_path / path.name).write_bytes(path.read_bytes())

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "MASTER_PARQUET", tmp_path / "all_players_stats.parquet")
    monkeypatch.setattr(config, "MATCH_EVENTS", tmp_path / "match_events.json")
    monkeypatch.setattr(config, "GLOSSARY_CSV", tmp_path / "glossary.csv")
    monkeypatch.setattr(config, "TEAM_FLAGS", tmp_path / "team_flags.json")
    monkeypatch.setattr(config, "STANDINGS", tmp_path / "standings.json")
    monkeypatch.setattr(config, "BRACKET", tmp_path / "bracket.json")
    monkeypatch.setattr(config, "SQUADS_RAW", tmp_path / "squads_raw.json")
    monkeypatch.setattr(config, "HISTORICAL_FORM", tmp_path / "historical_form.parquet")
    monkeypatch.setattr(config, "PLAYER_PROFILES", tmp_path / "player_profiles.parquet")
    monkeypatch.setattr(config, "TEAM_PROFILES", tmp_path / "team_profiles.parquet")

    stale = pd.read_parquet(config.PLAYER_PROFILES)
    stale["totalGoals_total"] = 0.0
    stale.to_parquet(config.PLAYER_PROFILES, index=False)

    player_path, _ = build_profiles()
    players = pd.read_parquet(player_path)
    master_goals = (
        pd.read_parquet(config.MASTER_PARQUET)
        .groupby("player_id")["totalGoals"]
        .sum()
        .round(2)
    )
    rebuilt = players.set_index("player_id")["totalGoals_total"]
    assert rebuilt.max() > 0
    assert rebuilt.max() == master_goals.max()
