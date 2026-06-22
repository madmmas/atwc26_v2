#!/usr/bin/env python3
"""
FIFA World Cup 2026 — fixture discovery.

Queries ESPN's public scoreboard API across the tournament's date range and
writes the full fixture list (gameId, kickoff time, teams, status) to
`data/schedule.json`. Any gameId not already present in `game_links.csv`
gets appended there automatically, so new matches no longer need to be added
by hand.

This is intentionally separate from scrape_wc26.py: that script pulls full
per-player stats for one match (expensive, ~1 request per player), while
this one just lists fixtures (cheap, ~1 request per date).

Usage
-----
  python3 fetch_schedule.py                       # full WC26 date range
  python3 fetch_schedule.py --start 2026-06-11 --end 2026-07-19
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
LINKS_CSV = ROOT / "game_links.csv"
DATA_DIR = ROOT / "data"
SCHEDULE_FILE = DATA_DIR / "schedule.json"
LOG_FILE = ROOT / "scrape.log"

DEFAULT_LEAGUE = "fifa.world"
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={ymd}"

# FIFA World Cup 2026: June 11 - July 19.
DEFAULT_START = date(2026, 6, 11)
DEFAULT_END = date(2026, 7, 19)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
REQUEST_TIMEOUT = 25

log = logging.getLogger("wc26.schedule")


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=0.8,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET"]), raise_on_status=False)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session


def fetch_day(session: requests.Session, league: str, day: date) -> list[dict]:
    url = SCOREBOARD_URL.format(league=league, ymd=day.strftime("%Y%m%d"))
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("events", [])
    except requests.RequestException as exc:
        log.warning("scoreboard fetch failed for %s: %s", day, exc)
        return []


def parse_event(event: dict) -> tuple[str, dict] | None:
    gid = event.get("id")
    if not gid:
        return None
    comp = (event.get("competitions") or [{}])[0]
    status = comp.get("status", {}).get("type", {})
    competitors = comp.get("competitors", [])
    home = next((c["team"]["displayName"] for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c["team"]["displayName"] for c in competitors if c.get("homeAway") == "away"), None)
    return gid, {
        "kickoff_utc": event.get("date"),
        "home": home,
        "away": away,
        "status_state": status.get("state"),
        "status_name": status.get("name"),
        "completed": bool(status.get("completed")),
    }


def load_schedule() -> dict:
    if SCHEDULE_FILE.exists():
        try:
            return json.loads(SCHEDULE_FILE.read_text())
        except ValueError:
            log.warning("schedule file corrupt; starting fresh")
    return {}


def append_new_links(gids: list[str]) -> int:
    existing = LINKS_CSV.read_text() if LINKS_CSV.exists() else ""
    existing_ids = set()
    for line in existing.splitlines():
        line = line.strip().strip(",").strip()
        if "gameId/" in line:
            existing_ids.add(line.rsplit("gameId/", 1)[-1])

    new_ids = [g for g in gids if g not in existing_ids]
    if not new_ids:
        return 0

    lines = [f"https://www.espn.com/soccer/player-stats/_/gameId/{g}" for g in new_ids]
    with LINKS_CSV.open("a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n".join(lines) + "\n")
    return len(new_ids)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FIFA WC26 fixture discovery")
    parser.add_argument("--start", type=lambda s: date.fromisoformat(s), default=DEFAULT_START)
    parser.add_argument("--end", type=lambda s: date.fromisoformat(s), default=DEFAULT_END)
    parser.add_argument("--league", default=DEFAULT_LEAGUE)
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)],
    )

    session = build_session()
    schedule = load_schedule()

    day = args.start
    fetched_days = 0
    while day <= args.end:
        for event in fetch_day(session, args.league, day):
            parsed = parse_event(event)
            if parsed:
                gid, info = parsed
                schedule[gid] = info
        fetched_days += 1
        day += timedelta(days=1)

    SCHEDULE_FILE.write_text(json.dumps(schedule, indent=2, sort_keys=True))
    added = append_new_links(sorted(schedule.keys(), key=int))

    log.info("scanned %d day(s), %d known fixture(s), %d new link(s) added to %s",
              fetched_days, len(schedule), added, LINKS_CSV.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
