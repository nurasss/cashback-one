"""Opaque, PII-free cursor token encoding and decoding for 1C streams."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)

CARDS_PREFIX = "c1_"
TRANSACTIONS_PREFIX = "t1_"


class CursorError(Exception):
    """Base error for cursor token operations."""


class CorruptedCursorError(CursorError):
    """Raised when a cursor token is corrupted or malformed."""


@dataclass(frozen=True)
class CardsPageCursor:
    session_id: str
    page: int
    last_card_ref_uuid: str
    total_found: int


@dataclass(frozen=True)
class CardsDoneCursor:
    session_id: str
    total_synced: int
    completed_at: str


@dataclass(frozen=True)
class TxPageCursor:
    window_start: str
    window_end: str
    last_period: str
    last_doc_uuid: str
    last_line: int


@dataclass(frozen=True)
class TxDoneCursor:
    hw_period: str
    hw_doc_uuid: str
    hw_line: int
    completed_at: str


def _compute_checksum(payload_dict: dict[str, Any]) -> str:
    clean = {k: v for k, v in payload_dict.items() if k != "cs"}
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]


def _encode_token(prefix: str, payload_dict: dict[str, Any]) -> str:
    payload_dict["cs"] = _compute_checksum(payload_dict)
    raw = json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{prefix}{b64}"


def _decode_token(prefix: str, token: str) -> dict[str, Any]:
    if not token.startswith(prefix):
        raise CorruptedCursorError("Prefix mismatch")
    body = token[len(prefix) :]
    padding = len(body) % 4
    if padding:
        body += "=" * (4 - padding)
    try:
        raw = base64.urlsafe_b64decode(body.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CorruptedCursorError("Base64/JSON decode failed") from exc

    if not isinstance(data, dict) or "cs" not in data:
        raise CorruptedCursorError("Missing checksum in cursor payload")

    expected_cs = _compute_checksum(data)
    if data["cs"] != expected_cs:
        raise CorruptedCursorError("Checksum mismatch in cursor token")

    return data


# --- Cards Cursor API ---


def encode_cards_page_cursor(cursor: CardsPageCursor) -> str:
    payload = {"v": 1, "k": "cards_page", **asdict(cursor)}
    return _encode_token(CARDS_PREFIX, payload)


def encode_cards_done_cursor(cursor: CardsDoneCursor) -> str:
    payload = {"v": 1, "k": "cards_done", **asdict(cursor)}
    return _encode_token(CARDS_PREFIX, payload)


def decode_cards_cursor(token: str | None) -> CardsPageCursor | CardsDoneCursor | None:
    if not token:
        return None
    try:
        data = _decode_token(CARDS_PREFIX, token)
        kind = data.get("k")
        if kind == "cards_page":
            return CardsPageCursor(
                session_id=str(data["session_id"]),
                page=int(data["page"]),
                last_card_ref_uuid=str(data["last_card_ref_uuid"]),
                total_found=int(data["total_found"]),
            )
        if kind == "cards_done":
            return CardsDoneCursor(
                session_id=str(data["session_id"]),
                total_synced=int(data["total_synced"]),
                completed_at=str(data["completed_at"]),
            )
        raise CorruptedCursorError(f"Unknown cards cursor kind: {kind}")
    except Exception:
        # Crucial safety: do NOT log token contents (could theoretically contain tainted input)
        logger.warning("CORRUPTED_CURSOR: Received malformed cards cursor token. Resetting to None.")
        return None


# --- Transactions Cursor API ---


def encode_tx_page_cursor(cursor: TxPageCursor) -> str:
    payload = {"v": 1, "k": "tx_page", **asdict(cursor)}
    return _encode_token(TRANSACTIONS_PREFIX, payload)


def encode_tx_done_cursor(cursor: TxDoneCursor) -> str:
    payload = {"v": 1, "k": "tx_done", **asdict(cursor)}
    return _encode_token(TRANSACTIONS_PREFIX, payload)


def decode_tx_cursor(token: str | None) -> TxPageCursor | TxDoneCursor | None:
    if not token:
        return None
    try:
        data = _decode_token(TRANSACTIONS_PREFIX, token)
        kind = data.get("k")
        if kind == "tx_page":
            return TxPageCursor(
                window_start=str(data["window_start"]),
                window_end=str(data["window_end"]),
                last_period=str(data["last_period"]),
                last_doc_uuid=str(data["last_doc_uuid"]),
                last_line=int(data["last_line"]),
            )
        if kind == "tx_done":
            return TxDoneCursor(
                hw_period=str(data["hw_period"]),
                hw_doc_uuid=str(data["hw_doc_uuid"]),
                hw_line=int(data["hw_line"]),
                completed_at=str(data["completed_at"]),
            )
        raise CorruptedCursorError(f"Unknown tx cursor kind: {kind}")
    except Exception:
        logger.warning("CORRUPTED_CURSOR: Received malformed transactions cursor token. Resetting to None.")
        return None
