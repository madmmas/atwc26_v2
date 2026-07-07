"""Sync published ETL artifacts from S3 using the DynamoDB LATEST manifest."""
from __future__ import annotations

import json
from pathlib import Path

from atwc26_core import config
from atwc26_core.api_cache.store import _from_dynamo
from atwc26_core.artifacts import ARTIFACTS, s3_key_for

DATASET = "wc26"
SYNC_MANIFEST = config.DATA_DIR / ".etl" / "sync-manifest.json"


def _local_hashes() -> dict[str, str]:
    if not SYNC_MANIFEST.exists():
        return {}
    data = json.loads(SYNC_MANIFEST.read_text())
    artifacts = data.get("artifacts") or {}
    return {
        name: meta.get("sha256", "")
        for name, meta in artifacts.items()
        if isinstance(meta, dict)
    }


def _fetch_latest_manifest(table) -> dict | None:
    resp = table.get_item(Key={"PK": f"DATASET#{DATASET}", "SK": "LATEST"})
    item = resp.get("Item")
    return _from_dynamo(item) if item else None


def sync_from_manifest(*, force: bool = False) -> list[str]:
    """Download artifacts whose sha256 differs from the published manifest.

    Returns artifact names that were downloaded. No-op when S3/DynamoDB are
    unset (local dev with a mounted ``data/`` directory).
    """
    bucket = config.S3_BUCKET
    table_name = config.DYNAMODB_TABLE
    if not bucket or not table_name:
        return []

    try:
        import boto3
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("boto3 required for S3 data sync") from exc

    ddb = boto3.resource("dynamodb", region_name=config.AWS_REGION)
    s3 = boto3.client("s3", region_name=config.AWS_REGION)
    latest = _fetch_latest_manifest(ddb.Table(table_name))
    if not latest:
        return []

    remote = latest.get("artifacts") or {}
    local = {} if force else _local_hashes()
    updated: list[str] = []

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for spec in ARTIFACTS:
        meta = remote.get(spec.name)
        if not meta:
            continue
        sha = meta.get("sha256", "")
        if not force and local.get(spec.name) == sha and spec.path.exists():
            continue
        key = meta.get("s3_key") or s3_key_for(spec)
        spec.path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, key, str(spec.path))
        updated.append(spec.name)

    SYNC_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    SYNC_MANIFEST.write_text(
        json.dumps(
            {
                "latest_publish_sk": latest.get("latest_publish_sk"),
                "published_at": latest.get("published_at"),
                "artifacts": remote,
            },
            indent=2,
        )
        + "\n"
    )
    return updated
