"""Pin the §7 reproduction-command fix landed in 0.29.0.

Per ``docs/proposals/PROOF_REPRODUCTION_COMMAND.md`` (Option C), the
``Scenario`` base class gained an opt-in ``runner_path`` metadata
field; when set, the auto-emitted ``Reproduction.command`` in each
proof points at that runner script rather than the historical
stale ``ophamin.cli scenario {name}`` form.

These tests pin:

1. The new ``runner_path`` attribute exists on the base ``Scenario``
   class and defaults to ``""``.
2. The 6 hand-rolled-runner scenarios all declare a ``runner_path``
   pointing at an existing file under ``examples/``.
3. When a scenario sets ``runner_path``, the emitted
   ``Reproduction.command`` references that path.
4. When a scenario does NOT set ``runner_path`` (falls through to
   base.py emission), the emitted ``Reproduction.command`` uses the
   ``run-all --scenarios`` form (the generic CLI fallback).

The test does NOT pin the EXACT command string format — only the
**presence** of the runner_path and the **routing logic**. The
command format can change at minor versions; the contract here is
that scenarios with hand-rolled runners get a working runner-path
form, and the field is wired through the base emission path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ophamin.measuring.scenarios import (
    ImmuneSiegeScenario,
    LogicTopologySiegeScenario,
    OrganizationalDissonanceScenario,
    PhilosophicalSelfReferenceScenario,
    RosettaScalingScenario,
    ThroughputCeilingScenario,
    ThroughputCeilingScenario as _Throughput,  # alias for clarity
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario
from ophamin.seeing.substrate import MockSubstrate


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_scenario_base_has_runner_path_attribute() -> None:
    """The base ``Scenario`` class declares ``runner_path: str = ''``."""
    assert hasattr(Scenario, "runner_path")
    assert isinstance(Scenario.runner_path, str)
    assert Scenario.runner_path == ""


@pytest.mark.parametrize(
    "cls, expected_path",
    [
        (ImmuneSiegeScenario, "examples/run_immune_siege.py"),
        (LogicTopologySiegeScenario, "examples/run_logic_topology_siege.py"),
        (OrganizationalDissonanceScenario, "examples/run_organizational_dissonance.py"),
        (PhilosophicalSelfReferenceScenario, "examples/run_philosophical_self_reference.py"),
        (RosettaScalingScenario, "examples/run_rosetta_scaling.py"),
        (ThroughputCeilingScenario, "examples/run_throughput_ceiling.py"),
    ],
)
def test_hand_rolled_runner_scenarios_declare_runner_path(
    cls: type[Scenario], expected_path: str
) -> None:
    """The 6 scenarios with hand-rolled runner scripts under
    ``examples/`` each declare their runner_path correctly."""
    assert cls.runner_path == expected_path
    runner_file = REPO_ROOT / expected_path
    assert runner_file.is_file(), (
        f"declared runner_path {expected_path!r} on {cls.__name__} "
        f"does not exist at {runner_file}"
    )


def test_reproduction_command_uses_runner_path_when_set() -> None:
    """A scenario with ``runner_path`` emits a Reproduction.command
    that references the runner path (no longer the stale
    ``ophamin.cli scenario`` form).

    Calls the ``_build_reproduction_command()`` helper directly
    rather than going through ``.run()`` — the helper's contract
    is what we're pinning, and ``.run()`` would require a real
    corpus (offensive-security-corpus is 4.4M records, not in CI).
    """
    scenario = ThroughputCeilingScenario(n_cycles=10)
    command = scenario._build_reproduction_command()
    assert "examples/run_throughput_ceiling.py" in command, (
        f"expected runner_path-form command, got: {command!r}"
    )
    # The stale form must be gone.
    assert "ophamin.cli scenario " not in command, (
        f"stale CLI form still present in command: {command!r}"
    )


def test_default_instantiable_scenario_emits_run_scenario_form() -> None:
    """A scenario without ``runner_path`` and with no required ctor
    args emits a ``examples/run_scenario.py {name}`` command via the
    R1 helper (landed at 0.30.0).

    Calls the helper directly — no full ``.run()`` invocation so
    the test doesn't depend on corpus availability on CI runners.
    """
    from ophamin.measuring.scenarios.spearman_crosscheck import (
        SpearmanCrosscheckScenario,
    )

    scenario = SpearmanCrosscheckScenario(n_pairs=2, sample_size=20)
    command = scenario._build_reproduction_command()
    assert "examples/run_scenario.py" in command
    assert scenario.name in command
    assert "ophamin.cli scenario " not in command  # stale form gone


def test_required_args_scenario_emits_inline_python_form() -> None:
    """A scenario with required ctor args emits an inline-Python form
    via the R1 helper. Validates by calling the helper directly
    against a scenario subclass that requires args (we can't
    instantiate cross-channel-mi without a real trajectory file, so
    we construct a minimal subclass)."""
    from ophamin.measuring.scenarios.base import (
        Scenario,
        ScenarioScore,
        Tier,
    )
    from ophamin.measuring.proof import Claim, Threshold

    class _NeedsArg(Scenario, register=False):
        name = "test-needs-arg"
        tier = Tier.SCIENTIFIC
        family = "test"
        goal = "test"
        explanation = "test"

        def __init__(self, required_arg: str):
            self.required_arg = required_arg

        def build_claim(self) -> Claim:  # pragma: no cover — helper only
            return Claim(
                statement="x",
                operationalization="x",
                threshold=Threshold(metric="m", comparator="<=", value=1.0),
                h0="x",
                h1="x",
            )

        def score(self, results):  # pragma: no cover — helper only
            return ScenarioScore(observed=0.0, evidence=[])

    instance = _NeedsArg(required_arg="/tmp/some/path")
    command = instance._build_reproduction_command()

    # The inline form must be a runnable Python invocation.
    assert "python -c" in command
    # It must reference the actual class.
    assert "_NeedsArg" in command
    # It must capture the actual argument value via self.<name>.
    assert "/tmp/some/path" in command
    # The stale form must be gone.
    assert "ophamin.cli scenario " not in command


def test_no_scenario_in_registry_still_emits_stale_string() -> None:
    """R1 closure pin: zero registered scenarios should emit a fresh
    proof whose Reproduction.command contains the stale CLI form.

    This is the structural completeness check — proves the R1
    refactor landed across all 32 sites.
    """
    import inspect
    from ophamin.measuring.scenarios import base as base_module
    from ophamin.measuring.scenarios import SCENARIOS

    # No scenario source contains the stale string anymore.
    scenario_modules = [
        inspect.getsourcefile(cls) for cls in SCENARIOS.values()
    ]
    for path in scenario_modules:
        if path is None:
            continue
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        assert "ophamin.cli scenario " not in src, (
            f"stale 'ophamin.cli scenario ' string still present in {path}"
        )

    # The helper exists on the base class.
    src = inspect.getsource(base_module)
    assert "def _build_reproduction_command" in src
    # All 3 routing branches are present.
    assert "if self.runner_path" in src
    assert "examples/run_scenario.py" in src
    assert 'python -c' in src  # inline-Python form for required-args case
