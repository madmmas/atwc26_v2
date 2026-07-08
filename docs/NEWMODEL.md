# atwc26_v2 — Multi-model prediction engine
# Cursor implementation spec
#
# Work top-to-bottom. Each step builds on the previous.
# Do NOT start a step until the previous step's tests pass.
# Do NOT touch etl/scrape/*, frontend/app/predict/page.tsx formation logic,
# or any existing API endpoints other than POST /api/predict.

# ════════════════════════════════════════════════════════════════════════════════
# CONTEXT
# ════════════════════════════════════════════════════════════════════════════════
#
# Current state:
#   - One prediction model: Poisson (packages/atwc26_core/atwc26_core/prediction.py)
#   - Called by: services/predict_api/predict_api/main.py → POST /api/predict
#   - Trained data: 94 WC26 matches + 332 historical = 426 total match rows
#   - Data location: data/all_players_stats.parquet + data/historical_form.parquet
#   - Pipeline: ETL transform → etl-local → etl-publish
#
# Target state after this spec:
#   - Four models: Poisson (existing), Elo, Dixon-Coles, XGBoost
#   - Common ModelEngine protocol — every model implements the same interface
#   - ?model=poisson|elo|dixon_coles|xgboost query param selects the model
#   - No ?model param → runs all four and returns comparison block
#   - New ETL step: etl/train/ runs after simulate, writes model artifacts to data/
#   - New artifacts registered in artifacts.py and published to S3
#   - Tests for every new file
#   - Zero changes to the frontend predict page formation/XI-picker logic


# ════════════════════════════════════════════════════════════════════════════════
# STEP 1 — Dependencies
# ════════════════════════════════════════════════════════════════════════════════
# Files to edit:
#   packages/atwc26_core/pyproject.toml
#   etl/requirements.txt
#   services/predict_api/requirements.txt

# 1A. packages/atwc26_core/pyproject.toml
# ADD to [project.optional-dependencies]:
#   ml = ["scikit-learn>=1.4", "xgboost>=2.0", "scipy>=1.11"]
# DO NOT add to core dependencies — ml is optional so Lambda layers stay small.

# 1B. etl/requirements.txt
# ADD these lines:
#   scikit-learn>=1.4
#   xgboost>=2.0
#   scipy>=1.11
# (ETL runs in GHA where size doesn't matter)

# 1C. services/predict_api/requirements.txt
# ADD these lines:
#   scikit-learn>=1.4
#   xgboost>=2.0
#   scipy>=1.11
# (predict service is ECS/Docker — size doesn't matter)


# ════════════════════════════════════════════════════════════════════════════════
# STEP 2 — Config paths for new artifacts
# ════════════════════════════════════════════════════════════════════════════════
# File to edit: packages/atwc26_core/atwc26_core/config.py

# ADD these four lines after the BRACKET_PREDICTIONS line:
#
#   ELO_RATINGS      = DATA_DIR / "elo_ratings.json"
#   DC_PARAMS        = DATA_DIR / "dc_params.json"
#   XGB_MODEL        = DATA_DIR / "xgb_model.ubj"
#   XGB_FEATURES     = DATA_DIR / "xgb_features.json"
#   RELOAD_SECRET    = os.getenv("ATWC26_RELOAD_SECRET", "")
#
# ALSO add RELOAD_SECRET here (removes the os.getenv call from predict main.py).
# After adding: update services/predict_api/predict_api/main.py to import
# RELOAD_SECRET from config instead of calling os.getenv directly:
#   from atwc26_core import config
#   _RELOAD_SECRET = config.RELOAD_SECRET


# ════════════════════════════════════════════════════════════════════════════════
# STEP 3 — Register new artifacts
# ════════════════════════════════════════════════════════════════════════════════
# File to edit: packages/atwc26_core/atwc26_core/artifacts.py

# ADD these four ArtifactSpec entries to the ARTIFACTS tuple,
# after the bracket_predictions entry:
#
#   ArtifactSpec("elo_ratings",   config.ELO_RATINGS,  False, "json"),
#   ArtifactSpec("dc_params",     config.DC_PARAMS,    False, "json"),
#   ArtifactSpec("xgb_model",     config.XGB_MODEL,    False, "json"),
#   ArtifactSpec("xgb_features",  config.XGB_FEATURES, False, "json"),
#
# NOTE: xgb_model artifact kind is "json" not "binary" — the registry only
# tracks metadata. The actual .ubj file is stored at config.XGB_MODEL path.
# The s3_key_for() function works by filename so "xgb_model.ubj" is correct.


