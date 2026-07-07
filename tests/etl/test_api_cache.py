"""Tests for DynamoDB API cache publish and read."""
from __future__ import annotations

from decimal import Decimal

import pytest

from atwc26_core import config
from atwc26_core.api_cache import keys
from atwc26_core.api_cache.builders import build_overview, build_standings, build_winner_probabilities
from atwc26_core.api_cache.store import ApiCacheStore, _from_dynamo, _to_dynamo
from atwc26_core.data import get_store
from etl.publish.api_cache import publish_api_cache, publish_matches_cache, publish_teams_cache
from etl.transform.run import build_manifest


@pytest.fixture
def local_cache_dir(tmp_path, monkeypatch):
    cache_dir = tmp_path / "api-cache"
    monkeypatch.setattr(
        "atwc26_core.api_cache.store.LOCAL_CACHE_DIR",
        cache_dir,
    )
    monkeypatch.setattr(config, "S3_BUCKET", "")
    monkeypatch.setenv("ATWC26_S3_BUCKET", "")
    get_store.cache_clear() if hasattr(get_store, "cache_clear") else None
    yield cache_dir


def test_to_dynamo_converts_floats_and_numpy():
    import numpy as np

    payload = {
        "score": 1.5,
        "count": np.int64(3),
        "rate": np.float64(0.75),
        "nested": [{"xg": 0.42}],
    }
    dynamo = _to_dynamo(payload)
    assert isinstance(dynamo["score"], Decimal)
    assert dynamo["count"] == 3
    assert isinstance(dynamo["rate"], Decimal)
    assert isinstance(dynamo["nested"][0]["xg"], Decimal)

    roundtrip = _from_dynamo(dynamo)
    assert roundtrip["score"] == 1.5
    assert roundtrip["count"] == 3
    assert roundtrip["rate"] == 0.75
    assert roundtrip["nested"][0]["xg"] == 0.42


def test_put_item_serializes_overview_for_dynamodb(monkeypatch):
    pytest.importorskip("boto3")
    store = get_store()
    manifest = build_manifest()
    overview, sha, sources = build_overview(store, manifest)

    captured: dict = {}

    class FakeTable:
        def put_item(self, Item):
            captured["item"] = Item

    monkeypatch.setattr(config, "S3_BUCKET", "test-bucket")
    monkeypatch.setattr(config, "DYNAMODB_TABLE", "test-table")
    cache = ApiCacheStore(table_name="test-table")
    cache._table = FakeTable()

    cache.put_item(
        pk=keys.dataset_pk(),
        sk=keys.overview_sk(),
        payload=overview,
        source_sha256=sha,
        source_artifacts=sources,
    )

    assert captured["item"]
    assert not any(isinstance(v, float) for v in _walk_values(captured["item"]))


def _walk_values(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_values(v)
    else:
        yield obj


def test_build_standings_payload():
    store = get_store()
    manifest = build_manifest()
    payload, sha, sources = build_standings(store, manifest)
    assert "groups" in payload
    assert payload["groups"] == store.standings
    assert sha
    assert sources == ["standings"]


def test_build_winner_probabilities_payload():
    store = get_store()
    manifest = build_manifest()
    payload, sha, sources = build_winner_probabilities(store, manifest)
    assert payload and "teams" in payload
    assert sha
    assert sources == ["winner_probabilities"]


def test_publish_standings_local_idempotent(local_cache_dir):
    store = get_store()
    manifest = build_manifest()
    first = publish_api_cache(manifest, store=store)
    second = publish_api_cache(manifest, store=store)
    assert first["written"] >= 1
    assert second["skipped"] >= 1

    cache = ApiCacheStore()
    item = cache.get_item(keys.dataset_pk(), keys.standings_sk())
    assert item is not None
    assert item["payload"]["groups"] == store.standings


def test_publish_teams_and_matches_local(local_cache_dir):
    store = get_store()
    manifest = build_manifest()
    teams = publish_teams_cache(manifest, store=store)
    matches = publish_matches_cache(manifest, store=store)
    assert teams["written"] >= 1
    assert matches["written"] >= 1

    cache = ApiCacheStore()
    teams_payload = cache.get_payload(keys.dataset_pk(), keys.teams_sk())
    assert teams_payload and "teams" in teams_payload


def test_read_cached_uses_local_file(local_cache_dir):
    from services.shared.api_reader import clear_memory_cache, read_cached

    clear_memory_cache()
    store = get_store()
    manifest = build_manifest()
    publish_api_cache(manifest, store=store)

    def _fallback():
        return {"groups": {"unexpected": True}}

    payload = read_cached(keys.dataset_pk(), keys.standings_sk(), _fallback)
    assert payload["groups"] == store.standings
