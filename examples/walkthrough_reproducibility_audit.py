"""Concept walkthrough — reproducibility audit (RFC 0002 Phase E4).

Ophamin's claim: every scenario produces a bit-identical proof for
the same ``(seed, corpus, substrate_commit, ophamin_commit)`` tuple.
This walkthrough demonstrates the audit primitives shipped in 0.11.x:

1. :class:`DeterministicSeedAuditScenario` — runs a target scenario
   twice with identical kwargs, computes the reproducibility hash of
   each emitted proof, VALIDATED iff bit-identical.
2. :func:`reproducibility_hash` — the canonical-form hash that strips
   wall-clock fields (timestamps, PROV-O activity times,
   reproduction.command absolute paths, timing-suffixed pillar
   detail keys) but preserves every load-bearing byte.

Run with::

    PYTHONPATH=src python examples/walkthrough_reproducibility_audit.py

The walkthrough audits ``crdt-laws`` (the canonical demo target) and
shows the matching hashes side by side. Safe to import; only runs as
``__main__``.
"""

from __future__ import annotations

from ophamin.measuring.scenarios.deterministic_seed_audit import (
    DeterministicSeedAuditScenario,
    reproducibility_hash,
)
from ophamin.seeing.substrate.mock import MockSubstrate


def main() -> None:
    print("# Reproducibility audit walkthrough — RFC 0002 Phase E4")
    print()
    print("Every scenario in Ophamin's registry must produce a bit-identical")
    print("proof for the same (seed, corpus, substrate_commit, ophamin_commit)")
    print("tuple. Without this property, the project's reproducibility claim")
    print("is rhetoric; with it, an external reviewer can rebuild a release")
    print("and demand byte-equal output.")

    # === Step 1: run the audit
    print("\n## Step 1: audit `crdt-laws`")
    audit = DeterministicSeedAuditScenario(
        target_scenario_name="crdt-laws",
        target_scenario_kwargs={
            "n_sequences": 3,
            "ops_per_sequence": 3,
            "seed": 20260517,
        },
    )
    proof = audit.run(substrate=MockSubstrate(seed=1))
    detail = proof.evidence[0].detail

    print(f"\n  Outcome:          {proof.verdict.outcome}")
    print(f"  Observed value:   {proof.verdict.observed_value}")
    print(f"  Threshold:        {proof.verdict.threshold.value}")
    print()
    print(f"  First run proof_id:   {detail['first_proof_id'][:32]}...")
    print(f"  Second run proof_id:  {detail['second_proof_id'][:32]}...")
    print(f"  (Different by design — created_at timestamps drift)")
    print()
    print(f"  First reproducibility_hash:   {detail['reproducibility_hash_first'][:32]}...")
    print(f"  Second reproducibility_hash:  {detail['reproducibility_hash_second'][:32]}...")
    match = (
        detail["reproducibility_hash_first"] == detail["reproducibility_hash_second"]
    )
    print(f"  → match: {match} (the load-bearing claim)")

    # === Step 2: what gets stripped, what gets preserved
    print("\n## Step 2: what `reproducibility_hash` strips")
    print()
    print("  Stripped (wall-clock + per-invocation):")
    print("    - identity.created_at")
    print("    - preregistration.preregistered_at")
    print("    - provenance (W3C PROV-O activity timestamps)")
    print("    - reproduction.command (may have absolute paths)")
    print("    - PillarEvidence.detail keys ending in _seconds/_avg_ms/")
    print("      _wall_time/_perf_counter")
    print()
    print("  Preserved (everything load-bearing):")
    print("    - schema_version")
    print("    - claim (statement, operationalization, threshold, h0, h1)")
    print("    - data.substrate_name, data.datasets")
    print("    - evidence: statistic_name, statistic_value, library, p_value")
    print("    - verdict: outcome, observed_value, threshold, reasoning")

    # === Step 3: direct use of the helper
    print("\n## Step 3: direct use of `reproducibility_hash`")
    print()
    print("  Two independent invocations of the SAME audit scenario emit")
    print("  proofs whose top-level reproducibility hashes match too:")
    audit_b = DeterministicSeedAuditScenario(
        target_scenario_name="crdt-laws",
        target_scenario_kwargs={
            "n_sequences": 3,
            "ops_per_sequence": 3,
            "seed": 20260517,
        },
    )
    proof_b = audit_b.run(substrate=MockSubstrate(seed=1))
    h_outer_a = reproducibility_hash(proof)
    h_outer_b = reproducibility_hash(proof_b)
    print(f"    proof   reproducibility_hash: {h_outer_a[:32]}...")
    print(f"    proof_b reproducibility_hash: {h_outer_b[:32]}...")
    print(f"  → match: {h_outer_a == h_outer_b}")

    # === Step 4: framework-wide gate
    print("\n## Step 4: framework-wide audit")
    print()
    print("  Since 0.11.1, `tests/test_framework_wide_reproducibility.py`")
    print("  runs this audit against EVERY scenario in the registry whose")
    print("  __init__ takes a `seed` parameter. As of 0.11.2 the eligible")
    print("  set is: crdt-laws, rosetta-scaling, bayesian-phi-posterior.")
    print()
    print("  Adding a new audit-eligible scenario? The CI gate catches a")
    print("  non-determinism leak at PR time rather than at downstream-")
    print("  replay time. Update `_AUDIT_KWARGS` if your scenario needs")
    print("  custom kwargs to run in CI-friendly time.")

    # === Invariants we can pin
    assert proof.verdict.outcome == "VALIDATED", "Audit must validate"
    assert detail["verdict_agreement"] is True, "Both runs must agree"
    assert h_outer_a == h_outer_b, "Audit-level reproducibility must also hold"

    print("\n✓ Reproducibility audit walkthrough complete. Contract validated.")


if __name__ == "__main__":
    main()
