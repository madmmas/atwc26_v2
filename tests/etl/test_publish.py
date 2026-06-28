"""Tests for ETL publish (local staging mode)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from atwc26_core import config


def test_publish_local_stages_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "S3_BUCKET", "")
    monkeypatch.setattr("etl.publish.publish.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("etl.publish.publish.config.S3_BUCKET", "")
    monkeypatch.setattr("etl.publish.publish.STAGING_DIR", tmp_path / ".etl" / "publish-staging")

    manifest_path = tmp_path / ".etl" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest = {
        "dataset": "wc26",
        "artifacts": {
            "master_parquet": {"exists": False},
        },
    }
    manifest_path.write_text(json.dumps(manifest))

    monkeypatch.setattr("etl.publish.publish.MANIFEST_FILE", manifest_path)

    from etl.publish.publish import publish_local

    staging = publish_local(manifest)
    assert staging.exists()
    assert (staging / "manifest.json").exists()


def test_publish_aws_idempotent_skip(monkeypatch):
    pytest.importorskip("boto3")
    from etl.publish import publish as publish_mod

    manifest = {
        "dataset": "wc26",
        "artifacts": {
            "master_parquet": {
                "exists": True,
                "sha256": "abc123",
                "bytes": 10,
            },
        },
    }

    class FakeTable:
        def get_item(self, Key):
            return {
                "Item": {
                    "artifacts": {
                        "master_parquet": {"sha256": "abc123"},
                    },
                },
            }

        def put_item(self, Item):
            self.last_item = Item

    class FakeS3:
        def upload_file(self, *args, **kwargs):
            raise AssertionError("should not upload unchanged artifact")

    fake_table = FakeTable()
    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(publish_mod.config, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(
        publish_mod,
        "boto3",
        type(
            "Boto",
            (),
            {
                "client": staticmethod(lambda *a, **k: FakeS3()),
                "resource": staticmethod(
                    lambda *a, **k: type("R", (), {"Table": staticmethod(lambda t: fake_table)})()
                ),
            },
        ),
    )

    result = publish_mod.publish_aws(manifest)
    assert result["skipped"] == ["master_parquet"]
    assert result["uploaded"] == []
