"""World Cup winner probability — Monte Carlo tournament simulation.

Reuses the exact same Poisson goal-rate model as the individual match
Predictor (`prediction.py`): each team's strength comes from its
auto-picked best XI, rated via `Predictor._rate_team()` against the same
`store.predictor_players` (WC26 + ~1yr qualifier/friendly history) used
for the head-to-head match predictor. The only difference from a single
prediction is that match outcomes are drawn at random from the Poisson
distribution (instead of reporting the expected scoreline), and that
random draw is propagated through the real remaining group fixtures and
the real knockout bracket thousands of times.

Each team's reported probability = the fraction of simulated tournaments
they win. See docs/WINNER_PROBABILITY_MODEL.md for the full methodology
and its documented simplifications.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from .data import DataStore
from .prediction import LAMBDA_CLAMP, Predictor, TeamRatings

DEFAULT_TRIALS = 10_000
THIRD_PLACE_POOL_SIZE = 8

# Mirrors frontend/app/predict/page.tsx's default formation — used only to
# auto-pick a representative XI per team for simulation, not shown to the user.
FORMATION = {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3}


# --------------------------------------------------------------------------- #
# Team strength (computed once per team, reused across every trial)
# --------------------------------------------------------------------------- #
def auto_pick_xi(players_df: pd.DataFrame, team_name: str) -> list[dict]:
    """Greedy best-by-minutes-per-role XI, falling back across roles when a
    team is short at a position — same logic as the frontend's `autoFill`.
    """
    team_players = players_df[players_df["team_name"] == team_name].sort_values(
        "minutes", ascending=False
    )
    used: set[int] = set()
    xi: list[dict] = []
    slots = [role for role, n in FORMATION.items() for _ in range(n)]
    for role in slots:
        pool = team_players[
            (team_players["role"] == role) & (~team_players["player_id"].isin(used))
        ]
        pick = pool.iloc[0] if not pool.empty else None
        if pick is None:
            fallback = team_players[~team_players["player_id"].isin(used)]
            pick = fallback.iloc[0] if not fallback.empty else None
        if pick is not None:
            xi.append({"player_id": int(pick["player_id"]), "role": role})
            used.add(pick["player_id"])
    return xi


def team_ratings(store: DataStore, predictor: Predictor) -> dict[str, TeamRatings]:
    """Who's selected must reflect who's actually playing *this tournament*
    (store.players, WC26-only minutes) — not blended minutes. Selecting by
    blended minutes let a player with heavy qualifier/friendly history but
    little-to-no real WC26 involvement outrank an actual current starter
    (caught via Belgium: the auto-pick chose Doku/Theate/Castagne/Raskin —
    minimal real WC26 minutes — over Trossard/Tielemans/Mechele/Ngoy, who
    are actually playing 150-180 real minutes this tournament).

    Once the real XI is selected, `predictor._rate_team()` still rates each
    of those specific players from `store.predictor_players` (blended) —
    that's the part that's *supposed* to benefit from the larger historical
    sample, for players with thin WC26 minutes so far.
    """
    ratings: dict[str, TeamRatings] = {}
    for name in store.players["team_name"].dropna().unique():
        xi = auto_pick_xi(store.players, name)
        if xi:
            ratings[name] = predictor._rate_team(xi)
    return ratings


# --------------------------------------------------------------------------- #
# One simulated match
# --------------------------------------------------------------------------- #
def simulate_match(
    ra: TeamRatings, rb: TeamRatings, avg_goals: float,
    rng: np.random.Generator, knockout: bool
) -> tuple[int, int]:
    """Poisson goal draw from the same lambda formula as Predictor.predict()
    (no home advantage — see docs/WINNER_PROBABILITY_MODEL.md). A draw in a
    knockout match is broken by a coin flip weighted by expected-goal share
    (a proxy for extra time + penalties, not a penalty-shootout model).
    """
    lam_a = avg_goals * ra.attack / rb.defense / rb.gk
    lam_b = avg_goals * rb.attack / ra.defense / ra.gk
    lam_a = min(max(lam_a, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])
    lam_b = min(max(lam_b, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])
    ga = int(rng.poisson(lam_a))
    gb = int(rng.poisson(lam_b))
    if knockout and ga == gb:
        if rng.random() < lam_a / (lam_a + lam_b):
            ga += 1
        else:
            gb += 1
    return ga, gb


# --------------------------------------------------------------------------- #
# Group stage: real stats + one simulated outcome per remaining fixture
# --------------------------------------------------------------------------- #
def simulate_group_stage(
    standings: dict, ratings: dict[str, TeamRatings], avg_goals: float,
    rng: np.random.Generator
) -> dict[str, list[dict]]:
    """Same Points -> GD -> Goals-scored tiebreak as GroupTable.tsx's
    applyHypotheticalResults, ported to Python so the simulator and the
    standings page agree on what "ranked" means.
    """
    ranked_groups: dict[str, list[dict]] = {}
    for gname, g in standings.items():
        teams = {t["team_id"]: dict(t) for t in g["teams"]}
        for m in g.get("remaining_matches", []):
            ra = ratings.get(m["home_team"])
            rb = ratings.get(m["away_team"])
            home = teams.get(m["home_team_id"])
            away = teams.get(m["away_team_id"])
            if not ra or not rb or not home or not away:
                continue
            ga, gb = simulate_match(ra, rb, avg_goals, rng, knockout=False)
            home["GP"] += 1
            away["GP"] += 1
            home["F"] += ga
            home["A"] += gb
            away["F"] += gb
            away["A"] += ga
            if ga > gb:
                home["W"] += 1
                away["L"] += 1
            elif gb > ga:
                away["W"] += 1
                home["L"] += 1
            else:
                home["D"] += 1
                away["D"] += 1

        ranked = list(teams.values())
        for t in ranked:
            t["GD"] = t["F"] - t["A"]
            t["P"] = t["W"] * 3 + t["D"]
        ranked.sort(key=lambda t: (-t["P"], -t["GD"], -t["F"], t["team_name"]))
        for i, t in enumerate(ranked):
            t["rank"] = i + 1
        ranked_groups[gname] = ranked
    return ranked_groups


def eliminated_teams(store: DataStore) -> set[str]:
    """Teams that are *actually, already* out — not just unlikely.

    Two real (non-simulated) signals:
      - lost a real, already-completed knockout match
      - finished a real, already-finished group in 4th — always eliminated,
        independent of every other group (4th never competes for a
        third-place wildcard slot)
      - finished 3rd in a real, already-finished group, but missed the
        real best-8-of-12 third-placed cutoff — only assessable once
        *every* group has finished, since that cutoff is cross-group

    A team failing to win in `trials` simulations is NOT the same as being
    eliminated — a genuine longshot can legitimately show 0.00% at a given
    trial count without actually being mathematically out yet. Conflating
    "rare" with "impossible" was an earlier bug in this module: caught by
    testing Panama/Tunisia, which reach the Round of 32 in a meaningful
    fraction of trials (so are clearly still alive) yet won 0/10,000 title
    simulations. See docs/WINNER_PROBABILITY_MODEL.md.
    """
    eliminated: set[str] = set()
    standings = store.standings
    bracket = store.bracket

    for round_def in bracket.get("rounds", []):
        for m in round_def["matches"]:
            if not m.get("completed"):
                continue
            sa, sb = int(m["score_a"] or 0), int(m["score_b"] or 0)
            if sa == sb:
                continue
            loser_slot = m["slot_a"] if sb > sa else m["slot_b"]
            if loser_slot.get("type") == "team" and loser_slot.get("team_name"):
                eliminated.add(loser_slot["team_name"])

    finished_groups = {
        gname: g for gname, g in standings.items() if not g.get("remaining_matches")
    }
    if finished_groups:
        ranked_finished = simulate_group_stage(finished_groups, {}, 0.0, np.random.default_rng())
        for g in ranked_finished.values():
            fourth = next((t for t in g if t["rank"] == 4), None)
            if fourth:
                eliminated.add(fourth["team_name"])

    if standings and len(finished_groups) == len(standings):
        ranked_groups = simulate_group_stage(standings, {}, 0.0, np.random.default_rng())
        qualifying_thirds = qualifying_third_place(ranked_groups)
        for g in ranked_groups.values():
            third = next((t for t in g if t["rank"] == 3), None)
            if third and third["team_id"] not in qualifying_thirds:
                eliminated.add(third["team_name"])
    return eliminated


def qualifying_third_place(ranked_groups: dict[str, list[dict]]) -> set[str]:
    thirds = [
        next(t for t in g if t["rank"] == 3)
        for g in ranked_groups.values() if len(g) >= 3
    ]
    thirds.sort(key=lambda t: (-t["P"], -t["GD"], -t["F"], t["team_name"]))
    return {t["team_id"] for t in thirds[:THIRD_PLACE_POOL_SIZE]}


# --------------------------------------------------------------------------- #
# Knockout bracket slot resolution
# --------------------------------------------------------------------------- #
def resolve_slot(
    slot: dict, ranked_groups: dict[str, list[dict]], qualifying_thirds: set[str],
    round_results: dict[tuple[str, int, str], tuple[str, str]],
) -> tuple[str | None, str | None]:
    """-> (team_id, team_name), resolved against this trial's (real +
    simulated) group order and any earlier rounds already simulated in this
    same trial. See etl/scrape/fetch_groups.py's parse_slot for how these
    four slot types are derived from ESPN's own bracket data.
    """
    t = slot.get("type")
    if t == "team":
        return slot.get("team_id"), slot.get("team_name")
    if t == "group_rank":
        group = ranked_groups.get(f"Group {slot['group']}")
        team = next((x for x in group if x["rank"] == slot["rank"]), None) if group else None
        return (team["team_id"], team["team_name"]) if team else (None, None)
    if t == "third_place":
        for gname in slot.get("candidate_groups", []):
            group = ranked_groups.get(f"Group {gname}")
            team = next((x for x in group if x["rank"] == 3), None) if group else None
            if team and team["team_id"] in qualifying_thirds:
                return team["team_id"], team["team_name"]
        return None, None
    if t in ("match_winner", "match_loser"):
        return round_results.get((slot["round"], slot["position"], t), (None, None))
    return None, None


# --------------------------------------------------------------------------- #
# Full tournament, N times
# --------------------------------------------------------------------------- #
def run_simulation(
    store: DataStore, predictor: Predictor, trials: int = DEFAULT_TRIALS,
    seed: int | None = None,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    ratings = team_ratings(store, predictor)
    avg_goals = predictor.avg_goals
    standings = store.standings
    bracket = store.bracket

    all_names = sorted(set(
        t["team_name"] for g in standings.values() for t in g["teams"]
    ))
    wins = defaultdict(int)

    for _ in range(trials):
        ranked_groups = simulate_group_stage(standings, ratings, avg_goals, rng)
        qualifying_thirds = qualifying_third_place(ranked_groups)
        round_results: dict[tuple[str, int, str], tuple[str, str]] = {}
        champion: str | None = None

        for round_def in bracket.get("rounds", []):
            rname = round_def["name"]
            for m in round_def["matches"]:
                if m.get("completed"):
                    a_id, a_name = m["slot_a"]["team_id"], m["slot_a"]["team_name"]
                    b_id, b_name = m["slot_b"]["team_id"], m["slot_b"]["team_name"]
                    sa, sb = int(m["score_a"] or 0), int(m["score_b"] or 0)
                else:
                    a_id, a_name = resolve_slot(m["slot_a"], ranked_groups, qualifying_thirds, round_results)
                    b_id, b_name = resolve_slot(m["slot_b"], ranked_groups, qualifying_thirds, round_results)
                    if a_id is None or b_id is None:
                        continue
                    ra, rb = ratings.get(a_name), ratings.get(b_name)
                    if not ra or not rb:
                        continue
                    sa, sb = simulate_match(ra, rb, avg_goals, rng, knockout=True)

                if sa == sb:
                    continue  # only possible for a real (already-decided) record we can't act on
                winner = (a_id, a_name) if sa > sb else (b_id, b_name)
                loser = (b_id, b_name) if sa > sb else (a_id, a_name)
                round_results[(rname, m["position"], "match_winner")] = winner
                round_results[(rname, m["position"], "match_loser")] = loser
                if rname == "Final":
                    champion = winner[1]

        if champion:
            wins[champion] += 1

    # Real (non-simulated) elimination overrides the simulated frequency —
    # a team can legitimately simulate to 0/trials title wins without being
    # mathematically out yet (a longshot, not an impossibility); only a real
    # confirmed elimination should report exactly 0%.
    real_eliminated = eliminated_teams(store)
    return {
        name: 0.0 if name in real_eliminated else wins.get(name, 0) / trials
        for name in all_names
    }


# --------------------------------------------------------------------------- #
# Deterministic bracket prediction (for bracket display)
# --------------------------------------------------------------------------- #
def _match_forecast(ra: TeamRatings, rb: TeamRatings, avg_goals: float) -> dict:
    """Most-likely scoreline + each side's probability of *advancing* for one
    knockout tie."""
    from .prediction import MAX_GOALS, _poisson_pmf

    lam_a = min(max(avg_goals * ra.attack / rb.defense / rb.gk, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])
    lam_b = min(max(avg_goals * rb.attack / ra.defense / ra.gk, LAMBDA_CLAMP[0]), LAMBDA_CLAMP[1])
    pa = [_poisson_pmf(i, lam_a) for i in range(MAX_GOALS + 1)]
    pb = [_poisson_pmf(j, lam_b) for j in range(MAX_GOALS + 1)]
    win_a = win_b = draw = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = pa[i] * pb[j]
            if i > j:
                win_a += p
            elif j > i:
                win_b += p
            else:
                draw += p
    total = win_a + win_b + draw or 1.0
    win_a, win_b, draw = win_a / total, win_b / total, draw / total
    share_a = lam_a / (lam_a + lam_b)
    advance_a = win_a + draw * share_a
    advance_b = win_b + draw * (1 - share_a)
    return {
        "score_a": round(lam_a),
        "score_b": round(lam_b),
        "advance_a": advance_a,
        "advance_b": advance_b,
    }


def predict_bracket_path(store: DataStore, predictor: Predictor) -> dict[str, dict]:
    """Walk rounds in order using real standings + actual results for completed
    matches, Poisson most-likely score for upcoming ones."""
    ratings = team_ratings(store, predictor)
    avg_goals = predictor.avg_goals

    ranked_groups: dict[str, list[dict]] = {}
    for gname, g in store.standings.items():
        ranked = sorted(
            [dict(t) for t in g["teams"]],
            key=lambda t: (-t["P"], -t.get("GD", 0), -t.get("F", 0), t["team_name"]),
        )
        for i, t in enumerate(ranked):
            t["rank"] = i + 1
        ranked_groups[gname] = ranked

    qualifying_thirds = qualifying_third_place(ranked_groups)
    round_results: dict[tuple[str, int, str], tuple[str, str]] = {}
    predictions: dict[str, dict] = {}

    for round_def in store.bracket.get("rounds", []):
        rname = round_def["name"]
        for m in round_def["matches"]:
            gid = str(m["game_id"])
            if m.get("completed"):
                a_id = m["slot_a"].get("team_id")
                a_name = m["slot_a"].get("team_name")
                b_id = m["slot_b"].get("team_id")
                b_name = m["slot_b"].get("team_name")
                sa, sb = int(m.get("score_a") or 0), int(m.get("score_b") or 0)
                if sa != sb:
                    winner = (a_id, a_name) if sa > sb else (b_id, b_name)
                    loser = (b_id, b_name) if sa > sb else (a_id, a_name)
                    round_results[(rname, m["position"], "match_winner")] = winner
                    round_results[(rname, m["position"], "match_loser")] = loser
            else:
                a_id, a_name = resolve_slot(
                    m["slot_a"], ranked_groups, qualifying_thirds, round_results
                )
                b_id, b_name = resolve_slot(
                    m["slot_b"], ranked_groups, qualifying_thirds, round_results
                )
                ra = ratings.get(a_name) if a_name else None
                rb = ratings.get(b_name) if b_name else None
                pred: dict = {
                    "team_a_name": a_name,
                    "team_a_flag": store.flag(a_name) if a_name else None,
                    "team_b_name": b_name,
                    "team_b_flag": store.flag(b_name) if b_name else None,
                    "predicted_score_a": None,
                    "predicted_score_b": None,
                    "predicted_winner": None,
                    "win_probability": None,
                }
                if ra and rb and a_id and b_id:
                    f = _match_forecast(ra, rb, avg_goals)
                    pred["predicted_score_a"] = f["score_a"]
                    pred["predicted_score_b"] = f["score_b"]
                    if f["advance_a"] >= f["advance_b"]:
                        w_id, w_name, l_id, l_name = a_id, a_name, b_id, b_name
                        pred["win_probability"] = round(f["advance_a"], 4)
                    else:
                        w_id, w_name, l_id, l_name = b_id, b_name, a_id, a_name
                        pred["win_probability"] = round(f["advance_b"], 4)
                    pred["predicted_winner"] = w_name
                    round_results[(rname, m["position"], "match_winner")] = (w_id, w_name)
                    round_results[(rname, m["position"], "match_loser")] = (l_id, l_name)
                predictions[gid] = pred

    return predictions


# Module-level cached singleton, mirroring prediction.py's get_predictor —
# recomputed once per process. The existing refresh cron restarts the
# backend after every data refresh, which is what "rerun after every
# finished match" maps to (no separate scheduling needed).
_probabilities: dict[str, float] | None = None
_bracket_predictions: dict[str, dict] | None = None


def get_winner_probabilities(store: DataStore) -> dict[str, float]:
    global _probabilities
    if _probabilities is None:
        from .prediction import get_predictor
        _probabilities = run_simulation(store, get_predictor(store))
    return _probabilities


def get_bracket_predictions(store: DataStore) -> dict[str, dict]:
    global _bracket_predictions
    if _bracket_predictions is None:
        from .prediction import get_predictor
        _bracket_predictions = predict_bracket_path(store, get_predictor(store))
    return _bracket_predictions
