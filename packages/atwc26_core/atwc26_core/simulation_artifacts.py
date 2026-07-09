"""Read/write precomputed simulation JSON artifacts (GHA → S3 → Lambda)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config


def write_winner_probabilities(
    probabilities: dict[str, float],
    *,
    stage_probabilities: dict[str, dict[str, float]] | None = None,
    trials: int,
    seed: int,
    generated_at: str,
    path: Path | None = None,
) -> Path:
    path = path or config.WINNER_PROBABILITIES
    payload = {
        "trials": trials,
        "seed": seed,
        "generated_at": generated_at,
        "probabilities": {k: round(float(v), 6) for k, v in probabilities.items()},
        "stage_probabilities": stage_probabilities or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def write_bracket_predictions(
    predictions: dict[str, dict],
    *,
    generated_at: str,
    path: Path | None = None,
) -> Path:
    path = path or config.BRACKET_PREDICTIONS
    payload = {
        "generated_at": generated_at,
        "predictions": predictions,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def load_winner_probabilities(path: Path | None = None) -> dict[str, float] | None:
    path = path or config.WINNER_PROBABILITIES
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    probs = data.get("probabilities")
    if not isinstance(probs, dict):
        return None
    return {str(k): float(v) for k, v in probs.items()}


def load_stage_probabilities(path: Path | None = None) -> dict[str, dict[str, float]] | None:
    """Load per-round reach probabilities from winner_probabilities.json."""
    path = path or config.WINNER_PROBABILITIES
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    stages = data.get("stage_probabilities")
    if not isinstance(stages, dict):
        return None
    return {
        str(team): {str(k): float(v) for k, v in rounds.items()}
        for team, rounds in stages.items()
        if isinstance(rounds, dict)
    }


def load_bracket_predictions(path: Path | None = None) -> dict[str, dict] | None:
    path = path or config.BRACKET_PREDICTIONS
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    preds = data.get("predictions")
    if not isinstance(preds, dict):
        return None
    return {str(k): v for k, v in preds.items() if isinstance(v, dict)}


def winner_probabilities_api_payload(
    probabilities: dict[str, float],
    *,
    flag_lookup: Any,
    stage_probabilities: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Shape for GET /api/winner-probabilities."""
    teams = sorted(
        (
            {
                "team_name": name,
                "flag_url": flag_lookup(name),
                "probability": round(float(p), 4),
                "eliminated": float(p) == 0.0,
                "stage_probabilities": (stage_probabilities or {}).get(name),
            }
            for name, p in probabilities.items()
        ),
        key=lambda t: -t["probability"],
    )
    return {"teams": teams}
