import re

_ALLOWED_CHARS = re.compile(r"^[\d\s+\-().]+$")
_NON_DIGIT_EXCEPT_PLUS = re.compile(r"[^\d+]")


def normalize_phone(raw_phone: str | None) -> str | None:
    """Normalize Kazakhstan / CIS and international phone numbers to E.164 format.

    Examples:
        '87001234567' -> '+77001234567'
        '+77001234567' -> '+77001234567'
        '77001234567' -> '+77001234567'
        '8 (701) 999-88-77' -> '+77019998877'
        '7019998877' -> '+77019998877'  (10-digit national number without trunk prefix)
        None -> None
        '' -> None

    Raises:
        ValueError: If phone string is malformed, contains invalid characters, or invalid length.
    """
    if raw_phone is None:
        return None

    stripped = raw_phone.strip()
    if not stripped:
        return None

    # Check for invalid characters like letters
    if not _ALLOWED_CHARS.match(stripped):
        raise ValueError(f"Invalid characters in phone number: '{raw_phone}'")

    cleaned = _NON_DIGIT_EXCEPT_PLUS.sub("", stripped)
    if not cleaned:
        raise ValueError(f"Phone number contains no digits: '{raw_phone}'")

    # Handle numbers starting with +
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if not digits.isdigit():
            raise ValueError(f"Invalid phone number: '{raw_phone}' contains misplaced '+'")
        if len(digits) == 11 and digits.startswith("7"):
            return f"+{digits}"
        if 10 <= len(digits) <= 15:
            return f"+{digits}"
        raise ValueError(f"Invalid phone number length in E.164: '{raw_phone}'")

    # Only digits remain
    digits = cleaned
    if not digits.isdigit():
        raise ValueError(f"Invalid phone number format: '{raw_phone}'")

    # Kazakhstan standard forms: 8700..., 7700...
    if len(digits) == 11:
        if digits.startswith("87"):
            return f"+7{digits[1:]}"
        if digits.startswith("7"):
            return f"+{digits}"
        if digits.startswith("8"):
            return f"+7{digits[1:]}"

    # Kazakhstan / Russia national number entered without 8/7 trunk prefix: 701 999 88 77
    if len(digits) == 10:
        return f"+7{digits}"

    if 11 <= len(digits) <= 15:
        return f"+{digits}"

    raise ValueError(f"Invalid phone number format or length: '{raw_phone}'")
