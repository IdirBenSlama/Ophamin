"""Mesh observation — watching Nodes pool experience across the wire.

Kimera's topology is Node → Archipel → Indra's Net: a Node is one substrate, an
Archipel a local mesh, Indra's Net the global pooled experience. "Intelligence is
constant across vessels; only experience scales with connectivity." Nothing
imposes onto a substrate — the wire carries **partitions** (the re-performable
unit: primes + Echoform operator sequence + Cronos + GWF), not commands.

This module is the observatory's mesh-watching core: it does NOT drive a mesh, it
**measures** one. Two readings, both order-aware where the substrate is path-
dependent:

  * ``partition_reperformance_fidelity`` — did the wire carry a partition
    faithfully? (the trust a mesh stands on: the receiver re-performed the same
    primes + the same operator sequence, in order — not just the same *set*.)
  * ``pooled_experience_convergence`` — how much experience has actually pooled
    across N Nodes (the Indra's-Net readout).

Built against partition dicts from ``observables.partition()`` so it works on a
controlled two-Node rig today and on the live mesh the moment the wire flows —
the "born together" discipline: the observation that makes wiring the connective
tissue safe and legible.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ophamin.seeing.substrate.observables import jaccard, sequence_edit_divergence


def partition_reperformance_fidelity(
    emitted: "Mapping[str, Any] | None",
    received: "Mapping[str, Any] | None",
) -> "float | None":
    """How faithfully ``received`` re-performed ``emitted`` ∈ [0, 1], or ``None``.

    1.0 = the wire carried the partition perfectly: the receiving Node landed on
    the **same primes in the same order** and replayed the **same Echoform
    operator sequence**. This is order-keeping by construction (a re-performance
    that reorders the walk is not faithful — the path *is* the meaning), so it
    reuses the trajectory edit-distance rather than a set comparison.

    Scored over the two re-performable constituents: the prime chain and the
    Echoform operator sequence. If only the primes are present on both sides, the
    fidelity is the prime score alone (an honest partial, not a fabricated whole).
    ``None`` if either side lacks even a prime chain (nothing to re-perform).
    """
    if not emitted or not received:
        return None
    ep, rp = emitted.get("primes"), received.get("primes")
    if not ep or not rp:
        return None
    prime_fidelity = 1.0 - sequence_edit_divergence(ep, rp)

    ee, re_ = emitted.get("echoform_sequence"), received.get("echoform_sequence")
    if not ee or not re_:
        return prime_fidelity  # only the primes were re-performable here
    e_ops = [str(x.get("op")) for x in ee if isinstance(x, Mapping)]
    r_ops = [str(x.get("op")) for x in re_ if isinstance(x, Mapping)]
    echoform_fidelity = 1.0 - sequence_edit_divergence(e_ops, r_ops)
    return (prime_fidelity + echoform_fidelity) / 2.0


def pooled_experience_convergence(
    node_prime_sets: "Sequence[Sequence[str] | frozenset[str]]",
) -> "float | None":
    """How much experience has pooled across N Nodes ∈ [0, 1], or ``None``.

    Mean pairwise overlap of the Nodes' experienced primes: 1.0 = the Nodes have
    fully converged (identical pooled experience); 0 = isolated Nodes sharing
    nothing. This is the Indra's-Net readout — "only experience scales with
    connectivity" made into a number: it rises as Nodes exchange partitions and
    pool what they have lived.

    Convergence ACROSS Nodes is a shared-content question (have they lived the
    same things?), so it is set-based here — distinct from order-mattering WITHIN
    a single Node's path. ``None`` if fewer than two non-empty Nodes.
    """
    sets = [frozenset(s) for s in node_prime_sets if s]
    if len(sets) < 2:
        return None
    pairs = [(i, j) for i in range(len(sets)) for j in range(i + 1, len(sets))]
    return sum(jaccard(sets[i], sets[j]) for i, j in pairs) / len(pairs)


def mesh_observation(
    emitted: "Mapping[str, Any] | None",
    received: "Mapping[str, Any] | None",
    node_prime_sets: "Sequence[Sequence[str] | frozenset[str]]",
) -> "dict[str, Any]":
    """One bundled mesh reading: re-performance fidelity + pooled convergence.

    The two numbers a mesh observatory reports for a partition exchange — whether
    the wire carried it faithfully, and how much experience has pooled. Either
    may be ``None`` (an honest gap), never fabricated.
    """
    return {
        "reperformance_fidelity": partition_reperformance_fidelity(emitted, received),
        "pooled_convergence": pooled_experience_convergence(node_prime_sets),
        "n_nodes": len([s for s in node_prime_sets if s]),
    }
