"""Canonical substrate-observable extractors — one home for reading Kimera's
OrchestratorResult fields out of a :class:`CycleResult`.

Before this module, every memory/finance scenario carried its own copy of
``_concept_set`` / ``_prime_set`` / ``_scar_count`` / ``_state_vector`` /
``_jaccard`` / ``_as_finite_float`` — copy-paste that drifts. These are the
single canonical versions; scenarios import them so a fix lands once.

Pairs with :mod:`ophamin.seeing.substrate.field_catalog` (the *declarative*
layer — what a field is and which scenario depends on it). This module is the
*extraction* layer — how to read it safely:

  * non-finite floats (NaN/Inf, which the Kimera runner serialises as strings)
    become ``None`` rather than poisoning a delta/monotonicity computation;
  * a failed or empty cycle yields ``None`` (a gap), never a fabricated 0 —
    so "the substrate crashed" never gets conflated with "the substrate said 0".
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from ophamin.seeing.substrate.base import CycleResult


def as_finite_float(value: Any) -> float | None:
    """Coerce a raw field to a finite float, or ``None``.

    The Kimera subprocess runner serialises non-finite floats (NaN/Inf) as
    strings, so a numeric field can arrive as a ``str`` — anything non-finite
    or unparseable is treated as absent.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, str):
        try:
            f = float(value)
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


def jaccard(a: "frozenset[str]", b: "frozenset[str]") -> float:
    """Jaccard similarity of two sets; two empty sets are trivially identical."""
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def concept_set(result: CycleResult) -> "frozenset[str] | None":
    """The per-cycle ``concepts`` set (recognition layer), or ``None``.

    Normalises str / dict ({name|label|concept|text}) / other concept entries
    to a set of names. ``None`` on failure or no concepts (a gap, not 0.0).
    """
    if not result.success:
        return None
    concepts = (result.raw or {}).get("concepts")
    if not isinstance(concepts, list) or not concepts:
        return None
    names: set[str] = set()
    for c in concepts:
        if isinstance(c, str):
            name = c.strip()
        elif isinstance(c, dict):
            name = str(
                c.get("name") or c.get("label") or c.get("concept") or c.get("text") or ""
            ).strip()
        else:
            name = str(c).strip()
        if name:
            names.add(name)
    return frozenset(names) if names else None


def prime_set(result: CycleResult) -> "frozenset[str] | None":
    """The per-cycle prime-address (``prime_chain``) as a set, or ``None``.

    Falls back to the ``rosetta_primes`` / ``alexandria_fused_primes`` maps when
    the chain is absent. Elements are stringified so the set is robust to int or
    str chain entries.
    """
    if not result.success:
        return None
    raw = result.raw or {}
    chain = raw.get("prime_chain")
    if isinstance(chain, list) and chain:
        primes = {str(p).strip() for p in chain if str(p).strip()}
        if primes:
            return frozenset(primes)
    for k in ("rosetta_primes", "alexandria_fused_primes"):
        v = raw.get(k)
        if isinstance(v, dict) and v:
            return frozenset(str(x) for x in v.keys())
    return None


def prime_chain(result: CycleResult) -> "tuple[str, ...] | None":
    """The per-cycle prime-address as an ORDERED sequence, or ``None``.

    The order-keeping sibling of :func:`prime_set`. ``prime_set`` discards order
    and repetition; this preserves both — the chain *is* the walk, and the walk's
    order is the path-dependence Kimera claims as its differentiator. A set
    metric over ``prime_set`` is order-blind by construction; this is the input a
    trajectory metric needs. ``None`` on a failed/empty cycle (a gap, never a
    fabricated empty walk).
    """
    if not result.success:
        return None
    chain = (result.raw or {}).get("prime_chain")
    if isinstance(chain, list) and chain:
        seq = tuple(str(p).strip() for p in chain if str(p).strip())
        if seq:
            return seq
    return None


