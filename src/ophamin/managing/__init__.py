"""Ophamin Manage facet — operate Kimera-SWM (status, health, lifecycle).

The operational read side of the horizontal platform: is the substrate
operational, which cognitive surfaces are reachable, at which commit. The
Control room's live backend, grounded in the real ``KimeraAdapter.probe()``.

Public API:

- :func:`substrate_status` — probe the live substrate → management status.
- :func:`normalize_status` — deterministic core (probe report → status).
"""

from __future__ import annotations

from ophamin.managing.status import normalize_status, substrate_status

__all__ = ["normalize_status", "substrate_status"]
