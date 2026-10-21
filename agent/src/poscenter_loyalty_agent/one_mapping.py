"""1C metadata mapping loader, validator, and configuration model."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from poscenter_loyalty_agent.stage0.mapping_models import Stage0Mapping
from poscenter_loyalty_agent.stage0.validator import validate_mapping

logger = logging.getLogger("poscenter_loyalty_agent.one_mapping")


# ==============================================================================
# Standard 1C Metadata Constants
# Verified by Stage 0 metadata probe 2026-10-17, POSCENTERONE 2.0.0.26.9
# Reference: metadata_inventory in C:\cashback-stage0\stage0_mapping.json
# ==============================================================================
FIELD_CARD_BLOCKED = "КартаЗапрещена"
FIELD_DELETION_MARK = "ПометкаУдаления"
FIELD_REGISTRAR = "Регистратор"
FIELD_LINE_NUMBER = "НомерСтроки"
DOC_RETAIL_REPORT = "Документ.ОтчетКассовойСмены"
FIELD_DOC_NUMBER = "Номер"
FIELD_WAREHOUSE = "Склад"
FIELD_NAME = "Наименование"


class MappingValidationError(Exception):
    """Raised when the Stage 0 mapping artifact fails integrity or verification checks."""


class OneMappingConfig:
    """Parsed and validated Stage 0 mapping configuration."""

    def __init__(self, mapping: Stage0Mapping) -> None:
        self.mapping = mapping

        # Configuration identity
        self.expected_configuration_name: str = mapping.one_configuration_identity.configuration_name
        self.expected_configuration_version: str = mapping.one_configuration_identity.configuration_version

        # Cards configuration
        self.card_source_object: str = mapping.cards.source_object.value
        self.card_catalog_name: str = self._extract_object_name(self.card_source_object)

        self.card_id_field: str = mapping.cards.stable_source_id.value
        self.card_barcode_field: str = mapping.cards.barcode_field.value
        self.card_phone_field: str = mapping.cards.phone_field.value
        self.card_full_name_field: str = mapping.cards.full_name_field.value
        self.card_blocked_source: str = mapping.cards.blocked_source.value
        self.card_updated_at_source: str = mapping.cards.updated_at_source.value

        # Balance source: "AccumulationRegisters.ОстаткиБонусныхКарт.Остатки: измерение БонуснаяКарта, ресурс СуммаОстаток"
        self.balance_register_name, self.balance_card_dimension, self.balance_amount_resource = (
            self._parse_balance_source(mapping.cards.balance_source.value)
        )

        # Transactions configuration
        self.tx_source_object: str = mapping.transactions.source_object.value
        self.tx_register_name: str = self._extract_object_name(self.tx_source_object)
        self.tx_card_field: str = mapping.transactions.card_relationship.value
        self.tx_type_field: str = mapping.transactions.type_field.value
        self.tx_type_mapping: dict[str, str] = mapping.transactions.type_mapping.value
        self.tx_amount_field: str = mapping.transactions.amount_field.value
        self.tx_occurred_at_field: str = mapping.transactions.occurred_at_field.value

        # Candidate fields
        self.balance_after_state: str = mapping.transactions.balance_after_field.state
        self.balance_after_enabled: bool = self.balance_after_state in ("CANDIDATE", "VERIFIED")

        self.receipt_ref_state: str = mapping.transactions.receipt_ref_field.state
        self.receipt_ref_enabled: bool = self.receipt_ref_state in ("CANDIDATE", "VERIFIED")

        self.store_state: str = mapping.transactions.store_field.state
        self.store_enabled: bool = self.store_state in ("CANDIDATE", "VERIFIED")

        if self.balance_after_enabled:
            logger.info("Field 'balance_after' is CANDIDATE: enabled via sequential calculation")
        if self.receipt_ref_enabled:
            logger.info("Field 'receipt_ref' is CANDIDATE: enabled for ОтчетКассовойСмены")
        if self.store_enabled:
            logger.info("Field 'store' is CANDIDATE: enabled for ОтчетКассовойСмены")

    @classmethod
    def load(cls, mapping_path: Path, require_verified: bool = True) -> OneMappingConfig:
        if not mapping_path.exists():
            raise MappingValidationError(f"Mapping file not found at: {mapping_path}")

        report = validate_mapping(mapping_path, require_verified=require_verified)
        if not report.is_valid:
            raise MappingValidationError(f"Mapping validation failed: {report.errors}")

        try:
            content = mapping_path.read_text(encoding="utf-8")
            mapping = Stage0Mapping.model_validate_json(content)
        except Exception as exc:
            raise MappingValidationError(f"Failed to parse mapping JSON: {exc}") from exc

        return cls(mapping)

    def verify_configuration(self, actual_name: str, actual_version: str) -> str | None:
        """Verify 1C configuration identity against mapping.

        - If name does not match -> fatal error (MAPPING_INTEGRITY_ERROR).
        - If version does not match -> return warning string (and log warning), execution continues.
        """
        if actual_name.strip() != self.expected_configuration_name.strip():
            raise MappingValidationError(
                f"MAPPING_INTEGRITY_ERROR: 1C configuration name mismatch: "
                f"expected '{self.expected_configuration_name}', got '{actual_name}'"
            )

        if actual_version.strip() != self.expected_configuration_version.strip():
            msg = (
                f"Configuration version mismatch: mapping expected '{self.expected_configuration_version}', "
                f"1C infobase has '{actual_version}'"
            )
            logger.warning(msg)
            return msg

        return None

    @staticmethod
    def _extract_object_name(source: str) -> str:
        """Extract short metadata object name (e.g. Catalogs.БонусныеКарты -> БонусныеКарты)."""
        clean = source.strip()
        if "." in clean:
            parts = clean.split(".")
            if len(parts) >= 2:
                return parts[1]
        return clean

    @staticmethod
    def _parse_balance_source(source: str) -> tuple[str, str, str]:
        """Parse register name, card dimension, and amount resource from balance source string."""
        reg_name = "ОстаткиБонусныхКарт"
        dim_name = "БонуснаяКарта"
        res_name = "СуммаОстаток"

        reg_match = re.search(r"(?:AccumulationRegisters|РегистрНакопления)\.([^\s.:,]+)", source)
        if reg_match:
            reg_name = reg_match.group(1)

        dim_match = re.search(r"измерение\s+([^\s,]+)", source, re.IGNORECASE)
        if dim_match:
            dim_name = dim_match.group(1)

        res_match = re.search(r"ресурс\s+([^\s,]+)", source, re.IGNORECASE)
        if res_match:
            res_name = res_match.group(1)

        return reg_name, dim_name, res_name


def load_one_mapping(mapping_path: Path, require_verified: bool = True) -> OneMappingConfig:
    """Helper to load and validate OneMappingConfig."""
    return OneMappingConfig.load(mapping_path, require_verified=require_verified)