# ════════════════════════════════════════════════════════════════════════════════
# STEP 4 — ModelEngine protocol
# ════════════════════════════════════════════════════════════════════════════════
# Create NEW file: packages/atwc26_core/atwc26_core/engines/__init__.py

# Write this file exactly:

"""Model engine protocol — every prediction model must implement this interface."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ModelEngine(Protocol):
    """Common interface for all prediction models.

    Each engine receives two team dicts (same shape as PredictRequest.team_a/b
    after .model_dump()) and returns a result dict that always contains:
      - win_probability_a: float  (0–1)
      - win_probability_b: float  (0–1)
      - draw_probability: float   (0–1)
      - model: dict with keys name (str), version (str), description (str)

    Engines may add extra keys (expected_goals, scorelines, radar, etc.)
    but must never omit the three probability fields.
    """

    @property
    def name(self) -> str:
        """Short identifier: 'poisson' | 'elo' | 'dixon_coles' | 'xgboost'."""
        ...

    def predict(self, team_a: dict, team_b: dict) -> dict:
        """Return prediction dict for team_a vs team_b."""
        ...

    def is_available(self) -> bool:
        """Return True if required artifacts are loaded and model is ready."""
        ...


# Registry: name -> engine instance (populated by load_engines)
_registry: dict[str, ModelEngine] = {}


def register(engine: ModelEngine) -> None:
    """Register a model engine by its name."""
    _registry[engine.name] = engine


def get_engine(name: str) -> ModelEngine | None:
    """Return a registered engine by name, or None."""
    return _registry.get(name)


def available_engines() -> dict[str, ModelEngine]:
    """Return all registered engines that report is_available() == True."""
    return {n: e for n, e in _registry.items() if e.is_available()}


def load_engines(store) -> None:
    """Instantiate and register all engines from the given store.

    Call this once at service startup (or after a reload).
    store must have: predictor_players, predictor_avg_goals, league.
    """
    from .prediction import Predictor
    from .engines.poisson import PoissonEngine
    from .engines.elo import EloEngine
    from .engines.dixon_coles import DixonColesEngine
    from .engines.xgboost_engine import XGBoostEngine

    _registry.clear()

    # Poisson (always available — uses in-memory player profiles)
    predictor = Predictor(store)
    register(PoissonEngine(predictor))

    # Elo (available if data/elo_ratings.json exists)
    elo = EloEngine()
    elo.load()
    register(elo)

    # Dixon-Coles (available if data/dc_params.json exists)
    dc = DixonColesEngine()
    dc.load()
    register(dc)

    # XGBoost (available if data/xgb_model.ubj + data/xgb_features.json exist)
    xgb = XGBoostEngine()
    xgb.load()
    register(xgb)


# ════════════════════════════════════════════════════════════════════════════════
# STEP 5 — PoissonEngine wrapper
# ════════════════════════════════════════════════════════════════════════════════
# Create NEW file: packages/atwc26_core/atwc26_core/engines/poisson.py

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
        result["draw_probability"]  = result["draw_prob"]
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


# ════════════════════════════════════════════════════════════════════════════════
# STEP 6 — Elo engine
# ════════════════════════════════════════════════════════════════════════════════
# Create NEW file: packages/atwc26_core/atwc26_core/engines/elo.py

"""Elo rating system for WC2026 team strength."""
from __future__ import annotations

import json
import math

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


# ════════════════════════════════════════════════════════════════════════════════
# STEP 7 — Dixon-Coles engine
# ════════════════════════════════════════════════════════════════════════════════
# Create NEW file: packages/atwc26_core/atwc26_core/engines/dixon_coles.py

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
            self._attack   = {str(k): float(v) for k, v in data.get("attack", {}).items()}
            self._defence  = {str(k): float(v) for k, v in data.get("defence", {}).items()}
            self._home     = float(data.get("home_advantage", 0.0))
            self._rho      = float(data.get("rho", 0.1))
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
                if h > a:   win_a += p
                elif h == a: draw += p
                else:        win_b += p
                if p > best[2]:
                    best = (h, a, p)
                scorelines.append((h, a, p))

        total = win_a + draw + win_b or 1.0
        win_a /= total; draw /= total; win_b /= total

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


# ════════════════════════════════════════════════════════════════════════════════
# STEP 8 — XGBoost engine
# ════════════════════════════════════════════════════════════════════════════════
# Create NEW file: packages/atwc26_core/atwc26_core/engines/xgboost_engine.py

"""XGBoost match outcome classifier."""
from __future__ import annotations

import json

import numpy as np

from atwc26_core import config


class XGBoostEngine:
    """XGBoost trained on team-level engineered features.

    Features (order defined by xgb_features.json):
      xg_diff, shots_diff, sot_diff,       ← per-90 attack differential
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
        model_path    = model_path    or config.XGB_MODEL
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
                self._dc_attack  = {str(k): float(v) for k, v in data.get("attack",  {}).items()}
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
        import math

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

        name_a   = team_a["team_name"]
        name_b   = team_b["team_name"]
        pl_a     = team_a.get("players", [])
        pl_b     = team_b.get("players", [])
        home_a   = 1.0 if team_a.get("home") else 0.0

        # NOTE: we pass player objects enriched with per-90 stats from the
        # predict service's store. The API handler is responsible for
        # attaching the per-90 stats to the player selection dicts.
        feat_map = {
            "xg_diff":          _p90_agg(pl_a, "expectedGoals_p90") - _p90_agg(pl_b, "expectedGoals_p90"),
            "shots_diff":       _p90_agg(pl_a, "totalShots_p90")    - _p90_agg(pl_b, "totalShots_p90"),
            "sot_diff":         _p90_agg(pl_a, "shotsOnTarget_p90") - _p90_agg(pl_b, "shotsOnTarget_p90"),
            "elo_diff":         _avg_elo(name_a) - _avg_elo(name_b),
            "dc_attack_ratio":  _dc_ratio(name_a, name_b, "attack"),
            "dc_defence_ratio": _dc_ratio(name_a, name_b, "defence"),
            "home_adv":         home_a,
            "h_form3":          float(team_a.get("form3_wins", 0)),
            "a_form3":          float(team_b.get("form3_wins", 0)),
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
                    "(xG diff, shots diff, Elo gap, Dixon-Coles ratios, home advantage, "
                    "recent form). max_depth=2, trained on 426 matches."
                ),
            },
        }


