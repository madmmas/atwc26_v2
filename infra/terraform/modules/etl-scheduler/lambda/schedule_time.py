"""UTC kickoff parsing for the ETL scheduler Lambda (keep in sync with atwc26_core.schedule_time)."""

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
