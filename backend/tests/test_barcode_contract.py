"""Unit tests verifying the 4-to-13 digit card barcode contract across all schemas."""
from datetime import UTC, datetime
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.admin import CardSearchRequest
from app.schemas.agent_sync import CardSyncItem, TransactionSyncItem
from app.schemas.common import BARCODE_ERROR_MSG, BARCODE_REGEX
from app.schemas.pos import RedemptionRequest
from app.schemas.wallet import BindCardRequest


def test_barcode_contract_valid_lengths_and_leading_zeros() -> None:
    valid_barcodes = [
        "0001",  # 4 digits with leading zeros (min boundary)
        "1234",  # 4 digits without leading zero
        "012345",  # 6 digits with leading zero
        "00012345678",  # 11 digits with leading zeros
        "12345678901",  # 11 digits
        "0123456789012",  # 13 digits with leading zero (legacy standard)
        "1234567890123",  # 13 digits max boundary
    ]

    now = datetime.now(UTC)
    for code in valid_barcodes:
        # 1. BindCardRequest
        bind_req = BindCardRequest(barcode=code)
        assert bind_req.barcode == code
        assert isinstance(bind_req.barcode, str)
        if code.startswith("0"):
            assert bind_req.barcode.startswith("0")

        # 2. CardSearchRequest
        search_req = CardSearchRequest(barcode=f"  {code}  ")
        assert search_req.barcode == code
        assert isinstance(search_req.barcode, str)

        # 3. CardSyncItem
        sync_item = CardSyncItem(
            barcode=code,
            balance=Decimal("100.0000"),
            updated_at=now,
        )
        assert sync_item.barcode == code
        assert isinstance(sync_item.barcode, str)

        # 4. TransactionSyncItem
        tx_item = TransactionSyncItem(
            external_id="ext-1",
            barcode=code,
            type="accrual",
            amount=Decimal("10.0000"),
            balance_after=Decimal("110.0000"),
            occurred_at=now,
        )
        assert tx_item.barcode == code
        assert isinstance(tx_item.barcode, str)

        # 5. RedemptionRequest
        redempt_req = RedemptionRequest(barcode=code, amount=Decimal("10.0000"))
        assert redempt_req.barcode == code
        assert isinstance(redempt_req.barcode, str)


@pytest.mark.parametrize(
    "invalid_code",
    [
        "123",  # 3 digits (too short)
        "012",  # 3 digits with leading zero
        "12345678901234",  # 14 digits (too long)
        "01234567890123",  # 14 digits with leading zero
        "1234567890123456",  # 16 digits (far too long)
        "12345a",  # contains letter
        "01234b678901",  # contains letter
        "123 456",  # internal space
        "012345 678901",  # internal space
        "",  # empty
        "-123456",  # negative sign
    ],
)
def test_barcode_contract_invalid_codes_rejected(invalid_code: str) -> None:
    now = datetime.now(UTC)

    # 1. BindCardRequest
    with pytest.raises(ValidationError) as exc_bind:
        BindCardRequest(barcode=invalid_code)
    assert BARCODE_ERROR_MSG in str(exc_bind.value)

    # 2. CardSearchRequest (unless empty, which is rejected by require_filter or length)
    if invalid_code:
        with pytest.raises(ValidationError) as exc_search:
            CardSearchRequest(barcode=invalid_code)
        assert BARCODE_ERROR_MSG in str(exc_search.value)

    # 3. CardSyncItem
    with pytest.raises(ValidationError):
        CardSyncItem(
            barcode=invalid_code,
            balance=Decimal("10.0000"),
            updated_at=now,
        )

    # 4. TransactionSyncItem
    with pytest.raises(ValidationError):
        TransactionSyncItem(
            external_id="ext-1",
            barcode=invalid_code,
            type="accrual",
            amount=Decimal("10.0000"),
            balance_after=Decimal("20.0000"),
            occurred_at=now,
        )

    # 5. RedemptionRequest
    with pytest.raises(ValidationError):
        RedemptionRequest(barcode=invalid_code, amount=Decimal("10.0000"))
