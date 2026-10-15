import pytest

from app.core.phone import normalize_phone


def test_phone_normalization_standard_kz() -> None:
    assert normalize_phone("87001234567") == "+77001234567"
    assert normalize_phone("+77001234567") == "+77001234567"
    assert normalize_phone("77001234567") == "+77001234567"
    assert normalize_phone("8 (701) 999-88-77") == "+77019998877"
    assert normalize_phone("+7 (777) 123-45-67") == "+77771234567"
    assert normalize_phone("8-705-555-44-33") == "+77055554433"


def test_phone_normalization_ten_digit_national_number() -> None:
    """10-digit numbers without the 8/7 trunk prefix are KZ/RU national numbers."""
    assert normalize_phone("7012345678") == "+77012345678"
    assert normalize_phone("701 234 56 78") == "+77012345678"
    assert normalize_phone("(701) 234-56-78") == "+77012345678"
    assert normalize_phone("9161234567") == "+79161234567"
    # Explicit international format is left untouched
    assert normalize_phone("+77012345678") == "+77012345678"


def test_phone_normalization_empty_and_none() -> None:
    assert normalize_phone(None) is None
    assert normalize_phone("") is None
    assert normalize_phone("   ") is None


def test_phone_normalization_invalid_cases() -> None:
    with pytest.raises(ValueError):
        normalize_phone("123")  # too short
    with pytest.raises(ValueError):
        normalize_phone("87001234567890123456")  # too long
    with pytest.raises(ValueError):
        normalize_phone("invalid-phone")
    with pytest.raises(ValueError):
        normalize_phone("+7700+1234567")  # misplaced plus