def sequence_edit_divergence(a: "Sequence[str]", b: "Sequence[str]") -> float:
    """Order-sensitive divergence of two prime sequences ∈ [0, 1].

    Length-normalised Levenshtein (edit) distance over the ordered tokens.
    Where ``1 - jaccard(prime_set(...))`` is a *set* operation — 0 whenever the
    two chains share the same primes, regardless of order — this is 0 only when
    the sequences match in BOTH content and order, and strictly > 0 for a
    re-ordering of the same primes. Two empty sequences are identical (0.0); a
    chain against an empty one is maximally divergent (1.0).
    """
    sa, sb = list(a), list(b)
    if not sa and not sb:
        return 0.0
    n, m = len(sa), len(sb)
    if n == 0 or m == 0:
        return 1.0
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = sa[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == sb[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m] / max(n, m)


def prime_energy_path(chain: "Sequence[str]") -> "tuple[float, ...]":
    """Per-step native energy of an ordered prime chain: ``E_p = ln(p)``.

    The prime energy scale is the logarithm of the prime itself (Kimera's
    founding spec). Tokens that aren't integers > 1 contribute nothing (a chain
    may carry non-numeric address fragments). Returns the ordered step-energy
    sequence — the walk, read in energy.
    """
    out: list[float] = []
    for tok in chain:
        try:
            p = int(str(tok).strip())
        except (TypeError, ValueError):
            continue
        if p > 1:
            out.append(math.log(p))
    return tuple(out)


def energy_path_divergence(a: "Sequence[str]", b: "Sequence[str]") -> "float | None":
    """Order-sensitive divergence of two chains *as energy walks* ∈ [0, 1].

    Reads each chain as its native energy accumulation (``E_p = ln p`` per step)
    and compares the normalised cumulative-energy curves — the fraction of the
    walk's total energy accrued by each fraction of its steps — returning the
    area between them. This is the physics-native trajectory metric: two chains
    built from the SAME primes in a DIFFERENT order share a set (and a total
    energy) but trace different accumulation curves, so divergence is > 0 exactly
    where a Jaccard/set metric reads 0. ``None`` if either chain carries no
    usable prime energy.
    """
    ea, eb = prime_energy_path(a), prime_energy_path(b)
    if not ea or not eb:
        return None
    grid = 64

    def _curve(energies: "tuple[float, ...]") -> list[float]:
        total = math.fsum(energies)
        if total <= 0.0:
            return [0.0] * (grid + 1)
        cum = [0.0]
        acc = 0.0
        for e in energies:
            acc += e
            cum.append(acc / total)
        n = len(cum) - 1
        out: list[float] = []
        for g in range(grid + 1):
            pos = (g / grid) * n
            lo = int(math.floor(pos))
            if lo >= n:
                out.append(cum[n])
            else:
                frac = pos - lo
                out.append(cum[lo] * (1.0 - frac) + cum[lo + 1] * frac)
        return out

    ca, cb = _curve(ea), _curve(eb)
    area = 0.0
    for k in range(grid):
        area += 0.5 * (abs(ca[k] - cb[k]) + abs(ca[k + 1] - cb[k + 1])) / grid
    return area


_PARTITION_CONSTITUENTS = ("primes", "echoform_sequence", "cronos_timestamp", "gwf_signature")


def partition(result: CycleResult) -> "dict[str, Any] | None":
    """Assemble the native partition — the re-performable wire-unit — from a cycle,
    as far as the current emission allows; ``None`` on a failed cycle.

    A FAITHFUL partition (CLAUDE.md) is **primes + Echoform operator sequence +
    Cronos timestamp + GWF signature**: the re-performable instruction the
    Indra's-Net wire carries between Nodes. Each constituent is read from the
    emitted telemetry; a constituent the substrate does not yet emit is ``None`` —
    an honest gap, never fabricated. Today's hard gap is the **Echoform operator
    sequence**: the substrate emits a single ``echoform_event`` dict, not the
    ordered ΔS sequence, so this reads the spec'd ``echoform_sequence`` list
    (absent until the emission contract widens — see docs/ECHOFORM_EMISSION_SPEC.md).
    """
    if not result.success:
        return None
    raw = result.raw or {}
    echo = raw.get("echoform_sequence")
    return {
        "primes": prime_chain(result),
        "echoform_sequence": list(echo) if isinstance(echo, list) and echo else None,
        "cronos_timestamp": raw.get("cronos_timestamp") or raw.get("substrate_state_stamp"),
        "gwf_signature": raw.get("gwf_signature") or raw.get("gwf_verdict"),
    }


def partition_faithfulness(result: CycleResult) -> "float | None":
    """Fraction of a faithful partition's four constituents the substrate emits this
    cycle ∈ {0, .25, .5, .75, 1}; ``None`` on a failed cycle.

    < 1 means the wire-unit is not yet fully re-performable, and the missing
    constituents name exactly what the emission contract must add. On a healthy
    cycle today this reads 0.75 — primes + Cronos stamp + GWF present, the Echoform
    operator sequence absent — which is the measured size of the gap the
    Echoform-emission spec closes (0.75 → 1.0).
    """
    p = partition(result)
    if p is None:
        return None
    present = sum(
        1 for k in _PARTITION_CONSTITUENTS if p.get(k) not in (None, "", [], {})
    )
    return present / len(_PARTITION_CONSTITUENTS)


def echoform_sequence_from_history(history: "Sequence[Any]") -> "list[dict[str, Any]]":
    """Map an Echoform transformation history to a partition's operator sequence.

    Each entry — a Kimera ``TransformationResult`` (object with ``operator_id`` +
    ``delta_entropy``) or its serialized dict — becomes ``{"op": <id>, "delta_s":
    <ΔS>}``, preserving order. This is the mapping the substrate runner applies to
    the per-cycle delta of ``EchoformOperatorSystem.get_transformation_history()``
    to fill the ``echoform_sequence`` constituent — the ΔS≥0 grammar the
    Constitution names as part of a faithful partition. The operator stream is
    RETAINED by the substrate (apply_operator → _transformation_history), so this
    needs no engine change: the runner reads it. Entries with no operator id are
    skipped (an honest drop, never a fabricated op).
    """
    out: list[dict[str, Any]] = []
    for entry in history or ():
        if isinstance(entry, Mapping):
            op = entry.get("operator_id")
            ds = entry.get("delta_entropy", entry.get("delta_s"))
        else:
            op = getattr(entry, "operator_id", None)
            ds = getattr(entry, "delta_entropy", None)
        if op is None:
            continue
        item: dict[str, Any] = {"op": str(op)}
        dsf = as_finite_float(ds)
        if dsf is not None:
            item["delta_s"] = dsf
        out.append(item)
    return out


def _angular_dispersion(points: "Sequence[Any]", cap: int = 100) -> "float | None":
    """Mean pairwise great-circle angle (radians) over a set of vectors, or ``None``.

    The native "how spread" of a point cloud on a sphere. Bounded to ``cap`` usable
    vectors to keep the pairwise cost finite; non-numeric / zero-norm entries skip.
    """
    vecs: list[list[float]] = []
    for p in points:
        if (
            isinstance(p, (list, tuple)) and p
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in p)
        ):
            vecs.append([float(x) for x in p])
        if len(vecs) >= cap:
            break
    if len(vecs) < 2:
        return None
    angles: list[float] = []
    for i in range(len(vecs)):
        na = math.sqrt(sum(x * x for x in vecs[i]))
        if na == 0.0:
            continue
        for j in range(i + 1, len(vecs)):
            nb = math.sqrt(sum(x * x for x in vecs[j]))
            if nb == 0.0:
                continue
            dot = sum(a * b for a, b in zip(vecs[i], vecs[j])) / (na * nb)
            angles.append(math.acos(max(-1.0, min(1.0, dot))))
    return sum(angles) / len(angles) if angles else None