# ════════════════════════════════════════════════════════════════════════════════
# STEP 9 — ETL train step: Elo + Dixon-Coles + XGBoost
# ════════════════════════════════════════════════════════════════════════════════
# Create NEW directory: etl/train/
# Create NEW files:
#   etl/train/__init__.py         (empty)
#   etl/train/__main__.py
#   etl/train/elo.py
#   etl/train/dixon_coles.py
#   etl/train/xgboost_model.py
#   etl/train/features.py
#   etl/train/run.py

# ── etl/train/__main__.py ────────────────────────────────────────────────────
# from .run import main, raise SystemExit(main())

# ── etl/train/features.py ────────────────────────────────────────────────────
# PURPOSE: Build the team-level match matrix that Elo, DC and XGBoost train on.
#
# def build_match_matrix(master_parquet_path, historical_form_path) -> pd.DataFrame:
#     """
#     Returns one row per match with columns:
#       game_id, match_date, home_team, away_team,
#       h_xg_p90, a_xg_p90,           ← team xG per 90 (sum of player xg_p90)
#       h_shots_p90, a_shots_p90,      ← team shots per 90
#       h_sot_p90, a_sot_p90,          ← shots on target per 90
#       outcome                         ← 2=home win, 1=draw, 0=away win
#     """
#     Load master_parquet + historical_form.
#     Concatenate them (same schema).
#     Group by [game_id, home_away] to get team-level stats.
#     Pivot home vs away into one row per match.
#     Compute per-90 by dividing sum by (sum_minutes/90).
#     Add outcome column.
#     Drop rows where team_score or opp_score is null.
#     Return sorted by match_date ascending.
#
# def add_rolling_form(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
#     """
#     Add h_form3 and a_form3 columns: wins in last {window} games per team.
#     Shift by 1 to avoid data leakage (only use past games, not current).
#     """
#
# IMPORTANT: This function is used by both dixon_coles.py and xgboost_model.py.
# It must be deterministic and have no side effects.

