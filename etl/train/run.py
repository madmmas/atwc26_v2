"""Orchestrate Elo, Dixon-Coles, and XGBoost training."""
from __future__ import annotations

from atwc26_core import config

from .dixon_coles import save_dc_params, train_dixon_coles
from .elo import save_elo, train_elo
from .features import build_match_matrix
from .xgboost_model import (
    FEATURE_COLS,
    build_xgb_features,
    save_xgb_features,
    save_xgb_model,
    train_xgboost,
)


def run_train() -> dict:
    """Build match matrix and train all three models."""
    match_df = build_match_matrix(config.MASTER_PARQUET, config.HISTORICAL_FORM)
    if match_df.empty:
        raise RuntimeError("No match data available for training")

    elo_ratings = train_elo(match_df)
    save_elo(elo_ratings)
    print(f"elo: {len(elo_ratings)} teams trained")

    dc_params = train_dixon_coles(match_df)
    save_dc_params(dc_params)
    print(f"dixon_coles: converged={dc_params['converged']}")

    X, y = build_xgb_features(match_df, elo_ratings, dc_params)
    booster = train_xgboost(X, y)
    save_xgb_model(booster)
    save_xgb_features(FEATURE_COLS)
    print(f"xgboost: {len(y)} samples, {X.shape[1]} features")

    return {
        "matches": len(match_df),
        "elo_teams": len(elo_ratings),
        "dc_converged": dc_params["converged"],
        "xgb_samples": len(y),
        "xgb_features": X.shape[1],
    }


def main() -> int:
    run_train()
    return 0
