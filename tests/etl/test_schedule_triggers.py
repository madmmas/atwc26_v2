"""Tests for match-based ETL scheduler trigger windows."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAMBDA_DIR = ROOT / "infra" / "terraform" / "modules" / "etl-scheduler" / "lambda"
sys.path.insert(0, str(LAMBDA_DIR))

from schedule_triggers import (  # noqa: E402
    due_triggers,
    match_end_utc,
    parse_kickoff_utc,
    trigger_at_utc,
    trigger_key,
)


def test_parse_kickoff_utc_accepts_z_suffix() -> None:
    kickoff = parse_kickoff_utc("2026-07-09T20:00Z")
    assert kickoff == datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)


def test_parse_kickoff_utc_treats_naive_as_utc() -> None:
    kickoff = parse_kickoff_utc("2026-07-09T20:00:00")
    assert kickoff == datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)


def test_parse_kickoff_utc_converts_offset_to_utc() -> None:
    kickoff = parse_kickoff_utc("2026-07-09T16:00:00-04:00")
    assert kickoff == datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)


def test_trigger_at_is_end_plus_offset() -> None:
    kickoff = datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)
    end = match_end_utc(kickoff, match_duration_minutes=105)
    assert end == datetime(2026, 7, 9, 21, 45, tzinfo=timezone.utc)
    assert trigger_at_utc(kickoff, offset_minutes=5, match_duration_minutes=105) == datetime(
        2026, 7, 9, 21, 50, tzinfo=timezone.utc
    )


def test_due_triggers_fires_within_catchup_window() -> None:
    schedule = {
        "760510": {
            "kickoff_utc": "2026-07-09T20:00Z",
            "completed": False,
        }
    }
    # kickoff 20:00 + 105m end = 21:45; +5m trigger = 21:50
    now = datetime(2026, 7, 9, 21, 52, tzinfo=timezone.utc)
    due = due_triggers(schedule, now, match_duration_minutes=105, trigger_offsets_minutes=(5,))
    assert due == [("760510", 5, datetime(2026, 7, 9, 21, 50, tzinfo=timezone.utc))]


def test_due_triggers_skips_future_slots() -> None:
    schedule = {
        "760510": {
            "kickoff_utc": "2026-07-09T20:00Z",
            "completed": False,
        }
    }
    now = datetime(2026, 7, 9, 20, 30, tzinfo=timezone.utc)
    assert due_triggers(schedule, now) == []


def test_trigger_key_format() -> None:
    assert trigger_key("760510", 20) == "760510#+20"
