#!/usr/bin/env python3
"""
Discover full team squads (including players who haven't played) for WC26.

This pulls the REAL 23-26 man squad for every team from ESPN's site API:

    https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{id}/roster

and writes the result to `data/squads_raw.json`. The backend (DataStore.load,
in backend/app/data.py) merges this in-memory on every load, adding a
synthetic 0-minute row for any squad member with no match appearance yet —
done at load time (not written into the match dataset) so it survives every
`rebuild_master()` in scrape_wc26.py. That rebuild prefers per-game parquets
and preserves master-only game IDs, but still only contains players who
appeared in a scraped match — never the full registered squad.

The result: the predictor / player-analysis UI can list ANY squad member;
untested players show 0 minutes and near-zero tournament-form ratings.

This is idempotent — re-running just overwrites squads_raw.json with a fresh
pull (squad members rarely change mid-tournament, e.g. injury replacements).

Usage
-----
  python3 scrape_squads.py                 # pull every team's real squad
  python3 scrape_squads.py --teams 206,452 # only specific team ids
  python3 scrape_squads.py --league fifa.world
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Discover full WC26 team squads")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--teams", help="comma-separated team ids (default: every WC26 team)")
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)],
    )

    session = build_session()

    team_ids = ([t.strip() for t in args.teams.split(",")] if args.teams
                else fetch_all_team_ids(session, args.league))
    if not team_ids:
        log.error("Could not list WC26 teams (pass --teams to specify ids manually).")
        return 1

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
        log.error("No squads fetched — squads_raw.json left unchanged.")
        return 1

    SQUADS_RAW.write_text(json.dumps(squads, indent=2))
    total_players = sum(len(s["players"]) for s in squads)
    log.info("Saved %d teams, %d players -> %s. Restart the backend to pick it up.",
             len(squads), total_players, SQUADS_RAW.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
