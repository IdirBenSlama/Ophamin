"""Behavioural drift detection — Layer C of Ophamin's Kimera-co-evolution stack.

Layer A surfaces *structural* drift (a field appeared or disappeared between
two Kimera commits). Layer C surfaces *behavioural* drift: the field is still
there, but its empirical value distribution shifted. The Wilson 95% CI not
overlapping between two runs of the same claim on different Kimera commits is
the load-bearing signal.

    ProofIndex          loads and groups EmpiricalProofRecord JSONs by
                        (statistic_name, kimera_git_commit). One index can
                        span every signed run under ``proofs/``.
    DriftReport         computes per-claim, per-commit deltas across two
                        proof records of the same primary claim. Flags
                        non-overlapping Wilson CIs as significant drift.
    detect_drift        the canonical entry point — feeds a ProofIndex into a
                        DriftReport per primary claim.

Behavioural drift only makes sense across **separate Kimera commits**.
Comparing two proof records on the *same* commit produces a noise estimate
(useful as a sanity check, never as a drift claim).
"""

from __future__ import annotations

from ophamin.comparing.drift.delta_report import DeltaEntry, DriftReport, ci_overlaps
from ophamin.comparing.drift.proof_index import ProofIndex, ProofIndexEntry, detect_drift

__all__ = [
    "DeltaEntry",
    "DriftReport",
    "ProofIndex",
    "ProofIndexEntry",
    "ci_overlaps",
    "detect_drift",
]
