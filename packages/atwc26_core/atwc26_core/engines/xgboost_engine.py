"""XGBoost match outcome classifier."""
from __future__ import annotations

import json
import math

import numpy as np

from atwc26_core import config


class XGBoostEngine:
    """XGBoost trained on team-level engineered features.

    Features (order defined by xgb_features.json):
      xg_diff, shots_diff, sot_diff,       ← pre-match rolling attack differentials
      elo_diff,                              ← Elo rating gap
      dc_attack_ratio, dc_defence_ratio,    ← Dixon-Coles strength ratios
      home_adv,                             ← 1 if home else 0
      h_form3, a_form3                      ← wins in last 3 games (0–3)

    Output classes: 0=away win, 1=draw, 2=home win.
    """

    name = "xgboost"

    def __init__(self) -> None:
        self._model = None
        self._features: list[str] = []
        # Team-level engineered features loaded at predict time from DC + Elo engines
        self._elo_ratings: dict[str, float] = {}
        self._dc_attack: dict[str, float] = {}
        self._dc_defence: dict[str, float] = {}

    def load(self, model_path=None, features_path=None) -> bool:
        model_path = model_path or config.XGB_MODEL
        features_path = features_path or config.XGB_FEATURES
        if not model_path.exists() or not features_path.exists():
            return False
        try:
            import xgboost as xgb

            booster = xgb.Booster()
            booster.load_model(str(model_path))
            self._model = booster
            self._features = json.loads(features_path.read_text())

            # Also load Elo + DC params for feature construction at predict time
            if config.ELO_RATINGS.exists():
                data = json.loads(config.ELO_RATINGS.read_text())
                self._elo_ratings = {str(k): float(v) for k, v in data.get("ratings", {}).items()}
            if config.DC_PARAMS.exists():
                data = json.loads(config.DC_PARAMS.read_text())
                self._dc_attack = {str(k): float(v) for k, v in data.get("attack", {}).items()}
                self._dc_defence = {str(k): float(v) for k, v in data.get("defence", {}).items()}
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        return self._model is not None

    def _build_feature_vector(self, team_a: dict, team_b: dict) -> np.ndarray:
        """Build feature vector matching xgb_features.json column order.

        The XGBoost model was trained on TEAM-LEVEL features, not per-player
        features. The XI selections give us player-level data from which we
        derive the team-level aggregates the model expects.
        """

        def _p90_agg(players: list[dict], col: str) -> float:
            """Sum a per-90 stat across all selected players (proxy for team strength)."""
            return sum(float(p.get(col, 0) or 0) for p in players)

        def _avg_elo(team_name: str) -> float:
            return self._elo_ratings.get(team_name, 1500.0)

        def _dc_ratio(team_h: str, team_a: str, kind: str) -> float:
            if kind == "attack":
                a = math.exp(self._dc_attack.get(team_h, 0.0))
                d = math.exp(self._dc_defence.get(team_a, 0.0))
                return a / max(d, 1e-6)
            else:
                a = math.exp(self._dc_attack.get(team_a, 0.0))
                d = math.exp(self._dc_defence.get(team_h, 0.0))
                return a / max(d, 1e-6)

        name_a = team_a["team_name"]
        name_b = team_b["team_name"]
        pl_a = team_a.get("players", [])
        pl_b = team_b.get("players", [])
        home_a = 1.0 if team_a.get("home") else 0.0

        # NOTE: we pass player objects enriched with per-90 stats from the
        # predict service's store. The API handler is responsible for
        # attaching the per-90 stats to the player selection dicts.
        feat_map = {
            "xg_diff": _p90_agg(pl_a, "expectedGoals_p90") - _p90_agg(pl_b, "expectedGoals_p90"),
            "shots_diff": _p90_agg(pl_a, "totalShots_p90") - _p90_agg(pl_b, "totalShots_p90"),
            "sot_diff": _p90_agg(pl_a, "shotsOnTarget_p90") - _p90_agg(pl_b, "shotsOnTarget_p90"),
            "elo_diff": _avg_elo(name_a) - _avg_elo(name_b),
            "dc_attack_ratio": _dc_ratio(name_a, name_b, "attack"),
            "dc_defence_ratio": _dc_ratio(name_a, name_b, "defence"),
            "home_adv": home_a,
            "h_form3": float(team_a.get("form3_wins", 0)),
            "a_form3": float(team_b.get("form3_wins", 0)),
        }
        # Build in the exact order the model was trained on
        return np.array([[feat_map.get(f, 0.0) for f in self._features]], dtype=np.float32)

    def predict(self, team_a: dict, team_b: dict) -> dict:
        import xgboost as xgb

        X = self._build_feature_vector(team_a, team_b)
        dmat = xgb.DMatrix(X, feature_names=self._features)
        probs = self._model.predict(dmat)[0]   # shape (3,): [p_away, p_draw, p_home]

        p_away, p_draw, p_home = float(probs[0]), float(probs[1]), float(probs[2])

        return {
            "team_a": {"team_name": team_a["team_name"], "win_probability": round(p_home, 4)},
            "team_b": {"team_name": team_b["team_name"], "win_probability": round(p_away, 4)},
            "draw_prob": round(p_draw, 4),
            "win_probability_a": round(p_home, 4),
            "win_probability_b": round(p_away, 4),
            "draw_probability": round(p_draw, 4),
            "model": {
                "name": "xgboost",
                "version": "1.0",
                "description": (
                    "XGBoost classifier trained on team-level engineered features "
                    "(pre-match rolling xG/shots diffs, Elo gap, Dixon-Coles ratios, "
                    "home advantage, recent form). max_depth=2."
                ),
            },
        }
