"""Mapping artifact validator and placeholder checker for Stage 0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from poscenter_loyalty_agent.stage0.mapping_models import (
    Stage0Mapping,
    calculate_mapping_fingerprint,
)
from poscenter_loyalty_agent.stage0.sanitizer import scan_for_sensitive_data

PLACEHOLDER_SUBSTRINGS_SYNTHETIC = (
    "TODO",
    "TBD",
    "guess",
    "unknown_object",
    "UNKNOWN",
    "mock",
    "placeholder",
)

PLACEHOLDER_SUBSTRINGS_STRICT = (
    "TODO",
    "TBD",
    "guess",
    "example",
    "synthetic",
    "unknown_object",
    "UNKNOWN",
    "mock",
    "placeholder",
)

MANDATORY_P0_FIELDS = (
    ("cards.source_object", ("cards", "source_object")),
    ("cards.stable_source_id", ("cards", "stable_source_id")),
    ("cards.barcode_field", ("cards", "barcode_field")),
    ("cards.phone_field", ("cards", "phone_field")),
    ("cards.balance_source", ("cards", "balance_source")),
    ("cards.blocked_source", ("cards", "blocked_source")),
    ("cards.updated_at_source", ("cards", "updated_at_source")),
    ("transactions.source_object", ("transactions", "source_object")),
    ("transactions.stable_source_id", ("transactions", "stable_source_id")),
    ("transactions.card_relationship", ("transactions", "card_relationship")),
    ("transactions.type_field", ("transactions", "type_field")),
    ("transactions.type_mapping", ("transactions", "type_mapping")),
    ("transactions.amount_field", ("transactions", "amount_field")),
    ("transactions.occurred_at_field", ("transactions", "occurred_at_field")),
    ("cursor_strategy.cards", ("cursor_strategy", "cards")),
    ("cursor_strategy.transactions", ("cursor_strategy", "transactions")),
)


class ValidationReport(BaseModel):
    """Structured report returned by mapping validation."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    require_verified: bool = False
    artifact_kind: str | None = None
    mapping_version: str | None = None
    calculated_fingerprint: str | None = None
    declared_fingerprint: str | None = None
    unverified_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def format_console(self) -> str:
        lines = [
            "=== Stage 0 Mapping Validation Report ===",
            f"Status:                 {'VALID' if self.is_valid else 'INVALID'}",
            f"Validation Mode:        {'REQUIRE_VERIFIED' if self.require_verified else 'STANDARD'}",
            f"Artifact Kind:          {self.artifact_kind or '(unknown)'}",
            f"Mapping Version:        {self.mapping_version or '(unknown)'}",
            f"Declared Fingerprint:   {self.declared_fingerprint or '(none)'}",
            f"Calculated Fingerprint: {self.calculated_fingerprint or '(none)'}",
        ]
        if self.unverified_fields:
            lines.append("\nUnverified Mandatory Fields:")
            for f in self.unverified_fields:
                lines.append(f" [UNVERIFIED] {f}")
        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f" [ERROR] {err}")
        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                lines.append(f" [WARN] {w}")
        return "\n".join(lines)


def _scan_placeholders(data: Any, path: str = "", strict: bool = False) -> list[str]:
    """Recursively search for forbidden placeholder words."""
    findings: list[str] = []
    forbidden = PLACEHOLDER_SUBSTRINGS_STRICT if strict else PLACEHOLDER_SUBSTRINGS_SYNTHETIC

    if isinstance(data, str):
        if data == "NOT_AVAILABLE":
            return []
        for p in forbidden:
            if p.lower() in data.lower():
                findings.append(f"Placeholder '{p}' detected at '{path}': {data!r}")
    elif isinstance(data, dict):
        for k, v in data.items():
            # Skip checking the artifact_kind key itself
            if k == "artifact_kind":
                continue
            sub_path = f"{path}.{k}" if path else k
            findings.extend(_scan_placeholders(v, sub_path, strict=strict))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            findings.extend(_scan_placeholders(item, f"{path}[{idx}]", strict=strict))
    return findings


