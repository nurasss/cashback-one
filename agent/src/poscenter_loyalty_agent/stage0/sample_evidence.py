"""Safe aggregate evidence accumulator for Stage 0 pilot inspections.

Guarantees:
- Raw customer data (phones, barcodes, full names, passwords) observed during sampling
  are evaluated purely in memory.
- The accumulator emits strictly statistical aggregates, types, precision, and counts.
- Raw sample values, individual records, and customer strings are NEVER retained, logged,
  or exported into output artifacts.
"""

from __future__ import annotations

from typing import Any

from poscenter_loyalty_agent.stage0.mapping_models import EvidenceAggregates


class SampleEvidenceBuilder:
    """Safe builder for pilot evidence aggregates adhering to zero-PII retention."""

    def __init__(self) -> None:
        self._sample_size = 0

        # Barcode counts
        self._barcode_valid_13 = 0
        self._barcode_invalid = 0
        self._barcode_null = 0

        # Phone counts
        self._phone_null = 0
        self._phone_normalizable = 0
        self._phone_invalid = 0

        # Customer name inspection
        self._name_null = 0
        self._name_populated = 0
        self._name_type = "String"

        # Balance inspection
        self._balance_null = 0
        self._balance_allows_negative = False
        self._balance_precision = 2
        self._balance_type = "Number(15,2)"

    def observe_card_record(
        self,
        *,
        barcode: Any = None,
        phone: Any = None,
        full_name: Any = None,
        balance: Any = None,
    ) -> None:
        """Inspect a single card record strictly in memory without retaining raw strings."""
        self._sample_size += 1

        # 1. Barcode inspection (13-digit barcode check)
        if barcode is None or str(barcode).strip() == "":
            self._barcode_null += 1
        else:
            b_str = str(barcode).strip()
            if len(b_str) == 13 and b_str.isdigit():
                self._barcode_valid_13 += 1
            else:
                self._barcode_invalid += 1

        # 2. Phone inspection (normalizability count)
        if phone is None or str(phone).strip() == "":
            self._phone_null += 1
        else:
            p_str = str(phone).strip()
            digits = [c for c in p_str if c.isdigit()]
            if len(digits) >= 10:
                self._phone_normalizable += 1
            else:
                self._phone_invalid += 1

        # 3. Customer name inspection (presence/type only, raw name discarded)
        if full_name is None or str(full_name).strip() == "":
            self._name_null += 1
        else:
            self._name_populated += 1
            self._name_type = "String"

        # 4. Balance inspection (numeric properties only)
        if balance is None:
            self._balance_null += 1
        else:
            try:
                val = float(balance)
                if val < 0:
                    self._balance_allows_negative = True
            except (ValueError, TypeError):
                pass
            self._balance_type = "Number(15,2)"

    def build_aggregates(self) -> EvidenceAggregates:
        """Produce safe EvidenceAggregates containing zero raw customer data."""
        return EvidenceAggregates(
            barcode_aggregate={
                "sample_size": self._sample_size,
                "valid_13_digit": self._barcode_valid_13,
                "invalid_count": self._barcode_invalid,
                "null_count": self._barcode_null,
            },
            phone_aggregate={
                "sample_size": self._sample_size,
                "null_count": self._phone_null,
                "normalizable_count": self._phone_normalizable,
                "invalid_count": self._phone_invalid,
            },
            name_aggregate={
                "sample_size": self._sample_size,
                "field_exists": (self._name_populated + self._name_null) > 0,
                "null_count": self._name_null,
                "populated_count": self._name_populated,
                "type": self._name_type,
            },
            balance_aggregate={
                "sample_size": self._sample_size,
                "numeric_type": self._balance_type,
                "precision": self._balance_precision,
                "allows_negative": self._balance_allows_negative,
                "null_count": self._balance_null,
            },
        )
