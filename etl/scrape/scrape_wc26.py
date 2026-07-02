#!/usr/bin/env python3
"""
FIFA World Cup 2026 — match-by-match player-stats scraper.

Reads game URLs from `etl/scrape/game_links.csv`. For every *new* game added to that file
it pulls the full per-player statistics for both teams and appends them to a
tidy dataset for analysis.

Why not scrape the HTML?
------------------------
ESPN's web pages sit behind an AWS WAF JavaScript challenge, so a plain
requests/BeautifulSoup fetch only gets a 202 "are you a bot?" page. ESPN's
underlying JSON APIs, however, are open and return *richer* data than the
rendered page:

  * summary API  -> game meta + both rosters (player identities, positions,
                    starters, substitutions).
                    https://site.web.api.espn.com/.../summary?event=<gameId>
  * core API     -> 127 stat fields per player across 4 categories
                    (defensive / general / goalKeeping / offensive), a full
                    superset of the on-page glossary (TCH, xG, xA, BCC, DINT,
                    DUELW, CLR, ...).
                    https://sports.core.api.espn.com/.../roster/<pid>/statistics/0

Outputs (under ./data)
----------------------
  raw/<gameId>.json              raw API payloads (so new fields can be
                                 re-derived later without re-scraping)
  games/game_<gameId>.parquet    one game's player rows (immutable)
  all_players_stats.parquet      combined master, rebuilt every run
  all_players_stats.csv          same, human-readable
  glossary.csv                   column -> human name -> category -> abbr
  processed_games.json           run state (which games are done)
  scrape.log                     log file

Usage
-----
  python3 scrape_wc26.py                  # process newly-added links, then exit
  python3 scrape_wc26.py --force          # reprocess every link in the csv
  python3 scrape_wc26.py --game 760416    # (re)process a single gameId
  python3 scrape_wc26.py --watch 60       # poll the csv every 60s for new links
  python3 scrape_wc26.py --include-dnp    # also store players who didn't play
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
LINKS_CSV = ROOT / "game_links.csv"
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
GAMES_DIR = DATA_DIR / "games"
MASTER_PARQUET = DATA_DIR / "all_players_stats.parquet"
MASTER_CSV = DATA_DIR / "all_players_stats.csv"
GLOSSARY_CSV = DATA_DIR / "glossary.csv"
STATE_FILE = DATA_DIR / "processed_games.json"
LOG_FILE = ROOT / "scrape.log"

# All WC26 matches live under this ESPN soccer league slug. Override with
# --league if you ever point the scraper at a different competition.
DEFAULT_LEAGUE = "fifa.world"

SUMMARY_URL = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={gid}"
STATS_URL = (
    "https://sports.core.api.espn.com/v2/sports/soccer/leagues/{league}"
    "/events/{gid}/competitions/{gid}/competitors/{team}/roster/{pid}"
    "/statistics/0?lang=en"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 25          # seconds per HTTP request
POLITE_DELAY = 0.35           # seconds between per-player stat requests

# Identity columns written before the stat columns, in this order.
IDENTITY_COLS = [
    "game_id", "match_date", "competition", "season",
    "team_id", "team_name", "home_away", "is_winner", "formation",
    "team_score", "team_shootout_score",
    "opp_team_id", "opp_team_name", "opp_score", "opp_shootout_score",
    "player_id", "player_name", "jersey", "position", "position_abbr",
    "starter", "subbed_in", "subbed_out", "minutes", "appearances",
    "scraped_at",
]

log = logging.getLogger("wc26")


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def build_session() -> requests.Session:
    """A session with automatic retry/backoff on transient failures."""
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=0.8,                       # 0.8s, 1.6s, 3.2s, ...
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def get_json(session: requests.Session, url: str) -> dict | None:
    """GET a URL and parse JSON, returning None on any failure."""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
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


# --------------------------------------------------------------------------- #
# Link / state handling
# --------------------------------------------------------------------------- #
GAMEID_RE = re.compile(r"gameId/(\d+)")


def read_game_links(csv_path: Path) -> dict[str, str]:
    """Return {gameId: url} parsed from the links csv.

    Tolerates an optional header row and blank lines; the only thing that
    matters is that each line contains `.../gameId/<digits>`.
    """
    links: dict[str, str] = {}
    if not csv_path.exists():
        log.error("links file not found: %s", csv_path)
        return links
    for raw in csv_path.read_text().splitlines():
        line = raw.strip().strip(",").strip()
        if not line:
            continue
        m = GAMEID_RE.search(line)
        if m:
            links[m.group(1)] = line
    return links


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except ValueError:
            log.warning("state file corrupt; starting fresh")
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


# --------------------------------------------------------------------------- #
# Stat flattening
# --------------------------------------------------------------------------- #
def flatten_player_stats(stats_payload: dict, glossary: dict) -> dict[str, float]:
    """Flatten the core-API statistics payload into {column: numeric value}.

    Columns are keyed by each stat's stable `name` (e.g. ``expectedGoals``,
    ``touches``, ``duelsWon``). A handful of names are reused across stat
    categories; those are disambiguated by prefixing the category
    (e.g. ``goalKeeping_crossesCaught``). The glossary dict is updated in place
    so we can emit a human-readable field reference afterwards.
    """
    out: dict[str, float] = {}
    categories = stats_payload.get("splits", {}).get("categories", []) or []
    for cat in categories:
        cat_name = cat.get("name", "")
        for st in cat.get("stats", []) or []:
            name = st.get("name")
            if not name:
                continue
            col = name
            prev = glossary.get(col)
            # Same column name already claimed by a different category -> namespace both.
            if prev and prev["category"] != cat_name:
                col = f"{cat_name}_{name}"
            value = st.get("value")
            if value is None:                      # fall back to parsing display text
                try:
                    value = float(st.get("displayValue"))
                except (TypeError, ValueError):
                    value = None
            out[col] = value
            glossary.setdefault(
                col,
                {
                    "column": col,
                    "category": cat_name,
                    "name": name,
                    "abbreviation": st.get("abbreviation"),
                    "description": st.get("description"),
                },
            )
    return out


def _stat_value(stats: dict[str, float], *names: str) -> float | None:
    for n in names:
        if n in stats and stats[n] is not None:
            return stats[n]
    return None


# --------------------------------------------------------------------------- #
# Per-game scraping
# --------------------------------------------------------------------------- #
def match_is_final(session: requests.Session, gid: str, league: str) -> bool | None:
    """Cheap pre-check: has ESPN marked this match's status as completed?

    Returns None if the status couldn't be determined (treat as a transient
    failure, retry later) rather than risk scraping a still-live match.
    """
    summary = get_json(session, SUMMARY_URL.format(league=league, gid=gid))
    if not summary:
        return None
    comp = (summary.get("header", {}).get("competitions") or [{}])[0]
    status = comp.get("status", {}).get("type", {})
    if "completed" not in status:
        return None
    return bool(status.get("completed"))


def scrape_game(
    session: requests.Session,
    gid: str,
    url: str,
    league: str,
    glossary: dict,
    include_dnp: bool,
) -> pd.DataFrame | None:
    """Scrape one game and return a wide DataFrame (one row per player)."""
    summary = get_json(session, SUMMARY_URL.format(league=league, gid=gid))
    if not summary or "rosters" not in summary:
        log.error("[%s] no summary/rosters returned", gid)
        return None

    # --- game-level meta from the header ---
    header = summary.get("header", {})
    comp = (header.get("competitions") or [{}])[0]
    match_date = comp.get("date")
    season = (header.get("season") or {}).get("year")
    competition = "FIFA World Cup"
    leag = header.get("league")
    if isinstance(leag, dict) and leag.get("name"):
        competition = leag["name"]

    competitors = comp.get("competitors", [])
    score_by_team = {c["team"]["id"]: c.get("score") for c in competitors}
    # Only set when a knockout draw was resolved on penalties.
    shootout_by_team = {c["team"]["id"]: c.get("shootoutScore") for c in competitors}
    name_by_team = {c["team"]["id"]: c["team"]["displayName"] for c in competitors}

    raw_player_payloads: dict[str, dict] = {}
    rows: list[dict] = []

    for roster in summary["rosters"]:
        team = roster.get("team", {})
        team_id = team.get("id")
        team_name = team.get("displayName")
        home_away = roster.get("homeAway")
        formation = roster.get("formation")
        is_winner = roster.get("winner")
        opp_ids = [t for t in name_by_team if t != team_id]
        opp_id = opp_ids[0] if opp_ids else None

        for entry in roster.get("roster", []):
            athlete = entry.get("athlete", {})
            pid = athlete.get("id")
            if not pid:
                continue

            stats_payload = get_json(
                session,
                STATS_URL.format(league=league, gid=gid, team=team_id, pid=pid),
            )
            time.sleep(POLITE_DELAY)
            stats = (
                flatten_player_stats(stats_payload, glossary)
                if stats_payload else {}
            )
            raw_player_payloads[str(pid)] = stats_payload or {}

            minutes = _stat_value(stats, "minutes")
            appearances = _stat_value(stats, "appearances")
            starter = bool(entry.get("starter"))
            subbed_in = bool((entry.get("subbedIn") or {}).get("didSub")
                             if isinstance(entry.get("subbedIn"), dict)
                             else entry.get("subbedIn"))
            subbed_out = bool((entry.get("subbedOut") or {}).get("didSub")
                              if isinstance(entry.get("subbedOut"), dict)
                              else entry.get("subbedOut"))

            played = starter or subbed_in or bool(minutes) or bool(appearances)
            if not played and not include_dnp:
                continue

            position = entry.get("position", {}) or {}
            row = {
                "game_id": gid,
                "match_date": match_date,
                "competition": competition,
                "season": season,
                "team_id": team_id,
                "team_name": team_name,
                "home_away": home_away,
                "is_winner": is_winner,
                "formation": formation,
                "team_score": score_by_team.get(team_id),
                "team_shootout_score": shootout_by_team.get(team_id),
                "opp_team_id": opp_id,
                "opp_team_name": name_by_team.get(opp_id),
                "opp_score": score_by_team.get(opp_id),
                "opp_shootout_score": shootout_by_team.get(opp_id),
                "player_id": pid,
                "player_name": athlete.get("displayName"),
                "jersey": entry.get("jersey"),
                "position": position.get("displayName"),
                "position_abbr": position.get("abbreviation"),
                "starter": starter,
                "subbed_in": subbed_in,
                "subbed_out": subbed_out,
                "minutes": minutes,
                "appearances": appearances,
                "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            row.update(stats)
            rows.append(row)

    if not rows:
        log.error("[%s] no player rows produced", gid)
        return None

    # Persist the raw payloads so new fields can be re-derived without re-scraping.
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{gid}.json").write_text(json.dumps(
        {"url": url, "league": league, "summary": summary,
         "player_statistics": raw_player_payloads}, indent=2))

    df = pd.DataFrame(rows)
    # Stat columns after the identity columns, alphabetically for stability.
    stat_cols = sorted(c for c in df.columns if c not in IDENTITY_COLS)
    ordered = [c for c in IDENTITY_COLS if c in df.columns] + stat_cols
    df = df[ordered]

    home = name_by_team.get(competitors[0]["team"]["id"]) if competitors else "?"
    log.info("[%s] %s — %d players, %d stat fields",
             gid, " vs ".join(name_by_team.values()) or home, len(df), len(stat_cols))
    return df


# --------------------------------------------------------------------------- #
# Output assembly
# --------------------------------------------------------------------------- #
def write_game(df: pd.DataFrame, gid: str) -> None:
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(GAMES_DIR / f"game_{gid}.parquet", index=False)


def rebuild_master(glossary: dict) -> None:
    """Rebuild the combined master files from every per-game parquet."""
    files = sorted(GAMES_DIR.glob("game_*.parquet"))
    if not files:
        return
    combined = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    stat_cols = sorted(c for c in combined.columns if c not in IDENTITY_COLS)
    combined = combined[[c for c in IDENTITY_COLS if c in combined.columns] + stat_cols]
    combined.to_parquet(MASTER_PARQUET, index=False)
    combined.to_csv(MASTER_CSV, index=False)

    if glossary:
        gdf = (pd.DataFrame(glossary.values())
               .sort_values(["category", "column"])
               .reset_index(drop=True))
        gdf.to_csv(GLOSSARY_CSV, index=False)

    log.info("master rebuilt: %d rows across %d games -> %s",
             len(combined), len(files), MASTER_PARQUET.name)


def load_glossary() -> dict:
    """Reload a previously-saved glossary so it accumulates across runs."""
    if not GLOSSARY_CSV.exists():
        return {}
    try:
        df = pd.read_csv(GLOSSARY_CSV)
        return {r["column"]: r.to_dict() for _, r in df.iterrows()}
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def process_once(session, args, glossary) -> int:
    """Process all pending games. Returns the number newly scraped."""
    links = read_game_links(LINKS_CSV)
    if not links:
        log.info("no game links found in %s", LINKS_CSV.name)
        return 0

    state = load_state()
    if args.game:
        targets = {args.game: links.get(args.game, f"gameId/{args.game}")}
    elif args.force:
        targets = links
    else:
        targets = {g: u for g, u in links.items()
                   if state.get(g, {}).get("status") != "ok"}

    if not targets:
        log.info("no new games to process (%d already done)", len(state))
        return 0

    log.info("processing %d game(s): %s", len(targets), ", ".join(targets))
    scraped = 0
    for gid, url in targets.items():
        final = match_is_final(session, gid, args.league)
        if final is False:
            log.info("[%s] match not finished yet — skipping until it's final", gid)
            state[gid] = {"url": url, "status": "pending",
                          "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            save_state(state)
            continue
        if final is None:
            log.warning("[%s] could not determine match status — will retry", gid)
            state[gid] = {"url": url, "status": "error",
                          "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            save_state(state)
            continue

        try:
            df = scrape_game(session, gid, url, args.league, glossary,
                             args.include_dnp)
        except Exception as exc:                   # never let one game kill the run
            log.exception("[%s] unexpected error: %s", gid, exc)
            df = None

        if df is None:
            state[gid] = {"url": url, "status": "error",
                          "scraped_at": datetime.now(timezone.utc).isoformat()}
            save_state(state)
            continue

        write_game(df, gid)
        state[gid] = {
            "url": url, "status": "ok", "players": int(len(df)),
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        save_state(state)
        scraped += 1

    rebuild_master(glossary)
    return scraped


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FIFA WC26 player-stats scraper")
    parser.add_argument("--force", action="store_true",
                        help="reprocess every link in the csv")
    parser.add_argument("--game", metavar="GAMEID",
                        help="process a single gameId")
    parser.add_argument("--watch", type=int, metavar="SECONDS",
                        help="poll the links csv on this interval (Ctrl-C to stop)")
    parser.add_argument("--league", default=DEFAULT_LEAGUE,
                        help=f"ESPN league slug (default: {DEFAULT_LEAGUE})")
    parser.add_argument("--include-dnp", action="store_true",
                        help="also store players who did not play")
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(LOG_FILE)],
    )

    session = build_session()
    glossary = load_glossary()

    if args.watch:
        log.info("watch mode: polling %s every %ds", LINKS_CSV.name, args.watch)
        try:
            while True:
                n = process_once(session, args, glossary)
                if n:
                    log.info("scraped %d new game(s); waiting for more...", n)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            log.info("watch stopped")
            return 0

    n = process_once(session, args, glossary)
    log.info("done — %d game(s) scraped this run", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
