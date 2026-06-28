"""Publish ETL artifacts to S3 and record manifest in DynamoDB."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from atwc26_core import config
from atwc26_core.artifacts import ARTIFACTS, s3_key_for

from ..transform.run import MANIFEST_FILE, build_manifest, write_manifest

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]

STAGING_DIR = config.DATA_DIR / ".etl" / "publish-staging"


def _load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text())
    return build_manifest()


def _existing_remote_hashes(table, dataset: str) -> dict[str, str]:
    """Return artifact_name -> sha256 from the LATEST DynamoDB record, if any."""
    try:
        resp = table.get_item(Key={"PK": f"DATASET#{dataset}", "SK": "LATEST"})
    except Exception:
        return {}
    item = resp.get("Item") or {}
    artifacts = item.get("artifacts") or {}
    return {
        name: meta.get("sha256", "")
        for name, meta in artifacts.items()
        if isinstance(meta, dict)
    }


def publish_local(manifest: dict) -> Path:
    """Dry-run publish: copy artifacts + manifest into local staging dir."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for spec in ARTIFACTS:
        if not spec.path.exists():
            continue
        dest = STAGING_DIR / spec.path.name
        dest.write_bytes(spec.path.read_bytes())
        copied += 1
    staging_manifest = STAGING_DIR / "manifest.json"
    staging_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"staged {copied} artifact(s) -> {STAGING_DIR}")
    return STAGING_DIR


def publish_aws(manifest: dict) -> dict:
    """Upload artifacts to S3 and upsert DynamoDB manifest (idempotent by sha256)."""
    from botocore.exceptions import ClientError

    if boto3 is None:
        raise ImportError("boto3 is required for AWS publish (pip install atwc26-core[publish])")
    if not config.S3_BUCKET:
        raise ValueError("ATWC26_S3_BUCKET is required for AWS publish")

    s3 = boto3.client("s3", region_name=config.AWS_REGION)
    dynamodb = boto3.resource("dynamodb", region_name=config.AWS_REGION)
    table = dynamodb.Table(config.DYNAMODB_TABLE)

    dataset = manifest.get("dataset", "wc26")
    remote_hashes = _existing_remote_hashes(table, dataset)

    uploaded: list[str] = []
    skipped: list[str] = []
    artifact_meta: dict[str, dict] = {}

    for spec in ARTIFACTS:
        entry = manifest["artifacts"].get(spec.name, {})
        if not entry.get("exists"):
            continue
        sha = entry.get("sha256", "")
        key = s3_key_for(spec)
        artifact_meta[spec.name] = {
            "s3_key": key,
            "sha256": sha,
            "bytes": entry.get("bytes"),
            "kind": spec.kind,
        }
        if remote_hashes.get(spec.name) == sha:
            skipped.append(spec.name)
            continue
        s3.upload_file(str(spec.path), config.S3_BUCKET, key)
        uploaded.append(spec.name)

    published_at = datetime.now(timezone.utc).isoformat()
    publish_id = published_at.replace(":", "").replace("-", "").replace("+", "")

    item = {
        "PK": f"DATASET#{dataset}",
        "SK": f"PUBLISH#{publish_id}",
        "dataset": dataset,
        "published_at": published_at,
        "s3_bucket": config.S3_BUCKET,
        "s3_prefix": config.S3_PREFIX,
        "artifacts": artifact_meta,
        "git_sha": os.getenv("GITHUB_SHA", ""),
    }

    try:
        table.put_item(Item=item)
        table.put_item(
            Item={
                "PK": f"DATASET#{dataset}",
                "SK": "LATEST",
                "published_at": published_at,
                "s3_bucket": config.S3_BUCKET,
                "s3_prefix": config.S3_PREFIX,
                "artifacts": artifact_meta,
                "latest_publish_sk": item["SK"],
            }
        )
    except ClientError as exc:
        raise RuntimeError(f"DynamoDB write failed: {exc}") from exc

    print(
        f"published to s3://{config.S3_BUCKET}/{config.S3_PREFIX}/ "
        f"({len(uploaded)} uploaded, {len(skipped)} unchanged)"
    )
    return {"uploaded": uploaded, "skipped": skipped, "publish_id": publish_id}


def run_publish(*, refresh_manifest: bool = True) -> int:
    if refresh_manifest:
        manifest = build_manifest()
        write_manifest(manifest)
    else:
        manifest = _load_manifest()

    if config.S3_BUCKET:
        publish_aws(manifest)
    else:
        publish_local(manifest)
        print("set ATWC26_S3_BUCKET (+ AWS creds) to publish to S3")
    return 0


def main() -> int:
    return run_publish()


if __name__ == "__main__":
    raise SystemExit(main())
