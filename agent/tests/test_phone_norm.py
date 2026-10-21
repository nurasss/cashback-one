"""Tests for agent phone normalization matching backend behavior."""

import pytest

from poscenter_loyalty_agent.phone_norm import normalize_phone


@pytest.mark.parametrize(
    ("raw_phone", "expected"),
    [
        # Standard KZ formats
        ("87001234567", "+77001234567"),
        ("+77001234567", "+77001234567"),
        ("77001234567", "+77001234567"),
        ("8 (701) 999-88-77", "+77019998877"),
        ("+7 (777) 123-45-67", "+77771234567"),
        ("8-705-555-44-33", "+77055554433"),
        # 10-digit national numbers
        ("7012345678", "+77012345678"),
        ("701 234 56 78", "+77012345678"),
        ("(701) 234-56-78", "+77012345678"),
        ("9161234567", "+79161234567"),
        ("+77012345678", "+77012345678"),
        # Empty and None
        (None, None),
        ("", None),
        ("   ", None),
        # Invalid cases -> must return None (safe, no exceptions)
        ("123", None),
        ("87001234567890123456", None),
        ("invalid-phone", None),
        ("+7700+1234567", None),
    ],
)
def test_phone_normalization_against_backend_spec(raw_phone: str | None, expected: str | None) -> None:
    assert normalize_phone(raw_phone) == expected
