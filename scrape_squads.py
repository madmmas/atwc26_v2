#!/usr/bin/env python3
"""
Add full team squads (including players who haven't played) to the dataset.

This pulls the REAL 23-26 man squad for every team from ESPN's site API:

    https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{id}/roster

For each squad member who has NOT appeared in a scraped match, it adds one
synthetic row to `all_players_stats.parquet` with the player's real identity
(ESPN id, name, position, jersey) but zero match stats and `game_id = NaN`.
Players who already have match data are left untouched.

The result: the predictor UI can select ANY squad member; untested players get
weak (near-zero) tournament-form ratings.

This is idempotent — re-running never duplicates players.

Usage
-----
  python3 scrape_squads.py                 # pull real squads for every team in the data
  python3 scrape_squads.py --teams 206,452 # only specific team ids
  python3 scrape_squads.py --league fifa.world
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MASTER_PARQUET = DATA_DIR / "all_players_stats.parquet"
SQUADS_RAW = DATA_DIR / "squads_raw.json"
LOG_FILE = ROOT / "scrape_squads.log"

DEFAULT_LEAGUE = "fifa.world"
TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams"
ROSTER_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}"
    "/teams/{team_id}/roster"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}
POLITE_DELAY = 0.3

# Identity columns (everything else in the parquet is a numeric stat column).
ID_COLS = [
    "game_id", "match_date", "competition", "season",
    "team_id", "team_name", "home_away", "is_winner", "formation",
    "team_score", "opp_team_id", "opp_team_name", "opp_score",
    "player_id", "player_name", "jersey", "position", "position_abbr",
    "starter", "subbed_in", "subbed_out", "minutes", "appearances",
    "scraped_at", "role",
]

log = logging.getLogger("squads")


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4, backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]), raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def get_json(session: requests.Session, url: str) -> dict | None:
    try:
        resp = session.get(url, timeout=25)
    except requests.RequestException as exc:
        log.warning("request failed: %s (%s)", url, exc)
        return None
    if resp.status_code != 200:
        log.warning("HTTP %s for %s", resp.status_code, url)
        return None
    try:
        return resp.json()
    except ValueError:
        log.warning("non-JSON response for %s", url)
        return None


def fetch_all_team_ids(session: requests.Session, league: str) -> list[str]:
    """Return every team id competing in the tournament (all 48 for WC26)."""
    data = get_json(session, TEAMS_URL.format(league=league))
    if not data:
        return []
    try:
        teams = data["sports"][0]["leagues"][0]["teams"]
    except (KeyError, IndexError):
        teams = data.get("leagues", [{}])[0].get("teams", [])
    return [str((t.get("team", t)).get("id")) for t in teams if (t.get("team", t)).get("id")]


def fetch_squad(session: requests.Session, league: str, team_id: str) -> dict | None:
    """Return {team_id, team_name, players:[{player_id, name, position, abbr, jersey}]}."""
    data = get_json(session, ROSTER_URL.format(league=league, team_id=team_id))
    if not data or "athletes" not in data:
        return None
    players = []
    for a in data["athletes"]:
        pos = a.get("position", {}) or {}
        players.append({
            "player_id": str(a.get("id")),            # keep as str to match dataset
            "player_name": a.get("displayName", "Unknown"),
            "position": pos.get("name"),
            "position_abbr": pos.get("abbreviation"),
            "jersey": a.get("jersey"),
        })
    return {
        "team_id": str(data["team"]["id"]),
        "team_name": data["team"]["displayName"],
        "players": players,
    }


def merge_squads(squads: list[dict], df: pd.DataFrame) -> pd.DataFrame:
    """Append synthetic rows for squad members with no match appearance."""
    existing = set(zip(df["player_id"].astype(str), df["team_name"].astype(str)))
    stat_cols = [c for c in df.columns if c not in ID_COLS]

    new_rows = []
    for squad in squads:
        team_id, team_name = squad["team_id"], squad["team_name"]
        added = 0
        for p in squad["players"]:
            if (p["player_id"], team_name) in existing:
                continue
            row = {c: None for c in df.columns}      # start all-null, full schema
            row.update({
                "competition": "FIFA World Cup",
                "season": 2026,
                "team_id": team_id,
                "team_name": team_name,
                "player_id": p["player_id"],
                "player_name": p["player_name"],
                "jersey": p["jersey"],
                "position": p["position"],
                "position_abbr": p["position_abbr"],
                "starter": False,
                "subbed_in": False,
                "subbed_out": False,
                "minutes": 0.0,
                "appearances": 0.0,
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            for c in stat_cols:
                row[c] = None                         # no stats — they didn't play
            new_rows.append(row)
            added += 1
        log.info("  %-22s +%d squad players (not yet played)", team_name, added)

    if not new_rows:
        log.info("No new squad players to add — dataset already complete.")
        return df

    out = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    # Match existing string dtype on id columns so pyarrow can serialize cleanly.
    for col in ("player_id", "team_id", "game_id"):
        out[col] = out[col].astype("object")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Add full team squads to the dataset")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--teams", help="comma-separated team ids (default: all teams in data)")
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)],
    )

    if not MASTER_PARQUET.exists():
        log.error("No match dataset found at %s — run scrape_wc26.py first.", MASTER_PARQUET)
        return 1
    df = pd.read_parquet(MASTER_PARQUET)
    log.info("Loaded %d match rows, %d players, %d teams.",
             len(df), df["player_id"].nunique(), df["team_name"].nunique())

    session = build_session()

    # Which teams to fetch: a given list, else EVERY team in the tournament
    # (all 48 for WC26 — including those who haven't played a match yet).
    if args.teams:
        team_ids = [t.strip() for t in args.teams.split(",")]
    else:
        team_ids = fetch_all_team_ids(session, args.league)
        if not team_ids:                       # fallback: at least cover played teams
            log.warning("Could not list all tournament teams; using teams in the data.")
            team_ids = (df[["team_id", "team_name"]].drop_duplicates()
                        ["team_id"].astype(str).tolist())
    log.info("Fetching real squads for %d teams from ESPN site API...", len(team_ids))
    squads = []
    for tid in team_ids:
        squad = fetch_squad(session, args.league, tid)
        time.sleep(POLITE_DELAY)
        if squad:
            squads.append(squad)
        else:
            log.warning("  no squad returned for team id %s", tid)
    if not squads:
        log.error("No squads fetched — aborting (dataset unchanged).")
        return 1

    SQUADS_RAW.write_text(json.dumps(squads, indent=2))
    log.info("Raw squads saved to %s", SQUADS_RAW.name)

    merged = merge_squads(squads, df)

    # Infer roles for the new (and existing) rows.
    from backend.app.data import classify_role
    merged["role"] = [classify_role(p, a)
                      for p, a in zip(merged["position"], merged["position_abbr"])]

    # Stable column order: identity first, then stats alphabetically.
    stat_cols = sorted(c for c in merged.columns if c not in ID_COLS)
    merged = merged[[c for c in ID_COLS if c in merged.columns] + stat_cols]

    merged.to_parquet(MASTER_PARQUET, index=False)
    merged.to_csv(DATA_DIR / "all_players_stats.csv", index=False)

    added = len(merged) - len(df)
    log.info("Done. Added %d squad players. Dataset now %d rows, %d players.",
             added, len(merged), merged["player_id"].nunique())
    log.info("Restart the backend to load the new players.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
