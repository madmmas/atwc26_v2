"""Dixon-Coles bivariate Poisson model for match prediction."""
from __future__ import annotations

import json
import math

from atwc26_core import config

MAX_GOALS = 8


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _dc_tau(h: int, a: int, lam_h: float, lam_a: float, rho: float) -> float:
    """Dixon-Coles low-score correction factor τ."""
    if h == 0 and a == 0:
        return 1.0 - lam_h * lam_a * rho
    if h == 1 and a == 0:
        return 1.0 + lam_a * rho
    if h == 0 and a == 1:
        return 1.0 + lam_h * rho
    if h == 1 and a == 1:
        return 1.0 - rho
    return 1.0


class DixonColesEngine:
    """Dixon-Coles bivariate Poisson. Parameters fitted by MLE in etl/train/."""

    name = "dixon_coles"

    def __init__(self) -> None:
        self._attack: dict[str, float] = {}   # team → α (log attack strength)
        self._defence: dict[str, float] = {}  # team → β (log defence weakness)
        self._home: float = 0.0               # home advantage coefficient
        self._rho: float = 0.1                # low-score correlation
        self._avg_goals: float = 1.3

    def load(self, path=None) -> bool:
        path = path or config.DC_PARAMS
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
            self._attack = {str(k): float(v) for k, v in data.get("attack", {}).items()}
            self._defence = {str(k): float(v) for k, v in data.get("defence", {}).items()}
            self._home = float(data.get("home_advantage", 0.0))
            self._rho = float(data.get("rho", 0.1))
            self._avg_goals = float(data.get("avg_goals", 1.3))
            return bool(self._attack)
        except Exception:
            return False

    def is_available(self) -> bool:
        return bool(self._attack)

    def _lambdas(self, team_h: str, team_a: str, home: bool) -> tuple[float, float]:
        ha = self._home if home else 0.0
        lam_h = math.exp(
            self._attack.get(team_h, 0.0) - self._defence.get(team_a, 0.0) + ha
        )
        lam_a = math.exp(
            self._attack.get(team_a, 0.0) - self._defence.get(team_h, 0.0)
        )
        return max(lam_h, 0.1), max(lam_a, 0.1)

    def predict(self, team_a: dict, team_b: dict) -> dict:
        name_a, name_b = team_a["team_name"], team_b["team_name"]
        lam_h, lam_a = self._lambdas(name_a, name_b, home=team_a.get("home", False))

        win_a = win_b = draw = 0.0
        best = (0, 0, 0.0)
        scorelines = []

        for h in range(MAX_GOALS + 1):
            for a in range(MAX_GOALS + 1):
                p = _poisson_pmf(h, lam_h) * _poisson_pmf(a, lam_a)
                p *= _dc_tau(h, a, lam_h, lam_a, self._rho)
                p = max(p, 0.0)
                if h > a:
                    win_a += p
                elif h == a:
                    draw += p
                else:
                    win_b += p
                if p > best[2]:
                    best = (h, a, p)
                scorelines.append((h, a, p))

        total = win_a + draw + win_b or 1.0
        win_a /= total
        draw /= total
        win_b /= total

        scorelines.sort(key=lambda x: -x[2])
        top = [{"a": h, "b": a, "prob": round(p / total, 4)} for h, a, p in scorelines[:6]]

        return {
            "team_a": {"team_name": name_a, "expected_goals": round(lam_h, 2), "win_probability": round(win_a, 4)},
            "team_b": {"team_name": name_b, "expected_goals": round(lam_a, 2), "win_probability": round(win_b, 4)},
            "draw_prob": round(draw, 4),
            "win_probability_a": round(win_a, 4),
            "win_probability_b": round(win_b, 4),
            "draw_probability": round(draw, 4),
            "most_likely_score": {"a": best[0], "b": best[1], "prob": round(best[2] / total, 4)},
            "top_scorelines": top,
            "model": {
                "name": "dixon_coles",
                "version": "1.0",
                "description": (
                    "Dixon-Coles bivariate Poisson. Team attack/defence parameters "
                    "fitted by MLE on WC26 + qualifier history. "
                    f"λ home={lam_h:.2f}, λ away={lam_a:.2f}."
                ),
            },
        }