def geoid_dispersion(result: CycleResult) -> "float | None":
    """Angular spread of the cycle's geoid points on the manifold ∈ [0, π], or ``None``.

    Mean pairwise great-circle angle between the concept positions Kimera placed on
    its S⁴ surface this cycle. Low = a focused, concentrated thought (the points
    cluster); high = a broad, dispersed one. Reads the substrate's ACTUAL positions
    (``raw['geoid_positions']``), not a proxy — ``None`` if fewer than two emitted.
    """
    if not result.success:
        return None
    return _angular_dispersion((result.raw or {}).get("geoid_positions") or [])


def manifold_deformation(result: CycleResult) -> "dict[str, Any] | None":
    """The scar load on the manifold this cycle — the shape of memory (deformation
    *is* the memory, per CLAUDE.md), or ``None``.

    Reads ``raw['scar_state']``: ``n_scars``, ``total_deformation``, and
    ``scar_dispersion`` (how spread the dents sit on the surface). ``None`` if no
    scar state was emitted — a gap, never a fabricated zero.
    """
    if not result.success:
        return None
    sc = (result.raw or {}).get("scar_state")
    if not isinstance(sc, dict):
        return None
    out: dict[str, Any] = {}
    n = sc.get("n_scars")
    if isinstance(n, (int, float)) and not isinstance(n, bool):
        out["n_scars"] = int(n)
    td = as_finite_float(sc.get("total_deformation"))
    if td is not None:
        out["total_deformation"] = td
    disp = _angular_dispersion(sc.get("positions") or [])
    if disp is not None:
        out["scar_dispersion"] = disp
    return out or None


