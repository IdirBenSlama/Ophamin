"""Primitive-inspector — scales the observatory from 4 hand-rolled scenarios
to a uniform per-primitive view across all 60+ Kimera-SWM primitives.

The inspector is a *composer*, not a new ring. It pulls from every wheel
that already exists:

  seeing.discovery     → schema mining (what fields the primitive emits)
  measuring.scenarios  → which scenarios already exercise this primitive
  comparing.drift      → behavioural drift across Kimera commits
  auditing             → static-analysis findings against the primitive's source
  instrumenting        → runtime resource cost when the primitive runs

…and adds *static introspection*: locate the primitive in the Kimera source
tree, extract its docstring + method signatures + callers, surface
biological-family classification per CLAUDE.md's primitive_inventory.md.

A primitive profile is the unified per-primitive artefact:

  PrimitiveProfile  — single primitive, full view (static + dynamic)
  PrimitiveCatalog  — curated list of known primitive names with their
                      canonical locations and biological-family tags
  PrimitiveLocator  — given a name, find its source file + class
  PrimitiveInspector — orchestrator that produces a PrimitiveProfile

CLI:

  ophamin inspect <kimera-repo> <primitive>     single-primitive deep-dive
  ophamin inspect-all <kimera-repo>             survey every catalogued primitive

.. note::

   Gap-G status (2026-05-16, closed by Move K): the composer narrative
   above is now implemented across all four wheels — static
   introspection (always), ``--with-discovery`` (Layer A schema
   mining), ``--with-audit`` (static analysis on the primitive's
   source file), ``--with-comparing`` (River ADWIN drift detection on
   the primitive's phi stream), and ``--with-instrumenting``
   (InstrumentedSubstrate wrapping for per-cycle resource profile).
   All four dynamic flags are best-effort: failures get captured as
   ``profile.notes`` rather than crashing the inspection.
"""

from __future__ import annotations

from ophamin.inspecting.catalog import (
    KNOWN_PRIMITIVES,
    PrimitiveCatalog,
    PrimitiveEntry,
)
from ophamin.inspecting.inspector import PrimitiveInspector
from ophamin.inspecting.locator import LocatedPrimitive, PrimitiveLocator
from ophamin.inspecting.primitive_profile import (
    CallerReference,
    PrimitiveProfile,
)

__all__ = [
    "CallerReference",
    "KNOWN_PRIMITIVES",
    "LocatedPrimitive",
    "PrimitiveCatalog",
    "PrimitiveEntry",
    "PrimitiveInspector",
    "PrimitiveLocator",
    "PrimitiveProfile",
]
