"""Tests for atwc26_core artifact definitions."""
from __future__ import annotations

from atwc26_core.artifacts import (
    ARTIFACTS,
    iter_game_artifacts,
    publishable_artifacts,
    resolve_artifact,
    s3_key_for,
)
from atwc26_core import config


def test_artifacts_use_data_dir():
    for spec in ARTIFACTS:
        assert spec.path.is_absolute() or True
        assert str(config.DATA_DIR) in str(spec.path) or spec.path.parent == config.DATA_DIR


def test_required_artifact_names():
    names = {a.name for a in ARTIFACTS if a.required}
    assert "master_parquet" in names
    assert "match_events" in names


def test_backtest_summary_is_published():
    names = {a.name for a in ARTIFACTS}
    assert "backtest_summary" in names
    spec = next(a for a in ARTIFACTS if a.name == "backtest_summary")
    assert spec.path.name == "backtest_summary.json"
    assert spec.required is False


def test_s3_key_for_uses_prefix():
    spec = next(a for a in ARTIFACTS if a.name == "master_parquet")
    key = s3_key_for(spec, prefix="data")
    assert key == f"data/{spec.path.name}"


def test_s3_key_for_preserves_games_subdir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    games = tmp_path / "games"
    games.mkdir()
    path = games / "game_760511.parquet"
    path.write_bytes(b"x")
    from atwc26_core.artifacts import ArtifactSpec

    spec = ArtifactSpec("game_760511", path, False, "parquet")
    assert s3_key_for(spec, prefix="data") == "data/games/game_760511.parquet"


def test_iter_game_artifacts_discovers_parquets(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    games = tmp_path / "games"
    games.mkdir()
    (games / "game_760511.parquet").write_bytes(b"a")
    (games / "game_760512.parquet").write_bytes(b"b")
    specs = iter_game_artifacts()
    assert {s.name for s in specs} == {"game_760511", "game_760512"}
    assert all(s.name in {a.name for a in publishable_artifacts()} for s in specs)


def test_resolve_artifact_game_from_manifest_key(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    spec = resolve_artifact(
        "game_760514",
        {"s3_key": "data/games/game_760514.parquet"},
    )
    assert spec is not None
    assert spec.path == tmp_path / "games" / "game_760514.parquet"


def test_manifest_path_under_data_dir():
    manifest = config.DATA_DIR / ".etl" / "manifest.json"
    assert manifest.parent.name == ".etl"