def thermo_magnitude(result: CycleResult) -> "float | None":
    """The substrate's thermodynamic magnitude this cycle — the entropy change ΔS
    (``raw['entropy_validation']['delta_entropy']``), or ``None``.

    The native "how much" signal: a candidate size-meter. (The manifold-state
    magnitude readout was REFUTED; this is the distinct *thermodynamic* one, worth
    testing path-aware against |Δ magnitude|.) ``None`` if not emitted — no
    substitute signal is read in its place.
    """
    if not result.success:
        return None
    ev = (result.raw or {}).get("entropy_validation")
    if isinstance(ev, dict):
        return as_finite_float(ev.get("delta_entropy"))
    return None


def scar_count(result: CycleResult) -> int | None:
    """The canonical permanent scar count for a cycle, or ``None``.

    Priority: ``vault_stats.total_scars_stored`` (canonical;
    = vault_a.scar_count + vault_b.scar_count) → the sum of the two vault
    scar_counts → ``enhanced_vault_total_memories`` (top-level mirror).
    """
    if not result.success:
        return None
    raw = result.raw or {}
    vs = raw.get("vault_stats")
    if isinstance(vs, dict):
        tss = vs.get("total_scars_stored")
        if isinstance(tss, (int, float)) and not isinstance(tss, bool):
            return int(tss)
        a = vs.get("vault_a") or {}
        b = vs.get("vault_b") or {}
        if isinstance(a, dict) and isinstance(b, dict):
            ac, bc = a.get("scar_count"), b.get("scar_count")
            if isinstance(ac, (int, float)) and isinstance(bc, (int, float)):
                return int(ac) + int(bc)
    evtm = raw.get("enhanced_vault_total_memories")
    if isinstance(evtm, (int, float)) and not isinstance(evtm, bool):
        return int(evtm)
    return None


def state_vector(
    result: CycleResult,
    fields: "Mapping[str, str] | Sequence[str]",
) -> "dict[str, float] | None":
    """A dict of finite-float manifold-state observables, or ``None``.

    ``fields`` is either a mapping ``label -> raw_key`` or a sequence of raw
    keys (used as both label and key). Only keys present as finite floats are
    included; ``None`` if none are readable.
    """
    if not result.success:
        return None
    raw = result.raw or {}
    items = fields.items() if isinstance(fields, Mapping) else ((k, k) for k in fields)
    out: dict[str, float] = {}
    for label, key in items:
        v = as_finite_float(raw.get(key))
        if v is not None:
            out[label] = v
    return out or None
