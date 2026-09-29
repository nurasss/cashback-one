"""Metadata probe and inventory extractor for POSCENTER ONE (1C:Enterprise 8.3).

Provides:
- MetadataProvider protocol for COM vs Fake abstraction.
- ComMetadataProvider: Strictly read-only inspection of live 1C infobase.
- FakeMetadataProvider: Test-only seam using neutral synthetic names.
- CandidateDiscoveryHeuristic: Heuristic identification of candidate entities.
- TargetedMetadataInventory: Targeted metadata inventory with truthful coverage declarations.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from poscenter_loyalty_agent.one_com import (
    OneComConnector,
)
from poscenter_loyalty_agent.stage0.environment import EnvironmentCheckResult, check_environment
from poscenter_loyalty_agent.stage0.mapping_models import ConfigurationIdentity

logger = logging.getLogger(__name__)

PROBED_LOYALTY_CATEGORIES = (
    "Catalogs",
    "AccumulationRegisters",
    "InformationRegisters",
    "Documents",
)

UNPROBED_METADATA_CATEGORIES = (
    "ChartsOfAccounts",
    "ChartsOfCalculationTypes",
    "ChartsOfCharacteristicTypes",
    "BusinessProcesses",
    "Tasks",
    "Enums",
    "Reports",
    "DataProcessors",
    "Constants",
    "Sequences",
    "ExchangePlans",
)


class MetadataField(BaseModel):
    """Description of an attribute, dimension, or resource in 1C metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Internal identifier of the attribute")
    synonym: str | None = Field(default=None, description="Human-readable synonym/label")
    type_desc: str = Field(default="Unknown", description="Type representation string")
    is_dimension: bool = Field(default=False, description="True for register dimensions")
    is_resource: bool = Field(default=False, description="True for register resources")


