from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return current UTC datetime with timezone awareness."""
    return datetime.now(UTC)


def as_utc(dt: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
