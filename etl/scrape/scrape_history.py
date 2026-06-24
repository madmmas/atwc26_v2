#!/usr/bin/env python3
"""
Backfill recent qualifier/friendly history for the 48 WC26 teams.

The Predictor rates players purely from WC26 tournament minutes, which is a
tiny (sometimes empty) sample for subs, backups, and players from eliminated
teams. This script pulls REAL match data (no synthetic rows) for the last
~12 months of World Cup qualifying and international friendlies — same
ESPN site API scrape_wc26.py already uses, just different league slugs:

  fifa.worldq.uefa / .concacaf / .conmebol / .caf / .afc / .ofc   (qualifiers)
  fifa.friendly                                                  (friendlies)

Confirmed these slugs return the identical summary/roster/stats structure
scrape_wc26.py already parses, so this reuses scrape_wc26.match_is_final()
and scrape_wc26.scrape_game() directly rather than duplicating that logic.

The scoreboard endpoint's `dates=` range silently truncates around ~100
events per call, so discovery is chunked by month, not by single day (slow)
or by a full year in one call (silently incomplete).

Output lives in its own namespace — never touches data/raw, data/games, or
all_players_stats.parquet — so it can't collide with or be wiped by the live
scrape_wc26.py/rebuild_master() refresh cycle:

  data/history_raw/<league>__<gameId>.json
  data/history_games/<league>__<gameId>.parquet
  data/historical_state.json      (incremental run state)
  data/historical_form.parquet    (combined output, rebuilt each run)

This is a manual/occasional backfill (results don't change), not part of
the live refresh cron. Safe to re-run — already-scraped games are skipped.

Usage
-----
  python3 etl/scrape/scrape_history.py                  # last 365 days, all leagues
  python3 etl/scrape/scrape_history.py --days 180
  python3 etl/scrape/scrape_history.py --leagues fifa.friendly,fifa.worldq.uefa
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import scrape_wc26

SCRAPER_DIR = Path(__file__).resolve().parent
ROOT = SCRAPER_DIR.parent.parent
DATA_DIR = ROOT / "data"
SQUADS_RAW = DATA_DIR / "squads_raw.json"
HISTORY_RAW_DIR = DATA_DIR / "history_raw"
HISTORY_GAMES_DIR = DATA_DIR / "history_games"
STATE_FILE = DATA_DIR / "historical_state.json"
OUTPUT_PARQUET = DATA_DIR / "historical_form.parquet"
LOG_FILE = SCRAPER_DIR / "scrape_history.log"

LEAGUES = [
    "fifa.worldq.uefa", "fifa.worldq.concacaf", "fifa.worldq.conmebol",
    "fifa.worldq.caf", "fifa.worldq.afc", "fifa.worldq.ofc",
    "fifa.friendly",
]
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={start}-{end}"
CHUNK_DAYS = 30
SCOREBOARD_DELAY = 0.2  # politeness between scoreboard calls

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

log = logging.getLogger("wc26.history")


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=0.8,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET"]), raise_on_status=False)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session


def load_team_ids() -> set[str]:
    """The 48 WC26 team ids, from the squads already discovered for the
    squad-completion feature (scrape_squads.py) — no need to re-fetch."""
    if not SQUADS_RAW.exists():
        log.error("%s not found — run `make squads` first.", SQUADS_RAW.name)
        return set()
    squads = json.loads(SQUADS_RAW.read_text())
    return {s["team_id"] for s in squads}


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except ValueError:
            log.warning("state file corrupt; starting fresh")
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def month_chunks(days: int) -> list[tuple[date, date]]:
    end = date.today() - timedelta(days=1)          # exclude today (possibly in-progress)
    start = end - timedelta(days=days)
    chunks = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS - 1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def discover_games(session: requests.Session, league: str, team_ids: set[str],
                    days: int) -> dict[str, str]:
    """Return {gameId: url} for completed matches involving a WC26 team."""
    found: dict[str, str] = {}
    for start, end in month_chunks(days):
        url = SCOREBOARD_URL.format(league=league, start=start.strftime("%Y%m%d"),
                                     end=end.strftime("%Y%m%d"))
        try:
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
            events = resp.json().get("events", [])
        except (requests.RequestException, ValueError) as exc:
            log.warning("[%s] scoreboard fetch failed for %s..%s: %s", league, start, end, exc)
            events = []
        for event in events:
            comp = (event.get("competitions") or [{}])[0]
            competitors = comp.get("competitors", [])
            if not any(str(c.get("team", {}).get("id")) in team_ids for c in competitors):
                continue
            gid = event.get("id")
            if gid:
                found[gid] = f"https://www.espn.com/soccer/player-stats/_/gameId/{gid}"
        time.sleep(SCOREBOARD_DELAY)
    return found


def rebuild_history_master() -> int:
    files = sorted(HISTORY_GAMES_DIR.glob("*.parquet"))
    if not files:
        return 0
    combined = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    combined.to_parquet(OUTPUT_PARQUET, index=False)
    return len(combined)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Backfill WC26 qualifier/friendly history")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--leagues", default=",".join(LEAGUES),
                        help="comma-separated ESPN league slugs")
    parser.add_argument("--include-dnp", action="store_true")
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(exist_ok=True)
    HISTORY_RAW_DIR.mkdir(exist_ok=True)
    HISTORY_GAMES_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)],
    )

    team_ids = load_team_ids()
    if not team_ids:
        return 1
    log.info("Tracking %d WC26 team ids.", len(team_ids))

    session = build_session()
    glossary = scrape_wc26.load_glossary()
    state = load_state()
    leagues = [l.strip() for l in args.leagues.split(",") if l.strip()]

    total_scraped = 0
    for league in leagues:
        log.info("Discovering fixtures for %s (last %d days)...", league, args.days)
        games = discover_games(session, league, team_ids, args.days)
        log.info("[%s] %d matches involving a WC26 team.", league, len(games))

        for gid, url in games.items():
            key = f"{league}:{gid}"
            if state.get(key, {}).get("status") == "ok":
                continue

            final = scrape_wc26.match_is_final(session, gid, league)
            if not final:
                state[key] = {"status": "pending" if final is False else "error"}
                save_state(state)
                continue

            try:
                df = scrape_wc26.scrape_game(session, gid, url, league, glossary,
                                             args.include_dnp)
            except Exception as exc:
                log.exception("[%s/%s] unexpected error: %s", league, gid, exc)
                df = None

            if df is None:
                state[key] = {"status": "error"}
                save_state(state)
                continue

            # scrape_game already tags `competition` from ESPN's own league
            # name (e.g. "FIFA World Cup Qualifying - UEFA") — no override needed.
            df.to_parquet(HISTORY_GAMES_DIR / f"{league}__{gid}.parquet", index=False)
            raw_dest = HISTORY_RAW_DIR / f"{league}__{gid}.json"
            src_raw = scrape_wc26.RAW_DIR / f"{gid}.json"
            if src_raw.exists():
                src_raw.replace(raw_dest)

            state[key] = {"status": "ok", "players": int(len(df)),
                          "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            save_state(state)
            total_scraped += 1

    rows = rebuild_history_master()
    log.info("Done — %d new game(s) scraped this run, %d total historical rows -> %s",
              total_scraped, rows, OUTPUT_PARQUET.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
