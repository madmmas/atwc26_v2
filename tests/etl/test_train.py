"""Tests for ETL model training pipeline."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from atwc26_core import config
from atwc26_core.engines.dixon_coles import DixonColesEngine
from atwc26_core.engines.elo import EloEngine
from etl.train.dixon_coles import save_dc_params, train_dixon_coles
from etl.train.elo import save_elo, train_elo
from etl.train.features import add_rolling_form, build_match_matrix
from etl.train.xgboost_model import FEATURE_COLS, build_xgb_features

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_DATA = REPO_ROOT / "data"


def _sample_match_matrix(n: int = 3) -> pd.DataFrame:
    rows = []
    teams = ["Alpha", "Beta", "Gamma", "Delta"]
    outcomes = [2, 0, 1]
    for i in range(n):
        h, a = teams[i % len(teams)], teams[(i + 1) % len(teams)]
        if outcomes[i % 3] == 2:
            hg, ag = 2, 1
        elif outcomes[i % 3] == 1:
            hg, ag = 1, 1
        else:
            hg, ag = 0, 2
        rows.append({
            "game_id": f"g{i}",
            "match_date": f"2025-0{i + 1}-01",
            "home_team": h,
            "away_team": a,
            "h_goals": hg,
            "a_goals": ag,
            "h_xg_p90": 1.2,
            "a_xg_p90": 1.0,
            "h_shots_p90": 10.0,
            "a_shots_p90": 8.0,
            "h_sot_p90": 4.0,
            "a_sot_p90": 3.0,
            "outcome": outcomes[i % 3],
        })
    return pd.DataFrame(rows)


def test_build_match_matrix_returns_correct_shape():
    if not (REPO_DATA / "all_players_stats.parquet").exists():
        pytest.skip("committed data artifacts required")

    df = build_match_matrix(config.MASTER_PARQUET, config.HISTORICAL_FORM)
    assert not df.empty
    for col in ("game_id", "home_team", "away_team", "outcome", "h_xg_p90", "a_xg_p90"):
        assert col in df.columns
    assert set(df["outcome"].unique()).issubset({0, 1, 2})
    assert df["outcome"].notna().all()


def test_train_elo_updates_ratings():
    df = _sample_match_matrix(3)
    ratings = train_elo(df)
    assert isinstance(ratings["Alpha"], float)
    assert 1000 <= ratings["Alpha"] <= 2000
    assert ratings["Alpha"] != ratings["Beta"]


def test_save_load_elo(tmp_path):
    df = _sample_match_matrix(3)
    ratings = train_elo(df)
    path = tmp_path / "elo.json"
    save_elo(ratings, path=path)
    engine = EloEngine()
    assert engine.load(path=path)
    assert engine.is_available()
    assert engine.get_rating("Alpha") == pytest.approx(ratings["Alpha"], rel=1e-2)


def test_train_dixon_coles_converges():
    df = _sample_match_matrix(12)
    result = train_dixon_coles(df)
    assert result["converged"] is True
    assert "attack" in result and "defence" in result
    assert all(isinstance(v, float) for v in result["attack"].values())
    assert all(isinstance(v, float) for v in result["defence"].values())


def test_save_load_dc_params(tmp_path):
    df = _sample_match_matrix(12)
    params = train_dixon_coles(df)
    path = tmp_path / "dc.json"
    save_dc_params(params, path=path)
    engine = DixonColesEngine()
    assert engine.load(path=path)
    assert engine.is_available()


def test_dc_engine_predict_sums_to_one():
    engine = DixonColesEngine()
    engine._attack = {"Alpha": 0.2, "Beta": -0.1}
    engine._defence = {"Alpha": -0.1, "Beta": 0.1}
    engine._home = 0.3
    engine._rho = 0.1
    result = engine.predict(
        {"team_name": "Alpha", "home": True, "players": []},
        {"team_name": "Beta", "home": False, "players": []},
    )
    total = result["win_probability_a"] + result["draw_probability"] + result["win_probability_b"]
    assert total == pytest.approx(1.0, abs=1e-4)


def test_xgb_feature_vector_shape():
    df = add_rolling_form(_sample_match_matrix(5))
    X, y = build_xgb_features(df, {}, {"attack": {}, "defence": {}})
    assert X.shape == (len(df), 9)
    assert set(y.tolist()).issubset({0, 1, 2})
    assert len(FEATURE_COLS) == 9


def test_engine_protocol_compliance():
    from atwc26_core.engines import ModelEngine
    from atwc26_core.engines.dixon_coles import DixonColesEngine
    from atwc26_core.engines.elo import EloEngine
    from atwc26_core.engines.poisson import PoissonEngine
    from atwc26_core.engines.xgboost_engine import XGBoostEngine

    class _MockPredictor:
        def predict(self, team_a, team_b):
            return {
                "team_a": {"win_probability": 0.5},
                "team_b": {"win_probability": 0.3},
                "draw_prob": 0.2,
            }

    engines = [
        PoissonEngine(_MockPredictor()),
        EloEngine(),
        DixonColesEngine(),
        XGBoostEngine(),
    ]
    for engine in engines:
        assert isinstance(engine, ModelEngine)
        assert isinstance(engine.name, str)
        assert isinstance(engine.is_available(), bool)
