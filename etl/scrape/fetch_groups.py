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

Also pulls the Round-of-32-through-Final knockout bracket skeleton from the
same scoreboard sweep. ESPN already encodes each slot structurally —
competitor `team.abbreviation` is "1A".."2L" for a group winner/runner-up,
or "3RD" (with the candidate groups spelled out in `displayName`, e.g.
"Third Place Group A/B/C/D/F") for the four third-place wildcard slots —
so slot meaning is parsed once here rather than by the frontend.

Output: data/standings.json (see above) and data/bracket.json
  {"rounds": [{"name": "Round of 32", "matches": [
      {"game_id", "kickoff_utc", "completed",
       "slot_a"/"slot_b": {"type": "group_rank", "group": "A", "rank": 1}
                          | {"type": "third_place", "candidate_groups": ["A","B","C","D","F"]}
                          | {"type": "team", "team_id", "team_name"},
       "score_a", "score_b",
       "shootout_a", "shootout_b": int | None, set only when the draw was
                                    resolved on penalties},
      ...]}, ...]}

Usage
-----
  python3 etl/scrape/fetch_groups.py
  python3 etl/scrape/fetch_groups.py --season 2026 --start 2026-06-11 --end 2026-07-19
"""

from __future__ import annotations

import argparse
import json
import logging
import re
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
BRACKET_FILE = DATA_DIR / "bracket.json"
LOG_FILE = SCRAPER_DIR / "scrape.log"

# season.slug -> display name, in bracket order.
ROUND_SLUGS = [
    ("round-of-32", "Round of 32"),
    ("round-of-16", "Round of 16"),
    ("quarterfinals", "Quarterfinals"),
    ("semifinals", "Semifinals"),
    ("3rd-place-match", "Third Place Match"),
    ("final", "Final"),
]

DEFAULT_LEAGUE = "fifa.world"
DEFAULT_SEASON = 2026
DEFAULT_START = date(2026, 6, 11)
DEFAULT_END = date(2026, 7, 19)

STANDINGS_URL = (
    "https://site.web.api.espn.com/apis/v2/sports/soccer/{league}/standings?season={season}"
)
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={ymd}"
# The scoreboard feed does NOT expose a match number; the core API does, at
# `competitions[0].matchNumber` — ESPN's canonical bracket numbering (group
# stage 1-72, Round of 32 73-88, Round of 16 89-96, QF 97-100, SF 101-102,
# 3rd-place 103, Final 104). This is the number later rounds reference in
# placeholder text ("Round of 32 15 Winner"), so it's what `position` must key
# off of. See fetch_bracket().
CORE_EVENT_URL = (
    "https://sports.core.api.espn.com/v2/sports/soccer/leagues/{league}/events/{event_id}"
)

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


def fetch_all_events(session: requests.Session, league: str,
                      start: date, end: date) -> list[dict]:
    """One day-by-day sweep of the scoreboard, reused for both group-stage
    remaining fixtures and the knockout bracket so we don't scan twice."""
    events = []
    day = start
    while day <= end:
        url = SCOREBOARD_URL.format(league=league, ymd=day.strftime("%Y%m%d"))
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            events.extend(resp.json().get("events", []))
        except requests.RequestException as exc:
            log.warning("scoreboard fetch failed for %s: %s", day, exc)
        day += timedelta(days=1)
    return events


def fetch_remaining_matches(events: list[dict]) -> list[dict]:
    """Not-yet-played group-stage fixtures."""
    remaining = []
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
    return remaining


# --------------------------------------------------------------------------- #
# Knockout bracket
# --------------------------------------------------------------------------- #
GROUP_RANK_RE = re.compile(r"^([12])([A-L])$")
THIRD_PLACE_GROUPS_RE = re.compile(r"Group ([A-L](?:/[A-L])*)")
# "Round of 32 3 Winner" / "Quarterfinal 1 Winner" / "Semifinal 2 Loser" —
# ESPN's own placeholder text for a later round referencing an earlier one.
MATCH_REF_RE = re.compile(
    r"^(Round of \d+|Quarterfinal|Semifinal) (\d+) (Winner|Loser)$"
)
# Normalizes the round name as it appears *inside* a reference string to
# match this script's own round display names (see ROUND_SLUGS).
MATCH_REF_ROUND_NAME = {
    "Round of 32": "Round of 32",
    "Round of 16": "Round of 16",
    "Quarterfinal": "Quarterfinals",
    "Semifinal": "Semifinals",
}


def parse_slot(competitor: dict) -> dict:
    """One bracket competitor -> a real team, a group-rank slot, a
    third-place wildcard slot, or a reference to another round's
    not-yet-played result.

    ESPN encodes all of this in `abbreviation`/`displayName`: "1A".."2L"
    for a group winner/runner-up, "3RD" (+ candidate groups spelled out in
    `displayName`) for the four wildcard slots, or plain text like "Round
    of 32 3 Winner" for anything that depends on an earlier knockout round
    — parsed once here so neither the simulator nor the frontend has to
    interpret ESPN's strings themselves.
    """
    team = competitor.get("team", {})
    abbr = team.get("abbreviation", "")
    name = team.get("displayName", "")
    m = GROUP_RANK_RE.match(abbr)
    if m:
        return {"type": "group_rank", "group": m.group(2), "rank": int(m.group(1))}
    if abbr == "3RD":
        m2 = THIRD_PLACE_GROUPS_RE.search(name)
        groups = m2.group(1).split("/") if m2 else []
        return {"type": "third_place", "candidate_groups": groups}
    m3 = MATCH_REF_RE.match(name)
    if m3:
        kind = "match_winner" if m3.group(3) == "Winner" else "match_loser"
        return {"type": kind, "round": MATCH_REF_ROUND_NAME[m3.group(1)], "position": int(m3.group(2))}
    # An already-decided real team.
    return {"type": "team", "team_id": str(team.get("id")), "team_name": name}


