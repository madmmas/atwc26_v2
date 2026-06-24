#!/usr/bin/env python3
"""
FIFA World Cup 2026 — group standings + remaining group-stage fixtures.

Pulls ESPN's own group-stage standings (real, with ESPN's own tiebreak
already applied) and pairs each group with its not-yet-played fixtures, so
the frontend's standings page can show real GP/W/D/L/F/A/GD/P tables plus
score inputs for the matches still to come.

  standings: https://site.web.api.espn.com/apis/v2/sports/soccer/{league}/standings?season={year}
  remaining fixtures: scoreboard events with season.slug == "group-stage"
                       and status not completed

Output: data/standings.json
  {"Group A": {"teams": [{team_id, team_name, GP, W, D, L, F, A, GD, P, rank}, ...],
               "remaining_matches": [{game_id, kickoff_utc, home_team, away_team}, ...]},
   ...}

Usage
-----
  python3 etl/scrape/fetch_groups.py
  python3 etl/scrape/fetch_groups.py --season 2026 --start 2026-06-11 --end 2026-07-19
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SCRAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRAPER_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
STANDINGS_FILE = DATA_DIR / "standings.json"
LOG_FILE = SCRAPER_DIR / "scrape.log"

DEFAULT_LEAGUE = "fifa.world"
DEFAULT_SEASON = 2026
DEFAULT_START = date(2026, 6, 11)
DEFAULT_END = date(2026, 7, 19)

STANDINGS_URL = (
    "https://site.web.api.espn.com/apis/v2/sports/soccer/{league}/standings?season={season}"
)
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={ymd}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
REQUEST_TIMEOUT = 25

log = logging.getLogger("wc26.groups")


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=0.8,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET"]), raise_on_status=False)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session


def fetch_standings(session: requests.Session, league: str, season: int) -> dict:
    """{"Group A": {"teams": [...]}, ...} keyed by ESPN's own group name."""
    url = STANDINGS_URL.format(league=league, season=season)
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    groups: dict[str, dict] = {}
    for child in resp.json().get("children", []):
        name = child.get("name")
        entries = child.get("standings", {}).get("entries", [])
        teams = []
        for e in entries:
            stats = {s["abbreviation"]: s.get("value") for s in e.get("stats", [])}
            teams.append({
                "team_id": str(e["team"]["id"]),
                "team_name": e["team"]["displayName"],
                "rank": int(stats.get("R") or 0),
                "GP": int(stats.get("GP") or 0),
                "W": int(stats.get("W") or 0),
                "D": int(stats.get("D") or 0),
                "L": int(stats.get("L") or 0),
                "F": int(stats.get("F") or 0),
                "A": int(stats.get("A") or 0),
                "GD": int(stats.get("GD") or 0),
                "P": int(stats.get("P") or 0),
                "advanced": bool(stats.get("ADV")),
            })
        teams.sort(key=lambda t: t["rank"] or 99)
        groups[name] = {"teams": teams, "remaining_matches": []}
    return groups


def fetch_remaining_matches(session: requests.Session, league: str,
                             start: date, end: date) -> list[dict]:
    """Not-yet-played group-stage fixtures across the tournament window."""
    remaining = []
    day = start
    while day <= end:
        url = SCOREBOARD_URL.format(league=league, ymd=day.strftime("%Y%m%d"))
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            events = resp.json().get("events", [])
        except requests.RequestException as exc:
            log.warning("scoreboard fetch failed for %s: %s", day, exc)
            events = []
        for event in events:
            if event.get("season", {}).get("slug") != "group-stage":
                continue
            comp = (event.get("competitions") or [{}])[0]
            status = comp.get("status", {}).get("type", {})
            if status.get("completed"):
                continue
            competitors = comp.get("competitors", [])
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            remaining.append({
                "game_id": event.get("id"),
                "kickoff_utc": event.get("date"),
                "home_team_id": str(home["team"]["id"]),
                "home_team": home["team"]["displayName"],
                "away_team_id": str(away["team"]["id"]),
                "away_team": away["team"]["displayName"],
            })
        day += timedelta(days=1)
    return remaining


def attach_remaining_matches(groups: dict, remaining: list[dict]) -> None:
    """Slot each remaining fixture into the group both its teams belong to."""
    team_to_group = {
        t["team_id"]: gname
        for gname, g in groups.items()
        for t in g["teams"]
    }
    for m in remaining:
        gname = team_to_group.get(m["home_team_id"]) or team_to_group.get(m["away_team_id"])
        if gname:
            groups[gname]["remaining_matches"].append(m)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="WC26 group standings + remaining fixtures")
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    parser.add_argument("--season", type=int, default=DEFAULT_SEASON)
    parser.add_argument("--start", type=lambda s: date.fromisoformat(s), default=DEFAULT_START)
    parser.add_argument("--end", type=lambda s: date.fromisoformat(s), default=DEFAULT_END)
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)],
    )

    session = build_session()
    groups = fetch_standings(session, args.league, args.season)
    log.info("fetched standings for %d group(s)", len(groups))

    remaining = fetch_remaining_matches(session, args.league, args.start, args.end)
    attach_remaining_matches(groups, remaining)
    log.info("found %d remaining group-stage fixture(s)", len(remaining))

    STANDINGS_FILE.write_text(json.dumps(groups, indent=2, sort_keys=True))
    log.info("wrote %d group(s) -> %s", len(groups), STANDINGS_FILE.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
