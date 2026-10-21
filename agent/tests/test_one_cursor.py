"""Tests for one_cursor token encoding, decoding, corrupted handling, and PII absence."""

import re

import pytest

from poscenter_loyalty_agent.one_cursor import (
    CardsDoneCursor,
    CardsPageCursor,
    TxDoneCursor,
    TxPageCursor,
    decode_cards_cursor,
    decode_tx_cursor,
    encode_cards_done_cursor,
    encode_cards_page_cursor,
    encode_tx_done_cursor,
    encode_tx_page_cursor,
)


def test_cards_page_cursor_roundtrip() -> None:
    original = CardsPageCursor(
        session_id="a1b2c3d4",
        page=2,
        last_card_ref_uuid="e8a9f012-3456-7890-abcd-ef0123456789",
        total_found=650,
    )
    token = encode_cards_page_cursor(original)
    assert token.startswith("c1_")
    decoded = decode_cards_cursor(token)
    assert decoded == original


def test_cards_done_cursor_roundtrip() -> None:
    original = CardsDoneCursor(
        session_id="a1b2c3d4",
        total_synced=650,
        completed_at="2026-10-19T10:00:00Z",
    )
    token = encode_cards_done_cursor(original)
    assert token.startswith("c1_")
    decoded = decode_cards_cursor(token)
    assert decoded == original


def test_tx_page_cursor_roundtrip() -> None:
    original = TxPageCursor(
        window_start="2026-10-16T00:00:00Z",
        window_end="2026-10-19T10:00:00Z",
        last_period="2026-10-18T14:22:10Z",
        last_doc_uuid="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        last_line=42,
    )
    token = encode_tx_page_cursor(original)
    assert token.startswith("t1_")
    decoded = decode_tx_cursor(token)
    assert decoded == original


def test_tx_done_cursor_roundtrip() -> None:
    original = TxDoneCursor(
        hw_period="2026-10-19T10:00:00Z",
        hw_doc_uuid="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        hw_line=10,
        completed_at="2026-10-19T10:05:00Z",
    )
    token = encode_tx_done_cursor(original)
    assert token.startswith("t1_")
    decoded = decode_tx_cursor(token)
    assert decoded == original


def test_corrupted_cursor_handling(caplog: pytest.LogCaptureFixture) -> None:
    # 1. Non-base64 garbage
    assert decode_cards_cursor("c1_NOT_VALID_BASE64!@#$") is None
    assert "CORRUPTED_CURSOR" in caplog.text
    assert "NOT_VALID_BASE64" not in caplog.text  # Token content must NEVER be logged!

    # 2. Wrong prefix
    assert decode_tx_cursor("c1_eyJ2IjoxfQ") is None

    # 3. Tampered checksum
    valid_tx = TxDoneCursor(
        hw_period="2026-10-19T10:00:00Z",
        hw_doc_uuid="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        hw_line=1,
        completed_at="2026-10-19T10:05:00Z",
    )
    token = encode_tx_done_cursor(valid_tx)
    # Mutate a character in base64 payload
    tampered = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1:]
    assert decode_tx_cursor(tampered) is None


def test_zero_pii_in_cursor_tokens() -> None:
    """Verify that decoded token contents never contain phone numbers, barcodes, or names."""
    phone = "+77011234567"
    raw_digits = "77011234567"
    name = "Иван Иванов"

    c_token = encode_cards_page_cursor(
        CardsPageCursor(
            session_id="a1b2c3d4",
            page=1,
            last_card_ref_uuid="e8a9f012-3456-7890-abcd-ef0123456789",
            total_found=10,
        )
    )
    t_token = encode_tx_page_cursor(
        TxPageCursor(
            window_start="2026-10-16T00:00:00Z",
            window_end="2026-10-19T10:00:00Z",
            last_period="2026-10-18T14:22:10Z",
            last_doc_uuid="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
            last_line=1,
        )
    )

    for token in (c_token, t_token):
        assert phone not in token
        assert raw_digits not in token
        assert name not in token
        # Check no 11-digit phone sequence inside token
        assert not re.search(r"7\d{10}", token)
