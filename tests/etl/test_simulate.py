"""Tests for offline tournament simulation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from atwc26_core import config
from atwc26_core.simulation_artifacts import load_bracket_predictions, load_winner_probabilities
from etl.simulate.run import run_simulate

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_DATA = REPO_ROOT / "data"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Copy committed data/ into an isolated tmp dir for simulate output."""
    if not (REPO_DATA / "all_players_stats.parquet").exists():
        pytest.skip("committed data artifacts required")

    for path in REPO_DATA.iterdir():
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
    monkeypatch.setattr(config, "WINNER_PROBABILITIES", tmp_path / "winner_probabilities.json")
    monkeypatch.setattr(config, "BRACKET_PREDICTIONS", tmp_path / "bracket_predictions.json")
    return tmp_path


def test_run_simulate_writes_artifacts(data_dir):
    result = run_simulate(trials=20, seed=1)
    assert result["teams"] > 0
    assert (data_dir / "winner_probabilities.json").exists()
    assert (data_dir / "bracket_predictions.json").exists()

    probs = load_winner_probabilities()
    assert probs
    assert sum(probs.values()) > 0

    preds = load_bracket_predictions()
    assert preds is not None

    winner_doc = json.loads((data_dir / "winner_probabilities.json").read_text())
    assert winner_doc["trials"] == 20
    assert winner_doc["seed"] == 1
    # Stage probabilities present after simulation
    assert "stage_probabilities" in winner_doc
    # At least the surviving teams should have stage data
    alive = {t for t, p in winner_doc["probabilities"].items() if p > 0}
    stages = winner_doc["stage_probabilities"]
    # Every alive team should appear in stage_probabilities
    for team in alive:
        assert team in stages, f"{team} missing from stage_probabilities"
        # title probability should match probabilities dict
        title_p = stages[team].get("title", 0.0)
        assert abs(title_p - winner_doc["probabilities"][team]) < 1e-4, (
            f"{team}: stage title={title_p} != probabilities={winner_doc['probabilities'][team]}"
        )