def validate_mapping(
    raw_data: dict[str, Any] | str | Path,
    require_verified: bool = False,
) -> ValidationReport:
    """Validate a Stage 0 mapping artifact against schema, placeholders, PII, and fingerprint.

    If require_verified=True:
    - artifact_kind must be 'real_discovery' (never 'synthetic_example')
    - configuration name must not be synthetic test configuration
    - all 16 mandatory P0 mapping decisions must have state='VERIFIED'
    - no placeholders (including 'example' and 'synthetic') are allowed
    """
    errors: list[str] = []
    warnings: list[str] = []
    unverified_fields: list[str] = []

    # 1. Parse JSON if string or Path
    if isinstance(raw_data, (str, Path)):
        path_obj = Path(raw_data)
        if not path_obj.exists():
            return ValidationReport(
                is_valid=False,
                require_verified=require_verified,
                errors=[f"Mapping file does not exist: {path_obj}"],
            )
        try:
            content = path_obj.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception as exc:
            return ValidationReport(
                is_valid=False,
                require_verified=require_verified,
                errors=[f"Failed to read/parse JSON from {path_obj}: {exc}"],
            )
    elif isinstance(raw_data, dict):
        data = raw_data
        content = json.dumps(data)
    else:
        return ValidationReport(
            is_valid=False,
            require_verified=require_verified,
            errors=[f"Unsupported data type for mapping validation: {type(raw_data)}"],
        )

    # 2. PII / Credentials Scan
    pii_findings = scan_for_sensitive_data(content)
    if pii_findings:
        for f in pii_findings:
            errors.append(f"Security violation: {f}")

    # 3. Pydantic schema validation
    try:
        Stage0Mapping.model_validate(data)
    except ValidationError as val_err:
        for err in val_err.errors():
            loc = ".".join(str(part) for part in err["loc"])
            errors.append(f"Schema violation at '{loc}': {err['msg']}")

    artifact_kind = data.get("artifact_kind")
    declared_fingerprint = data.get("mapping_sha256")
    calculated_fingerprint = calculate_mapping_fingerprint(data)

    # 4. Fingerprint check
    if not declared_fingerprint:
        errors.append("Declared 'mapping_sha256' field is missing from mapping artifact.")
    elif declared_fingerprint != calculated_fingerprint:
        errors.append(
            f"Fingerprint mismatch: declared={declared_fingerprint}, calculated={calculated_fingerprint}. "
            "Artifact may have been tampered with or modified without recalculating hash."
        )

    # 5. Placeholder detection
    is_strict = require_verified or artifact_kind == "real_discovery"
    placeholders = _scan_placeholders(data, strict=is_strict)
    if placeholders:
        for p in placeholders:
            errors.append(f"Incomplete mapping: {p}")

    # 6. Verification state enforcement (--require-verified)
    if require_verified:
        if artifact_kind != "real_discovery":
            errors.append(
                f"Verified validation rejected: artifact_kind must be 'real_discovery' "
                f"(current: '{artifact_kind}')"
            )

        conf_ident = data.get("one_configuration_identity", {})
        conf_name = conf_ident.get("configuration_name", "")
        if "synthetic" in conf_name.lower() or conf_name == "SyntheticTestConfiguration":
            errors.append(
                f"Verified validation rejected: synthetic configuration identity '{conf_name}' "
                "cannot be verified."
            )

        for field_label, field_path in MANDATORY_P0_FIELDS:
            curr: Any = data
            for part in field_path:
                if isinstance(curr, dict):
                    curr = curr.get(part)
                else:
                    curr = None
                    break

            state = curr.get("state") if isinstance(curr, dict) else None
            if state != "VERIFIED":
                unverified_fields.append(field_label)
                errors.append(
                    f"Mandatory mapping field '{field_label}' is not VERIFIED (current state: '{state}')"
                )

    mapping_version = data.get("mapping_version")
    is_valid = len(errors) == 0

    return ValidationReport(
        is_valid=is_valid,
        require_verified=require_verified,
        artifact_kind=artifact_kind,
        mapping_version=mapping_version,
        declared_fingerprint=declared_fingerprint,
        calculated_fingerprint=calculated_fingerprint,
        unverified_fields=unverified_fields,
        errors=errors,
        warnings=warnings,
    )
