"""Timezone handling and conversion for 1C:Enterprise timestamps."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def convert_one_datetime(dt: datetime, tz_name: str = "Asia/Almaty") -> datetime:
    """Convert 1C infobase timestamp to UTC-aware datetime.

    Critical COM marshalling note:
    pywin32 marshalling for COM VT_DATE attaches tzinfo=datetime.timezone.utc,
    even though the clock value is the civil/local time of the 1C infobase.
    Therefore, any existing tzinfo must be REPLACED with the local timezone,
    and only then converted to UTC via astimezone.
    """
    local_tz = ZoneInfo(tz_name)
    # Replace any pseudo-UTC or attach local timezone to naive datetime
    dt_local = dt.replace(tzinfo=local_tz)
    return dt_local.astimezone(UTC)


def to_one_naive_datetime(dt_utc: datetime, tz_name: str = "Asia/Almaty") -> datetime:
    """Convert UTC-aware datetime to naive local datetime for 1C query parameters.

    1C infobase expects naive local timestamps in parameters (e.g. &WindowStart).
    UTC -> ZoneInfo(tz_name) -> tzinfo=None.
    """
    local_tz = ZoneInfo(tz_name)
    local_dt = dt_utc.astimezone(local_tz)
    return local_dt.replace(tzinfo=None)

