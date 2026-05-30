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
