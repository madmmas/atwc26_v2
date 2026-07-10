"""Tests for backtest summary I/O in atwc26_core (predict runtime)."""
from __future__ import annotations

from atwc26_core.backtest_io import load_backtest_summary, save_backtest_summary


def test_save_and_load_backtest_summary(tmp_path):
    path = tmp_path / "backtest_summary.json"
    payload = {"generated_at": "2026-01-01T00:00:00+00:00", "models": {"elo": {"accuracy": 0.5}}}
    save_backtest_summary(payload, path=path)
    loaded = load_backtest_summary(path=path)
    assert loaded == payload


def test_load_backtest_summary_missing(tmp_path):
    assert load_backtest_summary(path=tmp_path / "missing.json") is None
