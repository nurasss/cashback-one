"""Tests for 1C timestamp conversion and timezone normalization."""

from datetime import UTC, datetime

from poscenter_loyalty_agent.one_time import convert_one_datetime, to_one_naive_datetime


def test_convert_one_datetime_pywin32_utc_label() -> None:
    # pywin32 returns 14:00 local time labeled with tzinfo=UTC
    dt_pywin32 = datetime(2026, 10, 10, 14, 0, 0, tzinfo=UTC)
    result = convert_one_datetime(dt_pywin32, tz_name="Asia/Almaty")
    assert result == datetime(2026, 10, 10, 9, 0, 0, tzinfo=UTC)
    assert result.tzinfo == UTC


def test_convert_one_datetime_naive() -> None:
    # Naive datetime from 1C
    dt_naive = datetime(2026, 10, 10, 14, 0, 0)
    result = convert_one_datetime(dt_naive, tz_name="Asia/Almaty")
    assert result == datetime(2026, 10, 10, 9, 0, 0, tzinfo=UTC)


def test_convert_one_datetime_day_boundary() -> None:
    # 02:00 in Almaty (UTC+5) is 21:00 on the previous calendar day in UTC
    dt_early = datetime(2026, 10, 10, 2, 30, 0, tzinfo=UTC)
    result = convert_one_datetime(dt_early, tz_name="Asia/Almaty")
    assert result == datetime(2026, 10, 9, 21, 30, 0, tzinfo=UTC)


def test_to_one_naive_datetime() -> None:
    # Curator requirement: UTC 2026-10-10T07:00:00Z at Asia/Almaty -> naive parameter 12:00:00
    dt_utc = datetime(2026, 10, 10, 7, 0, 0, tzinfo=UTC)
    result = to_one_naive_datetime(dt_utc, tz_name="Asia/Almaty")
    assert result == datetime(2026, 10, 10, 12, 0, 0)
    assert result.tzinfo is None

