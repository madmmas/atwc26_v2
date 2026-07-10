"""Match-based ETL trigger windows from data/schedule.json."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from schedule_time import parse_kickoff_utc

DEFAULT_MATCH_DURATION_MINUTES = 105
DEFAULT_TRIGGER_COUNT = 16
DEFAULT_TRIGGER_INTERVAL_MINUTES = 15
DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES = tuple(
    i * DEFAULT_TRIGGER_INTERVAL_MINUTES for i in range(DEFAULT_TRIGGER_COUNT)
)
# Group-stage matches rarely need ET/penalties — shorter poll window after estimated end.
DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES = (0, 15, 30, 45, 60)
GROUP_STAGE_ROUND_SLUG = "group-stage"
DEFAULT_CATCHUP_MINUTES = 15

# Back-compat alias used by existing tests and env defaults.
DEFAULT_TRIGGER_OFFSETS_MINUTES = DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES


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


def game_done_key(game_id: str) -> str:
    return f"{game_id}#DONE"


def is_knockout_round(round_slug: str | None) -> bool:
    """Return True for knockout rounds and legacy schedule rows without round_slug."""
    if not round_slug:
        return True
    return round_slug != GROUP_STAGE_ROUND_SLUG


def trigger_offsets_for_game(
    game: Mapping[str, Any],
    *,
    group_offsets: Sequence[int] = DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES,
    knockout_offsets: Sequence[int] = DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES,
) -> Sequence[int]:
    slug = str(game.get("round_slug") or "")
    if slug == GROUP_STAGE_ROUND_SLUG:
        return group_offsets
    return knockout_offsets


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
    group_offsets_minutes: Sequence[int] = DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES,
    knockout_offsets_minutes: Sequence[int] = DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES,
    catchup_minutes: int = DEFAULT_CATCHUP_MINUTES,
    finished_game_ids: set[str] | frozenset[str] | None = None,
) -> list[tuple[str, int, datetime]]:
    """Return (game_id, offset_minutes, trigger_at) for slots that should fire now."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    finished = finished_game_ids or frozenset()
    due: list[tuple[str, int, datetime]] = []
    catchup = timedelta(minutes=catchup_minutes)
    for game_id, game in schedule.items():
        if str(game_id) in finished:
            continue
        kickoff = parse_kickoff_utc(str(game.get("kickoff_utc") or ""))
        if kickoff is None:
            continue
        offsets = trigger_offsets_for_game(
            game,
            group_offsets=group_offsets_minutes,
            knockout_offsets=knockout_offsets_minutes,
        )
        end = match_end_utc(kickoff, match_duration_minutes=match_duration_minutes)
        for offset in offsets:
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
    group_offsets_minutes: Sequence[int] = DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES,
    knockout_offsets_minutes: Sequence[int] = DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES,
    limit: int = 3,
    finished_game_ids: set[str] | frozenset[str] | None = None,
) -> list[tuple[str, int, datetime]]:
    """Return the next trigger slots after ``now`` (all times UTC)."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    finished = finished_game_ids or frozenset()
    upcoming: list[tuple[str, int, datetime]] = []
    for game_id, game in schedule.items():
        if str(game_id) in finished:
            continue
        kickoff = parse_kickoff_utc(str(game.get("kickoff_utc") or ""))
        if kickoff is None:
            continue
        offsets = trigger_offsets_for_game(
            game,
            group_offsets=group_offsets_minutes,
            knockout_offsets=knockout_offsets_minutes,
        )
        end = match_end_utc(kickoff, match_duration_minutes=match_duration_minutes)
        for offset in offsets:
            trigger_at = end + timedelta(minutes=int(offset))
            if trigger_at > now:
                upcoming.append((str(game_id), int(offset), trigger_at))
    upcoming.sort(key=lambda row: row[2])
    return upcoming[:limit]
