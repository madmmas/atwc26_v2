"""Data access layer.

Loads the scraped master parquet once and derives cached, analysis-ready
aggregates: per-player tournament profiles (per-90 normalised), per-team
summaries and leaderboards. Everything downstream (API + prediction engine)
reads from these cached frames.
"""
from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config

# --------------------------------------------------------------------------- #
# Metric groups used across analytics and the prediction engine
# --------------------------------------------------------------------------- #
# Counting stats -> normalised "per 90 minutes".
ATTACK_STATS = [
    "expectedGoals", "expectedAssists", "totalGoals", "goalAssists",
    "totalShots", "shotsOnTarget", "bigChanceCreated", "touchesInOppBox",
]
POSSESSION_STATS = [
    "touches", "accuratePasses", "progressiveCarries",
    "finalThirdEntries", "penAreaEntries",
]
DEFENSE_STATS = [
    "defensiveInterventions", "interceptions", "totalClearance",
    "totalTackles", "duelsWon", "ballRecovery", "possWonDef3rd",
]
KEEPER_STATS = [
    "saves", "goalsConceded", "goalsPrevented",
    "expectedGoalsOnTargetConceded", "shotsOnGoalAgainst",
]
# Rate stats -> averaged per game (already normalised, don't divide by minutes).
RATE_STATS = ["passPct", "duelWinPct", "tacklePct"]

PER90_STATS = ATTACK_STATS + POSSESSION_STATS + DEFENSE_STATS + KEEPER_STATS

# Identity columns we never treat as stats.
ID_COLS = {
    "game_id", "match_date", "competition", "season", "team_id", "team_name",
    "home_away", "is_winner", "formation", "team_score", "opp_team_id",
    "opp_team_name", "opp_score", "player_id", "player_name", "jersey",
    "position", "position_abbr", "starter", "subbed_in", "subbed_out",
    "minutes", "appearances", "scraped_at",
}


def classify_role(position: str | None, abbr: str | None) -> str:
    """Map ESPN position labels to one of GK / DEF / MID / FWD."""
    text = f"{position or ''} {abbr or ''}".lower()
    if "goalkeeper" in text or abbr == "G":
        return "GK"
    if any(k in text for k in ("forward", "striker", "winger")) or abbr in {
        "CF-L", "CF-R", "LF", "RF", "F", "ST",
    }:
        return "FWD"
    if "midfield" in text or abbr in {
        "CM", "CM-L", "CM-R", "DM", "AM", "AM-L", "AM-R", "LM", "RM", "M",
    }:
        return "MID"
    if any(k in text for k in ("defender", "back", "sweeper")) or abbr in {
        "CD", "CD-L", "CD-R", "LB", "RB", "SW",
    }:
        return "DEF"
    return "MID"  # sensible default for ambiguous/substitute rows


