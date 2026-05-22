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
