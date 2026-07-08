"""Train XGBoost match outcome classifier."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from atwc26_core import config

from .features import add_rolling_form

FEATURE_COLS = [
    "xg_diff",
    "shots_diff",
    "sot_diff",
    "elo_diff",
    "dc_attack_ratio",
    "dc_defence_ratio",
    "home_adv",
    "h_form3",
    "a_form3",
]

XGB_PARAMS = {
    "objective": "multi:softprob",
    "num_class": 3,
    "max_depth": 2,
    "eta": 0.05,
    "subsample": 0.7,
    "colsample_bytree": 0.7,
    "min_child_weight": 3,
    "lambda": 2.0,
    "alpha": 0.5,
    "eval_metric": "mlogloss",
    "seed": 42,
}
NUM_ROUNDS = 200


def build_xgb_features(
    match_matrix: pd.DataFrame,
    elo_ratings: dict[str, float],
    dc_params: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Build feature matrix X and label vector y."""
    df = add_rolling_form(match_matrix.copy())
    attack = dc_params.get("attack", {})
    defence = dc_params.get("defence", {})

    rows = []
    labels = []
    for _, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        elo_h = elo_ratings.get(home, 1500.0)
        elo_a = elo_ratings.get(away, 1500.0)
        a_h = math.exp(attack.get(home, 0.0))
        d_a = math.exp(defence.get(away, 0.0))
        a_a = math.exp(attack.get(away, 0.0))
        d_h = math.exp(defence.get(home, 0.0))
        rows.append([
            row["h_xg_p90"] - row["a_xg_p90"],
            row["h_shots_p90"] - row["a_shots_p90"],
            row["h_sot_p90"] - row["a_sot_p90"],
            elo_h - elo_a,
            a_h / max(d_a, 1e-6),
            a_a / max(d_h, 1e-6),
            1.0,
            row["h_form3"],
            row["a_form3"],
        ])
        labels.append(int(row["outcome"]))

    return np.array(rows, dtype=np.float32), np.array(labels, dtype=np.int32)


def train_xgboost(X: np.ndarray, y: np.ndarray) -> xgb.Booster:
    """Train XGBoost booster on feature matrix."""
    dtrain = xgb.DMatrix(X, label=y, feature_names=FEATURE_COLS)
    return xgb.train(XGB_PARAMS, dtrain, num_boost_round=NUM_ROUNDS)


def save_xgb_model(booster: xgb.Booster, path: Path | None = None) -> Path:
    """Save booster to config.XGB_MODEL."""
    path = path or config.XGB_MODEL
    path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(path))
    return path


def save_xgb_features(features: list[str], path: Path | None = None) -> Path:
    """Write feature column list to config.XGB_FEATURES."""
    path = path or config.XGB_FEATURES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(features, indent=2))
    return path
