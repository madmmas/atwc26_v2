#!/usr/bin/env python3
"""
Build per-match event timelines + a momentum series from the raw ESPN
summary payloads already saved under data/raw/<gameId>.json.

Uses only fields ESPN itself returns:
  - summary.keyEvents   -> goals, cards, substitutions, KO/HT/FT markers
                            (minute, team, description — all literal ESPN data)
  - summary.commentary  -> minute-by-minute play-by-play (shots, corners,
                            offsides, ...), used to derive an *approximate*
                            momentum wave. This is our own heuristic built
                            from real per-minute events; it is not ESPN's
                            proprietary momentum metric.

Output: data/match_events.json, keyed by game_id. Re-run any time after
scraping new games (`make events`, or it's chained into `make refresh`).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_FILE = ROOT / "data" / "match_events.json"

# Event types worth showing as a marker on the timeline.
MARKER_TYPES = {
    "kickoff": "KO",
    "halftime": "HT",
    "end-regular-time": "FT",
    "goal": "goal",
    "goal---header": "goal",
    "own-goal": "own-goal",
    "yellow-card": "yellow-card",
    "red-card": "red-card",
    "substitution": "substitution",
}

# Heuristic attacking-action weights for the momentum approximation.
# Only real, scraped play-by-play events feed this — no fabricated data.
ATTACK_WEIGHTS = {
    "goal": 6.0,
    "goal---header": 6.0,
    "own-goal": 6.0,
    "shot-on-target": 3.0,
    "shot-blocked": 1.5,
    "shot-off-target": 1.0,
    "corner-awarded": 1.0,
    "offside": 0.5,
}

SMOOTH_WINDOW = 2  # +/- minutes averaged on each side


def home_away(summary: dict) -> tuple[str | None, str | None]:
    comps = (summary.get("header", {}).get("competitions") or [{}])[0]
    home = away = None
    for c in comps.get("competitors", []):
        name = (c.get("team") or {}).get("displayName")
        if c.get("homeAway") == "home":
            home = name
        elif c.get("homeAway") == "away":
            away = name
    return home, away


def build_events(key_events: list[dict]) -> list[dict]:
    out = []
    for e in key_events:
        etype = e.get("type", {}).get("type")
        if etype not in MARKER_TYPES:
            continue
        clock = e.get("clock", {})
        out.append({
            "minute": round((clock.get("value") or 0.0) / 60, 1),
            "display": clock.get("displayValue") or MARKER_TYPES[etype],
            "type": etype,
            "team": (e.get("team") or {}).get("displayName"),
            "label": e.get("shortText") or e.get("text") or "",
            "scoring": bool(e.get("scoringPlay")),
        })
    out.sort(key=lambda x: x["minute"])
    return out


def build_momentum(
    commentary: list[dict], home: str | None, away: str | None, duration: int
) -> list[dict]:
    raw_home: dict[int, float] = {}
    raw_away: dict[int, float] = {}

    for entry in commentary:
        play = entry.get("play") or {}
        ptype = play.get("type", {}).get("type")
        weight = ATTACK_WEIGHTS.get(ptype)
        if not weight:
            continue
        team = (play.get("team") or {}).get("displayName")
        clock = play.get("clock") or entry.get("time") or {}
        minute = int((clock.get("value") or 0.0) // 60)
        if team == home:
            raw_home[minute] = raw_home.get(minute, 0.0) + weight
        elif team == away:
            raw_away[minute] = raw_away.get(minute, 0.0) + weight

    def smooth(raw: dict[int, float], m: int) -> float:
        lo, hi = max(0, m - SMOOTH_WINDOW), m + SMOOTH_WINDOW
        vals = [raw.get(i, 0.0) for i in range(lo, hi + 1)]
        return sum(vals) / len(vals)

    # Spans the *full* match (including stoppage time from keyEvents), not
    # just whichever minutes the commentary happened to tag with a weighted
    # play — otherwise the wave looks like it stops early when later minutes
    # genuinely had no shot/corner/offside commentary attached.
    series = []
    for m in range(0, duration + 1):
        h = smooth(raw_home, m)
        a = smooth(raw_away, m)
        series.append({"minute": m, "value": round(h - a, 2)})
    return series


def main() -> int:
    if not RAW_DIR.exists():
        print(f"no raw data found at {RAW_DIR}")
        return 1

    result = {}
    for path in sorted(RAW_DIR.glob("*.json")):
        gid = path.stem
        data = json.loads(path.read_text())
        summary = data.get("summary", {})
        key_events = summary.get("keyEvents") or []
        commentary = summary.get("commentary") or []
        if not key_events:
            continue

        home, away = home_away(summary)
        events = build_events(key_events)
        duration = max(
            [90] +
            [int((e.get("clock", {}).get("value") or 0.0) // 60) for e in key_events]
        )
        momentum = build_momentum(commentary, home, away, duration)

        result[gid] = {
            "home_team": home,
            "away_team": away,
            "events": events,
            "momentum": momentum,
            "duration": duration,
        }

    OUT_FILE.write_text(json.dumps(result, indent=2))
    print(f"wrote {len(result)} match timelines -> {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
