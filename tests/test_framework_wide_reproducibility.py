"""Framework-wide reproducibility audit (RFC 0002 Phase E4 closeout).

The 0.11.0 release shipped `DeterministicSeedAuditScenario` + the
`reproducibility_hash` helper that prove ONE target scenario at a time
produces bit-identical proofs across two independent invocations.

This file extends that contract to **every scenario that exposes a
`seed` parameter** — the audit-eligible set, in framework parlance.
A new scenario landing without honouring its seed is a Phase E4
contract violation; the gate catches it at PR time.

How discovery works
===================

The test walks `SCENARIOS` (the global scenario registry) and selects
every class whose `__init__` accepts a `seed` parameter. For each
selected target, it constructs a `DeterministicSeedAuditScenario`
pointing at that target with minimal-cost kwargs (per
``_AUDIT_KWARGS`` below) and asserts the emitted proof is
``VALIDATED``.

How to extend
=============

When you add a new seed-taking scenario, add a line to
``_AUDIT_KWARGS`` with the minimal kwargs that exercise the scenario
in CI-friendly time. If your scenario doesn't need a custom kwargs
override, the test falls back to ``{"seed": 20260517}`` — the
canonical audit seed used across the framework.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from ophamin.measuring.scenarios import SCENARIOS, ScenarioFieldContractViolation
from ophamin.measuring.scenarios.deterministic_seed_audit import (
    DeterministicSeedAuditScenario,
)
from ophamin.seeing.corpus.base import CorpusUnavailableError
from ophamin.seeing.substrate.mock import MockSubstrate


# Minimal-cost kwargs per audit-eligible scenario. The default
# constructor kwargs would emit fine but burn too much CI time — these
# overrides keep each audit well under 5 seconds.
_AUDIT_KWARGS: dict[str, dict[str, Any]] = {
    "crdt-laws": {"n_sequences": 2, "ops_per_sequence": 2, "seed": 20260517},
    "rosetta-scaling": {"seed": 20260517},
    "bayesian-phi-posterior": {
        "seed": 20260517,
        "sample_sizes": (20, 50),
        "draws": 100,
        "tune": 50,
    },
    "bayesian-phi-posterior-crosscheck": {
        "seed": 20260517,
        "n_samples": 80,
        "pymc_draws": 300,
        "pymc_tune": 100,
        "numpyro_samples": 300,
        "numpyro_warmup": 100,
    },
    "wilson-ci-crosscheck": {
        "seed": 20260517,
        "n_pairs": 20,
        "max_n": 200,
    },
    "spearman-crosscheck": {
        "seed": 20260517,
        "n_pairs": 8,
        "sample_size": 40,
    },
    "pearson-crosscheck": {
        "seed": 20260518,
        "n_pairs": 8,
        "sample_size": 40,
    },
    "welch-t-crosscheck": {
        "seed": 20260518,
        "n_pairs": 8,
        "sample_size": 40,
    },
    "anova-crosscheck": {
        "seed": 20260518,
        "n_datasets": 8,
        "sample_size": 20,
    },
    "mann-whitney-crosscheck": {
        "seed": 20260518,
        "n_pairs": 8,
        "sample_size": 40,
    },
    # Live-Kimera scenario: takes `seed` (so it's audit-eligible) but its
    # run() reads manifold-state fields the MockSubstrate doesn't emit. These
    # kwargs only need to let it CONSTRUCT (return_windows is required); the
    # audit below skips it when the mock can't satisfy its field contract.
    "finance-path-magnitude-fidelity": {
        "seed": 20260517,
        "return_windows": ((0.01, -0.02, 0.03, -0.01, 0.02),),
        "n_orderings": 6,
    },
}


def _audit_eligible_scenarios() -> list[tuple[str, type[Any]]]:
    """Return every registered scenario whose __init__ takes `seed`.

    Excludes the audit scenario itself (auditing the auditor is a
    different test — see test_deterministic_seed_audit.py's
    end-to-end test for that).
    """
    out: list[tuple[str, type[Any]]] = []
    for name, cls in sorted(SCENARIOS.items()):
        if name == "deterministic-seed-audit":
            continue
        try:
            sig = inspect.signature(cls.__init__)
        except (TypeError, ValueError):
            continue
        if "seed" in sig.parameters:
            out.append((name, cls))
    return out


_ELIGIBLE = _audit_eligible_scenarios()


@pytest.mark.parametrize(
    "name,cls",
    _ELIGIBLE,
    ids=[name for name, _ in _ELIGIBLE],
)
def test_every_seed_taking_scenario_satisfies_reproducibility_contract(
    name: str,
    cls: type[Any],
) -> None:
    """Every audit-eligible scenario must produce bit-identical
    reproducibility-form proofs across two independent invocations.

    This is the load-bearing assertion of RFC 0002 Phase E4: the
    framework's reproducibility contract holds for every scenario
    that's structurally testable.
    """
    kwargs = _AUDIT_KWARGS.get(name, {"seed": 20260517})
    audit = DeterministicSeedAuditScenario(
        target_scenario_name=name,
        target_scenario_kwargs=kwargs,
    )
    try:
        proof = audit.run(substrate=MockSubstrate(seed=1))
    except CorpusUnavailableError as exc:
        # The target scenario's required corpus isn't on this runner
        # (typical for CI where third-party-licensed corpora like
        # FLORES-200 can't be redistributed). The reproducibility
        # contract still applies to this scenario — the test is just
        # not measurable in this environment.
        pytest.skip(
            f"Scenario {name!r} requires corpus that's not available "
            f"here: {exc}. Run with the corpus downloaded to verify "
            f"the reproducibility contract for this scenario."
        )
    except ScenarioFieldContractViolation as exc:
        # A live-substrate scenario (e.g. a Kimera comparison) whose
        # field contract the MockSubstrate can't satisfy — the same
        # "not measurable in this environment" case as a missing corpus,
        # just along the substrate axis instead of the corpus axis. Its
        # reproducibility contract still holds; it must be audited against
        # the real substrate that emits the required fields.
        pytest.skip(
            f"Scenario {name!r} requires substrate fields the MockSubstrate "
            f"does not emit: {exc}. Run against the real substrate (e.g. the "
            f"Kimera adapter) to verify its reproducibility contract."
        )
    assert proof.verdict.outcome == "VALIDATED", (
        f"Scenario {name!r} fails the reproducibility contract — two "
        f"independent runs with seed={kwargs.get('seed')} produced "
        f"different reproducibility-form hashes. "
        f"first={proof.evidence[0].detail['reproducibility_hash_first'][:16]}..., "
        f"second={proof.evidence[0].detail['reproducibility_hash_second'][:16]}..., "
        f"verdict_agreement={proof.evidence[0].detail['verdict_agreement']}. "
        f"Diff the two proof_ids ({proof.evidence[0].detail['first_proof_id'][:16]}..., "
        f"{proof.evidence[0].detail['second_proof_id'][:16]}...) to "
        f"isolate the source of non-determinism."
    )


def test_audit_eligible_set_is_non_empty() -> None:
    """Sanity: the framework must have at least one auditable scenario.

    Failing this means either the discovery logic broke OR every
    scenario in the registry stopped taking a `seed` parameter —
    both of which warrant investigation. As of 0.11.0 we expect at
    least three: crdt-laws, rosetta-scaling, bayesian-phi-posterior.
    """
    assert len(_ELIGIBLE) >= 3, (
        f"Expected ≥ 3 audit-eligible scenarios; found {len(_ELIGIBLE)}: "
        f"{[name for name, _ in _ELIGIBLE]}"
    )


def test_audit_eligible_set_matches_pinned_list() -> None:
    """Drift detector: when a new seed-taking scenario lands, this test
    flags that ``_AUDIT_KWARGS`` should be updated to give the new
    scenario optimal kwargs.

    The test is INFORMATIONAL rather than a hard gate — a new scenario
    falls back to ``{"seed": 20260517}`` and runs with its defaults
    for everything else, which is usually fine for CI.
    """
    eligible_names = {name for name, _ in _ELIGIBLE}
    pinned_names = set(_AUDIT_KWARGS.keys())
    missing_overrides = eligible_names - pinned_names
    extra_overrides = pinned_names - eligible_names
    # Extra overrides for now-removed scenarios are a real defect:
    assert not extra_overrides, (
        f"_AUDIT_KWARGS lists kwargs for scenarios not in the registry: "
        f"{sorted(extra_overrides)}. Remove the stale entries."
    )
    # Missing overrides only become real defects if the default
    # `{"seed": 20260517}` is too slow / wrong-shaped. The
    # parametrize-driven test above will surface that as a test
    # failure on its own.
    if missing_overrides:
        # Emit a hint without failing — the test is informational.
        print(
            f"\nINFO: new audit-eligible scenarios not yet in "
            f"_AUDIT_KWARGS: {sorted(missing_overrides)}. The default "
            f"kwargs `{{'seed': 20260517}}` will be used; if the audit "
            f"is slow or fails for one of these, add an explicit entry."
        )
