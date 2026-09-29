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

PLACEHOLDER_SUBSTRINGS = (
    "TODO",
    "TBD",
    "guess",
    "example",
    "unknown_object",
    "UNKNOWN",
    "mock",
    "placeholder",
)


class ValidationReport(BaseModel):
    """Structured report returned by mapping validation."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    mapping_version: str | None = None
    calculated_fingerprint: str | None = None
    declared_fingerprint: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def format_console(self) -> str:
        lines = [
            "=== Stage 0 Mapping Validation Report ===",
            f"Status:                 {'VALID' if self.is_valid else 'INVALID'}",
            f"Mapping Version:        {self.mapping_version or '(unknown)'}",
            f"Declared Fingerprint:   {self.declared_fingerprint or '(none)'}",
            f"Calculated Fingerprint: {self.calculated_fingerprint or '(none)'}",
        ]
        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f" [ERROR] {err}")
        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                lines.append(f" [WARN] {w}")
        return "\n".join(lines)


def _scan_placeholders(data: Any, path: str = "") -> list[str]:
    """Recursively search for forbidden placeholder words."""
    findings: list[str] = []
    if isinstance(data, str):
        # NOT_AVAILABLE is a valid normative indicator for absent optional fields
        if data == "NOT_AVAILABLE":
            return []
        for p in PLACEHOLDER_SUBSTRINGS:
            if p.lower() in data.lower():
                findings.append(f"Placeholder '{p}' detected at '{path}': {data!r}")
    elif isinstance(data, dict):
        for k, v in data.items():
            sub_path = f"{path}.{k}" if path else k
            findings.extend(_scan_placeholders(v, sub_path))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            findings.extend(_scan_placeholders(item, f"{path}[{idx}]"))
    return findings


def validate_mapping(raw_data: dict[str, Any] | str | Path) -> ValidationReport:
    """Validate a Stage 0 mapping artifact against schema, placeholders, PII, and fingerprint."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Parse JSON if string or Path
    if isinstance(raw_data, (str, Path)):
        path_obj = Path(raw_data)
        if not path_obj.exists():
            return ValidationReport(
                is_valid=False,
                errors=[f"Mapping file does not exist: {path_obj}"],
            )
        try:
            content = path_obj.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception as exc:
            return ValidationReport(
                is_valid=False,
                errors=[f"Failed to read/parse JSON from {path_obj}: {exc}"],
            )
    elif isinstance(raw_data, dict):
        data = raw_data
        content = json.dumps(data)
    else:
        return ValidationReport(
            is_valid=False,
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
    placeholders = _scan_placeholders(data)
    if placeholders:
        for p in placeholders:
            errors.append(f"Incomplete mapping: {p}")

    mapping_version = data.get("mapping_version")
    is_valid = len(errors) == 0

    return ValidationReport(
        is_valid=is_valid,
        mapping_version=mapping_version,
        declared_fingerprint=declared_fingerprint,
        calculated_fingerprint=calculated_fingerprint,
        errors=errors,
        warnings=warnings,
    )
