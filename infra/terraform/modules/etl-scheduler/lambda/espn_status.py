"""Lightweight ESPN completion probe for the ETL scheduler Lambda."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

SUMMARY_URL = (
    "https://site.web.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={game_id}"
)


def match_completed(
    game_id: str,
    *,
    league: str,
    schedule_completed: bool = False,
    timeout_seconds: int = 15,
) -> bool:
    """Return True when ESPN reports the match as completed.

    On network/API errors, fall back to ``schedule_completed`` from schedule.json.
    """
    url = SUMMARY_URL.format(league=league, game_id=game_id)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "atwc26-etl-scheduler",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"ESPN probe failed for {game_id}: {exc}; using schedule completed={schedule_completed}")
        return schedule_completed

    header = payload.get("header") or {}
    competitions = header.get("competitions") or payload.get("competitions") or []
    if not competitions:
        return schedule_completed
    comp = competitions[0] if isinstance(competitions[0], dict) else {}
    status = (comp.get("status") or {}).get("type") or {}
    return bool(status.get("completed"))
