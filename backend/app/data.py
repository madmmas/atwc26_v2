"""Data access layer.

Loads the scraped master parquet once and derives cached, analysis-ready
aggregates: per-player tournament profiles (per-90 normalised), per-team
summaries and leaderboards. Everything downstream (API + prediction engine)
reads from these cached frames.
"""
from __future__ import annotations

import json
import threading
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config

# Team-level indicators compared in Match Analysis (column, label, how-to-agg,
# whether a higher value is "better"). possession% is computed separately.
MATCH_INDICATORS = [
    ("expectedGoals", "Expected goals (xG)", "sum", True),
    ("totalShots", "Shots", "sum", True),
    ("shotsOnTarget", "Shots on target", "sum", True),
    ("bigChanceCreated", "Big chances", "sum", True),
    ("totalPasses", "Passes", "sum", True),
    ("touchesInOppBox", "Touches in opp. box", "sum", True),
    ("duelsWon", "Duels won", "sum", True),
    ("totalTackles", "Tackles", "sum", True),
    ("interceptions", "Interceptions", "sum", True),
    ("totalClearance", "Clearances", "sum", True),
    ("saves", "Saves", "sum", True),
    ("foulsCommitted", "Fouls", "sum", False),
    ("yellowCards", "Yellow cards", "sum", False),
]

