"""Chronological out-of-sample backtest for Elo and Dixon-Coles."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from atwc26_core.backtest_io import load_backtest_summary, save_backtest_summary
from atwc26_core.engines.dixon_coles import DixonColesEngine
from atwc26_core.engines.elo import EloEngine
from etl.train.dixon_coles import train_dixon_coles
from etl.train.elo import train_elo


def _outcome_probs_to_vector(p_home: float, p_draw: float, p_away: float) -> np.ndarray:
    total = p_home + p_draw + p_away
    if total <= 0:
        return np.array([1 / 3, 1 / 3, 1 / 3])
    return np.array([p_away, p_draw, p_home]) / total


def _metrics(y_true: np.ndarray, probs: np.ndarray) -> dict:
    """y_true in {0,1,2}; probs shape (n, 3) ordered [away, draw, home]."""
    n = len(y_true)
    if n == 0:
        return {"n": 0, "log_loss": None, "accuracy": None, "brier": None}
    clipped = np.clip(probs, 1e-7, 1.0)
    clipped = clipped / clipped.sum(axis=1, keepdims=True)
    ll = float(-np.mean(np.log(clipped[np.arange(n), y_true])))
    preds = clipped.argmax(axis=1)
    acc = float(np.mean(preds == y_true))
    one_hot = np.zeros_like(clipped)
    one_hot[np.arange(n), y_true] = 1.0
    brier = float(np.mean(np.sum((clipped - one_hot) ** 2, axis=1)))
    return {
        "n": int(n),
        "log_loss": round(ll, 4),
        "accuracy": round(acc, 4),
        "brier": round(brier, 4),
    }


def _predict_row_elo(engine: EloEngine, row: pd.Series) -> np.ndarray:
    result = engine.predict(
        {"team_name": row["home_team"], "home": True, "players": []},
        {"team_name": row["away_team"], "home": False, "players": []},
    )
    return _outcome_probs_to_vector(
        result["win_probability_a"],
        result["draw_probability"],
        result["win_probability_b"],
    )


def _predict_row_dc(engine: DixonColesEngine, row: pd.Series) -> np.ndarray:
    result = engine.predict(
        {"team_name": row["home_team"], "home": True, "players": []},
        {"team_name": row["away_team"], "home": False, "players": []},
    )
    return _outcome_probs_to_vector(
        result["win_probability_a"],
        result["draw_probability"],
        result["win_probability_b"],
    )


def run_backtest(match_matrix: pd.DataFrame, holdout_frac: float = 0.2) -> dict:
    """Train on earliest (1-holdout) matches; score Elo + DC on the hold-out."""
    if match_matrix.empty or len(match_matrix) < 10:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "holdout_frac": holdout_frac,
            "models": {},
            "error": "insufficient_matches",
        }

    df = match_matrix.sort_values("match_date").reset_index(drop=True)
    split = max(1, int(len(df) * (1.0 - holdout_frac)))
    if split >= len(df):
        split = len(df) - 1
    train_df = df.iloc[:split]
    test_df = df.iloc[split:]
    y_true = test_df["outcome"].astype(int).to_numpy()

    models: dict = {}

    elo_ratings = train_elo(train_df)
    elo_engine = EloEngine()
    elo_engine._ratings = elo_ratings
    elo_probs = np.vstack([_predict_row_elo(elo_engine, row) for _, row in test_df.iterrows()])
    models["elo"] = _metrics(y_true, elo_probs)

    dc_params = train_dixon_coles(train_df)
    dc_engine = DixonColesEngine()
    dc_engine._attack = dc_params["attack"]
    dc_engine._defence = dc_params["defence"]
    dc_engine._home = dc_params["home_advantage"]
    dc_engine._rho = dc_params["rho"]
    dc_probs = np.vstack([_predict_row_dc(dc_engine, row) for _, row in test_df.iterrows()])
    models["dixon_coles"] = {
        **_metrics(y_true, dc_probs),
        "train_converged": dc_params["converged"],
        "train_max_abs_param": round(float(dc_params.get("max_abs_param", 0.0)), 4),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holdout_frac": holdout_frac,
        "train_n": int(len(train_df)),
        "holdout_n": int(len(test_df)),
        "models": models,
    }


__all__ = [
    "run_backtest",
    "save_backtest_summary",
    "load_backtest_summary",
]
