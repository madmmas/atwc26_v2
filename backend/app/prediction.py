"""Match-result prediction engine.

Given two user-built XIs, predict the match outcome from each selected player's
*tournament* per-90 performance. The approach is the football-analytics standard:

  1. Aggregate each XI into role-weighted **attack** and **defense** ratings plus a
     **goalkeeping** factor, using per-90 expected-goals / expected-assists and
     defensive-action metrics.
  2. Normalise those ratings against a league-average XI so an average team ~= 1.0.
  3. Convert to an expected-goals rate (lambda) for each side with a Poisson
     goals model:  lambda_A = avg_goals * attack_A / defense_B * gk_B * home.
  4. Build the score-line probability matrix -> win / draw / loss, most-likely
     score, and an explainable per-dimension breakdown.

Assumptions are intentionally transparent (independent Poisson goals; ratings
centred on the tournament's own averages) so the output is explainable — exactly
what a capability demo needs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from .data import DataStore

# --------------------------------------------------------------------------- #
# Tunable model weights (transparent on purpose)
# --------------------------------------------------------------------------- #
# How strongly each per-90 metric feeds a player's raw attack score.
ATTACK_WEIGHTS = {
    "expectedGoals_p90": 2.0,
    "expectedAssists_p90": 1.5,
    "bigChanceCreated_p90": 0.40,
    "shotsOnTarget_p90": 0.30,
    "touchesInOppBox_p90": 0.12,
}
# ...and a player's raw defensive score.
DEFENSE_WEIGHTS = {
    "interceptions_p90": 0.40,
    "duelsWon_p90": 0.35,
    "totalClearance_p90": 0.30,
    "totalTackles_p90": 0.30,
    "ballRecovery_p90": 0.18,
    "defensiveInterventions_p90": 0.12,
}
# Role -> (how much the slot contributes to team attack, to team defense).
ROLE_WEIGHTS = {
    "GK":  (0.00, 0.00),   # keeper handled separately
    "DEF": (0.30, 1.00),
    "MID": (0.70, 0.70),
    "FWD": (1.00, 0.25),
}
HOME_ADVANTAGE = 1.10      # applied to the team flagged home (neutral = 1.0)
MAX_GOALS = 8              # scoreline matrix dimension
LAMBDA_CLAMP = (0.2, 5.0)


# --------------------------------------------------------------------------- #
@dataclass
class TeamRatings:
    attack: float
    defense: float
    gk: float
    creativity: float
    possession: float
    contributors: list


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


class Predictor:
    """Holds league reference ratings; produces match predictions."""

    def __init__(self, store: DataStore) -> None:
        self.store = store
        players = store.players.set_index("player_id")
        self.players = players
        self.avg_goals = store.league["avg_team_goals"]
        self._compute_reference()

    # -- league reference so an average XI normalises to ~1.0 -------------- #
    def _compute_reference(self) -> None:
        p = self.players
        qualified = p[p["minutes"] >= 45]
        self.ref_attack_by_role = {}
        self.ref_defense_by_role = {}
        for role in ("GK", "DEF", "MID", "FWD"):
            grp = qualified[qualified["role"] == role]
            grp = grp if len(grp) else qualified
            self.ref_attack_by_role[role] = max(self._raw_attack(grp).mean(), 1e-6)
            self.ref_defense_by_role[role] = max(self._raw_defense(grp).mean(), 1e-6)
        self.ref_gk = max(self._raw_gk(qualified[qualified["role"] == "GK"]).mean(), 1e-6)

    # -- raw per-player scores (vectorised) -------------------------------- #
    def _raw_attack(self, frame: pd.DataFrame) -> pd.Series:
        s = pd.Series(0.0, index=frame.index)
        for col, w in ATTACK_WEIGHTS.items():
            if col in frame:
                s = s + frame[col].fillna(0) * w
        return s

    def _raw_defense(self, frame: pd.DataFrame) -> pd.Series:
        s = pd.Series(0.0, index=frame.index)
        for col, w in DEFENSE_WEIGHTS.items():
            if col in frame:
                s = s + frame[col].fillna(0) * w
        return s

    def _raw_gk(self, frame: pd.DataFrame) -> pd.Series:
        # Shot-stopping above expectation is the key keeper signal.
        gp = frame["goalsPrevented_p90"].fillna(0) if "goalsPrevented_p90" in frame else 0
        sv = frame["saves_p90"].fillna(0) if "saves_p90" in frame else 0
        return 1.0 + gp * 1.2 + sv * 0.10

    # -- ratings for one selected XI --------------------------------------- #
    def _rate_team(self, selections: list[dict]) -> TeamRatings:
        attack = defense = 0.0
        creativity = possession = 0.0
        gk = 1.0
        contribs = []
        for sel in selections:
            pid = sel["player_id"]
            role = sel.get("role", "MID")
            if pid not in self.players.index:
                continue
            row = self.players.loc[pid]
            aw, dw = ROLE_WEIGHTS.get(role, ROLE_WEIGHTS["MID"])

            if role == "GK":
                gk = float(self._raw_gk(row.to_frame().T).iloc[0]) / self.ref_gk
                contribs.append({
                    "player_id": int(pid), "player_name": row["player_name"],
                    "role": role, "attack": 0.0,
                    "defense": round(gk, 2),
                })
                continue

            a_raw = float(self._raw_attack(row.to_frame().T).iloc[0])
            d_raw = float(self._raw_defense(row.to_frame().T).iloc[0])
            a_norm = a_raw / self.ref_attack_by_role[role]
            d_norm = d_raw / self.ref_defense_by_role[role]
            attack += a_norm * aw
            defense += d_norm * dw
            creativity += float(row.get("expectedAssists_p90", 0) or 0) + \
                0.5 * float(row.get("bigChanceCreated_p90", 0) or 0)
            possession += float(row.get("touches_p90", 0) or 0) / 90.0 + \
                0.01 * float(row.get("passPct", 0) or 0)
            contribs.append({
                "player_id": int(pid), "player_name": row["player_name"],
                "role": role, "attack": round(a_norm * aw, 2),
                "defense": round(d_norm * dw, 2),
            })

        # Normalise each team sum by the reference total for the chosen outfield
        # slots, so an average XI lands at ~1.0 for both attack and defense.
        attack_rating = attack / self._ref_team_attack(selections)
        defense_rating = defense / self._ref_team_defense(selections)

        contribs.sort(key=lambda c: c["attack"] + c["defense"], reverse=True)
        return TeamRatings(
            attack=max(attack_rating, 0.05),
            defense=max(defense_rating, 0.05),
            gk=max(gk, 0.3),
            creativity=creativity,
            possession=possession,
            contributors=contribs[:6],
        )

    def _ref_team_attack(self, selections: list[dict]) -> float:
        total = sum(ROLE_WEIGHTS.get(s.get("role", "MID"), (0, 0))[0]
                    for s in selections if s.get("role") != "GK")
        return max(total, 1e-6)

    def _ref_team_defense(self, selections: list[dict]) -> float:
        total = sum(ROLE_WEIGHTS.get(s.get("role", "MID"), (0, 0))[1]
                    for s in selections if s.get("role") != "GK")
        return max(total, 1e-6)

    # -- full match prediction --------------------------------------------- #
    def predict(self, team_a: dict, team_b: dict) -> dict:
        ra = self._rate_team(team_a["players"])
        rb = self._rate_team(team_b["players"])

        home_a = HOME_ADVANTAGE if team_a.get("home") else 1.0
        home_b = HOME_ADVANTAGE if team_b.get("home") else 1.0

        # Poisson goal rates: own attack vs opponent defense & keeper.
        lam_a = self.avg_goals * ra.attack / rb.defense / rb.gk * home_a
        lam_b = self.avg_goals * rb.attack / ra.defense / ra.gk * home_b
        lam_a = min(max(lam_a, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])
        lam_b = min(max(lam_b, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])

        # Scoreline probability matrix.
        pa = [_poisson_pmf(i, lam_a) for i in range(MAX_GOALS + 1)]
        pb = [_poisson_pmf(j, lam_b) for j in range(MAX_GOALS + 1)]
        win_a = win_b = draw = 0.0
        best = (0, 0, 0.0)
        scorelines = []
        for i in range(MAX_GOALS + 1):
            for j in range(MAX_GOALS + 1):
                p = pa[i] * pb[j]
                if i > j:
                    win_a += p
                elif j > i:
                    win_b += p
                else:
                    draw += p
                if p > best[2]:
                    best = (i, j, p)
                scorelines.append((i, j, p))
        total = win_a + win_b + draw
        win_a, win_b, draw = win_a / total, win_b / total, draw / total

        scorelines.sort(key=lambda x: x[2], reverse=True)
        top_scores = [
            {"a": i, "b": j, "prob": round(p / total, 4)}
            for i, j, p in scorelines[:6]
        ]

        return {
            "team_a": self._team_block(team_a["team_name"], ra, lam_a, win_a),
            "team_b": self._team_block(team_b["team_name"], rb, lam_b, win_b),
            "draw_prob": round(draw, 4),
            "most_likely_score": {"a": best[0], "b": best[1],
                                  "prob": round(best[2] / total, 4)},
            "top_scorelines": top_scores,
            "radar": self._radar(team_a["team_name"], ra, team_b["team_name"], rb),
            "narrative": self._narrative(team_a["team_name"], win_a,
                                         team_b["team_name"], win_b, draw,
                                         lam_a, lam_b, best),
            "model": {
                "type": "Poisson goals model (player-aggregated, per-90 xG/xA + "
                        "defensive actions)",
                "avg_team_goals_baseline": self.avg_goals,
                "assumptions": "Independent Poisson goals; ratings normalised to "
                               "tournament averages; home advantage x1.10 if set.",
            },
        }

    def _team_block(self, name, r: TeamRatings, lam, win) -> dict:
        return {
            "team_name": name,
            "attack_rating": round(r.attack, 2),
            "defense_rating": round(r.defense, 2),
            "gk_rating": round(r.gk, 2),
            "expected_goals": round(lam, 2),
            "win_probability": round(win, 4),
            "key_players": r.contributors,
        }

    @staticmethod
    def _scale(v: float) -> float:
        """Map a rating centred on 1.0 to a 0-100 dial."""
        return round(min(max(50 * v, 5), 100), 1)

    def _radar(self, na, ra: TeamRatings, nb, rb: TeamRatings) -> dict:
        dims = ["Attack", "Creativity", "Possession", "Defense", "Goalkeeping"]
        def vec(r):
            return {
                "Attack": self._scale(r.attack),
                "Creativity": self._scale(0.6 + r.creativity),
                "Possession": self._scale(0.5 + r.possession / 8),
                "Defense": self._scale(r.defense),
                "Goalkeeping": self._scale(r.gk),
            }
        return {"dimensions": dims, na: vec(ra), nb: vec(rb)}

    def _narrative(self, na, wa, nb, wb, draw, la, lb, best) -> str:
        fav, p = (na, wa) if wa >= wb else (nb, wb)
        edge = "narrow" if abs(wa - wb) < 0.1 else (
            "clear" if abs(wa - wb) < 0.25 else "strong")
        return (
            f"The model gives {fav} a {edge} edge ({p*100:.0f}% win probability), "
            f"with a {draw*100:.0f}% chance of a draw. Projected expected goals: "
            f"{na} {la:.2f} – {lb:.2f} {nb}. Most likely score: "
            f"{na} {best[0]}–{best[1]} {nb}."
        )


# Lazily-built singleton tied to the data store.
_predictor: Predictor | None = None


def get_predictor(store: DataStore) -> Predictor:
    global _predictor
    if _predictor is None:
        _predictor = Predictor(store)
    return _predictor
