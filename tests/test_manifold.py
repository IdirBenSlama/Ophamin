"""Manifold-state readings — Ophamin measuring the substrate's actual surface.

Now that the runner emits the live geoid positions, scar deformation, and the
thermodynamic ΔS, these turn the raw readings into native measurements: how spread
the thought sits on the sphere, the shape of memory (scar load), and the "how much"
energy signal. Pure readers — honest gaps, never fabricated, no substitute signals.
"""

import math

from ophamin.seeing.substrate.base import CycleResult
from ophamin.seeing.substrate.observables import (
    geoid_dispersion,
    manifold_deformation,
    thermo_magnitude,
)


def _cycle(raw, success=True):
    return CycleResult(cycle_index=0, success=success, raw=raw)


def test_geoid_dispersion_clustered_vs_spread():
    same = _cycle({"geoid_positions": [[1, 0, 0, 0, 0], [1, 0, 0, 0, 0]]})
    assert geoid_dispersion(same) == 0.0  # identical positions → a focused thought
    orth = _cycle({"geoid_positions": [[1, 0, 0, 0, 0], [0, 1, 0, 0, 0]]})
    d = geoid_dispersion(orth)
    assert d is not None and abs(d - math.pi / 2) < 1e-9  # orthogonal → 90° spread


def test_geoid_dispersion_gaps():
    assert geoid_dispersion(_cycle({"geoid_positions": [[1, 0, 0]]})) is None  # < 2 points
    assert geoid_dispersion(_cycle({})) is None
    assert geoid_dispersion(_cycle({"geoid_positions": [[1, 0], [0, 1]]}, success=False)) is None


def test_manifold_deformation_reads_scar_load():
    m = manifold_deformation(_cycle({"scar_state": {"n_scars": 1, "total_deformation": 1.0}}))
    assert m == {"n_scars": 1, "total_deformation": 1.0}


def test_manifold_deformation_scar_dispersion():
    m = manifold_deformation(_cycle({"scar_state": {
        "n_scars": 2, "total_deformation": 2.0, "positions": [[1, 0, 0], [0, 1, 0]]}}))
    assert m["n_scars"] == 2 and "scar_dispersion" in m and m["scar_dispersion"] > 0


def test_manifold_deformation_gap():
    assert manifold_deformation(_cycle({})) is None  # no scar state → gap, not zero


def test_thermo_magnitude_reads_delta_entropy_no_substitute():
    assert thermo_magnitude(_cycle({"entropy_validation": {"delta_entropy": 4.17}})) == 4.17
    assert thermo_magnitude(_cycle({})) is None                                    # no substitute
    assert thermo_magnitude(_cycle({"entropy_validation": {"delta_entropy": "nan"}})) is None
