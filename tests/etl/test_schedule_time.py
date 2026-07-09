"""Tests for UTC schedule timestamp helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from atwc26_core.schedule_time import format_kickoff_utc, parse_kickoff_utc


def test_format_kickoff_utc_normalizes_z() -> None:
    assert format_kickoff_utc("2026-07-09T20:00Z") == "2026-07-09T20:00:00Z"


def test_format_kickoff_utc_converts_offset() -> None:
    assert format_kickoff_utc("2026-07-09T16:00:00-04:00") == "2026-07-09T20:00:00Z"


def test_parse_kickoff_utc_from_datetime() -> None:
    dt = datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)
    assert parse_kickoff_utc(format_kickoff_utc(dt)) == dt
