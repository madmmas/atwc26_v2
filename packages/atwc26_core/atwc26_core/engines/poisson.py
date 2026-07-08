"""Wraps the existing Predictor as a ModelEngine."""
from __future__ import annotations

from ..prediction import Predictor


class PoissonEngine:
    name = "poisson"

    def __init__(self, predictor: Predictor) -> None:
        self._predictor = predictor

    def is_available(self) -> bool:
        return self._predictor is not None

    def predict(self, team_a: dict, team_b: dict) -> dict:
        result = self._predictor.predict(team_a, team_b)
        # Normalise to common field names expected by the multi-model response.
        result["win_probability_a"] = result["team_a"]["win_probability"]
        result["win_probability_b"] = result["team_b"]["win_probability"]
        result["draw_probability"] = result["draw_prob"]
        result["model"] = {
            "name": "poisson",
            "version": "1.0",
            "description": (
                "Player-aggregated Poisson goals model. "
                "Role-weighted per-90 xG/xA/defensive stats → team λ → "
                "scoreline probability matrix."
            ),
        }
        return result