class DataStore:
    """Thread-safe, lazily-loaded singleton holding the derived frames."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self.raw: pd.DataFrame | None = None
        self.players: pd.DataFrame | None = None       # one row per player
        self.teams: pd.DataFrame | None = None         # one row per team
        self.league: dict = {}

    # -- loading ----------------------------------------------------------- #
    def load(self, force: bool = False) -> None:
        with self._lock:
            if self._loaded and not force:
                return
            df = pd.read_parquet(config.MASTER_PARQUET)

            # Coerce every stat column to numeric (some arrive as strings).
            for c in df.columns:
                if c not in ID_COLS:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            df["team_score"] = pd.to_numeric(df["team_score"], errors="coerce")
            df["opp_score"] = pd.to_numeric(df["opp_score"], errors="coerce")
            df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce").fillna(0)
            # Use assign() (not item-set) to avoid a fragmented-frame warning on
            # this wide table.
            df = df.assign(role=[
                classify_role(p, a)
                for p, a in zip(df["position"], df["position_abbr"])
            ])
            self.raw = df
            self.players = self._build_player_profiles(df)
            self.teams = self._build_team_profiles(df)
            self.league = self._build_league_context(df)
            self._loaded = True

    # -- player profiles --------------------------------------------------- #
    def _build_player_profiles(self, df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for pid, g in df.groupby("player_id"):
            minutes = float(g["minutes"].sum())
            # dominant non-substitute role, else most frequent role
            roles = g.loc[g["role"] != "MID", "role"]
            role = (g["role"].mode().iat[0] if not g["role"].mode().empty
                    else "MID")
            # prefer an explicit outfield/keeper role over the MID default
            explicit = g.loc[g["position"] != "Substitute", "role"]
            if not explicit.empty:
                role = explicit.mode().iat[0]

            rec = {
                "player_id": int(pid),
                "player_name": g["player_name"].iat[0],
                "team_name": g["team_name"].iat[0],
                "team_id": g["team_id"].iat[0],
                "role": role,
                "games": int(g["game_id"].notna().sum()),  # count non-null games
                "minutes": round(minutes, 0),
                "rating": round(float(
                    pd.to_numeric(g["avgRatingFromDataFeed"], errors="coerce").mean()
                ) if "avgRatingFromDataFeed" in g else 0.0, 2),
                "played": minutes > 0,  # flag: did this player appear in a match?
            }
            # per-90 counting stats (0 for players who never played)
            factor = 90.0 / minutes if minutes > 0 else 0.0
            for c in PER90_STATS:
                if c in g:
                    rec[f"{c}_p90"] = round(float(g[c].sum()) * factor, 3) if minutes > 0 else 0.0
            # per-game rate stats
            for c in RATE_STATS:
                if c in g:
                    rec[c] = round(float(g[c].mean()), 3) if minutes > 0 else 0.0
            # raw tournament totals for a few headline stats
            for c in ("totalGoals", "goalAssists", "expectedGoals", "expectedAssists"):
                if c in g:
                    rec[f"{c}_total"] = round(float(g[c].sum()), 2)
            rows.append(rec)

        players = pd.DataFrame(rows).sort_values(
            ["team_name", "role", "minutes"], ascending=[True, True, False]
        ).reset_index(drop=True)
        return players

    # -- team profiles ----------------------------------------------------- #
    def _build_team_profiles(self, df: pd.DataFrame) -> pd.DataFrame:
        # one row per team per game first
        per_game = df.groupby(["game_id", "team_name"]).agg(
            goals=("team_score", "first"),
            conceded=("opp_score", "first"),
            xg=("expectedGoals", "sum"),
            xga=("expectedGoalsConceded", "sum"),
            shots=("totalShots", "sum"),
            sot=("shotsOnTarget", "sum"),
            big_chances=("bigChanceCreated", "sum"),
            possession_proxy=("touches", "sum"),
        ).reset_index()

        rows = []
        for team, g in per_game.groupby("team_name"):
            n = len(g)
            rows.append({
                "team_name": team,
                "games": int(n),
                "goals_for": round(float(g["goals"].sum()), 0),
                "goals_against": round(float(g["conceded"].sum()), 0),
                "goals_per_game": round(float(g["goals"].mean()), 2),
                "conceded_per_game": round(float(g["conceded"].mean()), 2),
                "xg_per_game": round(float(g["xg"].mean()), 2),
                "xga_per_game": round(float(g["xga"].mean()), 2),
                "shots_per_game": round(float(g["shots"].mean()), 1),
                "sot_per_game": round(float(g["sot"].mean()), 1),
                "big_chances_per_game": round(float(g["big_chances"].mean()), 1),
            })

        # Include teams that are in the tournament (have squad players) but
        # haven't played a match yet — so they're still selectable everywhere.
        played_teams = {r["team_name"] for r in rows}
        for team in sorted(set(df["team_name"]) - played_teams):
            rows.append({
                "team_name": team, "games": 0,
                "goals_for": 0, "goals_against": 0,
                "goals_per_game": 0.0, "conceded_per_game": 0.0,
                "xg_per_game": 0.0, "xga_per_game": 0.0,
                "shots_per_game": 0.0, "sot_per_game": 0.0,
                "big_chances_per_game": 0.0,
            })

        return pd.DataFrame(rows).sort_values(
            ["games", "xg_per_game"], ascending=[False, False]
        ).reset_index(drop=True)

    # -- league baselines -------------------------------------------------- #
    def _build_league_context(self, df: pd.DataFrame) -> dict:
        per_game = df.groupby(["game_id", "team_name"]).agg(
            goals=("team_score", "first"),
        ).reset_index()
        avg_goals = float(per_game["goals"].mean())
        return {
            "avg_team_goals": round(avg_goals, 3),
            "games": int(df["game_id"].nunique()),
            "teams": int(df["team_name"].nunique()),
            "players": int(df["player_id"].nunique()),
        }


# Module-level singleton
store = DataStore()


def get_store() -> DataStore:
    store.load()
    return store
