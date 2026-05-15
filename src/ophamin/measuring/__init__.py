"""Wheel 2 — Measuring.

The middle ring of Ophamin: pre-registered measurement engines and plug-in
statistical pillars. Submodules:

  - ``proof``      — the signed 9-section Empirical Proof Record
  - ``scenarios``  — corpus + target + pre-registered claim runners
                     (Immune Siege, Rosetta Scaling, Organizational
                     Dissonance, Logic-Topology Siege)
  - ``metrics``    — the three-tier metric model (cycle / per-run / cross-run)
  - ``pillars``    — six library-backed analytic pillars:
                     - ``observability``   SPC, SRM, drift detectors
                     - ``adaptive``        SPRT, mSPRT anytime-valid inference
                     - ``effects``         mixed-effects + MEA (statsmodels)
                     - ``synthesis``       cumulative meta-analysis
                     - ``robustness``      cross-validation (scikit-learn)
                     - ``diagnostics``     anticipatory / inertia / kernel coupling

In the Ophanim image, this is the rim that turns — every pre-registered
claim and every pillar's evidence sits on this wheel.
"""

from __future__ import annotations

from ophamin.measuring import metrics, pillars, proof, scenarios

__all__ = ["metrics", "pillars", "proof", "scenarios"]
