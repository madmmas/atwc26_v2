"""Tests for predict service data bootstrap."""
from __future__ import annotations

import inspect


def test_ensure_predictor_data_includes_model_artifacts():
    """Model engines need elo/dc/xgb artifacts synced alongside player profiles."""
    from services.shared import predict_bootstrap as pb

    src = inspect.getsource(pb.ensure_predictor_data)
    for name in ("elo_ratings", "dc_params", "xgb_model", "xgb_features", "backtest_summary"):
        assert name in src
    assert "config.ELO_RATINGS" in src
    assert "config.XGB_MODEL" in src
    assert "config.BACKTEST_SUMMARY" in src
