"""Wheel 3 — Comparing.

The outermost ring of Ophamin: cross-Kimera-commit retrospection. Submodules:

  - ``drift``           — Wilson-CI-based behavioural drift detection across
                          signed proof records (Layer C of the Kimera-co-
                          evolution stack)
  - ``drift_detection`` — per-stream online drift detection (River-backed
                          ADWIN / KSWIN / PageHinkley). PR #4 of
                          docs/PLUGIN_CATALOG_2026_05_15.md.
  - ``provenance``      — W3C PROV-O graph + lineage store (MLflow + DVC)
  - ``orchestration``   — parent / child experiment runs that apply the pillars

In the Ophanim image, this is the rim that sees the longest arc — it
watches what changed across Kimera's evolution, not what Kimera is doing
right now.
"""

from __future__ import annotations

from ophamin.comparing import drift, drift_detection, orchestration, provenance

__all__ = ["drift", "drift_detection", "orchestration", "provenance"]
