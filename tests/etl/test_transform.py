"""Tests for ETL transform manifest generation."""
from __future__ import annotations

import json

from etl.transform.run import build_manifest, write_manifest, MANIFEST_FILE


def test_build_manifest_has_artifacts():
    manifest = build_manifest()
    assert manifest["dataset"] == "wc26"
    assert "artifacts" in manifest
    assert "master_parquet" in manifest["artifacts"]
    assert "match_events" in manifest["artifacts"]


def test_write_manifest_creates_file(tmp_path, monkeypatch):
    from atwc26_core import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr("etl.transform.run.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("etl.transform.run.MANIFEST_DIR", tmp_path / ".etl")
    monkeypatch.setattr("etl.transform.run.MANIFEST_FILE", tmp_path / ".etl" / "manifest.json")

    path = write_manifest({"dataset": "wc26", "artifacts": {}})
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["dataset"] == "wc26"
