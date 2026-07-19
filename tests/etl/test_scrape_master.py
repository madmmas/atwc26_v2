"""Regression tests for scrape state healing and master rebuild merge."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from etl.scrape import scrape_wc26 as scrape


@pytest.fixture
def scrape_dirs(tmp_path, monkeypatch):
    data = tmp_path / "data"
    games = data / "games"
    games.mkdir(parents=True)
    monkeypatch.setattr(scrape, "DATA_DIR", data)
    monkeypatch.setattr(scrape, "GAMES_DIR", games)
    monkeypatch.setattr(scrape, "MASTER_PARQUET", data / "all_players_stats.parquet")
    monkeypatch.setattr(scrape, "MASTER_CSV", data / "all_players_stats.csv")
    monkeypatch.setattr(scrape, "GLOSSARY_CSV", data / "glossary.csv")
    monkeypatch.setattr(scrape, "STATE_FILE", data / "processed_games.json")
    return data, games


def _player_row(game_id: str, player_id: int, team: str) -> dict:
    return {
        "game_id": game_id,
        "match_date": "2026-07-10T19:00Z",
        "competition": "FIFA World Cup",
        "season": 2026,
        "team_id": "1",
        "team_name": team,
        "home_away": "home",
        "is_winner": True,
        "formation": "4-3-3",
        "team_score": 1,
        "team_shootout_score": None,
        "opp_team_id": "2",
        "opp_team_name": "Away",
        "opp_score": 0,
        "opp_shootout_score": None,
        "player_id": player_id,
        "player_name": f"P{player_id}",
        "jersey": "10",
        "position": "Forward",
        "position_abbr": "F",
        "starter": True,
        "subbed_in": False,
        "subbed_out": False,
        "minutes": 90.0,
        "appearances": 1.0,
        "scraped_at": "2026-07-10T21:00:00+00:00",
        "totalGoals": 1.0,
    }


def test_heal_missing_parquet_state_downgrades_ok(scrape_dirs):
    data, games = scrape_dirs
    state = {
        "760511": {"status": "ok", "players": 22},
        "760510": {"status": "ok", "players": 31},
    }
    pd.DataFrame([_player_row("760510", 1, "France")]).to_parquet(
        games / "game_760510.parquet", index=False
    )

    healed = scrape.heal_missing_parquet_state(state)
    assert healed["760511"]["status"] == "pending"
    assert healed["760511"]["reason"] == "missing_parquet"
    assert healed["760510"]["status"] == "ok"
    saved = json.loads(data.joinpath("processed_games.json").read_text())
    assert saved["760511"]["status"] == "pending"


def test_games_needing_scrape_includes_bracket_gap(scrape_dirs):
    data, games = scrape_dirs
    (data / "bracket.json").write_text(json.dumps({
        "rounds": [{
            "name": "Semifinals",
            "matches": [
                {"game_id": "760514", "completed": True},
                {"game_id": "760515", "completed": False},
            ],
        }],
    }))
    pd.DataFrame([_player_row("760510", 1, "France")]).to_parquet(
        scrape.MASTER_PARQUET, index=False
    )
    links = {
        "760510": "gameId/760510",
        "760514": "gameId/760514",
    }
    state = {"760510": {"status": "ok"}}
    pd.DataFrame([_player_row("760510", 1, "France")]).to_parquet(
        games / "game_760510.parquet", index=False
    )

    targets = scrape.games_needing_scrape(links, state)
    assert "760514" in targets
    assert "760510" not in targets


def test_rebuild_master_preserves_master_only_games(scrape_dirs):
    _data, games = scrape_dirs
    # Synced master has 511 (no local parquet) + we scrape 516 into a parquet
    master = pd.DataFrame([
        _player_row("760511", 10, "Spain"),
        _player_row("760510", 11, "France"),
    ])
    master.to_parquet(scrape.MASTER_PARQUET, index=False)

    pd.DataFrame([_player_row("760516", 20, "France")]).to_parquet(
        games / "game_760516.parquet", index=False
    )
    # Local parquet also refreshes 760510 — should replace master copy
    pd.DataFrame([_player_row("760510", 12, "France")]).to_parquet(
        games / "game_760510.parquet", index=False
    )

    scrape.rebuild_master({})
    out = pd.read_parquet(scrape.MASTER_PARQUET)
    ids = set(out["game_id"].astype(str))
    assert ids == {"760510", "760511", "760516"}
    # parquet wins for 760510
    row = out[out["game_id"].astype(str) == "760510"].iloc[0]
    assert int(row["player_id"]) == 12
