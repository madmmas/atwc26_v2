"""Build team-level match matrix for Elo, Dixon-Coles, and XGBoost training."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _team_game_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate player rows to one row per (game_id, team_name)."""
    agg: dict[str, tuple[str, str]] = {
        "match_date": ("match_date", "first"),
        "home_away": ("home_away", "first"),
        "team_score": ("team_score", "first"),
        "opp_team_name": ("opp_team_name", "first"),
        "opp_score": ("opp_score", "first"),
        "expectedGoals": ("expectedGoals", "sum"),
        "totalShots": ("totalShots", "sum"),
        "shotsOnTarget": ("shotsOnTarget", "sum"),
        "minutes": ("minutes", "sum"),
    }
    present = {k: v for k, v in agg.items() if v[0] in df.columns}
    return df.groupby(["game_id", "team_name"], as_index=False).agg(**present)


def _p90(total: float, minutes: float) -> float:
    if minutes <= 0:
        return 0.0
    return float(total) / (float(minutes) / 90.0)


def build_match_matrix(
    master_parquet_path: Path,
    historical_form_path: Path,
) -> pd.DataFrame:
    """Return one row per match with team-level per-90 stats and outcome."""
    frames: list[pd.DataFrame] = []
    if master_parquet_path.exists():
        frames.append(pd.read_parquet(master_parquet_path))
    if historical_form_path.exists():
        frames.append(pd.read_parquet(historical_form_path))
    if not frames:
        return pd.DataFrame()

    raw = pd.concat(frames, ignore_index=True)
    raw["team_score"] = pd.to_numeric(raw["team_score"], errors="coerce")
    raw["opp_score"] = pd.to_numeric(raw["opp_score"], errors="coerce")
    raw = raw.dropna(subset=["team_score", "opp_score", "game_id"])

    team_games = _team_game_stats(raw)
    home = team_games[team_games["home_away"] == "home"].copy()
    away = team_games[team_games["home_away"] == "away"].copy()

    merged = home.merge(
        away,
        on="game_id",
        suffixes=("_h", "_a"),
        how="inner",
    )

    rows = []
    for _, r in merged.iterrows():
        h_min = float(r.get("minutes_h", 0) or 0)
        a_min = float(r.get("minutes_a", 0) or 0)
        h_score = int(r["team_score_h"])
        a_score = int(r["team_score_a"])
        if h_score > a_score:
            outcome = 2
        elif h_score == a_score:
            outcome = 1
        else:
            outcome = 0

        rows.append({
            "game_id": str(r["game_id"]),
            "match_date": r["match_date_h"],
            "home_team": r["team_name_h"],
            "away_team": r["team_name_a"],
            "h_goals": h_score,
            "a_goals": a_score,
            "h_xg_p90": _p90(r.get("expectedGoals_h", 0), h_min),
            "a_xg_p90": _p90(r.get("expectedGoals_a", 0), a_min),
            "h_shots_p90": _p90(r.get("totalShots_h", 0), h_min),
            "a_shots_p90": _p90(r.get("totalShots_a", 0), a_min),
            "h_sot_p90": _p90(r.get("shotsOnTarget_h", 0), h_min),
            "a_sot_p90": _p90(r.get("shotsOnTarget_a", 0), a_min),
            "outcome": outcome,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["match_date"] = pd.to_datetime(out["match_date"], errors="coerce")
    return out.sort_values("match_date").reset_index(drop=True)


def add_rolling_form(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """Add h_form3 and a_form3: wins in last {window} games per team (shifted)."""
    if df.empty:
        return df

    out = df.copy()
    out["h_form3"] = 0.0
    out["a_form3"] = 0.0

    team_history: dict[str, list[int]] = {}

    def _record(team: str, won: int) -> None:
        hist = team_history.setdefault(team, [])
        hist.append(won)

    for idx, row in out.iterrows():
        h_team = row["home_team"]
        a_team = row["away_team"]
        h_hist = team_history.get(h_team, [])
        a_hist = team_history.get(a_team, [])
        out.at[idx, "h_form3"] = float(sum(h_hist[-window:]))
        out.at[idx, "a_form3"] = float(sum(a_hist[-window:]))

        outcome = int(row["outcome"])
        _record(h_team, 1 if outcome == 2 else 0)
        _record(a_team, 1 if outcome == 0 else 0)

    return out
