"""Pydantic models and fingerprinting for Stage 0 Mapping Artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

VerificationState = Literal["NOT_STARTED", "CANDIDATE", "VERIFIED"]


class ConfigurationIdentity(BaseModel):
    """Identity and version information of the target POSCENTER ONE infobase."""

    model_config = ConfigDict(extra="forbid")

    configuration_name: str = Field(description="Internal name of the 1C configuration")
    configuration_version: str = Field(description="Configuration version string (e.g. 2.3.12.45)")
    platform_version: str = Field(description="1C:Enterprise platform version (e.g. 8.3.24.1342)")


class CardMapping(BaseModel):
    """Verified metadata mapping for loyalty card entity."""

    model_config = ConfigDict(extra="forbid")

    source_object: str = Field(description="Metadata object name (e.g. Catalogs.InformationCards)")
    stable_source_id: str = Field(description="Stable primary key field in 1C (e.g. Ref / UUID)")
    barcode_field: str = Field(description="Field containing 13-digit EAN barcode")
    phone_field: str = Field(description="Field containing customer phone number")
    full_name_field: str = Field(description="Field containing customer full name or NOT_AVAILABLE")
    balance_source: str = Field(description="Register or attribute supplying the current balance")
    blocked_source: str = Field(description="Field or expression indicating blocked / deletion mark")
    updated_at_source: str = Field(description="Timestamp field or version indicating last modification")


class TransactionMapping(BaseModel):
    """Verified metadata mapping for loyalty bonus movements/transactions."""

    model_config = ConfigDict(extra="forbid")

    source_object: str = Field(description="Metadata source (e.g. AccumulationRegisters.BonusPoints)")
    stable_source_id: str = Field(
        description="Deterministic stable immutable expression for Cloud external_id"
    )
    card_relationship: str = Field(description="Dimension or requisite linking movement to card")
    type_field: str = Field(description="Field indicating movement direction or operation kind")
    type_mapping: dict[str, str] = Field(
        description="Explicit dictionary mapping 1C movement types to 'accrual' or 'redemption'"
    )
    amount_field: str = Field(description="Field storing transaction bonus amount")
    balance_after_field: str | None = Field(
        default=None,
        description="Field storing balance after movement, or NOT_AVAILABLE",
    )
    occurred_at_field: str = Field(description="Movement timestamp field")
    receipt_ref_field: str | None = Field(
        default=None, description="Receipt / document reference or null"
    )
    store_field: str | None = Field(default=None, description="Store / retail point reference or null")


class CursorStrategy(BaseModel):
    """Deterministic pagination and incremental checkpoint strategy."""

    model_config = ConfigDict(extra="forbid")

    cards_cursor_strategy: str = Field(description="Strategy name (e.g. keyset_timestamp_ref)")
    cards_ordering_fields: list[str] = Field(description="Fields determining ordering")
    cards_tie_breaker: str = Field(description="Deterministic tie-breaker field")
    transactions_cursor_strategy: str = Field(
        description="Strategy name (e.g. keyset_period_recorder)"
    )
    transactions_ordering_fields: list[str] = Field(description="Fields determining ordering")
    transactions_tie_breaker: str = Field(description="Deterministic tie-breaker field")


class EvidenceAggregates(BaseModel):
    """Aggregated, non-PII evidence proving data suitability from pilot run."""

    model_config = ConfigDict(extra="forbid")

    barcode_aggregate: dict[str, int] = Field(
        description="Aggregated barcode validation counts (sample_size, valid_13_digit, etc.)"
    )
    phone_aggregate: dict[str, int] = Field(
        description="Aggregated phone counts (null_count, normalizable_count, invalid_count)"
    )
    name_aggregate: dict[str, Any] = Field(
        description="Customer name inspection metadata (field_exists, type, null_count)"
    )
    balance_aggregate: dict[str, Any] = Field(
        description="Balance precision and range metadata (numeric_type, precision, allows_negative)"
    )


class Stage0Mapping(BaseModel):
    """Complete Stage 0 Discovery Mapping Artifact."""

    model_config = ConfigDict(extra="forbid")

    mapping_version: str = Field(default="1.0.0")
    one_configuration_identity: ConfigurationIdentity
    discovered_at: str = Field(description="ISO 8601 UTC timestamp of discovery")
    cards: CardMapping
    transactions: TransactionMapping
    cursor_strategy: CursorStrategy
    evidence: EvidenceAggregates
    mapping_sha256: str = Field(description="SHA-256 canonical hash of the mapping definition")


def calculate_mapping_fingerprint(data: dict[str, Any]) -> str:
    """Calculate canonical SHA-256 fingerprint for a mapping dictionary.

    The 'mapping_sha256' field itself is excluded during calculation.
    """
    clean_copy = {k: v for k, v in data.items() if k != "mapping_sha256"}
    canonical_json = json.dumps(clean_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