# ── etl/train/elo.py ─────────────────────────────────────────────────────────
# PURPOSE: Compute Elo ratings from match history and save to data/elo_ratings.json
#
# ELO_START = 1500.0
# K = 32                    ← update factor per match
# HOME_ADVANTAGE = 100      ← Elo points added to home team
#
# def train_elo(match_matrix: pd.DataFrame) -> dict[str, float]:
#     """
#     Iterate matches in chronological order.
#     For each match:
#       1. Get current ratings (default ELO_START if team not seen yet)
#       2. expected_a = 1 / (1 + 10 ** ((r_b - r_a - HOME_ADVANTAGE) / 400))
#       3. actual_a = 1.0 if home win, 0.5 if draw, 0.0 if away win
#       4. r_a += K * (actual_a - expected_a)
#       5. r_b += K * ((1 - actual_a) - (1 - expected_a))
#     Return final ratings dict: team_name -> rating.
#     """
#
# def save_elo(ratings: dict, path=None) -> Path:
#     """Write to config.ELO_RATINGS as JSON: {"ratings": {...}, "generated_at": ...}"""

# ── etl/train/dixon_coles.py ─────────────────────────────────────────────────
# PURPOSE: Fit Dixon-Coles parameters by MLE and save to data/dc_params.json
#
# Uses scipy.optimize.minimize with L-BFGS-B.
# Parameters: one attack (α_i) and one defence (β_i) per team, plus home (γ) and rho (ρ).
#
# def negative_log_likelihood(params, teams, matches, rho=0.1) -> float:
#     """
#     params layout: [α_0, α_1, ..., α_N, β_0, ..., β_N, γ]
#     N = number of unique teams.
#     For each match:
#       λ_h = exp(α_home - β_away + γ)
#       λ_a = exp(α_away - β_home)
#       p = poisson_pmf(goals_h, λ_h) * poisson_pmf(goals_a, λ_a) * τ(h,a,λ_h,λ_a,rho)
#       total_ll += log(max(p, 1e-10))
#     Return -total_ll.
#     """
#
# def train_dixon_coles(match_matrix: pd.DataFrame) -> dict:
#     """
#     1. Get sorted unique team list.
#     2. Initialise params: all zeros except home=0.3.
#     3. Call minimize(negative_log_likelihood, x0, method='L-BFGS-B', ...)
#        maxiter=500, ftol=1e-8
#     4. Extract attack[i], defence[i], home from result.x
#     5. Return {"attack": {team: val}, "defence": {team: val},
#                "home_advantage": γ, "rho": 0.1,
#                "avg_goals": mean(all goals), "converged": result.success}
#     """
#
# def save_dc_params(params: dict, path=None) -> Path:
#     """Write to config.DC_PARAMS as JSON: {attack, defence, home_advantage, rho, ...}"""

