"""Central PII and credentials sanitizer for Stage 0 Discovery artifacts.

Guarantees that no raw customer data, connection string secrets, passwords,
E.164 phone numbers, or 13-digit barcodes leak into logs, stdout, or reports.
"""

from __future__ import annotations

import re
from typing import Any

# Regex patterns for sensitive data detection
RE_PHONE = re.compile(
    r"\+[1-9]\d{7,14}\b|\b8[\s\-]?(?:\(\d{3}\)|\d{3})[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b|\b7\d{10}\b"
)
RE_BARCODE_13 = re.compile(r"\b\d{13}\b")
# Lookahead ensures already-redacted values like ***REDACTED*** or [REDACTED] are not re-flagged
RE_CONN_PARAM = re.compile(
    r"(?i)\b(pwd|password|pass|usr|ws|srvr|ref)\s*=\s*['\"]?(?!\*\*\*REDACTED\*\*\*|\[REDACTED\])([^;'\"\s]+)['\"]?"
)
RE_SECRET_KEY = re.compile(
    r"(?i)\b(secret|token|api_key|apikey)\s*[:=]\s*['\"]?(?!\*\*\*REDACTED\*\*\*|\[REDACTED\])([a-zA-Z0-9_\-\.]{8,})['\"]?"
)


class SecuritySanitizerError(ValueError):
    """Raised when an output artifact contains unredacted sensitive data."""


def scan_for_sensitive_data(text: str) -> list[str]:
    """Scan text and return descriptions of all detected sensitive patterns."""
    findings: list[str] = []

    # Check for credentials and connection strings
    for m in RE_CONN_PARAM.finditer(text):
        findings.append(f"Connection parameter detected: {m.group(1)}=***")

    for m in RE_SECRET_KEY.finditer(text):
        findings.append(f"Secret/key pattern detected: {m.group(1)}")

    # Check for 13-digit barcodes
    barcodes = RE_BARCODE_13.findall(text)
    if barcodes:
        findings.append(f"13-digit barcode pattern detected ({len(barcodes)} match(es))")

    # Check for phone numbers
    phones = RE_PHONE.findall(text)
    if phones:
        findings.append(f"Phone number pattern detected ({len(phones)} match(es))")

    return findings


def contains_sensitive_data(text: str) -> bool:
    """Returns True if any unredacted sensitive pattern is detected."""
    return len(scan_for_sensitive_data(text)) > 0


def sanitize_text(text: str) -> str:
    """Mask sensitive patterns in text."""
    # 1. Connection strings and passwords
    sanitized = RE_CONN_PARAM.sub(r"\1=***REDACTED***", text)
    sanitized = RE_SECRET_KEY.sub(r"\1=***REDACTED***", sanitized)

    # 2. 13-digit barcodes (process before phone numbers)
    sanitized = RE_BARCODE_13.sub("[BARCODE_REDACTED]", sanitized)

    # 3. E.164 and local phone numbers
    sanitized = RE_PHONE.sub("[PHONE_REDACTED]", sanitized)

    return sanitized


def sanitize_object(obj: Any) -> Any:
    """Recursively sanitize dictionary, list, or primitive structure."""
    if isinstance(obj, str):
        return sanitize_text(obj)
    if isinstance(obj, dict):
        return {k: sanitize_object(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_object(item) for item in obj]
    return obj


def validate_safe_output(content: str, context: str = "") -> None:
    """Validate that text content is safe for writing to file or printing.

    Raises SecuritySanitizerError if unredacted sensitive data is discovered.
    """
    findings = scan_for_sensitive_data(content)
    if findings:
        prefix = f"[{context}] " if context else ""
        raise SecuritySanitizerError(
            f"{prefix}Security safety violation: detected sensitive data: {'; '.join(findings)}"
        )
