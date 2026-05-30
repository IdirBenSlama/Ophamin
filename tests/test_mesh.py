"""Mesh observation — watching Nodes pool experience across the wire.

Pins that the mesh observatory measures honestly: re-performance is order-keeping
(a reordered replay is NOT faithful — the path is the meaning), and pooled-
experience convergence rises with shared experience. Built against controlled
two-Node partitions, ready for the live mesh.
"""

from ophamin.comparing.mesh import (
    mesh_observation,
    partition_reperformance_fidelity,
    pooled_experience_convergence,
)


def _partition(primes, ops):
    return {
        "primes": tuple(primes),
        "echoform_sequence": [{"op": o, "delta_s": 0.0} for o in ops],
        "cronos_timestamp": 1,
        "gwf_signature": "cleared",
    }


A = _partition(["2", "3", "5"], ["OP_SCALE_001", "OP_MERGE_001"])


def test_faithful_reperformance_is_one():
    twin = _partition(["2", "3", "5"], ["OP_SCALE_001", "OP_MERGE_001"])
    assert partition_reperformance_fidelity(A, twin) == 1.0


def test_reordered_replay_is_not_faithful():
    # Same primes + ops, different ORDER → < 1.0. The path is the meaning.
    reordered = _partition(["5", "3", "2"], ["OP_MERGE_001", "OP_SCALE_001"])
    f = partition_reperformance_fidelity(A, reordered)
    assert f is not None and f < 1.0


def test_corrupted_wire_lowers_fidelity():
    dropped = _partition(["2", "3"], ["OP_SCALE_001"])  # lost a prime + an op
    assert partition_reperformance_fidelity(A, dropped) < 1.0


def test_primes_only_is_an_honest_partial_when_echoform_absent():
    a = {"primes": ("2", "3"), "echoform_sequence": None}
    b = {"primes": ("2", "3"), "echoform_sequence": None}
    assert partition_reperformance_fidelity(a, b) == 1.0  # primes match; no echoform to score


def test_reperformance_none_when_nothing_to_replay():
    assert partition_reperformance_fidelity({"primes": None}, A) is None
    assert partition_reperformance_fidelity(None, A) is None


def test_pooled_convergence_extremes_and_middle():
    assert pooled_experience_convergence([["2", "3", "5"], ["2", "3", "5"]]) == 1.0  # converged
    assert pooled_experience_convergence([["2", "3"], ["7", "11"]]) == 0.0           # isolated
    mid = pooled_experience_convergence([["2", "3", "5"], ["3", "5", "7"]])
    assert mid is not None and 0.0 < mid < 1.0                                       # partial pool
    assert pooled_experience_convergence([["2", "3"]]) is None                       # < 2 nodes


def test_mesh_observation_bundles_both():
    obs = mesh_observation(A, A, [["2", "3", "5"], ["2", "3", "5"]])
    assert obs["reperformance_fidelity"] == 1.0
    assert obs["pooled_convergence"] == 1.0
    assert obs["n_nodes"] == 2
