"""Run offline Monte Carlo + bracket predictions; write JSON artifacts."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from atwc26_core import config
from atwc26_core.data import get_store
from atwc26_core.prediction import get_predictor
from atwc26_core.simulation_artifacts import write_bracket_predictions, write_winner_probabilities
from atwc26_core.tournament import DEFAULT_TRIALS, predict_bracket_path, run_simulation


def simulate_trials() -> int:
    raw = os.getenv("ATWC26_SIMULATE_TRIALS", str(DEFAULT_TRIALS)).strip()
    return max(1, int(raw))


def simulate_seed() -> int:
    raw = os.getenv("ATWC26_SIMULATE_SEED", "42").strip()
    return int(raw)


def run_simulate(*, trials: int | None = None, seed: int | None = None) -> dict:
    """Compute winner probabilities and bracket path; persist JSON under data/."""
    trials = trials if trials is not None else simulate_trials()
    seed = seed if seed is not None else simulate_seed()

    store = get_store()
    store.load()
    predictor = get_predictor(store)

    result = run_simulation(store, predictor, trials=trials, seed=seed)
    probabilities = result["probabilities"]
    stage_probabilities = result.get("stage_probabilities", {})
    predictions = predict_bracket_path(store, predictor)
    generated_at = datetime.now(timezone.utc).isoformat()

    winner_path = write_winner_probabilities(
        probabilities,
        stage_probabilities=stage_probabilities,
        trials=trials,
        seed=seed,
        generated_at=generated_at,
    )
    bracket_path = write_bracket_predictions(predictions, generated_at=generated_at)

    print(
        f"simulate: {trials} trials -> {winner_path.name}, "
        f"{len(predictions)} bracket match(es) -> {bracket_path.name}"
    )
    return {
        "trials": trials,
        "seed": seed,
        "winner_probabilities": str(winner_path),
        "bracket_predictions": str(bracket_path),
        "teams": len(probabilities),
        "teams_with_stages": len(stage_probabilities),
        "bracket_matches": len(predictions),
    }


def main() -> int:
    run_simulate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
