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


def test_sync_writes_manifest_with_dynamodb_decimals(tmp_path, monkeypatch):
    """DynamoDB returns Decimal for numbers; sync manifest must json.dumps cleanly."""
    from decimal import Decimal

    pytest.importorskip("boto3")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(config, "DYNAMODB_TABLE", "test-manifest")

    master = tmp_path / "all_players_stats.parquet"
    from atwc26_core.artifacts import ArtifactSpec

    import services.shared.data_sync as data_sync_mod

    monkeypatch.setattr(
        data_sync_mod,
        "resolve_artifact",
        lambda name, meta=None: ArtifactSpec("master_parquet", master, True, "parquet")
        if name == "master_parquet"
        else None,
    )
    monkeypatch.setattr(data_sync_mod, "SYNC_MANIFEST", tmp_path / ".etl" / "sync-manifest.json")

    latest = {
        "latest_publish_sk": "PUBLISH#1",
        "published_at": "2026-07-01T00:00:00+00:00",
        "artifacts": {
            "master_parquet": {
                "sha256": "aaa",
                "s3_key": "data/all_players_stats.parquet",
                "size_bytes": Decimal("12345"),
            },
        },
    }

    class FakeS3:
        def download_file(self, bucket, key, dest):
            Path(dest).write_bytes(b"parquet")

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
    assert updated == ["master_parquet"]

    manifest = json.loads((tmp_path / ".etl" / "sync-manifest.json").read_text())
    assert manifest["artifacts"]["master_parquet"]["size_bytes"] == 12345


def test_sync_downloads_only_changed_artifacts(tmp_path, monkeypatch):
    pytest.importorskip("boto3")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(config, "DYNAMODB_TABLE", "test-manifest")

    master = tmp_path / "all_players_stats.parquet"
    events = tmp_path / "match_events.json"
    master.write_bytes(b"unchanged")
    events.write_text("{}")

    from atwc26_core.artifacts import ArtifactSpec

    def fake_resolve(name, meta=None):
        if name == "master_parquet":
            return ArtifactSpec("master_parquet", master, True, "parquet")
        if name == "match_events":
            return ArtifactSpec("match_events", events, True, "json")
        return None

    import services.shared.data_sync as data_sync_mod

    monkeypatch.setattr(data_sync_mod, "resolve_artifact", fake_resolve)
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


def test_sync_downloads_game_parquets(tmp_path, monkeypatch):
    pytest.importorskip("boto3")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(config, "DYNAMODB_TABLE", "test-manifest")

    import services.shared.data_sync as data_sync_mod

    monkeypatch.setattr(data_sync_mod, "SYNC_MANIFEST", tmp_path / ".etl" / "sync-manifest.json")

    latest = {
        "latest_publish_sk": "PUBLISH#1",
        "published_at": "2026-07-01T00:00:00+00:00",
        "artifacts": {
            "game_760511": {
                "sha256": "g1",
                "s3_key": "data/games/game_760511.parquet",
            },
        },
    }

    downloads: list[str] = []

    class FakeS3:
        def download_file(self, bucket, key, dest):
            downloads.append(key)
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"game-bytes")

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
    assert updated == ["game_760511"]
    assert downloads == ["data/games/game_760511.parquet"]
    assert (tmp_path / "games" / "game_760511.parquet").read_bytes() == b"game-bytes"


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