# ── etl/train/xgboost_model.py ───────────────────────────────────────────────
# PURPOSE: Train XGBoost classifier and save model + feature list.
#
# FEATURE_COLS (in this exact order, becomes xgb_features.json):
#   ["xg_diff", "shots_diff", "sot_diff",
#    "elo_diff", "dc_attack_ratio", "dc_defence_ratio",
#    "home_adv", "h_form3", "a_form3"]
#
# XGB_PARAMS = {
#     "objective":       "multi:softprob",
#     "num_class":       3,
#     "max_depth":       2,        ← shallow: only 426 training rows
#     "eta":             0.05,
#     "subsample":       0.7,
#     "colsample_bytree": 0.7,
#     "min_child_weight": 3,
#     "lambda":          2.0,      ← heavy L2 regularisation
#     "alpha":           0.5,      ← L1 regularisation
#     "eval_metric":     "mlogloss",
#     "seed":            42,
# }
# NUM_ROUNDS = 200
#
# def build_xgb_features(match_matrix: pd.DataFrame,
#                        elo_ratings: dict,
#                        dc_params: dict) -> tuple[np.ndarray, np.ndarray]:
#     """
#     Add columns to match_matrix:
#       elo_diff = elo[home_team] - elo[away_team]   (default 0 if not found)
#       dc_attack_ratio  = exp(dc_attack[home]) / exp(dc_defence[away])
#       dc_defence_ratio = exp(dc_attack[away]) / exp(dc_defence[home])
#       home_adv = 1 (all matches in matrix have home/away designation)
#     Then add h_form3 / a_form3 via add_rolling_form().
#     Return X (shape: n × 9), y (shape: n,) with values 0/1/2.
#     """
#
# def train_xgboost(X, y) -> xgb.Booster:
#     """
#     1. dtrain = xgb.DMatrix(X, label=y)
#     2. booster = xgb.train(XGB_PARAMS, dtrain, num_boost_round=NUM_ROUNDS)
#     3. Return booster.
#     DO NOT use cross-validation here — too few rows.
#     """
#
# def save_xgb_model(booster, path=None) -> Path:
#     """booster.save_model(str(config.XGB_MODEL))  — saves as .ubj binary"""
#
# def save_xgb_features(features: list[str], path=None) -> Path:
#     """Write FEATURE_COLS to config.XGB_FEATURES as JSON list."""

# ── etl/train/run.py ─────────────────────────────────────────────────────────
# PURPOSE: Orchestrate all three training steps and print summary.
#
# def run_train() -> dict:
#     """
#     1. build_match_matrix(config.MASTER_PARQUET, config.HISTORICAL_FORM)
#        → match_df  (426 rows)
#     2. elo_ratings = train_elo(match_df)
#        save_elo(elo_ratings)
#        print(f"elo: {len(elo_ratings)} teams trained")
#     3. dc_params = train_dixon_coles(match_df)
#        save_dc_params(dc_params)
#        print(f"dixon_coles: converged={dc_params['converged']}")
#     4. X, y = build_xgb_features(match_df, elo_ratings, dc_params)
#        booster = train_xgboost(X, y)
#        save_xgb_model(booster)
#        save_xgb_features(FEATURE_COLS)
#        print(f"xgboost: {len(y)} samples, {X.shape[1]} features")
#     5. Return summary dict.
#     """
#
# def main() -> int:
#     run_train()
#     return 0


# ════════════════════════════════════════════════════════════════════════════════
# STEP 10 — Wire train into ETL pipeline
# ════════════════════════════════════════════════════════════════════════════════

# 10A. Makefile
# ADD this target after etl-simulate:
#
#   etl-train: setup-etl ## Train Elo, Dixon-Coles, XGBoost models
#   	cd $(ROOT) && $(PYTHON) -m etl.train
#
# MODIFY etl-local target to include etl-train:
# FIND:
#   etl-local: setup-etl ## Transform + simulate + QA (local manifest)
#   	cd $(ROOT) && $(PYTHON) -m etl.transform
#   	cd $(ROOT) && $(PYTHON) -m etl.simulate
#   	cd $(ROOT) && $(PYTHON) -m etl.qa
# REPLACE WITH:
#   etl-local: setup-etl ## Transform + simulate + train + QA (local manifest)
#   	cd $(ROOT) && $(PYTHON) -m etl.transform
#   	cd $(ROOT) && $(PYTHON) -m etl.simulate
#   	cd $(ROOT) && $(PYTHON) -m etl.train
#   	cd $(ROOT) && $(PYTHON) -m etl.qa

# 10B. .github/workflows/etl.yml
# FIND the "Transform + simulate + QA" step:
#   run: make etl-local
# It already runs make etl-local — no change needed here since
# etl-local now includes etl-train.
#
# HOWEVER, the step runs scikit-learn and xgboost which are not in etl/requirements.txt yet.
# Step 1B above adds them. Confirm that "Install ETL dependencies" step
# (pip install -r requirements.txt) runs before this step. It already does.


# ════════════════════════════════════════════════════════════════════════════════
# STEP 11 — Update predict service to use multi-model registry
# ════════════════════════════════════════════════════════════════════════════════
# File to edit: services/predict_api/predict_api/main.py

