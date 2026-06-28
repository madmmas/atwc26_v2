"""Cold-start data bootstrap for Lambda (sync artifacts from S3)."""
from __future__ import annotations

import os
from pathlib import Path

from atwc26_core.artifacts import ARTIFACTS
from atwc26_core import config


def ensure_data_available() -> None:
    """Download published artifacts from S3 when running without a local data/ mount."""
    bucket = config.S3_BUCKET or os.getenv("ATWC26_S3_BUCKET", "")
    if not bucket:
        return

    data_dir = Path(os.getenv("ATWC26_DATA_DIR", str(config.DATA_DIR)))
    marker = data_dir / ".etl" / "lambda-synced"
    if marker.exists():
        return

    try:
        import boto3
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("boto3 required for S3 data bootstrap") from exc

    data_dir.mkdir(parents=True, exist_ok=True)
    s3 = boto3.client("s3", region_name=config.AWS_REGION)
    for spec in ARTIFACTS:
        if not spec.path.exists():
            key = f"{config.S3_PREFIX}/{spec.path.name}"
            try:
                s3.download_file(bucket, key, str(spec.path))
            except Exception:
                if spec.required:
                    raise

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("ok\n")
