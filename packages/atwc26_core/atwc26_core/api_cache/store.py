"""Read/write API-ready cache items (DynamoDB or local dry-run)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atwc26_core import config

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]

LOCAL_CACHE_DIR = config.DATA_DIR / ".etl" / "api-cache"


def _local_path(pk: str, sk: str) -> Path:
    safe = f"{pk}__{sk}".replace("/", "_").replace("#", "_")
    return LOCAL_CACHE_DIR / f"{safe}.json"


class ApiCacheStore:
    """DynamoDB-backed API cache with local dry-run fallback."""

    def __init__(self, *, table_name: str | None = None) -> None:
        self.table_name = table_name or config.DYNAMODB_TABLE
        self._table = None
        if boto3 and config.S3_BUCKET and self.table_name:
            dynamodb = boto3.resource("dynamodb", region_name=config.AWS_REGION)
            self._table = dynamodb.Table(self.table_name)

    def get_item(self, pk: str, sk: str) -> dict[str, Any] | None:
        if self._table is not None:
            resp = self._table.get_item(Key={"PK": pk, "SK": sk})
            return resp.get("Item")

        path = _local_path(pk, sk)
        if path.exists():
            return json.loads(path.read_text())
        return None

    def get_payload(self, pk: str, sk: str) -> Any | None:
        item = self.get_item(pk, sk)
        if not item:
            return None
        return item.get("payload")

    def put_item(
        self,
        *,
        pk: str,
        sk: str,
        payload: Any,
        source_sha256: str,
        source_artifacts: list[str],
        published_at: str | None = None,
    ) -> None:
        published_at = published_at or datetime.now(timezone.utc).isoformat()
        item = {
            "PK": pk,
            "SK": sk,
            "published_at": published_at,
            "source_sha256": source_sha256,
            "source_artifacts": source_artifacts,
            "payload": payload,
        }

        if self._table is not None:
            self._table.put_item(Item=item)
            return

        LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _local_path(pk, sk).write_text(json.dumps(item, indent=2) + "\n")

    def should_skip(self, pk: str, sk: str, source_sha256: str) -> bool:
        existing = self.get_item(pk, sk)
        return bool(existing and existing.get("source_sha256") == source_sha256)


_store: ApiCacheStore | None = None


def get_api_cache_store() -> ApiCacheStore:
    global _store
    if _store is None:
        _store = ApiCacheStore()
    return _store
