"""Shared core library for AnalyseThisWC26."""

from .artifacts import ARTIFACTS, ArtifactSpec
from .config import (
    BRACKET,
    DATA_DIR,
    GLOSSARY_CSV,
    HISTORICAL_FORM,
    MASTER_PARQUET,
    MATCH_EVENTS,
    SQUADS_RAW,
    STANDINGS,
    TEAM_FLAGS,
)

__all__ = [
    "ARTIFACTS",
    "ArtifactSpec",
    "BRACKET",
    "DATA_DIR",
    "GLOSSARY_CSV",
    "HISTORICAL_FORM",
    "MASTER_PARQUET",
    "MATCH_EVENTS",
    "SQUADS_RAW",
    "STANDINGS",
    "TEAM_FLAGS",
]
