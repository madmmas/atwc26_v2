from __future__ import annotations

from pathlib import Path

import atwc26_core.config as core_config
from etl.changed.detect import compare_snapshot, fingerprint, save_snapshot


def _use_data_dir(tmp_path: Path, monkeypatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(core_config, "DATA_DIR", data)
    monkeypatch.setattr(core_config, "MASTER_PARQUET", data / "all_players_stats.parquet")
    monkeypatch.setattr(core_config, "MATCH_EVENTS", data / "match_events.json")
    monkeypatch.setattr(core_config, "SQUADS_RAW", data / "squads_raw.json")
    monkeypatch.setattr(core_config, "STANDINGS", data / "standings.json")
    monkeypatch.setattr(core_config, "BRACKET", data / "bracket.json")
    monkeypatch.setattr(core_config, "GLOSSARY_CSV", data / "glossary.csv")
    monkeypatch.setattr(core_config, "TEAM_FLAGS", data / "team_flags.json")
    return data


def test_fingerprint_stable_for_same_files(tmp_path, monkeypatch):
    data = _use_data_dir(tmp_path, monkeypatch)
    raw = data / "raw"
    raw.mkdir()
    (raw / "1.json").write_text('{"a": 1}\n')
    (data / "schedule.json").write_text('{"games": []}\n')

    assert fingerprint() == fingerprint()


def test_compare_detects_new_raw_file(tmp_path, monkeypatch):
    data = _use_data_dir(tmp_path, monkeypatch)
    raw = data / "raw"
    raw.mkdir()
    (raw / "1.json").write_text('{"a": 1}\n')

    snap = tmp_path / "fp.json"
    save_snapshot(snap)
    assert compare_snapshot(snap) == 1

    (raw / "2.json").write_text('{"b": 2}\n')
    assert compare_snapshot(snap) == 0
