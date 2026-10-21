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
from typing import Any, Protocol, runtime_checkable

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
    "Enums",
)

UNPROBED_METADATA_CATEGORIES = (
    "ChartsOfAccounts",
    "ChartsOfCalculationTypes",
    "ChartsOfCharacteristicTypes",
    "BusinessProcesses",
    "Tasks",
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
    kind: str | None = Field(
        default=None,
        description="Field kind (e.g. StandardAttribute, Dimension, Resource, Attribute)",
    )


class MetadataObject(BaseModel):
    """Technical description of an identified 1C metadata object."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(description="Category (e.g. Catalogs, AccumulationRegisters, Documents, Enums)")
    name: str = Field(description="Internal object name")
    synonym: str | None = Field(default=None, description="Synonym / display name")
    register_kind: str | None = Field(default=None, description="Register kind or periodicity")
    fields: list[MetadataField] = Field(default_factory=list)
    tabular_sections: list[str] = Field(default_factory=list)
    catalog_props: dict[str, str] | None = Field(
        default=None,
        description="Catalog properties (e.g. CodeLength, CodeType, DescriptionLength, Hierarchical)",
    )


class CandidateMatch(BaseModel):
    """Heuristic candidate detected during inventory analysis."""

    model_config = ConfigDict(extra="forbid")

    object_name: str
    category: str
    role: str = Field(
        description="Role: card, transaction, or balance_source_candidate (heuristic candidate only; not mapping evidence; not verification)"
    )
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
            "Complete 1C metadata root enumeration was not performed. "
            "Category membership is only a search heuristic and is not evidence that the final mapping must use that category."
        ),
        description="Explicit notice regarding category coverage limitation",
    )
    configuration: ConfigurationIdentity
    discovered_at: str
    objects: list[MetadataObject] = Field(default_factory=list)
    candidate_cards: list[CandidateMatch] = Field(default_factory=list)
    candidate_transactions: list[CandidateMatch] = Field(default_factory=list)
    candidate_balance_sources: list[CandidateMatch] = Field(
        default_factory=list,
        description="Heuristic candidates for balance sources (heuristic candidates only; not mapping evidence; not verification)",
    )

    def __init__(self, **data: Any) -> None:
        if "candidate_registers" in data and "candidate_balance_sources" not in data:
            data["candidate_balance_sources"] = data.pop("candidate_registers")
        super().__init__(**data)

    @property
    def candidate_registers(self) -> list[CandidateMatch]:
        """Backward-compatible alias for candidate_balance_sources."""
        return self.candidate_balance_sources


# Backward-compatible alias
MetadataInventory = TargetedMetadataInventory


class CandidateDiscoveryHeuristic:
    """Configurable, non-presumptive heuristics to surface candidate metadata objects.

    Category membership is only a search heuristic and is not evidence that the
    final mapping must use that category. All discovered candidates are heuristic
    candidates only, not mapping evidence, and not verification.
    """

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

            # Check for candidate balance sources (heuristic candidates only)
            if obj.category in ("AccumulationRegisters", "InformationRegisters", "Catalogs"):
                matched_fields = [f.name for f in obj.fields]
                if any(k in text for k in cls.BALANCE_KEYWORDS):
                    regs.append(
                        CandidateMatch(
                            object_name=f"{obj.category}.{obj.name}",
                            category=obj.category,
                            role="balance_source_candidate",
                            confidence_reason="Matches bonus / balance keywords (heuristic candidate only; not mapping evidence; not verification)",
                            requires_manual_verification=True,
                            matched_fields=matched_fields,
                        )
                    )

            # Check for transaction documents or registers
            if obj.category in ("Documents", "AccumulationRegisters", "InformationRegisters"):
                if any(k in text for k in cls.TX_KEYWORDS) or any(k in text for k in cls.BALANCE_KEYWORDS):
                    txs.append(
                        CandidateMatch(
                            object_name=f"{obj.category}.{obj.name}",
                            category=obj.category,
                            role="transaction",
                            confidence_reason="Source matches configured transaction/movement candidate keywords; heuristic only, not mapping evidence.",
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
                    MetadataField(
                        name="SyntheticTabularA.SyntheticTabAttr",
                        synonym="TabularAttribute",
                        type_desc="String(50)",
                    ),
                ],
                tabular_sections=["SyntheticTabularA"],
            ),
            MetadataObject(
                category="AccumulationRegisters",
                name="SyntheticRegisterA",
                synonym="BonusRegisterSynonym",
                register_kind="Balances",
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
            MetadataObject(
                category="Enums",
                name="SyntheticEnumA",
                synonym="EnumSynonym",
                fields=[
                    MetadataField(name="Active", synonym="ActiveStatus", type_desc="EnumValue"),
                    MetadataField(name="Blocked", synonym="BlockedStatus", type_desc="EnumValue"),
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
            candidate_balance_sources=regs,
        )


class ComMetadataProvider:
    """Strictly read-only 1C metadata reader using V83.COMConnector.

    Guarantees:
    - Never invokes write, delete, or commit methods.
    - Captures technical metadata structure only (no customer records).
    - Safely guards against non-Windows platforms.
    """

    def __init__(self, connection_string: str, existing_connection: Any = None) -> None:
        self.connector = OneComConnector(connection_string=connection_string, existing_connection=existing_connection)

    @staticmethod
    def _type_to_str(conn: Any, type_obj: Any) -> str:
        """Safely convert a 1C TypeDescription object to string via conn.String()."""
        try:
            return str(conn.String(type_obj))
        except Exception:
            return "Unknown"

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
        """Extract metadata inventory across Catalogs, Registers, Documents, and Enums."""
        logger.debug("discover_metadata: calling self.connector.connect()...")
        conn = self.connector.connect()
        logger.debug("discover_metadata: got conn, accessing Metadata root...")
        try:
            meta = conn.Metadata
            logger.debug("discover_metadata: got conn.Metadata, reading ConfigurationIdentity...")
            conf_identity = ConfigurationIdentity(
                configuration_name=str(getattr(meta, "Name", "Unknown")),
                configuration_version=str(getattr(meta, "Version", "0.0.0")),
                platform_major="8.3",
                platform_version="NOT_AVAILABLE",
                platform_version_state="NOT_STARTED",
            )
            logger.debug("Connected to 1C: %s v%s", conf_identity.configuration_name, conf_identity.configuration_version)

            discovered_objects: list[MetadataObject] = []
            categories_to_probe = [
                ("Catalogs", getattr(meta, "Catalogs", None)),
                ("AccumulationRegisters", getattr(meta, "AccumulationRegisters", None)),
                ("InformationRegisters", getattr(meta, "InformationRegisters", None)),
                ("Documents", getattr(meta, "Documents", None)),
                ("Enums", getattr(meta, "Enums", None)),
            ]

            for cat_name, collection in categories_to_probe:
                if collection is None:
                    continue
                count = int(getattr(collection, "Count", lambda: 0)())
                logger.debug("Probing category %s: %d objects", cat_name, count)
                for i in range(count):
                    obj_meta = collection.Get(i)
                    obj_name = str(getattr(obj_meta, "Name", f"Obj_{i}"))
                    obj_synonym = str(getattr(obj_meta, "Synonym", "")) or None

                    fields: list[MetadataField] = []
                    register_kind: str | None = None
                    catalog_props: dict[str, str] | None = None

                    if cat_name == "Enums":
                        enum_values = getattr(obj_meta, "EnumValues", None)
                        if enum_values is not None:
                            ev_count = int(getattr(enum_values, "Count", lambda: 0)())
                            for k in range(ev_count):
                                ev = enum_values.Get(k)
                                fields.append(
                                    MetadataField(
                                        name=str(getattr(ev, "Name", f"Value_{k}")),
                                        synonym=str(getattr(ev, "Synonym", "")) or None,
                                        type_desc="EnumValue",
                                    )
                                )
                    else:
                        if cat_name == "AccumulationRegisters":
                            reg_type = getattr(obj_meta, "RegisterType", None)
                            if reg_type is not None:
                                try:
                                    register_kind = str(conn.String(reg_type))
                                except Exception:
                                    register_kind = "Unknown"
                        elif cat_name == "InformationRegisters":
                            periodicity = getattr(obj_meta, "InformationRegisterPeriodicity", None)
                            if periodicity is not None:
                                try:
                                    register_kind = str(conn.String(periodicity))
                                except Exception:
                                    register_kind = "Unknown"

                        # Read StandardAttributes (Catalogs, Documents)
                        if cat_name in ("Catalogs", "Documents"):
                            try:
                                std_attrs = getattr(obj_meta, "StandardAttributes", None)
                                if std_attrs is not None:
                                    for s, s_attr in enumerate(std_attrs):
                                        fields.append(
                                            MetadataField(
                                                name=str(getattr(s_attr, "Name", f"StdAttr_{s}")),
                                                synonym=str(getattr(s_attr, "Synonym", "")) or None,
                                                type_desc=self._type_to_str(conn, getattr(s_attr, "Type", None)),
                                                kind="StandardAttribute",
                                            )
                                        )
                            except Exception as e:
                                logger.debug("Failed reading StandardAttributes for %s: %s", obj_name, e)
                                if catalog_props is None:
                                    catalog_props = {}
                                catalog_props["standard_attributes"] = f"unavailable: {type(e).__name__}"

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
                                        type_desc=self._type_to_str(conn, getattr(attr, "Type", None)),
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
                                        type_desc=self._type_to_str(conn, getattr(dim, "Type", None)),
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
                                        type_desc=self._type_to_str(conn, getattr(r, "Type", None)),
                                        is_resource=True,
                                    )
                                )

                    # Read TabularSections
                    tabular_sections: list[str] = []
                    if cat_name != "Enums":
                        tabs = getattr(obj_meta, "TabularSections", None)
                        if tabs is not None:
                            tab_count = int(getattr(tabs, "Count", lambda: 0)())
                            for j in range(tab_count):
                                tab = tabs.Get(j)
                                tab_name = str(getattr(tab, "Name", f"Tab_{j}"))
                                tabular_sections.append(tab_name)

                                if cat_name in ("Documents", "Catalogs"):
                                    tab_attrs = getattr(tab, "Attributes", None)
                                    if tab_attrs is not None:
                                        tab_attr_count = int(getattr(tab_attrs, "Count", lambda: 0)())
                                        for k in range(tab_attr_count):
                                            t_attr = tab_attrs.Get(k)
                                            fields.append(
                                                MetadataField(
                                                    name=f"{tab_name}.{getattr(t_attr, 'Name', f'Attr_{k}')}",
                                                    synonym=str(getattr(t_attr, "Synonym", "")) or None,
                                                    type_desc=self._type_to_str(conn, getattr(t_attr, "Type", None)),
                                                )
                                            )

                    if cat_name == "Catalogs":
                        if catalog_props is None:
                            catalog_props = {}
                        try:
                            for prop_name in ("CodeLength", "CodeType", "DescriptionLength", "Hierarchical"):
                                val = getattr(obj_meta, prop_name, None)
                                if val is not None:
                                    try:
                                        catalog_props[prop_name] = str(conn.String(val))
                                    except Exception:
                                        catalog_props[prop_name] = str(val)
                                else:
                                    catalog_props[prop_name] = "None"
                        except Exception as e:
                            logger.debug("Failed reading catalog_props for %s: %s", obj_name, e)
                            catalog_props["catalog_props_error"] = f"unavailable: {type(e).__name__}"

                    discovered_objects.append(
                        MetadataObject(
                            category=cat_name,
                            name=obj_name,
                            synonym=obj_synonym,
                            register_kind=register_kind,
                            fields=fields,
                            tabular_sections=tabular_sections,
                            catalog_props=catalog_props,
                        )
                    )

            logger.debug("Discovered %d objects total. Running heuristic analysis...", len(discovered_objects))
            cards, txs, regs = CandidateDiscoveryHeuristic.analyze(discovered_objects)
            logger.debug("Heuristic analysis finished.")
            return TargetedMetadataInventory(
                configuration=conf_identity,
                discovered_at=datetime.now(UTC).isoformat(),
                objects=discovered_objects,
                candidate_cards=cards,
                candidate_transactions=txs,
                candidate_balance_sources=regs,
            )

        finally:
            self.connector.disconnect()