class MetadataObject(BaseModel):
    """Technical description of an identified 1C metadata object."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(description="Category (e.g. Catalogs, AccumulationRegisters, Documents)")
    name: str = Field(description="Internal object name")
    synonym: str | None = Field(default=None, description="Synonym / display name")
    fields: list[MetadataField] = Field(default_factory=list)
    tabular_sections: list[str] = Field(default_factory=list)


class CandidateMatch(BaseModel):
    """Heuristic candidate detected during inventory analysis."""

    model_config = ConfigDict(extra="forbid")

    object_name: str
    category: str
    role: str = Field(description="Role: card, transaction, or balance_register")
    confidence_reason: str
    requires_manual_verification: bool = Field(default=True)
    matched_fields: list[str] = Field(default_factory=list)


class TargetedMetadataInventory(BaseModel):
    """Targeted inventory of discovered 1C metadata for loyalty integration."""

    model_config = ConfigDict(extra="forbid")

    coverage_scope: str = Field(
        default="targeted_loyalty_core",
        description="Targeted scope: Catalogs, AccumulationRegisters, InformationRegisters, Documents",
    )
    probed_categories: list[str] = Field(
        default_factory=lambda: list(PROBED_LOYALTY_CATEGORIES),
        description="List of 1C metadata categories inspected by this probe",
    )
    unprobed_categories: list[str] = Field(
        default_factory=lambda: list(UNPROBED_METADATA_CATEGORIES),
        description="List of 1C metadata categories outside targeted loyalty scope",
    )
    coverage_limitation: str = Field(
        default=(
            "Targeted discovery focused on core transactional loyalty objects. "
            "Complete 1C metadata root enumeration was not performed."
        ),
        description="Explicit notice regarding category coverage limitation",
    )
    configuration: ConfigurationIdentity
    discovered_at: str
    objects: list[MetadataObject] = Field(default_factory=list)
    candidate_cards: list[CandidateMatch] = Field(default_factory=list)
    candidate_transactions: list[CandidateMatch] = Field(default_factory=list)
    candidate_registers: list[CandidateMatch] = Field(default_factory=list)


# Backward-compatible alias
MetadataInventory = TargetedMetadataInventory


class CandidateDiscoveryHeuristic:
    """Configurable, non-presumptive heuristics to surface candidate metadata objects."""

    CARD_KEYWORDS = ("карт", "card", "клиент", "покупател", "дисконт", "client", "customer")
    PHONE_KEYWORDS = ("телефон", "phone", "тел", "моб", "mobile")
    BARCODE_KEYWORDS = ("штрихкод", "штрих", "barcode", "кодкарты", "cardcode")
    BALANCE_KEYWORDS = ("бонус", "bonus", "баланс", "balance", "остаток", "баллы", "points")
    TX_KEYWORDS = ("продаж", "чек", "движение", "movement", "sales", "receipt", "операция")

    @classmethod
    def analyze(
        cls, objects: list[MetadataObject]
    ) -> tuple[list[CandidateMatch], list[CandidateMatch], list[CandidateMatch]]:
        cards: list[CandidateMatch] = []
        txs: list[CandidateMatch] = []
        regs: list[CandidateMatch] = []

        for obj in objects:
            name_lower = obj.name.lower()
            syn_lower = (obj.synonym or "").lower()
            text = f"{name_lower} {syn_lower}"

            # Check for candidate card catalogs
            if obj.category in ("Catalogs", "InformationRegisters"):
                matched_fields = []
                for f in obj.fields:
                    f_text = f"{f.name.lower()} {(f.synonym or '').lower()}"
                    if any(k in f_text for k in cls.PHONE_KEYWORDS) or any(
                        k in f_text for k in cls.BARCODE_KEYWORDS
                    ):
                        matched_fields.append(f.name)

                if any(k in text for k in cls.CARD_KEYWORDS) or matched_fields:
                    cards.append(
                        CandidateMatch(
                            object_name=f"{obj.category}.{obj.name}",
                            category=obj.category,
                            role="card",
                            confidence_reason=(
                                f"Matches card keywords or contains candidate fields: "
                                f"{', '.join(matched_fields) if matched_fields else 'name match'}"
                            ),
                            requires_manual_verification=True,
                            matched_fields=matched_fields,
                        )
                    )

            # Check for accumulation registers (balance / movements)
            if obj.category == "AccumulationRegisters":
                matched_fields = [f.name for f in obj.fields]
                if any(k in text for k in cls.BALANCE_KEYWORDS):
                    regs.append(
                        CandidateMatch(
                            object_name=f"{obj.category}.{obj.name}",
                            category=obj.category,
                            role="balance_register",
                            confidence_reason="Accumulation register matching bonus / balance keywords",
                            requires_manual_verification=True,
                            matched_fields=matched_fields,
                        )
                    )

            # Check for transaction documents or registers
            if obj.category in ("Documents", "AccumulationRegisters"):
                if any(k in text for k in cls.TX_KEYWORDS) or any(k in text for k in cls.BALANCE_KEYWORDS):
                    txs.append(
                        CandidateMatch(
                            object_name=f"{obj.category}.{obj.name}",
                            category=obj.category,
                            role="transaction",
                            confidence_reason="Source matches sales / transaction / bonus movement keywords",
                            requires_manual_verification=True,
                            matched_fields=[f.name for f in obj.fields[:5]],
                        )
                    )

        return cards, txs, regs


@runtime_checkable
class MetadataProvider(Protocol):
    """Protocol defining the metadata reader interface for Stage 0 Discovery."""

    def check_env(self) -> EnvironmentCheckResult:
        ...

    def get_configuration_identity(self) -> ConfigurationIdentity:
        ...

    def discover_metadata(self) -> TargetedMetadataInventory:
        ...


class FakeMetadataProvider:
    """In-memory test double using neutral synthetic metadata names (TEST-ONLY)."""

    def __init__(
        self,
        config: ConfigurationIdentity | None = None,
        objects: list[MetadataObject] | None = None,
    ) -> None:
        self.config = config or ConfigurationIdentity(
            configuration_name="SyntheticTestConfiguration",
            configuration_version="1.0.0.0",
            platform_major="8.3",
            platform_version="NOT_AVAILABLE",
            platform_version_state="NOT_STARTED",
        )
        self.objects = objects or [
            MetadataObject(
                category="Catalogs",
                name="SyntheticObjectA",
                synonym="SynonymA",
                fields=[
                    MetadataField(name="SyntheticFieldBarcode", synonym="Barcode", type_desc="String(13)"),
                    MetadataField(name="SyntheticFieldPhone", synonym="Phone", type_desc="String(32)"),
                    MetadataField(name="SyntheticFieldStatus", synonym="Status", type_desc="Boolean"),
                ],
            ),
            MetadataObject(
                category="AccumulationRegisters",
                name="SyntheticRegisterA",
                synonym="BonusRegisterSynonym",
                fields=[
                    MetadataField(
                        name="SyntheticDimCard",
                        synonym="CardRef",
                        type_desc="CatalogRef.SyntheticObjectA",
                        is_dimension=True,
                    ),
                    MetadataField(
                        name="SyntheticResAmount",
                        synonym="Amount",
                        type_desc="Number(15,2)",
                        is_resource=True,
                    ),
                ],
            ),
        ]

    def check_env(self) -> EnvironmentCheckResult:
        return check_environment()

    def get_configuration_identity(self) -> ConfigurationIdentity:
        return self.config

    def discover_metadata(self) -> TargetedMetadataInventory:
        cards, txs, regs = CandidateDiscoveryHeuristic.analyze(self.objects)
        return TargetedMetadataInventory(
            configuration=self.config,
            discovered_at=datetime.now(UTC).isoformat(),
            objects=self.objects,
            candidate_cards=cards,
            candidate_transactions=txs,
            candidate_registers=regs,
        )


class ComMetadataProvider:
    """Strictly read-only 1C metadata reader using V83.COMConnector.

    Guarantees:
    - Never invokes write, delete, or commit methods.
    - Captures technical metadata structure only (no customer records).
    - Safely guards against non-Windows platforms.
    """

    def __init__(self, connection_string: str) -> None:
        self.connector = OneComConnector(connection_string=connection_string)

    def check_env(self) -> EnvironmentCheckResult:
        return check_environment()

    def get_configuration_identity(self) -> ConfigurationIdentity:
        """Read configuration name, version, and platform major version via COM."""
        conn = self.connector.connect()
        try:
            meta = conn.Metadata
            name = str(getattr(meta, "Name", "UnknownConfiguration"))
            version = str(getattr(meta, "Version", "0.0.0.0"))
            return ConfigurationIdentity(
                configuration_name=name,
                configuration_version=version,
                platform_major="8.3",
                platform_version="NOT_AVAILABLE",
                platform_version_state="NOT_STARTED",
            )
        finally:
            self.connector.disconnect()

    def discover_metadata(self) -> TargetedMetadataInventory:
        """Extract metadata inventory across Catalogs, Registers, and Documents."""
        conn = self.connector.connect()
        try:
            meta = conn.Metadata
            conf_identity = ConfigurationIdentity(
                configuration_name=str(getattr(meta, "Name", "Unknown")),
                configuration_version=str(getattr(meta, "Version", "0.0.0")),
                platform_major="8.3",
                platform_version="NOT_AVAILABLE",
                platform_version_state="NOT_STARTED",
            )

            discovered_objects: list[MetadataObject] = []
            categories_to_probe = [
                ("Catalogs", getattr(meta, "Catalogs", None)),
                ("AccumulationRegisters", getattr(meta, "AccumulationRegisters", None)),
                ("InformationRegisters", getattr(meta, "InformationRegisters", None)),
                ("Documents", getattr(meta, "Documents", None)),
            ]

            for cat_name, collection in categories_to_probe:
                if collection is None:
                    continue
                count = int(getattr(collection, "Count", lambda: 0)())
                for i in range(count):
                    obj_meta = collection.Get(i)
                    obj_name = str(getattr(obj_meta, "Name", f"Obj_{i}"))
                    obj_synonym = str(getattr(obj_meta, "Synonym", "")) or None

                    fields: list[MetadataField] = []
                    # Read Attributes / Requisites
                    attrs = getattr(obj_meta, "Attributes", None)
                    if attrs is not None:
                        attr_count = int(getattr(attrs, "Count", lambda: 0)())
                        for j in range(attr_count):
                            attr = attrs.Get(j)
                            fields.append(
                                MetadataField(
                                    name=str(getattr(attr, "Name", f"Attr_{j}")),
                                    synonym=str(getattr(attr, "Synonym", "")) or None,
                                    type_desc=str(getattr(attr, "Type", "Unknown")),
                                )
                            )

                    # Read Dimensions (Registers)
                    dims = getattr(obj_meta, "Dimensions", None)
                    if dims is not None:
                        dim_count = int(getattr(dims, "Count", lambda: 0)())
                        for j in range(dim_count):
                            dim = dims.Get(j)
                            fields.append(
                                MetadataField(
                                    name=str(getattr(dim, "Name", f"Dim_{j}")),
                                    synonym=str(getattr(dim, "Synonym", "")) or None,
                                    type_desc=str(getattr(dim, "Type", "Unknown")),
                                    is_dimension=True,
                                )
                            )

                    # Read Resources (Registers)
                    res = getattr(obj_meta, "Resources", None)
                    if res is not None:
                        res_count = int(getattr(res, "Count", lambda: 0)())
                        for j in range(res_count):
                            r = res.Get(j)
                            fields.append(
                                MetadataField(
                                    name=str(getattr(r, "Name", f"Res_{j}")),
                                    synonym=str(getattr(r, "Synonym", "")) or None,
                                    type_desc=str(getattr(r, "Type", "Unknown")),
                                    is_resource=True,
                                )
                            )

                    # Read TabularSections
                    tabular_sections: list[str] = []
                    tabs = getattr(obj_meta, "TabularSections", None)
                    if tabs is not None:
                        tab_count = int(getattr(tabs, "Count", lambda: 0)())
                        for j in range(tab_count):
                            tab = tabs.Get(j)
                            tabular_sections.append(str(getattr(tab, "Name", f"Tab_{j}")))

                    discovered_objects.append(
                        MetadataObject(
                            category=cat_name,
                            name=obj_name,
                            synonym=obj_synonym,
                            fields=fields,
                            tabular_sections=tabular_sections,
                        )
                    )

            cards, txs, regs = CandidateDiscoveryHeuristic.analyze(discovered_objects)
            return TargetedMetadataInventory(
                configuration=conf_identity,
                discovered_at=datetime.now(UTC).isoformat(),
                objects=discovered_objects,
                candidate_cards=cards,
                candidate_transactions=txs,
                candidate_registers=regs,
            )

        finally:
            self.connector.disconnect()
