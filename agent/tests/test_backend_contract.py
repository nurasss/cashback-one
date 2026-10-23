"""Contract compatibility test verifying agent models against backend schemas."""

import json
from datetime import UTC, datetime
from decimal import Decimal

from poscenter_loyalty_agent.models import (
    CardsSyncPayload,
    CardSyncItem,
    HeartbeatPayload,
    TransactionsSyncPayload,
    TransactionSyncItem,
)


def test_cards_payload_matches_backend_contract() -> None:
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    card = CardSyncItem(
        barcode="2000000000001",
        phone="+77011234567",
        full_name="Assan Assanov",
        balance=Decimal("1234.5600"),
        is_blocked=False,
        updated_at=now,
    )
    payload = CardsSyncPayload(cards=[card])
    dumped = json.loads(payload.model_dump_json())

    assert "cards" in dumped
    assert len(dumped["cards"]) == 1
    c = dumped["cards"][0]
    assert c["barcode"] == "2000000000001"
    assert c["phone"] == "+77011234567"
    assert c["balance"] == "1234.56" or float(c["balance"]) == 1234.56
    assert c["is_blocked"] is False


def test_transactions_payload_matches_backend_contract() -> None:
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    tx = TransactionSyncItem(
        external_id="1C-DOC-12345",
        barcode="2000000000001",
        type="accrual",
        amount=Decimal("100.00"),
        balance_after=Decimal("500.00"),
        occurred_at=now,
        receipt_ref="REC-999",
        store="Store #1",
    )
    payload = TransactionsSyncPayload(transactions=[tx])
    dumped = json.loads(payload.model_dump_json())

    assert "transactions" in dumped
    t = dumped["transactions"][0]
    assert t["external_id"] == "1C-DOC-12345"
    assert t["barcode"] == "2000000000001"
    assert t["type"] == "accrual"
    assert t["receipt_ref"] == "REC-999"


def test_heartbeat_payload_matches_backend_contract() -> None:
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    hb = HeartbeatPayload(
        version="0.1.0",
        last_successful_sync_at=now,
        error="Network timeout connecting to 1C infobase",
    )
    dumped = json.loads(hb.model_dump_json())
    assert dumped["version"] == "0.1.0"
    assert dumped["error"] == "Network timeout connecting to 1C infobase"


def test_timezone_aware_validation() -> None:
    import pytest
    from pydantic import ValidationError

    naive_dt = datetime(2026, 9, 29, 12, 0, 0)  # No tzinfo

    # CardSyncItem rejects naive
    with pytest.raises(ValidationError, match="timezone-aware"):
        CardSyncItem(
            barcode="2000000000001",
            balance=Decimal("100"),
            updated_at=naive_dt,
        )

    # TransactionSyncItem rejects naive
    with pytest.raises(ValidationError, match="timezone-aware"):
        TransactionSyncItem(
            external_id="tx-1",
            barcode="2000000000001",
            type="accrual",
            amount=Decimal("10"),
            balance_after=Decimal("20"),
            occurred_at=naive_dt,
        )

    # HeartbeatPayload rejects naive
    with pytest.raises(ValidationError, match="timezone-aware"):
        HeartbeatPayload(last_successful_sync_at=naive_dt)

    # Aware datetimes are accepted
    aware_dt = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    card = CardSyncItem(
        barcode="2000000000001",
        balance=Decimal("100"),
        updated_at=aware_dt,
    )
    assert card.updated_at.tzinfo is not None


def test_agent_sync_routes_match_backend_contract() -> None:
    """Explicitly verify expected Cloud API route contracts without importing backend."""
    from poscenter_loyalty_agent.cloud_client import (
        CARDS_SYNC_PATH,
        HEARTBEAT_PATH,
        TRANSACTIONS_SYNC_PATH,
    )

    assert CARDS_SYNC_PATH == "/agent/sync/cards"
    assert TRANSACTIONS_SYNC_PATH == "/agent/sync/transactions"
    assert HEARTBEAT_PATH == "/agent/heartbeat"


def test_barcode_validation_contract() -> None:
    import pytest
    from pydantic import ValidationError

    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)

    # Valid barcodes: 4, 11, 13 digits, leading zeroes preserved
    valid_barcodes = ["0001", "77011234567", "0000000000001", "1234567890123"]
    for bc in valid_barcodes:
        card = CardSyncItem(barcode=bc, balance=Decimal("0"), updated_at=now)
        assert card.barcode == bc
        tx = TransactionSyncItem(
            external_id="tx-1",
            barcode=bc,
            type="accrual",
            amount=Decimal("10"),
            balance_after=Decimal("10"),
            occurred_at=now,
        )
        assert tx.barcode == bc

    # Invalid barcodes: 3, 14 digits, letters, spaces
    invalid_barcodes = ["123", "12345678901234", "12345A", " 123456 ", "", "abcdef"]
    for bc in invalid_barcodes:
        with pytest.raises(ValidationError):
            CardSyncItem(barcode=bc, balance=Decimal("0"), updated_at=now)
        with pytest.raises(ValidationError):
            TransactionSyncItem(
                external_id="tx-1",
                barcode=bc,
                type="accrual",
                amount=Decimal("10"),
                balance_after=Decimal("10"),
                occurred_at=now,
            )

