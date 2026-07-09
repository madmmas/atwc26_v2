"""UTC kickoff parsing and normalization for schedule.json."""

from __future__ import annotations

from datetime import datetime, timezone


def parse_kickoff_utc(value: str | None) -> datetime | None:
    """Parse kickoff timestamps; naive values are treated as UTC."""
    if not value:
        return None
    try:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def format_kickoff_utc(value: str | datetime | None) -> str | None:
    """Return canonical UTC ISO-8601 with Z suffix, or None when invalid."""
    if isinstance(value, datetime):
        dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    else:
        dt = parse_kickoff_utc(str(value or ""))
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
