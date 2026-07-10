"""Fit Dixon-Coles parameters by MLE with L2 regularization."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from atwc26_core import config

# Ridge penalty on attack/defence (not home). Stabilises sparse international panels.
L2_LAMBDA = 1.0
MAX_ABS_PARAM = 3.0


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _dc_tau(h: int, a: int, lam_h: float, lam_a: float, rho: float) -> float:
    if h == 0 and a == 0:
        return 1.0 - lam_h * lam_a * rho
    if h == 1 and a == 0:
        return 1.0 + lam_a * rho
    if h == 0 and a == 1:
        return 1.0 + lam_h * rho
    if h == 1 and a == 1:
        return 1.0 - rho
    return 1.0


def negative_log_likelihood(
    params: np.ndarray,
    teams: list[str],
    matches: pd.DataFrame,
    rho: float = 0.1,
    l2: float = L2_LAMBDA,
) -> float:
    """Negative log-likelihood for Dixon-Coles model (+ L2 on α, β)."""
    n = len(teams)
    attack = {teams[i]: params[i] for i in range(n)}
    defence = {teams[i]: params[n + i] for i in range(n)}
    home_adv = params[2 * n]

    total_ll = 0.0
    for _, row in matches.iterrows():
        h_team = row["home_team"]
        a_team = row["away_team"]
        goals_h = int(row["h_goals"])
        goals_a = int(row["a_goals"])
        lam_h = math.exp(attack.get(h_team, 0.0) - defence.get(a_team, 0.0) + home_adv)
        lam_a = math.exp(attack.get(a_team, 0.0) - defence.get(h_team, 0.0))
        lam_h = max(lam_h, 1e-6)
        lam_a = max(lam_a, 1e-6)
        p = (
            _poisson_pmf(goals_h, lam_h)
            * _poisson_pmf(goals_a, lam_a)
            * _dc_tau(goals_h, goals_a, lam_h, lam_a, rho)
        )
        total_ll += math.log(max(p, 1e-10))

    # Identifiability-friendly ridge on team strengths only.
    penalty = l2 * float(np.sum(params[: 2 * n] ** 2))
    return -total_ll + penalty


def _center_team_params(attack: dict[str, float], defence: dict[str, float]) -> None:
    """Enforce sum(α)=0 and sum(β)=0 in-place."""
    if not attack:
        return
    a_mean = sum(attack.values()) / len(attack)
    d_mean = sum(defence.values()) / len(defence)
    for team in attack:
        attack[team] -= a_mean
        defence[team] -= d_mean


def train_dixon_coles(
    match_matrix: pd.DataFrame,
    rho: float = 0.1,
    l2: float = L2_LAMBDA,
) -> dict:
    """Fit Dixon-Coles attack/defence parameters via regularized MLE."""
    teams = sorted(set(match_matrix["home_team"]) | set(match_matrix["away_team"]))
    n = len(teams)
    x0 = np.zeros(2 * n + 1)
    x0[-1] = 0.3

    result = minimize(
        negative_log_likelihood,
        x0,
        args=(teams, match_matrix, rho, l2),
        method="L-BFGS-B",
        options={"maxiter": 800, "ftol": 1e-8},
    )

    attack = {teams[i]: float(result.x[i]) for i in range(n)}
    defence = {teams[i]: float(result.x[n + i]) for i in range(n)}
    _center_team_params(attack, defence)
    home_adv = float(result.x[2 * n])
    all_goals = list(match_matrix["h_goals"]) + list(match_matrix["a_goals"])
    avg_goals = float(np.mean(all_goals)) if all_goals else 1.3

    max_abs = max(
        [abs(v) for v in attack.values()] + [abs(v) for v in defence.values()] or [0.0]
    )
    converged = bool(result.success) and max_abs <= MAX_ABS_PARAM

    return {
        "attack": attack,
        "defence": defence,
        "home_advantage": home_adv,
        "rho": rho,
        "avg_goals": avg_goals,
        "converged": converged,
        "l2_lambda": l2,
        "max_abs_param": max_abs,
    }


def save_dc_params(params: dict, path: Path | None = None) -> Path:
    """Write Dixon-Coles parameters to config.DC_PARAMS."""
    path = path or config.DC_PARAMS
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **params,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2))
    return path
