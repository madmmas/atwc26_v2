"""Publish ETL artifacts to S3 and record manifest in DynamoDB."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from atwc26_core import config
from atwc26_core.artifacts import ARTIFACTS, s3_key_for

from ..changed.detect import changed_game_ids, fingerprint, match_fingerprint
from ..changed.store import read_scrape_state, save_fingerprint, save_scrape_state
from ..changed.triggers import mark_games_finished
from ..transform.run import MANIFEST_FILE, build_manifest, write_manifest
from .api_cache import (
    publish_api_cache,
    publish_leaderboards_cache,
    publish_matches_cache,
    publish_teams_cache,
)
from .refresh import refresh_compute

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


def _publish_api_caches(manifest: dict) -> None:
    from atwc26_core.data import get_store

    store = get_store()
    s = publish_api_cache(manifest, store=store)
    t = publish_teams_cache(manifest, store=store)
    m = publish_matches_cache(manifest, store=store)
    l = publish_leaderboards_cache(manifest, store=store)
    total_written = s["written"] + t["written"] + m["written"] + l["written"]
    total_skipped = s["skipped"] + t["skipped"] + m["skipped"] + l["skipped"]
    if total_written or total_skipped:
        print(f"api cache: {total_written} written, {total_skipped} unchanged")


def _load_before_fingerprint() -> dict[str, str] | None:
    path = os.getenv("ETL_BEFORE_FINGERPRINT", "")
    if not path:
        return None
    fp_path = Path(path)
    if not fp_path.is_file():
        return None
    data = json.loads(fp_path.read_text())
    return data if isinstance(data, dict) else None


def _persist_etl_state(*, before_fingerprint: dict[str, str] | None = None) -> None:
    """Record scrape inputs + processed_games for the next scheduled CI run."""
    after = fingerprint()
    save_fingerprint(after)
    if before_fingerprint is not None:
        game_ids = changed_game_ids(before_fingerprint, match_fingerprint())
        if game_ids:
            mark_games_finished(game_ids)
    state = read_scrape_state()
    if state:
        save_scrape_state(state)


def run_publish(
    *,
    refresh_manifest: bool = True,
    refresh_lambdas: bool = True,
    refresh_ecs: bool = True,
) -> int:
    if refresh_manifest:
        manifest = build_manifest()
        write_manifest(manifest)
    else:
        manifest = _load_manifest()

    if config.S3_BUCKET:
        result = publish_aws(manifest)
        _persist_etl_state(before_fingerprint=_load_before_fingerprint())
        if result.get("uploaded") and (refresh_lambdas or refresh_ecs):
            refreshed = refresh_compute(
                result["publish_id"],
                refresh_lambdas=refresh_lambdas,
                refresh_ecs=refresh_ecs,
            )
            lambdas = refreshed["lambdas"]
            services = refreshed["services"]
            if lambdas:
                print(f"refreshed Lambda(s): {', '.join(lambdas)}")
            if services:
                print(f"refreshed ECS service(s): {', '.join(services)}")
    else:
        publish_local(manifest)
        print("set ATWC26_S3_BUCKET (+ AWS creds) to publish to S3")

    _publish_api_caches(manifest)
    return 0


def main() -> int:
    return run_publish()


if __name__ == "__main__":
    raise SystemExit(main())
