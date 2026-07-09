"""Match-based ETL trigger windows from data/schedule.json."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from schedule_time import parse_kickoff_utc

DEFAULT_MATCH_DURATION_MINUTES = 105
DEFAULT_TRIGGER_OFFSETS_MINUTES = (5, 20, 40)
DEFAULT_CATCHUP_MINUTES = 15


def match_end_utc(kickoff: datetime, *, match_duration_minutes: int) -> datetime:
    return kickoff + timedelta(minutes=match_duration_minutes)


def trigger_at_utc(
    kickoff: datetime,
    *,
    offset_minutes: int,
    match_duration_minutes: int,
) -> datetime:
    return match_end_utc(kickoff, match_duration_minutes=match_duration_minutes) + timedelta(
        minutes=offset_minutes
    )


def trigger_key(game_id: str, offset_minutes: int) -> str:
    return f"{game_id}#+{offset_minutes}"


def load_schedule(payload: str | bytes) -> dict[str, dict[str, Any]]:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("schedule.json must be a JSON object")
    return {str(game_id): game for game_id, game in data.items() if isinstance(game, dict)}


def due_triggers(
    schedule: Mapping[str, Mapping[str, Any]],
    now: datetime,
    *,
    match_duration_minutes: int = DEFAULT_MATCH_DURATION_MINUTES,
    trigger_offsets_minutes: Sequence[int] = DEFAULT_TRIGGER_OFFSETS_MINUTES,
    catchup_minutes: int = DEFAULT_CATCHUP_MINUTES,
) -> list[tuple[str, int, datetime]]:
    """Return (game_id, offset_minutes, trigger_at) for slots that should fire now."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    due: list[tuple[str, int, datetime]] = []
    catchup = timedelta(minutes=catchup_minutes)
    for game_id, game in schedule.items():
        kickoff = parse_kickoff_utc(str(game.get("kickoff_utc") or ""))
        if kickoff is None:
            continue
        end = match_end_utc(kickoff, match_duration_minutes=match_duration_minutes)
        for offset in trigger_offsets_minutes:
            trigger_at = end + timedelta(minutes=int(offset))
            if trigger_at <= now < trigger_at + catchup:
                due.append((str(game_id), int(offset), trigger_at))
    due.sort(key=lambda row: row[2])
    return due


def upcoming_triggers(
    schedule: Mapping[str, Mapping[str, Any]],
    now: datetime,
    *,
    match_duration_minutes: int = DEFAULT_MATCH_DURATION_MINUTES,
    trigger_offsets_minutes: Sequence[int] = DEFAULT_TRIGGER_OFFSETS_MINUTES,
    limit: int = 3,
) -> list[tuple[str, int, datetime]]:
    """Return the next trigger slots after ``now`` (all times UTC)."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    upcoming: list[tuple[str, int, datetime]] = []
    for game_id, game in schedule.items():
        kickoff = parse_kickoff_utc(str(game.get("kickoff_utc") or ""))
        if kickoff is None:
            continue
        end = match_end_utc(kickoff, match_duration_minutes=match_duration_minutes)
        for offset in trigger_offsets_minutes:
            trigger_at = end + timedelta(minutes=int(offset))
            if trigger_at > now:
                upcoming.append((str(game_id), int(offset), trigger_at))
    upcoming.sort(key=lambda row: row[2])
    return upcoming[:limit]
