"""Elo rating system for WC2026 team strength."""
from __future__ import annotations

import json

from atwc26_core import config


class EloEngine:
    """Team-level Elo ratings. Produces win/draw/loss probabilities only
    (no scoreline, no xG — Elo is a ranking signal, not a goals model)."""

    name = "elo"
    HOME_ADVANTAGE = 100   # Elo points added to home team rating
    DRAW_FACTOR = 0.25     # approximate draw probability when teams are equal

    def __init__(self) -> None:
        self._ratings: dict[str, float] = {}

    def load(self, path=None) -> bool:
        """Load ratings from data/elo_ratings.json. Returns True if loaded."""
        path = path or config.ELO_RATINGS
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
            self._ratings = {str(k): float(v) for k, v in data.get("ratings", {}).items()}
            return bool(self._ratings)
        except Exception:
            return False

    def is_available(self) -> bool:
        return bool(self._ratings)

    def get_rating(self, team_name: str, default: float = 1500.0) -> float:
        return self._ratings.get(team_name, default)

    def _win_probs(self, r_a: float, r_b: float, home_a: bool) -> tuple[float, float, float]:
        ha = self.HOME_ADVANTAGE if home_a else 0.0
        e_a = 1.0 / (1.0 + 10.0 ** ((r_b - r_a - ha) / 400.0))
        # draw probability peaks at ~0.25 when teams are equal
        p_draw = self.DRAW_FACTOR * (1.0 - abs(e_a - 0.5) * 2.0)
        p_a = e_a * (1.0 - p_draw)
        p_b = (1.0 - e_a) * (1.0 - p_draw)
        return round(p_a, 4), round(p_draw, 4), round(p_b, 4)

    def predict(self, team_a: dict, team_b: dict) -> dict:
        r_a = self.get_rating(team_a["team_name"])
        r_b = self.get_rating(team_b["team_name"])
        home_a = team_a.get("home", False)
        p_a, p_draw, p_b = self._win_probs(r_a, r_b, home_a)
        return {
            "team_a": {"team_name": team_a["team_name"], "elo_rating": round(r_a, 1), "win_probability": p_a},
            "team_b": {"team_name": team_b["team_name"], "elo_rating": round(r_b, 1), "win_probability": p_b},
            "draw_prob": p_draw,
            "win_probability_a": p_a,
            "win_probability_b": p_b,
            "draw_probability": p_draw,
            "model": {
                "name": "elo",
                "version": "1.0",
                "description": (
                    "Elo rating system. Ratings built from WC26 + 1yr qualifier/friendly "
                    "history. Home advantage = 100 Elo points. "
                    f"Rating difference: {round(r_a - r_b, 0):+.0f}."
                ),
            },
        }
