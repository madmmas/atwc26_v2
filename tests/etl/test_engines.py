"""Tests for multi-model prediction engines."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from atwc26_core.engines import available_engines, load_engines
from atwc26_core.engines.elo import EloEngine
from atwc26_core.engines.poisson import PoissonEngine


def _mock_store() -> MagicMock:
    store = MagicMock()
    store.predictor_players = pd.DataFrame([
        {
            "player_id": 1,
            "player_name": "Keeper",
            "team_name": "Brazil",
            "role": "GK",
            "minutes": 90,
            "goalsPrevented_p90": 0.1,
            "saves_p90": 2.0,
        },
        {
            "player_id": 2,
            "player_name": "Midfielder",
            "team_name": "Brazil",
            "role": "MID",
            "minutes": 90,
            "expectedGoals_p90": 0.2,
            "expectedAssists_p90": 0.1,
        },
    ])
    store.predictor_avg_goals = 1.3
    store.league = {"avg_team_goals": 1.3}
    return store


class _MockPredictor:
    def predict(self, team_a, team_b):
        return {
            "team_a": {
                "team_name": team_a["team_name"],
                "win_probability": 0.52,
                "expected_goals": 1.5,
            },
            "team_b": {
                "team_name": team_b["team_name"],
                "win_probability": 0.24,
                "expected_goals": 1.1,
            },
            "draw_prob": 0.24,
            "most_likely_score": {"a": 1, "b": 1, "prob": 0.12},
            "top_scorelines": [],
            "radar": {"dimensions": []},
            "narrative": "test",
            "model": {"type": "poisson"},
        }


def test_poisson_engine_wraps_predictor():
    engine = PoissonEngine(_MockPredictor())
    result = engine.predict(
        {"team_name": "Brazil", "players": [], "home": True},
        {"team_name": "Argentina", "players": [], "home": False},
    )
    assert "win_probability_a" in result
    assert "draw_probability" in result
    assert "win_probability_b" in result
    total = result["win_probability_a"] + result["draw_probability"] + result["win_probability_b"]
    assert total == pytest.approx(1.0, abs=1e-4)
    assert result["model"]["name"] == "poisson"


def test_load_engines_registers_all(tmp_path, monkeypatch):
    from atwc26_core import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ELO_RATINGS", tmp_path / "elo_ratings.json")
    monkeypatch.setattr(config, "DC_PARAMS", tmp_path / "dc_params.json")
    monkeypatch.setattr(config, "XGB_MODEL", tmp_path / "xgb_model.ubj")
    monkeypatch.setattr(config, "XGB_FEATURES", tmp_path / "xgb_features.json")

    (tmp_path / "elo_ratings.json").write_text(
        json.dumps({"ratings": {"Brazil": 1600.0, "Argentina": 1550.0}})
    )

    mock_store = _mock_store()
    load_engines(mock_store)

    engines = available_engines()
    assert "poisson" in engines
    assert "elo" in engines
    assert isinstance(engines["elo"], EloEngine)


def test_multi_model_predict_returns_comparison(tmp_path, monkeypatch):
    from atwc26_core import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ELO_RATINGS", tmp_path / "elo_ratings.json")
    monkeypatch.setattr(config, "DC_PARAMS", tmp_path / "dc_params.json")
    monkeypatch.setattr(config, "XGB_MODEL", tmp_path / "xgb_model.ubj")
    monkeypatch.setattr(config, "XGB_FEATURES", tmp_path / "xgb_features.json")

    (tmp_path / "elo_ratings.json").write_text(
        json.dumps({"ratings": {"Brazil": 1600.0, "Argentina": 1550.0}})
    )

    mock_store = _mock_store()
    load_engines(mock_store)

    team_a = {"team_name": "Brazil", "players": [], "home": True}
    team_b = {"team_name": "Argentina", "players": [], "home": False}

    results = {}
    for name, engine in available_engines().items():
        results[name] = engine.predict(team_a, team_b)

    comparison = {
        name: {
            "win_probability_a": r.get("win_probability_a"),
            "draw_probability": r.get("draw_probability"),
            "win_probability_b": r.get("win_probability_b"),
            "model_name": r.get("model", {}).get("name"),
        }
        for name, r in results.items()
        if "error" not in r
    }

    assert len(comparison) >= 1
    for entry in comparison.values():
        for key in ("win_probability_a", "draw_probability", "win_probability_b", "model_name"):
            assert key in entry
