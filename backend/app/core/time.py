from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return current UTC datetime with timezone awareness."""
    return datetime.now(UTC)
