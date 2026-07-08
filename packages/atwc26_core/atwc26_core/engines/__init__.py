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
    from ..prediction import Predictor
    from .poisson import PoissonEngine
    from .elo import EloEngine
    from .dixon_coles import DixonColesEngine
    from .xgboost_engine import XGBoostEngine

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
