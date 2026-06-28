"""Run transform steps and write a publish manifest under data/.etl/."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from atwc26_core.artifacts import ARTIFACTS, ArtifactSpec, s3_key_for
from atwc26_core import config

ETL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ETL_DIR.parent
MANIFEST_DIR = config.DATA_DIR / ".etl"
MANIFEST_FILE = MANIFEST_DIR / "manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_match_events() -> None:
    """Rebuild match timelines from data/raw/*.json."""
    script = ETL_DIR / "build_match_events.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=REPO_ROOT)


def build_manifest() -> dict:
    """Collect artifact metadata (paths, sizes, hashes, S3 keys)."""
    published_at = datetime.now(timezone.utc).isoformat()
    artifacts: dict[str, dict] = {}
    for spec in ARTIFACTS:
        entry: dict = {
            "name": spec.name,
            "path": str(spec.path.relative_to(REPO_ROOT)),
            "kind": spec.kind,
            "required": spec.required,
            "s3_key": s3_key_for(spec),
            "exists": spec.path.exists(),
        }
        if spec.path.exists():
            entry["bytes"] = spec.path.stat().st_size
            entry["sha256"] = _sha256(spec.path)
        artifacts[spec.name] = entry

    return {
        "dataset": "wc26",
        "published_at": published_at,
        "data_dir": str(config.DATA_DIR),
        "s3_bucket": config.S3_BUCKET or None,
        "s3_prefix": config.S3_PREFIX,
        "dynamodb_table": config.DYNAMODB_TABLE,
        "artifacts": artifacts,
    }


def write_manifest(manifest: dict | None = None) -> Path:
    manifest = manifest or build_manifest()
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2) + "\n")
    return MANIFEST_FILE


def run_transform(*, skip_match_events: bool = False) -> Path:
    """Execute transform steps and write manifest.json."""
    if not skip_match_events:
        run_match_events()
    return write_manifest()


def main() -> int:
    run_transform()
    print(f"wrote manifest -> {MANIFEST_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