# 11A. Add model param to PredictRequest schema
# File: packages/atwc26_core/atwc26_core/schemas.py
# FIND the PredictRequest class. ADD field:
#   model: str | None = Field(None, description="poisson|elo|dixon_coles|xgboost|None=all")

# 11B. Update predict main.py
# REPLACE the entire file with the updated version below.
# Key changes:
#   - Import and call load_engines() on startup
#   - POST /api/predict uses ?model or req.model to select engine
#   - When model is None: run all available engines and return comparison
#   - When model is specified: run only that engine
#   - _store global is still used for Poisson (needs predictor_players)
#   - Health endpoint reports available models

# New predict main.py structure (write this exactly):
#
# from atwc26_core.engines import load_engines, get_engine, available_engines
#
# @app.on_event("startup")
# def _warm() -> None:
#     global _store
#     ensure_predictor_data()
#     _store = build_predictor_store()
#     load_engines(_store)   # registers all four engines
#
# @app.get("/api/health")
# def health():
#     store = _get_store()
#     return {
#         "status": "ok",
#         "service": "predict",
#         "models_available": list(available_engines().keys()),
#         **store.league,
#     }
#
# @app.post("/api/predict")
# def predict(req: PredictRequest):
#     a = req.team_a.model_dump()
#     b = req.team_b.model_dump()
#     if not a["players"] or not b["players"]:
#         raise HTTPException(400, "Each team needs at least one selected player.")
#
#     # Enrich player selections with per-90 stats so XGBoost engine
#     # can build team-level feature vectors.
#     store = _get_store()
#     _enrich_players(a["players"], store)
#     _enrich_players(b["players"], store)
#
#     engines = available_engines()
#     if not engines:
#         raise HTTPException(503, "No prediction models available.")
#
#     model_name = req.model
#     if model_name:
#         engine = engines.get(model_name)
#         if engine is None:
#             raise HTTPException(400, f"Model '{model_name}' not available. "
#                                      f"Available: {list(engines.keys())}")
#         return clean_json(engine.predict(a, b))
#
#     # No model specified → run all, return comparison
#     results = {}
#     for name, engine in engines.items():
#         try:
#             results[name] = engine.predict(a, b)
#         except Exception as exc:
#             results[name] = {"error": str(exc)}
#
#     # Primary result is poisson (always available, most detailed)
#     primary = results.get("poisson", next(iter(results.values())))
#     return clean_json({
#         **primary,
#         "comparison": {
#             name: {
#                 "win_probability_a": r.get("win_probability_a"),
#                 "draw_probability":  r.get("draw_probability"),
#                 "win_probability_b": r.get("win_probability_b"),
#                 "model_name":        r.get("model", {}).get("name"),
#             }
#             for name, r in results.items()
#             if "error" not in r
#         },
#     })
#
#
# def _enrich_players(player_selections: list[dict], store) -> None:
#     """
#     Attach per-90 stats to each player selection dict in-place.
#     player_selections is a list of {"player_id": int, "role": str}.
#     We look up each player in store.predictor_players by player_id and
#     merge all _p90 columns into the dict.
#     This lets XGBoostEngine._build_feature_vector() read p.get("expectedGoals_p90")
#     without needing separate DB lookups.
#     """
#     players_df = store.predictor_players.set_index("player_id")
#     p90_cols = [c for c in players_df.columns if c.endswith("_p90")]
#     for sel in player_selections:
#         pid = sel.get("player_id")
#         if pid in players_df.index:
#             row = players_df.loc[pid]
#             for col in p90_cols:
#                 sel[col] = float(row.get(col, 0) or 0)
#
# @app.post("/api/predict/reload")
# def reload_predictor(request: Request):
#     # Keep existing implementation.
#     # ALSO call load_engines(_store) after rebuilding _store:
#     #   _store = build_predictor_store()
#     #   _pred._predictor = None
#     #   get_predictor(_store)
#     #   load_engines(_store)    ← ADD THIS LINE
#     pass   # (replace with actual implementation, adding load_engines call)


# ════════════════════════════════════════════════════════════════════════════════
# STEP 12 — Update api.ts for comparison response
# ════════════════════════════════════════════════════════════════════════════════
# File to edit: frontend/lib/api.ts

