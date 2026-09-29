"""Pydantic models and fingerprinting for Stage 0 Mapping Artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

VerificationState = Literal["NOT_STARTED", "CANDIDATE", "VERIFIED"]
ArtifactKind = Literal["synthetic_example", "real_discovery"]

T = TypeVar("T")


class MappingValue(BaseModel, Generic[T]):
    """Wrapper holding a mapped value, its verification state, and empirical evidence."""

    model_config = ConfigDict(extra="forbid")

    value: T
    state: VerificationState = "NOT_STARTED"
    evidence: list[str] = Field(default_factory=list)


class ConfigurationIdentity(BaseModel):
    """Identity and version information of the target POSCENTER ONE infobase."""

    model_config = ConfigDict(extra="forbid")

    configuration_name: str = Field(description="Internal name of the 1C configuration")
    configuration_version: str = Field(description="Configuration version string (e.g. 2.3.12.45)")
    platform_major: str = Field(default="8.3", description="Target 1C platform major family")
    platform_version: str = Field(
        default="NOT_AVAILABLE",
        description="Exact 1C:Enterprise platform version if verified, otherwise NOT_AVAILABLE",
    )
    platform_version_state: VerificationState = Field(
        default="NOT_STARTED",
        description="Verification state of platform version (VERIFIED only if exact build discovered)",
    )


class CardMapping(BaseModel):
    """Verified metadata mapping for loyalty card entity."""

    model_config = ConfigDict(extra="forbid")

    source_object: MappingValue[str] = Field(
        description="Exact metadata object identifier discovered from the pilot configuration"
    )
    stable_source_id: MappingValue[str] = Field(
        description="Single immutable identifier or verified deterministic composite identity verified on the pilot configuration"
    )
    barcode_field: MappingValue[str] = Field(
        description="Field containing 13-digit loyalty-card barcode string"
    )
    phone_field: MappingValue[str] = Field(description="Field containing customer phone number")
    full_name_field: MappingValue[str] = Field(
        default_factory=lambda: MappingValue[str](value="NOT_AVAILABLE", state="NOT_STARTED"),
        description="Field containing customer full name or NOT_AVAILABLE",
    )
    balance_source: MappingValue[str] = Field(
        description="Exact verified source or derivation rule for the current loyalty balance"
    )
    blocked_source: MappingValue[str] = Field(
        description="Exact verified source or deterministic rule used to derive Cloud is_blocked"
    )
    updated_at_source: MappingValue[str] = Field(
        description="Verified source or deterministic versioning rule used to derive Card.updated_at semantics"
    )


class TransactionMapping(BaseModel):
    """Verified mapping for loyalty transaction/movement data."""

    model_config = ConfigDict(extra="forbid")

    source_object: MappingValue[str] = Field(
        description="Exact metadata source or deterministic read model containing loyalty movements"
    )
    stable_source_id: MappingValue[str] = Field(
        description="Single immutable identifier or verified deterministic composite identity for Cloud external_id"
    )
    card_relationship: MappingValue[str] = Field(
        description="Verified source or deterministic relationship used to associate a movement with the loyalty card"
    )
    type_field: MappingValue[str] = Field(
        description="Verified source or deterministic rule exposing the source movement semantics required for Cloud type mapping"
    )
    type_mapping: MappingValue[dict[str, str]] = Field(
        description="Verified deterministic mapping from source movement semantics to the canonical Cloud transaction type string"
    )
    amount_field: MappingValue[str] = Field(
        description="Verified source or deterministic derivation rule for the Cloud transaction amount"
    )
    occurred_at_field: MappingValue[str] = Field(
        description="Verified source or deterministic rule used to derive the Cloud occurred_at timestamp"
    )
    balance_after_field: MappingValue[str | None] = Field(
        default_factory=lambda: MappingValue[str | None](value=None, state="NOT_STARTED"),
        description="Optional verified source or deterministic derivation rule for Cloud balance_after, or null when unavailable",
    )
    receipt_ref_field: MappingValue[str | None] = Field(
        default_factory=lambda: MappingValue[str | None](value=None, state="NOT_STARTED"),
        description="Optional safe source for Cloud receipt_ref, or null if no reliable source exists",
    )
    store_field: MappingValue[str | None] = Field(
        default_factory=lambda: MappingValue[str | None](value=None, state="NOT_STARTED"),
        description="Optional verified source for the Cloud store field, or null when no reliable source exists",
    )


class EntityCursorStrategy(BaseModel):
    """Deterministic pagination and incremental checkpoint strategy definition."""

    model_config = ConfigDict(extra="forbid")

    strategy_name: str = Field(description="Deterministic cursor pagination strategy identifier")
    ordering_fields: list[str] = Field(description="Fields determining ordering")
    tie_breaker: str = Field(description="Deterministic tie-breaker field")


class CursorStrategy(BaseModel):
    """Deterministic pagination and incremental checkpoint strategy."""

    model_config = ConfigDict(extra="forbid")

    cards: MappingValue[EntityCursorStrategy] = Field(description="Cursor strategy for cards")
    transactions: MappingValue[EntityCursorStrategy] = Field(description="Cursor strategy for transactions")


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

    artifact_kind: ArtifactKind = Field(
        default="synthetic_example",
        description="Kind of mapping artifact: 'synthetic_example' or 'real_discovery'",
    )
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
