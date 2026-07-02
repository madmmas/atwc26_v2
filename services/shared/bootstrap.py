"""Cold-start data bootstrap for Lambda and ECS (sync artifacts from S3)."""
from __future__ import annotations

from atwc26_core import config
from atwc26_core.reload import reload_data

from .data_sync import sync_from_manifest


def ensure_data_available() -> list[str]:
    """Sync published artifacts from S3 and reload caches when data changed.

    Returns artifact names downloaded. No-op when ``ATWC26_S3_BUCKET`` is unset
    (local dev with a mounted ``data/`` tree).
    """
    if not config.S3_BUCKET:
        return []

    updated = sync_from_manifest()
    if updated:
        reload_data()
    return updated
