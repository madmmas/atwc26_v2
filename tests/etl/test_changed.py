from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import atwc26_core.config as core_config
from etl.changed.detect import (
    changed_game_ids,
    check_trigger,
    compare_matches_snapshot,
    compare_snapshot,
    data_changed,
    describe_changes,
    fingerprint,
    mark_finished_from_snapshot,
    match_fingerprint,
    save_snapshot,
)
from etl.changed.store import (
    load_fingerprint,
    restore_scrape_state,
    save_fingerprint,
    save_scrape_state,
)
from etl.changed.triggers import game_done_key, is_game_finished, mark_games_finished


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
    (data / "standings.json").write_text('{"groups": {}}\n')

    assert fingerprint() == fingerprint()


def test_fingerprint_ignores_derived_and_volatile_files(tmp_path, monkeypatch):
    data = _use_data_dir(tmp_path, monkeypatch)
    raw = data / "raw"
    raw.mkdir()
    (raw / "1.json").write_text('{"a": 1}\n')

    fp1 = fingerprint()
    match1 = match_fingerprint()
    (data / "schedule.json").write_text('{"updated": true}\n')
    (data / "squads_raw.json").write_text('[]\n')
    (data / "match_events.json").write_text('{}\n')
    assert fingerprint() == fp1
    assert match_fingerprint() == match1


def test_compare_detects_new_raw_file(tmp_path, monkeypatch):
    data = _use_data_dir(tmp_path, monkeypatch)
    raw = data / "raw"
    raw.mkdir()
    (raw / "1.json").write_text('{"a": 1}\n')

    snap = tmp_path / "fp.json"
    save_snapshot(snap)
    assert compare_snapshot(snap) == 1
    assert compare_matches_snapshot(snap) == 1

    (raw / "2.json").write_text('{"b": 2}\n')
    assert compare_snapshot(snap) == 0
    assert compare_matches_snapshot(snap) == 0


def test_compare_matches_ignores_bracket_only_change(tmp_path, monkeypatch):
    data = _use_data_dir(tmp_path, monkeypatch)
    raw = data / "raw"
    raw.mkdir()
    (raw / "1.json").write_text('{"a": 1}\n')
    (data / "bracket.json").write_text('{"rounds": []}\n')

    snap = tmp_path / "fp.json"
    save_snapshot(snap)
    assert compare_matches_snapshot(snap) == 1

    (data / "bracket.json").write_text('{"rounds": [{"name": "Final"}]}\n')
    assert compare_snapshot(snap) == 0
    assert compare_matches_snapshot(snap) == 1


def test_data_changed_ignores_missing_local_raw_files():
    before = {
        "data/raw/1.json": "aaa",
        "data/raw/2.json": "bbb",
        "data/standings.json": "ccc",
    }
    after = {
        "data/raw/1.json": "aaa",
        "data/standings.json": "ccc",
    }
    assert not data_changed(before, after)


def test_data_changed_detects_modified_standings():
    before = {"data/standings.json": "old"}
    after = {"data/standings.json": "new"}
    assert data_changed(before, after)
    assert "standings" in describe_changes(before, after)


def test_changed_game_ids_detects_new_and_modified_raw_files():
    before = {"data/raw/760001.json": "aaa"}
    after = {
        "data/raw/760001.json": "bbb",
        "data/raw/760002.json": "ccc",
        "data/standings.json": "unchanged",
    }
    assert changed_game_ids(before, after) == {"760001", "760002"}


def test_mark_finished_from_snapshot_writes_done_records(tmp_path, monkeypatch):
    data = _use_data_dir(tmp_path, monkeypatch)
    raw = data / "raw"
    raw.mkdir()
    (raw / "760001.json").write_text('{"a": 1}\n')

    snap = tmp_path / "fp.json"
    snap.write_text(json.dumps({"data/raw/760001.json": "old"}) + "\n")

    monkeypatch.setattr("etl.changed.triggers.config.DYNAMODB_TABLE", "test-table")
    items: dict[tuple[str, str], dict] = {}

    class FakeTable:
        def put_item(self, *, Item):
            items[(Item["PK"], Item["SK"])] = Item

        def get_item(self, *, Key):
            return {"Item": items.get((Key["PK"], Key["SK"]))}

    monkeypatch.setattr("etl.changed.triggers._table", lambda: FakeTable())

    assert mark_finished_from_snapshot(snap) == 0
    assert game_done_key("760001") in {item["SK"] for item in items.values()}
    assert is_game_finished("760001")


def test_mark_games_finished_noop_without_table(monkeypatch):
    monkeypatch.setattr("etl.changed.triggers.config.DYNAMODB_TABLE", "")
    assert mark_games_finished({"760001"}) is False


def test_check_trigger_exits_when_game_finished(monkeypatch):
    monkeypatch.setattr("etl.changed.detect.trigger_still_needed", lambda gid: gid != "760001")
    assert check_trigger("760510") == 0
    assert check_trigger("760001") == 1


def test_save_and_load_fingerprint_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("etl.changed.store.config.DYNAMODB_TABLE", "test-table")
    items: dict[tuple[str, str], dict] = {}

    class FakeTable:
        def get_item(self, *, Key):
            return {"Item": items.get((Key["PK"], Key["SK"]))}

        def put_item(self, *, Item):
            items[(Item["PK"], Item["SK"])] = Item

    monkeypatch.setattr("etl.changed.store._table", lambda: FakeTable())

    fp = {"data/raw/1.json": "deadbeef"}
    assert save_fingerprint(fp)
    assert load_fingerprint() == fp


def test_restore_scrape_state_writes_processed_games(tmp_path, monkeypatch):
    data = _use_data_dir(tmp_path, monkeypatch)
    monkeypatch.setattr("etl.changed.store.config.DYNAMODB_TABLE", "test-table")
    monkeypatch.setattr("etl.changed.store.config.DATA_DIR", data)
    state = {"760001": {"status": "ok"}}

    class FakeTable:
        def get_item(self, *, Key):
            if Key["SK"] == "SCRAPE_STATE":
                return {"Item": {"processed_games": state}}
            return {}

    monkeypatch.setattr("etl.changed.store._table", lambda: FakeTable())

    assert restore_scrape_state()
    assert (data / "processed_games.json").exists()


def test_restore_scrape_state_converts_dynamodb_decimals(tmp_path, monkeypatch):
    data = _use_data_dir(tmp_path, monkeypatch)
    monkeypatch.setattr("etl.changed.store.config.DYNAMODB_TABLE", "test-table")
    monkeypatch.setattr("etl.changed.store.config.DATA_DIR", data)
    state = {
        "760001": {
            "status": "ok",
            "players": Decimal("32"),
        }
    }

    class FakeTable:
        def get_item(self, *, Key):
            if Key["SK"] == "SCRAPE_STATE":
                return {"Item": {"processed_games": state}}
            return {}

    monkeypatch.setattr("etl.changed.store._table", lambda: FakeTable())

    assert restore_scrape_state()
    restored = json.loads((data / "processed_games.json").read_text())
    assert restored["760001"]["players"] == 32
    assert isinstance(restored["760001"]["players"], int)
