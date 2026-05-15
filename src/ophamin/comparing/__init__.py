"""Wheel 3 — Comparing.

The outermost ring of Ophamin: cross-Kimera-commit retrospection. Submodules:

  - ``drift``        — Wilson-CI-based behavioural drift detection across
                       signed proof records (Layer C of the Kimera-co-
                       evolution stack)
  - ``provenance``   — W3C PROV-O graph + lineage store (MLflow + DVC)
  - ``orchestration``— parent / child experiment runs that apply the pillars

In the Ophanim image, this is the rim that sees the longest arc — it
watches what changed across Kimera's evolution, not what Kimera is doing
right now.
"""

from __future__ import annotations

from ophamin.comparing import drift, orchestration, provenance

__all__ = ["drift", "orchestration", "provenance"]
