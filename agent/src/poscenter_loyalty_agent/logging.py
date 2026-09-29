"""Structured logging configuration for POSCENTER Loyalty Agent.

Provides console and rotating file logging with automatic sanitization
of sensitive data (passwords, connection strings, API keys, tokens, and PII).
"""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Sensitive patterns to scrub from log messages
SENSITIVE_PATTERNS = [
    # 1C connection string passwords
    (re.compile(r'(?i)(pwd|password|pass)\s*=\s*[^;\s]+'), r'\1=***REDACTED***'),
    # API key / Bearer tokens / Secrets
    (re.compile(r'(?i)(x-agent-key|api[-_]?key|bearer|token|secret)\s*[:=]\s*["\']?[a-zA-Z0-9_\-\.]{8,}["\']?'), r'\1: ***REDACTED***'),
    # Phone numbers (Kazakhstan / international formats)
    (re.compile(r'(?<!\d)(?:\+?7|8)?7\d{9}(?!\d)'), r'***PHONE_REDACTED***'),
    # Card / Barcode sequences (12-16 digits)
    (re.compile(r'(?<!\d)\d{12,19}(?!\d)'), r'***BARCODE_REDACTED***'),
]


class SanitizingFormatter(logging.Formatter):
    """Log formatter that masks secrets and sensitive PII from record messages."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        sanitized = original
        for pattern, replacement in SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized


def sanitize_message(msg: str) -> str:
    """Sanitize a standalone string from sensitive info (e.g. for error storage)."""
    sanitized = str(msg)
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def configure_logging(
    log_level: str = "INFO",
    log_file_path: Path | None = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """Configure structured logging for the agent package."""
    root_logger = logging.getLogger("poscenter_loyalty_agent")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if reconfigured
    root_logger.handlers.clear()

    formatter = SanitizingFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler if path provided
    if log_file_path is not None:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger
