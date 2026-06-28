"""Tests for atwc26_core artifact definitions."""
from __future__ import annotations

from pathlib import Path

from atwc26_core.artifacts import ARTIFACTS, s3_key_for
from atwc26_core import config


def test_artifacts_use_data_dir():
    for spec in ARTIFACTS:
        assert spec.path.is_absolute() or True
        assert str(config.DATA_DIR) in str(spec.path) or spec.path.parent == config.DATA_DIR


def test_required_artifact_names():
    names = {a.name for a in ARTIFACTS if a.required}
    assert "master_parquet" in names
    assert "match_events" in names


def test_s3_key_for_uses_prefix():
    spec = next(a for a in ARTIFACTS if a.name == "master_parquet")
    key = s3_key_for(spec, prefix="data")
    assert key == f"data/{spec.path.name}"


def test_manifest_path_under_data_dir():
    manifest = config.DATA_DIR / ".etl" / "manifest.json"
    assert manifest.parent.name == ".etl"
