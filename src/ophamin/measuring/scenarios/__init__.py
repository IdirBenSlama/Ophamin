"""The catastrophic-scenario layer.

Each scenario binds a real corpus + a Kimera component target + a pre-registered
falsifiable claim, runs the corpus through the substrate, and emits a signed
Empirical Proof Record.

Scenarios come in three experimentation tiers (the user's framing):

    Scientific tier — claims about substrate *behaviour*
        ImmuneSiegeScenario               GWF false-positive ceiling
        RosettaScalingScenario            Rosetta cross-language agreement
        OrganizationalDissonanceScenario  dissonance active-rate on cleared
        LogicTopologySiegeScenario        walker sustained-traversal rate

    Engineering tier — claims about substrate *cost*
        ThroughputCeilingScenario             p95 cycle wall-time ceiling

    Philosophical tier — claims about substrate *self-model*
        PhilosophicalSelfReferenceScenario    Cohen's d on dissonance:
                                              self-referential vs neutral text

All tiers share the same Scenario / ScenarioScore / signed proof-record
discipline. They differ in what fields they read from CycleResult.raw + how
they pre-register the falsifiable threshold.
"""

from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore
from ophamin.measuring.scenarios.immune_siege import ImmuneSiegeScenario
from ophamin.measuring.scenarios.interface_contract_stability import (
    InterfaceContractStabilityScenario,
)
from ophamin.measuring.scenarios.logic_topology_siege import LogicTopologySiegeScenario
from ophamin.measuring.scenarios.organizational_dissonance import OrganizationalDissonanceScenario
from ophamin.measuring.scenarios.philosophical_self_reference import (
    PhilosophicalSelfReferenceScenario,
    SELF_REFERENTIAL_TEXTS,
)
from ophamin.measuring.scenarios.rosetta_scaling import RosettaScalingScenario
from ophamin.measuring.scenarios.throughput_ceiling import ThroughputCeilingScenario

#: registered scenarios, by name
SCENARIOS: dict[str, type[Scenario]] = {
    ImmuneSiegeScenario.name: ImmuneSiegeScenario,
    RosettaScalingScenario.name: RosettaScalingScenario,
    OrganizationalDissonanceScenario.name: OrganizationalDissonanceScenario,
    LogicTopologySiegeScenario.name: LogicTopologySiegeScenario,
    ThroughputCeilingScenario.name: ThroughputCeilingScenario,
    PhilosophicalSelfReferenceScenario.name: PhilosophicalSelfReferenceScenario,
    InterfaceContractStabilityScenario.name: InterfaceContractStabilityScenario,
}

__all__ = [
    "Scenario",
    "ScenarioScore",
    "ImmuneSiegeScenario",
    "RosettaScalingScenario",
    "OrganizationalDissonanceScenario",
    "LogicTopologySiegeScenario",
    "ThroughputCeilingScenario",
    "PhilosophicalSelfReferenceScenario",
    "InterfaceContractStabilityScenario",
    "SELF_REFERENTIAL_TEXTS",
    "SCENARIOS",
    "DEFAULT_SIGN_KEY",
]
