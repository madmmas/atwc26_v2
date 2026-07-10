"""Tests for match-based ETL scheduler trigger windows."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAMBDA_DIR = ROOT / "infra" / "terraform" / "modules" / "etl-scheduler" / "lambda"
sys.path.insert(0, str(LAMBDA_DIR))

from schedule_triggers import (  # noqa: E402
    DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES,
    DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES,
    DEFAULT_TRIGGER_OFFSETS_MINUTES,
    due_triggers,
    game_done_key,
    is_knockout_round,
    match_end_utc,
    parse_kickoff_utc,
    trigger_at_utc,
    trigger_key,
    trigger_offsets_for_game,
    upcoming_triggers,
)


def test_default_knockout_offsets_are_sixteen_runs_every_fifteen_minutes() -> None:
    assert DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES == tuple(range(0, 16 * 15, 15))
    assert len(DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES) == 16
    assert DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES[-1] == 225
    assert DEFAULT_TRIGGER_OFFSETS_MINUTES == DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES


def test_default_group_stage_offsets_cover_ninety_minutes() -> None:
    assert DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES == (0, 15, 30, 45, 60)


def test_trigger_offsets_for_game_by_round_slug() -> None:
    group = {"round_slug": "group-stage"}
    knockout = {"round_slug": "round-of-16"}
    legacy = {}
    assert trigger_offsets_for_game(group) == DEFAULT_GROUP_STAGE_TRIGGER_OFFSETS_MINUTES
    assert trigger_offsets_for_game(knockout) == DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES
    assert trigger_offsets_for_game(legacy) == DEFAULT_KNOCKOUT_TRIGGER_OFFSETS_MINUTES


def test_is_knockout_round() -> None:
    assert is_knockout_round("group-stage") is False
    assert is_knockout_round("round-of-32") is True
    assert is_knockout_round(None) is True


def test_parse_kickoff_utc_accepts_z_suffix() -> None:
    kickoff = parse_kickoff_utc("2026-07-09T20:00Z")
    assert kickoff == datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)


def test_parse_kickoff_utc_treats_naive_as_utc() -> None:
    kickoff = parse_kickoff_utc("2026-07-09T20:00:00")
    assert kickoff == datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)


def test_parse_kickoff_utc_converts_offset_to_utc() -> None:
    kickoff = parse_kickoff_utc("2026-07-09T16:00:00-04:00")
    assert kickoff == datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)


def test_first_trigger_is_kickoff_plus_match_duration() -> None:
    kickoff = datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)
    end = match_end_utc(kickoff, match_duration_minutes=105)
    assert end == datetime(2026, 7, 9, 21, 45, tzinfo=timezone.utc)
    assert trigger_at_utc(kickoff, offset_minutes=0, match_duration_minutes=105) == end
    assert trigger_at_utc(kickoff, offset_minutes=15, match_duration_minutes=105) == datetime(
        2026, 7, 9, 22, 0, tzinfo=timezone.utc
    )


def test_due_triggers_fires_within_catchup_window() -> None:
    schedule = {
        "760510": {
            "kickoff_utc": "2026-07-09T20:00Z",
            "completed": False,
            "round_slug": "round-of-16",
        }
    }
    now = datetime(2026, 7, 9, 21, 47, tzinfo=timezone.utc)
    due = due_triggers(
        schedule,
        now,
        match_duration_minutes=105,
        knockout_offsets_minutes=(0,),
    )
    assert due == [("760510", 0, datetime(2026, 7, 9, 21, 45, tzinfo=timezone.utc))]


def test_due_triggers_skips_future_slots() -> None:
    schedule = {
        "760510": {
            "kickoff_utc": "2026-07-09T20:00Z",
            "completed": False,
        }
    }
    now = datetime(2026, 7, 9, 20, 30, tzinfo=timezone.utc)
    assert due_triggers(schedule, now) == []


def test_due_triggers_skips_finished_games() -> None:
    schedule = {
        "760510": {
            "kickoff_utc": "2026-07-09T20:00Z",
            "round_slug": "round-of-16",
        }
    }
    now = datetime(2026, 7, 9, 21, 47, tzinfo=timezone.utc)
    due = due_triggers(
        schedule,
        now,
        knockout_offsets_minutes=(0,),
        finished_game_ids={"760510"},
    )
    assert due == []


def test_group_stage_uses_shorter_offset_window() -> None:
    schedule = {
        "760510": {
            "kickoff_utc": "2026-07-09T20:00Z",
            "round_slug": "group-stage",
        }
    }
    # kickoff 20:00 + 105m + 45m = 22:30 (group offset +45)
    now = datetime(2026, 7, 9, 22, 32, tzinfo=timezone.utc)
    due = due_triggers(schedule, now)
    assert due == [("760510", 45, datetime(2026, 7, 9, 22, 30, tzinfo=timezone.utc))]

    # Group stage has no +75m slot; knockout still polls until +225m.
    later = datetime(2026, 7, 9, 23, 2, tzinfo=timezone.utc)
    knockout_schedule = {
        "760510": {
            "kickoff_utc": "2026-07-09T20:00Z",
            "round_slug": "quarterfinals",
        }
    }
    assert due_triggers(schedule, later) == []
    assert due_triggers(knockout_schedule, later) == [
        ("760510", 75, datetime(2026, 7, 9, 23, 0, tzinfo=timezone.utc))
    ]


def test_upcoming_triggers_skips_finished_games() -> None:
    schedule = {
        "760510": {
            "kickoff_utc": "2026-07-09T20:00Z",
            "round_slug": "round-of-16",
        }
    }
    now = datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)
    upcoming = upcoming_triggers(
        schedule,
        now,
        finished_game_ids={"760510"},
    )
    assert upcoming == []


def test_trigger_key_format() -> None:
    assert trigger_key("760510", 15) == "760510#+15"
    assert game_done_key("760510") == "760510#DONE"
