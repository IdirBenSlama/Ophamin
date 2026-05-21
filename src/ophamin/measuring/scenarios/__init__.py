"""The catastrophic-scenario layer.

Each scenario binds a real corpus + a Kimera component target + a pre-registered
falsifiable claim, runs the corpus through the substrate, and emits a signed
Empirical Proof Record.

Scenarios come in five experimentation tiers:

    Scientific tier — claims about substrate *behaviour*
        ImmuneSiegeScenario               GWF false-positive ceiling
        RosettaScalingScenario            Rosetta cross-language agreement
        OrganizationalDissonanceScenario  dissonance active-rate on cleared
        LogicTopologySiegeScenario        walker sustained-traversal rate
        InterfaceContractStabilityScenario OrchestratorResult field-contract
        SubstrateCompletenessScenario     repo-wide orphan-rate ceiling
        MemoryAsDeformationScenario       cycle-level re-exposure Jaccard floor

    Engineering tier — claims about substrate *cost*
        ThroughputCeilingScenario         p95 cycle wall-time ceiling

    Philosophical tier — claims about substrate *self-model*
        PhilosophicalSelfReferenceScenario Cohen's d on dissonance:
                                           self-referential vs neutral text

    Empirical-deep tier — substrate-physics characterisation
        BayesianPhiPosteriorScenario      Φ posterior HDI contraction
        CausalDiscoveryScenario           PCMCI directed-link recovery
        CrossChannelMutualInformationScenario  cross-channel MI floor
        PrimeStructureScenario            concept-Jaccard floor + F.1.1
        PrimeFactorizationScenario        p_identity invariance
        PrimeEcosystemScenario            Alexandria fused-key persistence
        PrimeDirectLookupScenario         ArachneProtocol direct-lookup
        PrimeCrossInstanceScenario        cross-process p_identity invariance
        QuantumBasisCorrelationScenario   content-class effect on QBE

    Measurement-machinery tier — validation of upstream libraries
        CRDTLawsScenario                  Yjs CRDT convergence
        BayesianPhiPosteriorCrosscheckScenario  PyMC ↔ NumPyro cross-framework
        WilsonCICrosscheckScenario        scipy ↔ statsmodels Wilson CI
        SpearmanCrosscheckScenario        scipy ↔ pingouin Spearman ρ
        PearsonCrosscheckScenario         scipy ↔ numpy ↔ pingouin Pearson r
        WelchTTestCrosscheckScenario      scipy ↔ statsmodels ↔ pingouin Welch t
        OneWayAnovaCrosscheckScenario     scipy ↔ statsmodels ↔ pingouin one-way ANOVA
        MannWhitneyUCrosscheckScenario    scipy ↔ pingouin Mann-Whitney U (non-param)

All tiers share the same Scenario / ScenarioScore / signed proof-record
discipline. They differ in what fields they read from CycleResult.raw + how
they pre-register the falsifiable threshold.

Registration
============

Every concrete :class:`Scenario` subclass auto-registers in
:data:`SCENARIOS` at class-definition time via the
:meth:`Scenario.__init_subclass__` hook. This module's job is to
**import every scenario module** so the hook fires; auto-walk via
:func:`pkgutil.iter_modules` makes this exhaustive without manual
edits.

A duplicate ``name`` across two subclasses raises
:class:`DuplicateScenarioNameError` at import time — loud-failure
keeps the registry single-valued.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from ophamin.measuring.scenarios.base import (
    DEFAULT_SIGN_KEY,
    DuplicateScenarioNameError,
    SCENARIOS,
    Scenario,
    ScenarioFieldContractViolation,
    ScenarioMetadataMissingError,
    ScenarioNameNotOverriddenError,
    ScenarioScore,
    Tier,
)

# Modules excluded from the auto-walk: infrastructure modules that are NOT
# scenarios themselves (and that, in some cases, depend on scenarios being
# already importable). Keeping this list explicit means the auto-walk's
# coverage is reviewable at a glance.
_AUTO_WALK_EXCLUDE: frozenset[str] = frozenset({"base", "helpers"})


def _auto_import_scenario_modules() -> tuple[ModuleType, ...]:
    """Import every ``.py`` module in this package (except the exclude list).

    Each import fires :meth:`Scenario.__init_subclass__` for every concrete
    subclass declared in that module, populating :data:`SCENARIOS`.

    Loud-failure: if a scenario module fails to import (for example, a
    syntax error or a required dependency that was supposed to be optional
    is unexpectedly missing), the original exception is re-raised with
    the offending module name in the chain. There is no silent skip — a
    scenario that can't import is a real problem the operator needs to
    see.

    Returns the tuple of imported module objects so callers / tests can
    introspect what was loaded.
    """
    imported: list[ModuleType] = []
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.ispkg:
            continue
        name = module_info.name
        if name.startswith("_") or name in _AUTO_WALK_EXCLUDE:
            continue
        full_name = f"{__name__}.{name}"
        try:
            module = importlib.import_module(full_name)
        except Exception as exc:  # noqa: BLE001 — re-raised with context
            raise ImportError(
                f"failed to auto-import scenario module {full_name!r}: {exc}"
            ) from exc
        imported.append(module)
    return tuple(imported)


# Fire the hook for every scenario class in this package.
_AUTO_IMPORTED_MODULES: tuple[ModuleType, ...] = _auto_import_scenario_modules()


# --- back-compat re-exports -------------------------------------------------
#
# Prior versions of this package exposed scenario classes by name at the
# package level (e.g. ``from ophamin.measuring.scenarios import
# ImmuneSiegeScenario``). These re-exports preserve that surface. New
# scenarios do not need to be added here — the registry is the canonical
# discovery mechanism. These names exist only for back-compat with code
# that imports them directly.

from ophamin.measuring.scenarios.immune_siege import ImmuneSiegeScenario  # noqa: E402
from ophamin.measuring.scenarios.interface_contract_stability import (  # noqa: E402
    InterfaceContractStabilityScenario,
)
from ophamin.measuring.scenarios.logic_topology_siege import (  # noqa: E402
    LogicTopologySiegeScenario,
)
from ophamin.measuring.scenarios.manifold_topology import (  # noqa: E402
    ManifoldTopologyScenario,
)
from ophamin.measuring.scenarios.memory_deformation_flow import (  # noqa: E402
    MemoryDeformationFlowScenario,
)
from ophamin.measuring.scenarios.organizational_dissonance import (  # noqa: E402
    OrganizationalDissonanceScenario,
)
from ophamin.measuring.scenarios.philosophical_self_reference import (  # noqa: E402
    PhilosophicalSelfReferenceScenario,
    SELF_REFERENTIAL_TEXTS,
)
from ophamin.measuring.scenarios.rosetta_scaling import RosettaScalingScenario  # noqa: E402
from ophamin.measuring.scenarios.substrate_completeness import (  # noqa: E402
    SubstrateCompletenessScenario,
)
from ophamin.measuring.scenarios.throughput_ceiling import ThroughputCeilingScenario  # noqa: E402


__all__ = [
    "DEFAULT_SIGN_KEY",
    "DuplicateScenarioNameError",
    "ImmuneSiegeScenario",
    "InterfaceContractStabilityScenario",
    "LogicTopologySiegeScenario",
    "ManifoldTopologyScenario",
    "MemoryDeformationFlowScenario",
    "OrganizationalDissonanceScenario",
    "PhilosophicalSelfReferenceScenario",
    "RosettaScalingScenario",
    "SCENARIOS",
    "SELF_REFERENTIAL_TEXTS",
    "Scenario",
    "ScenarioFieldContractViolation",
    "ScenarioMetadataMissingError",
    "ScenarioNameNotOverriddenError",
    "ScenarioScore",
    "SubstrateCompletenessScenario",
    "ThroughputCeilingScenario",
    "Tier",
]
