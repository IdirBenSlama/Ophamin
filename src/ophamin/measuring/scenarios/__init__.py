"""The catastrophic-scenario layer.

Each scenario binds a real corpus + a Kimera component target + a pre-registered
falsifiable claim, runs the corpus through the substrate, and emits a signed
Empirical Proof Record.

    Scenario                          the substrate-agnostic harness
    ScenarioScore                     a scenario's read of a completed run
    ImmuneSiegeScenario               offensive-security corpus -> GWF (false-positive ceiling)
    RosettaScalingScenario            FLORES-200 parallel text -> Rosetta canonical-agreement at K
    OrganizationalDissonanceScenario  Enron email -> dissonance-layer active-rate on cleared
    LogicTopologySiegeScenario        Linux kernel commits -> walker sustained-traversal rate

Scenarios are added in priority order; ``SCENARIOS`` is the registry.
"""

from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore
from ophamin.measuring.scenarios.immune_siege import ImmuneSiegeScenario
from ophamin.measuring.scenarios.logic_topology_siege import LogicTopologySiegeScenario
from ophamin.measuring.scenarios.organizational_dissonance import OrganizationalDissonanceScenario
from ophamin.measuring.scenarios.rosetta_scaling import RosettaScalingScenario

#: registered scenarios, by name
SCENARIOS: dict[str, type[Scenario]] = {
    ImmuneSiegeScenario.name: ImmuneSiegeScenario,
    RosettaScalingScenario.name: RosettaScalingScenario,
    OrganizationalDissonanceScenario.name: OrganizationalDissonanceScenario,
    LogicTopologySiegeScenario.name: LogicTopologySiegeScenario,
}

__all__ = [
    "Scenario",
    "ScenarioScore",
    "ImmuneSiegeScenario",
    "RosettaScalingScenario",
    "OrganizationalDissonanceScenario",
    "LogicTopologySiegeScenario",
    "SCENARIOS",
    "DEFAULT_SIGN_KEY",
]
