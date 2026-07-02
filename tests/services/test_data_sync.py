"""Tests for manifest-based S3 sync and data reload."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from atwc26_core import config


def test_sync_from_manifest_no_aws_is_noop(monkeypatch):
    monkeypatch.setattr(config, "S3_BUCKET", "")
    monkeypatch.setattr(config, "DYNAMODB_TABLE", "")

    from services.shared.data_sync import sync_from_manifest

    assert sync_from_manifest() == []


def test_sync_downloads_only_changed_artifacts(tmp_path, monkeypatch):
    pytest.importorskip("boto3")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(config, "DYNAMODB_TABLE", "test-manifest")

    master = tmp_path / "all_players_stats.parquet"
    events = tmp_path / "match_events.json"
    master.write_bytes(b"unchanged")
    events.write_text("{}")

    fake_artifacts = (
        type("S", (), {"name": "master_parquet", "path": master, "required": True})(),
        type("S", (), {"name": "match_events", "path": events, "required": True})(),
    )

    import services.shared.data_sync as data_sync_mod

    monkeypatch.setattr(data_sync_mod, "ARTIFACTS", fake_artifacts)
    monkeypatch.setattr(data_sync_mod, "SYNC_MANIFEST", tmp_path / ".etl" / "sync-manifest.json")

    latest = {
        "latest_publish_sk": "PUBLISH#1",
        "published_at": "2026-07-01T00:00:00+00:00",
        "artifacts": {
            "master_parquet": {"sha256": "aaa", "s3_key": "data/all_players_stats.parquet"},
            "match_events": {"sha256": "bbb", "s3_key": "data/match_events.json"},
        },
    }

    sync_manifest = tmp_path / ".etl" / "sync-manifest.json"
    sync_manifest.parent.mkdir(parents=True)
    sync_manifest.write_text(
        json.dumps({"artifacts": {"master_parquet": {"sha256": "aaa"}}}) + "\n"
    )

    downloads: list[str] = []

    class FakeS3:
        def download_file(self, bucket, key, dest):
            downloads.append(key)
            Path(dest).write_bytes(b"new-bytes")

    class FakeTable:
        def get_item(self, Key):
            return {"Item": latest}

    import sys

    fake_boto = type(
        "Boto",
        (),
        {
            "client": staticmethod(lambda *a, **k: FakeS3()),
            "resource": staticmethod(
                lambda *a, **k: type("R", (), {"Table": staticmethod(lambda t: FakeTable())})()
            ),
        },
    )
    monkeypatch.setitem(sys.modules, "boto3", fake_boto)

    from services.shared.data_sync import sync_from_manifest

    updated = sync_from_manifest()
    assert updated == ["match_events"]
    assert downloads == ["data/match_events.json"]
    assert (tmp_path / "match_events.json").read_bytes() == b"new-bytes"


def test_reload_data_clears_predictor_cache(monkeypatch):
    import atwc26_core.prediction as prediction
    import atwc26_core.tournament as tournament
    from atwc26_core import reload as reload_mod
    from atwc26_core.reload import reload_data

    prediction._predictor = object()
    tournament._probabilities = {"Brazil": 0.1}
    monkeypatch.setattr(reload_mod.store, "load", lambda force=False: None)

    reload_data()

    assert prediction._predictor is None
    assert tournament._probabilities is None


def test_ensure_data_available_reloads_on_update(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    reloaded: list[bool] = []

    monkeypatch.setattr(
        "services.shared.bootstrap.sync_from_manifest",
        lambda: ["master_parquet"],
    )
    monkeypatch.setattr(
        "services.shared.bootstrap.reload_data",
        lambda: reloaded.append(True),
    )

    from services.shared.bootstrap import ensure_data_available

    assert ensure_data_available() == ["master_parquet"]
    assert reloaded == [True]
