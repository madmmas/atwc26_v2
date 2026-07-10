"""Tests for chronological backtest harness."""
from __future__ import annotations

import pandas as pd

from etl.eval.backtest import run_backtest, save_backtest_summary


def _matrix(n: int = 20) -> pd.DataFrame:
    rows = []
    teams = ["Alpha", "Beta", "Gamma", "Delta"]
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 1) % 4]
        outcome = [2, 0, 1][i % 3]
        hg, ag = (2, 1) if outcome == 2 else ((1, 1) if outcome == 1 else (0, 2))
        rows.append({
            "game_id": f"g{i}",
            "match_date": f"2025-{(i % 12) + 1:02d}-01",
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
            "outcome": outcome,
        })
    return pd.DataFrame(rows)


def test_backtest_summary_shape(tmp_path):
    summary = run_backtest(_matrix(20), holdout_frac=0.25)
    assert "models" in summary
    assert "elo" in summary["models"]
    assert "dixon_coles" in summary["models"]
    assert summary["holdout_n"] >= 1
    for name, metrics in summary["models"].items():
        assert metrics["n"] == summary["holdout_n"]
        assert metrics["log_loss"] is not None
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert metrics["brier"] is not None

    path = tmp_path / "backtest.json"
    save_backtest_summary(summary, path=path)
    assert path.exists()


def test_backtest_insufficient_matches():
    summary = run_backtest(_matrix(5))
    assert summary.get("error") == "insufficient_matches"