def fetch_match_number(session: requests.Session, league: str, event_id: str):
    """ESPN's canonical bracket match number for an event, or None.

    Read from the core API's `competitions[0].matchNumber` (the scoreboard
    feed doesn't carry it). This is the fixed, structural number that later
    rounds reference in placeholder text — it is NOT the same as the event id
    or the kickoff order (e.g. Australia-Egypt kicks off before Argentina-Cape
    Verde and has the smaller event id, yet is the *later* bracket match, #16
    vs #14), which is exactly why keying off either of those mis-pairs the
    Round of 16.
    """
    url = CORE_EVENT_URL.format(league=league, event_id=event_id)
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        comp = (resp.json().get("competitions") or [{}])[0]
        number = comp.get("matchNumber")
        return int(number) if number is not None else None
    except (requests.RequestException, ValueError, TypeError) as exc:
        log.warning("no matchNumber for event %s: %s", event_id, exc)
        return None


def fetch_bracket(session: requests.Session, league: str, events: list[dict]) -> dict:
    """Build the Round-of-32-through-Final fixture skeleton.

    Each round's matches are sorted by ESPN's canonical `matchNumber` (fetched
    per event from the core API) and given an explicit 1-indexed `position`.
    That number is exactly what later rounds reference in placeholder text
    (e.g. Round-of-32 match #15 is "Round of 32 15 Winner" wherever a
    Round-of-16 match references it), so `position` must equal it.

    This must NOT be keyed off discovery order (the order `events` are scanned
    day-by-day, which isn't stable across scrapes) NOR off the event id / kickoff
    time (which don't match ESPN's bracket numbering — Australia-Egypt has an
    earlier kickoff and smaller event id than Argentina-Cape Verde yet is the
    later bracket match). Any of those mis-pair the Round of 16 — e.g. resolving
    "Egypt vs Colombia" / "Switzerland vs Argentina" instead of the correct
    "Argentina vs Egypt" / "Switzerland vs Colombia".
    """
    slugs = dict(ROUND_SLUGS)
    rounds: dict[str, list[dict]] = {name: [] for _, name in ROUND_SLUGS}
    for event in events:
        slug = event.get("season", {}).get("slug")
        if slug not in slugs:
            continue
        comp = (event.get("competitions") or [{}])[0]
        status = comp.get("status", {}).get("type", {})
        competitors = comp.get("competitors", [])
        a = next((c for c in competitors if c.get("homeAway") == "home"), None)
        b = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not a or not b:
            continue
        rounds[slugs[slug]].append({
            "game_id": event.get("id"),
            "kickoff_utc": event.get("date"),
            "completed": bool(status.get("completed")),
            "slot_a": parse_slot(a),
            "slot_b": parse_slot(b),
            "score_a": a.get("score"),
            "score_b": b.get("score"),
            # Only present when a knockout draw was resolved on penalties
            # (ESPN sets this directly on the competitor; status.type.id
            # "47"/"STATUS_FINAL_PEN" is the same signal, but the score
            # fields are simpler for the frontend to key off of).
            "shootout_a": a.get("shootoutScore"),
            "shootout_b": b.get("shootoutScore"),
        })
    for matches in rounds.values():
        # Sort by ESPN's canonical matchNumber so `position` equals the number
        # placeholders reference. Fall back to event id if matchNumber is ever
        # unavailable (network hiccup) — still deterministic, just not
        # guaranteed canonical for that scrape.
        gid = lambda m: int(m["game_id"]) if str(m["game_id"]).isdigit() else 0
        numbers = {
            m["game_id"]: fetch_match_number(session, league, m["game_id"])
            for m in matches
        }
        matches.sort(key=lambda m: (
            numbers[m["game_id"]] is None,          # unknowns sort last
            numbers[m["game_id"]] if numbers[m["game_id"]] is not None else 0,
            gid(m),
        ))
        for i, m in enumerate(matches):
            m["position"] = i + 1
    return {"rounds": [{"name": name, "matches": rounds[name]} for _, name in ROUND_SLUGS]}


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

    events = fetch_all_events(session, args.league, args.start, args.end)

    remaining = fetch_remaining_matches(events)
    attach_remaining_matches(groups, remaining)
    log.info("found %d remaining group-stage fixture(s)", len(remaining))
    STANDINGS_FILE.write_text(json.dumps(groups, indent=2, sort_keys=True))
    log.info("wrote %d group(s) -> %s", len(groups), STANDINGS_FILE.name)

    bracket = fetch_bracket(session, args.league, events)
    total_matches = sum(len(r["matches"]) for r in bracket["rounds"])
    BRACKET_FILE.write_text(json.dumps(bracket, indent=2))
    log.info("wrote %d knockout fixture(s) across %d round(s) -> %s",
              total_matches, len(bracket["rounds"]), BRACKET_FILE.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
