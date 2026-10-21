"""Phone number normalization rules matching backend/app/core/phone.py.

Returns normalized E.164 phone string, or None for empty / invalid phones (never raises).
"""

from __future__ import annotations

import re

_ALLOWED_CHARS = re.compile(r"^[\d\s+\-().]+$")
_NON_DIGIT_EXCEPT_PLUS = re.compile(r"[^\d+]")


def normalize_phone(raw_phone: str | None) -> str | None:
    """Normalize phone numbers according to POSCENTER Loyalty rules.

    Kazakhstan / CIS and international phone numbers are normalized to E.164 format.
    Unlike backend version which raises ValueError on invalid input,
    the agent version returns None for invalid or unparseable inputs to prevent
    entire batch rejections by Cloud API.
    """
    if raw_phone is None:
        return None

    stripped = raw_phone.strip()
    if not stripped:
        return None

    # Check for invalid characters like letters
    if not _ALLOWED_CHARS.match(stripped):
        return None

    cleaned = _NON_DIGIT_EXCEPT_PLUS.sub("", stripped)
    if not cleaned:
        return None

    # Handle numbers starting with +
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if not digits.isdigit():
            return None
        if len(digits) == 11 and digits.startswith("7"):
            return f"+{digits}"
        if 10 <= len(digits) <= 15:
            return f"+{digits}"
        return None

    # Only digits remain
    digits = cleaned
    if not digits.isdigit():
        return None

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

    return None
