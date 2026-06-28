"""Canonical ETL artifact definitions used by transform, QA, and publish."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: Path
    required: bool
    kind: str  # parquet | json | csv


ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("master_parquet", config.MASTER_PARQUET, True, "parquet"),
    ArtifactSpec("historical_form", config.HISTORICAL_FORM, False, "parquet"),
    ArtifactSpec("match_events", config.MATCH_EVENTS, True, "json"),
    ArtifactSpec("squads_raw", config.SQUADS_RAW, False, "json"),
    ArtifactSpec("standings", config.STANDINGS, False, "json"),
    ArtifactSpec("bracket", config.BRACKET, False, "json"),
    ArtifactSpec("glossary", config.GLOSSARY_CSV, False, "csv"),
    ArtifactSpec("team_flags", config.TEAM_FLAGS, False, "json"),
)


def s3_key_for(artifact: ArtifactSpec, prefix: str = config.S3_PREFIX) -> str:
    """Return the S3 object key for an artifact under the configured prefix."""
    return f"{prefix}/{artifact.path.name}"
