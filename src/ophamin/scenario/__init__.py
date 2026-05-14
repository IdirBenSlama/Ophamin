"""The catastrophic-scenario layer.

Each scenario binds a real corpus + a Kimera component target + a pre-registered
falsifiable claim, runs the corpus through the substrate, and emits a signed
Empirical Proof Record.

    Scenario              the substrate-agnostic harness
    ScenarioScore         a scenario's read of a completed run
    ImmuneSiegeScenario   offensive-security corpus -> GWF (false-positive ceiling)

Scenarios are added in priority order; ``SCENARIOS`` is the registry.
"""

from ophamin.scenario.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore
from ophamin.scenario.immune_siege import ImmuneSiegeScenario

#: registered scenarios, by name
SCENARIOS: dict[str, type[Scenario]] = {
    ImmuneSiegeScenario.name: ImmuneSiegeScenario,
}

__all__ = [
    "Scenario",
    "ScenarioScore",
    "ImmuneSiegeScenario",
    "SCENARIOS",
    "DEFAULT_SIGN_KEY",
]
