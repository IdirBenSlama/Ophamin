"""The substrate-under-test layer.

    base            SubstrateUnderTest ABC + CycleResult
    mock            MockSubstrate — self-contained, makes the framework runnable
    kimera_adapter  KimeraAdapter — multi-component bridge to Kimera-SWM
                    (entity or any named component; subprocess or batch mode)
    field_catalog   KIMERA_FIELD_CATALOG + ScenarioFieldContract — declarative
                    knowledge of OrchestratorResult fields scenarios depend on
"""

from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest
from ophamin.seeing.substrate.field_catalog import (
    CATALOG_BY_NAME,
    CATALOG_FAMILIES,
    KIMERA_FIELD_CATALOG,
    CatalogedField,
    ContractViolation,
    FieldContract,
    ScenarioFieldContract,
    catalog_by_family,
    catalog_coverage,
    cataloged,
    validate_contract_against_raw,
)
from ophamin.seeing.substrate.kimera_adapter import (
    KIMERA_TARGETS,
    KimeraAdapter,
    KimeraAdapterError,
)
from ophamin.seeing.substrate.mock import MockSubstrate

__all__ = [
    "CATALOG_BY_NAME",
    "CATALOG_FAMILIES",
    "CatalogedField",
    "ContractViolation",
    "CycleResult",
    "FieldContract",
    "KIMERA_FIELD_CATALOG",
    "KIMERA_TARGETS",
    "KimeraAdapter",
    "KimeraAdapterError",
    "MockSubstrate",
    "ScenarioFieldContract",
    "SubstrateUnderTest",
    "catalog_by_family",
    "catalog_coverage",
    "cataloged",
    "validate_contract_against_raw",
]