# 12A. Add model param to PredictRequest body type (in api.ts api.predict call):
# The frontend doesn't need to send model — it can optionally pass it.
# ADD to the Prediction type:
#   comparison?: Record<string, {
#     win_probability_a: number;
#     draw_probability: number;
#     win_probability_b: number;
#     model_name: string;
#   }>;

# 12B. ALSO add next_cursor to the players return type (existing bug fix):
# FIND:
#   players: (q: string) => get<{ count: number; players: Player[] }>(`/api/players?${q}`),
# REPLACE WITH:
#   players: (q: string) => get<{
#     count: number;
#     page_size: number;
#     next_cursor: string | null;
#     players: Player[];
#   }>(`/api/players?${q}`),


# ════════════════════════════════════════════════════════════════════════════════
# STEP 13 — Update PredictionResult component (optional model comparison panel)
# ════════════════════════════════════════════════════════════════════════════════
# File to edit: frontend/components/PredictionResult.tsx

# If a comparison field is present in the Prediction response,
# render a "Model comparison" panel below the main result.
# The panel shows a simple table:
#
#   Model          | P(home win) | P(draw) | P(away win)
#   Poisson        |    52%      |  24%    |    24%
#   Elo            |    48%      |  25%    |    27%
#   Dixon-Coles    |    51%      |  24%    |    25%
#   XGBoost        |    55%      |  20%    |    25%
#
# Render only when result.comparison exists and has > 1 entry.
# The table is read-only — no interaction needed.
# Style: same card class as existing panels, small text (text-sm).


# ════════════════════════════════════════════════════════════════════════════════
# STEP 14 — Tests
# ════════════════════════════════════════════════════════════════════════════════
# Create NEW file: tests/etl/test_train.py

# Write tests for:
#
# test_build_match_matrix_returns_correct_shape()
#   - Call build_match_matrix with test fixtures
#   - Assert columns: game_id, home_team, away_team, outcome, h_xg_p90, a_xg_p90
#   - Assert outcome values are only {0, 1, 2}
#   - Assert no null outcomes
#
# test_train_elo_updates_ratings()
#   - Create 3-row match matrix (known results)
#   - Call train_elo()
#   - Assert winning team has higher rating than before
#   - Assert ratings are floats in reasonable range (1000-2000)
#
# test_save_load_elo(tmp_path)
#   - train_elo() → save_elo(path=tmp_path/elo.json) → EloEngine().load(path=...)
#   - Assert EloEngine.is_available() == True
#   - Assert ratings match
#
# test_train_dixon_coles_converges()
#   - Call train_dixon_coles with ≥ 10 rows
#   - Assert result["converged"] == True
#   - Assert "attack" and "defence" keys present
#   - Assert all float values
#
# test_save_load_dc_params(tmp_path)
#   - train_dixon_coles() → save_dc_params() → DixonColesEngine().load()
#   - Assert DixonColesEngine.is_available() == True
#
# test_dc_engine_predict_sums_to_one()
#   - Build DixonColesEngine with known params (inject directly)
#   - predict(team_a, team_b)
#   - Assert win_a + draw + win_b ≈ 1.0 (within 1e-4)
#
# test_xgb_feature_vector_shape()
#   - Call build_xgb_features with test match_df, empty elo/dc dicts
#   - Assert X.shape == (n, 9)
#   - Assert y values are only {0, 1, 2}
#
# test_engine_protocol_compliance()
#   - For each engine class (Poisson, Elo, DC, XGB):
#     - Assert instance satisfies ModelEngine protocol
#     - Assert engine.name is a string
#     - Assert engine.is_available() returns bool

# Create NEW file: tests/etl/test_engines.py
#
# test_poisson_engine_wraps_predictor()
#   - Build PoissonEngine with a mock Predictor
#   - Call predict() with minimal team_a/team_b
#   - Assert response contains win_probability_a, draw_probability, win_probability_b
#   - Assert response contains comparison-compatible fields
#   - Assert probabilities sum to ≈ 1.0
#
# test_load_engines_registers_all(mock_store)
#   - Call load_engines(mock_store)
#   - Assert "poisson" in available_engines()
#   - (Elo/DC/XGB available only if data files exist — use tmp fixtures)
#
# test_multi_model_predict_returns_comparison()
#   - Set up all four engines with minimal params
#   - Call predict endpoint with no model param
#   - Assert response has "comparison" key
#   - Assert comparison has at least 1 entry
#   - Assert each comparison entry has the four required fields