# Per-player indicators shown in Player Analysis (column, label, per90-able).
PLAYER_INDICATORS = [
    ("totalGoals", "Goals", True),
    ("goalAssists", "Assists", True),
    ("expectedGoals", "xG", True),
    ("expectedAssists", "xA", True),
    ("totalShots", "Shots", True),
    ("shotsOnTarget", "Shots on target", True),
    ("touches", "Touches", True),
    ("totalPasses", "Passes", True),
    ("passPct", "Pass %", False),
    ("duelsWon", "Duels won", True),
    ("totalTackles", "Tackles", True),
    ("interceptions", "Interceptions", True),
    ("totalClearance", "Clearances", True),
    ("defensiveInterventions", "Defensive actions", True),
    ("foulsCommitted", "Fouls", True),
    ("saves", "Saves", True),
    ("goalsConceded", "Goals conceded", True),
]

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
            df = self._merge_squads(df)

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
            self.flags = self._load_flags()
            self.events = self._load_events()
            self.players = self._build_player_profiles(df)
            self.teams = self._build_team_profiles(df)
            self.matches = self._build_matches(df)
            self.league = self._build_league_context(df)
            self._loaded = True

    # -- squads -------------------------------------------------------------- #
    def _merge_squads(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add a synthetic 0-minute row for every registered squad member who
        hasn't appeared in a scraped match yet, so player pickers (Predictor,
        Player Analysis) can list a full squad, not just those with stats.

        Done in-memory on every load (not written back to the parquet) so it
        survives `rebuild_master()` in scrape_wc26.py, which only ever knows
        about players who appeared in a match and otherwise overwrites the
        master parquet wholesale on every scrape/refresh cycle.
        """
        if not config.SQUADS_RAW.exists():
            return df
        try:
            squads = json.loads(config.SQUADS_RAW.read_text())
        except Exception:
            return df

        existing = set(zip(df["player_id"].astype(str), df["team_name"].astype(str)))
        new_rows = []
        for squad in squads:
            for p in squad.get("players", []):
                key = (str(p["player_id"]), squad["team_name"])
                if key in existing:
                    continue
                row = {c: None for c in df.columns}
                row.update({
                    "competition": "FIFA World Cup",
                    "season": 2026,
                    "team_id": squad["team_id"],
                    "team_name": squad["team_name"],
                    "player_id": p["player_id"],
                    "player_name": p["player_name"],
                    "jersey": p.get("jersey"),
                    "position": p.get("position"),
                    "position_abbr": p.get("position_abbr"),
                    "starter": False,
                    "subbed_in": False,
                    "subbed_out": False,
                    "minutes": 0.0,
                    "appearances": 0.0,
                })
                new_rows.append(row)
                existing.add(key)
        if not new_rows:
            return df
        return pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    # -- flags ------------------------------------------------------------- #
    def _load_flags(self) -> dict:
        """team_name -> flag image url (authentic ESPN country flags)."""
        try:
            raw = json.loads(config.TEAM_FLAGS.read_text())
            return {name: info.get("flag_url") for name, info in raw.items()}
        except Exception:
            return {}

    def flag(self, team_name: str) -> str | None:
        return self.flags.get(team_name)

    # -- match events / momentum ------------------------------------------- #
    def _load_events(self) -> dict:
        """game_id -> {home_team, away_team, events[], momentum[], duration}.

        Built by build_match_events.py from ESPN's own keyEvents (literal,
        for the markers) and commentary (used to derive an approximate
        momentum wave). See that script's docstring for the methodology.
        """
        try:
            return json.loads(config.MATCH_EVENTS.read_text())
        except Exception:
            return {}

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
                "flag_url": self.flag(g["team_name"].iat[0]),
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
                "flag_url": self.flag(team),
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
                "team_name": team, "flag_url": self.flag(team), "games": 0,
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

    # -- matches ----------------------------------------------------------- #
    def _build_matches(self, df: pd.DataFrame) -> list[dict]:
        """One entry per played match (most recent first)."""
        played = df[df["game_id"].notna()]
        matches = []
        for gid, g in played.groupby("game_id"):
            # home row tells us both sides + score from one perspective
            home = g[g["home_away"] == "home"]
            row = home.iloc[0] if not home.empty else g.iloc[0]
            home_name = row["team_name"]
            away_name = row["opp_team_name"]
            hs, as_ = row["team_score"], row["opp_score"]
            matches.append({
                "game_id": str(gid),
                "date": row["match_date"],
                "home_team": home_name,
                "away_team": away_name,
                "home_flag": self.flag(home_name),
                "away_flag": self.flag(away_name),
                "home_score": None if pd.isna(hs) else int(hs),
                "away_score": None if pd.isna(as_) else int(as_),
            })
        matches.sort(key=lambda m: m["date"] or "", reverse=True)
        return matches

    def match_detail(self, game_id: str) -> dict | None:
        """Side-by-side team indicator comparison for one match."""
        g = self.raw[self.raw["game_id"].astype(str) == str(game_id)]
        g = g[g["minutes"] > 0]
        if g.empty:
            return None
        teams = list(g["team_name"].unique())[:2]
        if len(teams) < 2:
            return None

        def team_block(team):
            t = g[g["team_name"] == team]
            return t, {
                "team_name": team,
                "flag_url": self.flag(team),
                "score": (None if t["team_score"].isna().all()
                          else int(t["team_score"].iloc[0])),
            }

        ta, a = team_block(teams[0])
        tb, b = team_block(teams[1])

        # Possession proxy = share of total passes.
        pa = float(ta["totalPasses"].sum()) if "totalPasses" in ta else 0.0
        pb = float(tb["totalPasses"].sum()) if "totalPasses" in tb else 0.0
        tot = pa + pb
        indicators = [{
            "key": "possession", "label": "Possession %", "better_high": True,
            "a": round(pa / tot * 100, 1) if tot else 50.0,
            "b": round(pb / tot * 100, 1) if tot else 50.0,
        }]
        for col, label, _agg, better in MATCH_INDICATORS:
            if col not in g.columns:
                continue
            av = round(float(ta[col].sum()), 2)
            bv = round(float(tb[col].sum()), 2)
            indicators.append({"key": col, "label": label,
                               "better_high": better, "a": av, "b": bv})

        meta = next((m for m in self.matches if m["game_id"] == str(game_id)), {})
        timeline = self.events.get(str(game_id))
        return {
            "meta": meta, "team_a": a, "team_b": b, "indicators": indicators,
            "timeline": timeline,
        }

    # -- player detail ----------------------------------------------------- #
    def player_detail(self, player_id: int) -> dict | None:
        df = self.raw[self.raw["player_id"].astype(str) == str(player_id)]
        if df.empty:
            return None
        first = df.iloc[0]
        team = first["team_name"]
        played = df[df["game_id"].notna() & (df["minutes"] > 0)].copy()

        cols = [c for c, _l, _p in PLAYER_INDICATORS if c in df.columns]
        labels = [{"key": c, "label": l, "per90": p}
                  for c, l, p in PLAYER_INDICATORS if c in df.columns]

        # Per-match breakdown.
        matches = []
        for _, r in played.sort_values("match_date").iterrows():
            ts, os_ = r["team_score"], r["opp_score"]
            result = None
            if not pd.isna(ts) and not pd.isna(os_):
                result = "W" if ts > os_ else "L" if ts < os_ else "D"
            matches.append({
                "game_id": str(r["game_id"]),
                "date": r["match_date"],
                "opponent": r["opp_team_name"],
                "opp_flag": self.flag(r["opp_team_name"]),
                "home_away": r["home_away"],
                "result": result,
                "score": (None if pd.isna(ts) or pd.isna(os_)
                          else f"{int(ts)}-{int(os_)}"),
                "minutes": int(r["minutes"]),
                "stats": {c: (None if pd.isna(r[c]) else round(float(r[c]), 2))
                          for c in cols},
            })

        total_minutes = float(played["minutes"].sum())
        totals, per90 = {}, {}
        for c, _l, per in PLAYER_INDICATORS:
            if c not in df.columns:
                continue
            s = float(played[c].sum())
            if per:
                totals[c] = round(s, 2)
                per90[c] = round(s / total_minutes * 90, 2) if total_minutes else 0.0
            else:                                  # rate stat -> average
                totals[c] = round(float(played[c].mean()), 2) if not played.empty else 0.0
                per90[c] = totals[c]

        rating = (round(float(pd.to_numeric(played["avgRatingFromDataFeed"],
                  errors="coerce").mean()), 2)
                  if "avgRatingFromDataFeed" in played and not played.empty else None)

        return {
            "player": {
                "player_id": int(player_id),
                "player_name": first["player_name"],
                "team_name": team,
                "flag_url": self.flag(team),
                "role": first["role"],
                "position": first["position"],
                "games": int(len(played)),
                "minutes": int(total_minutes),
                "rating": rating,
            },
            "indicators": labels,
            "matches": matches,
            "totals": totals,
            "per90": per90,
        }


# Module-level singleton
store = DataStore()


def get_store() -> DataStore:
    store.load()
    return store
