"""Reload in-memory data and model caches after artifact sync."""
from __future__ import annotations

from . import prediction, tournament
from .data import store


def reload_data() -> None:
    """Force DataStore reload and clear derived singleton caches."""
    prediction._predictor = None  # noqa: SLF001
    tournament._probabilities = None  # noqa: SLF001
    tournament._bracket_predictions = None  # noqa: SLF001
    store.load(force=True)
