"""The substrate-under-test layer.

    base            SubstrateUnderTest ABC + CycleResult
    mock            MockSubstrate — self-contained, makes the framework runnable
    kimera_adapter  KimeraAdapter — multi-component bridge to Kimera-SWM
                    (entity or any named component; subprocess or batch mode)
"""

from ophamin.substrate.base import CycleResult, SubstrateUnderTest
from ophamin.substrate.kimera_adapter import (
    KIMERA_TARGETS,
    KimeraAdapter,
    KimeraAdapterError,
)
from ophamin.substrate.mock import MockSubstrate

__all__ = [
    "SubstrateUnderTest",
    "CycleResult",
    "MockSubstrate",
    "KimeraAdapter",
    "KimeraAdapterError",
    "KIMERA_TARGETS",
]