# ════════════════════════════════════════════════════════════════════════════════
# STEP 15 — Final checks before committing
# ════════════════════════════════════════════════════════════════════════════════

# 15A. Run locally end-to-end:
#   make etl-local                  ← should run transform, simulate, train, qa
#   Check data/ contains:
#     elo_ratings.json
#     dc_params.json
#     xgb_model.ubj
#     xgb_features.json
#
# 15B. Start predict service locally:
#   uvicorn services.predict_api.predict_api.main:app --reload
#   curl http://localhost:8000/api/health
#   → should show "models_available": ["poisson", "elo", "dixon_coles", "xgboost"]
#
# 15C. Test all four model paths:
#   curl -X POST http://localhost:8000/api/predict \
#     -H "Content-Type: application/json" \
#     -d '{"team_a": {"team_name": "Brazil", "players": [...]},
#          "team_b": {"team_name": "Argentina", "players": [...]},
#          "model": "elo"}'
#   → should return Elo prediction only
#
#   curl -X POST http://localhost:8000/api/predict \
#     -d '{"team_a": ..., "team_b": ...}'   (no model field)
#   → should return poisson result + comparison block with all 4 models
#
# 15D. Run tests:
#   pytest tests/etl/test_train.py tests/etl/test_engines.py -v
#
# 15E. Fix config.py RELOAD_SECRET import in predict main.py.
#      Fix cache_headers.py CACHE_RULES ordering (specific paths before generic).
#      Change ATWC26_SIMULATE_TRIALS to "1000" in etl.yml if not already done.

# ════════════════════════════════════════════════════════════════════════════════
# FILE SUMMARY — what gets created vs edited
# ════════════════════════════════════════════════════════════════════════════════
#
# NEW files:
#   packages/atwc26_core/atwc26_core/engines/__init__.py      ← Step 4
#   packages/atwc26_core/atwc26_core/engines/poisson.py       ← Step 5
#   packages/atwc26_core/atwc26_core/engines/elo.py           ← Step 6
#   packages/atwc26_core/atwc26_core/engines/dixon_coles.py   ← Step 7
#   packages/atwc26_core/atwc26_core/engines/xgboost_engine.py ← Step 8
#   etl/train/__init__.py                                       ← Step 9
#   etl/train/__main__.py                                       ← Step 9
#   etl/train/features.py                                       ← Step 9
#   etl/train/elo.py                                            ← Step 9
#   etl/train/dixon_coles.py                                    ← Step 9
#   etl/train/xgboost_model.py                                  ← Step 9
#   etl/train/run.py                                            ← Step 9
#   tests/etl/test_train.py                                     ← Step 14
#   tests/etl/test_engines.py                                   ← Step 14
#
# EDITED files:
#   packages/atwc26_core/pyproject.toml    ← Step 1A (add ml optional deps)
#   etl/requirements.txt                   ← Step 1B (add sklearn, xgb, scipy)
#   services/predict_api/requirements.txt  ← Step 1C (add sklearn, xgb, scipy)
#   packages/atwc26_core/atwc26_core/config.py    ← Step 2 (4 new paths + RELOAD_SECRET)
#   packages/atwc26_core/atwc26_core/artifacts.py ← Step 3 (4 new ArtifactSpec entries)
#   packages/atwc26_core/atwc26_core/schemas.py   ← Step 11A (add model field)
#   services/predict_api/predict_api/main.py       ← Step 11B (multi-model routing)
#   Makefile                                        ← Step 10A (etl-train target)
#   frontend/lib/api.ts                             ← Step 12 (comparison + cursor types)
#   frontend/components/PredictionResult.tsx        ← Step 13 (comparison panel)
#   services/shared/cache_headers.py                ← Step 15E (rule order fix)
#   .github/workflows/etl.yml                       ← Step 15E (trials=1000)
#
# DATA artifacts produced (by make etl-local):
#   data/elo_ratings.json
#   data/dc_params.json
#   data/xgb_model.ubj
#   data/xgb_features.json