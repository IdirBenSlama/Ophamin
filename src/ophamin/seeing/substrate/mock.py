"""MockSubstrate — a self-contained substrate under test.

This is what makes Ophamin runnable and testable with no external system. It is
a deterministic, seedable stand-in that produces plausible cycle results: a
``phi``-like cognitive signal that drifts as state accumulates, an energy gauge
that depletes, latency timers, and a tunable collapse mode so the diagnostics
have something to find.

It is *not* a model of any real substrate — it exists so the framework's pillars
and orchestration can be exercised and verified end-to-end. Real systems plug in
through their own ``SubstrateUnderTest`` adapter (see ``kimera_adapter``).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ophamin.measuring.metrics.tiers import MetricBundle, Tier1Metrics, Tier2Metrics, Tier3Metrics
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

_HALT_MODES = ["commit", "commit", "commit", "selective", "exhausted"]
_TREATMENT_LABELS = {"treatment", "b", "B", 1, "1", True}


class MockSubstrate(SubstrateUnderTest):
    """A deterministic, seedable substrate stand-in.

    Behaviour responds to swept parameters so the framework can be exercised:

        injection_rate       raises ``phi``, lowers cross-modal overlap & energy
        immune_threshold     low + high injection -> occasional overwhelm collapse
        variant              "treatment"-like labels add a small positive effect
        entropy_coefficient  in a ``collapse_cell``, low entropy triggers collapse
        cell                 topological cell id (for the kernel-coupling probe)

    State (cycle count, energy, accumulated phi) carries across cycles and is
    cleared by ``reset`` — the seed makes the whole sequence reproducible.
    """

    def __init__(
        self,
        seed: int = 0,
        drift_rate: float = 0.0008,
        base_phi: float = 0.5,
        injection_effect: float = 0.15,
        collapse_cells: list | None = None,
        collapse_entropy_below: float = 0.02,
        name: str = "mock",
    ) -> None:
        self.name = name
        self.seed = int(seed)
        self.drift_rate = float(drift_rate)
        self.base_phi = float(base_phi)
        self.injection_effect = float(injection_effect)
        self.collapse_cells = set(collapse_cells or [])
        self.collapse_entropy_below = float(collapse_entropy_below)
        self._rng = np.random.default_rng(self.seed)
        self._cycle = 0
        self._prev_phi = self.base_phi
        self._collapses = 0
        self._energy = 1.0

    def git_commit(self) -> str:
        return f"mock-{self.seed:07d}"

    def reset(self) -> None:
        self._rng = np.random.default_rng(self.seed)
        self._cycle = 0
        self._prev_phi = self.base_phi
        self._collapses = 0
        self._energy = 1.0

    def run_cycle(
        self, stimulus: Any, params: dict[str, Any] | None = None
    ) -> CycleResult:
        params = params or {}
        injection_rate = float(params.get("injection_rate", 0.0))
        immune_threshold = float(params.get("immune_threshold", 0.5))
        entropy_coefficient = float(params.get("entropy_coefficient", 0.1))
        cell = params.get("cell")
        variant = params.get("variant")

        self._cycle += 1
        noise = float(self._rng.normal(0.0, 0.02))
        variant_effect = 0.05 if variant in _TREATMENT_LABELS else 0.0

        phi = (
            self.base_phi
            + self.drift_rate * self._cycle
            + self.injection_effect * injection_rate
            + variant_effect
            + noise
        )
        phi = max(0.0, phi)

        # collapse logic — two distinct routes:
        #  1. a collapse-prone cell at low entropy coefficient (miscalibrated boundary).
        #     Deterministic, so the kernel-coupling diagnostic reads a clean signal.
        #  2. heavy injection overwhelming a weak immune threshold (intrinsic stress).
        collapsed = False
        if cell is not None and cell in self.collapse_cells:
            if entropy_coefficient < self.collapse_entropy_below:
                collapsed = True
        if not collapsed and injection_rate > 0.8 and immune_threshold < 0.4:
            collapsed = self._rng.random() < 0.3

        if collapsed:
            self._collapses += 1
            halt_mode = "amplitude_death"
        else:
            halt_mode = _HALT_MODES[int(self._rng.integers(0, len(_HALT_MODES)))]

        self._energy = max(0.0, self._energy - 0.001 - 0.002 * injection_rate)
        latency_ns = 5_000_000.0 + float(self._rng.exponential(1_000_000.0))
        latency_ns += 2_000.0 * self._cycle  # gentle drift, for the SPC chart

        prime_deformation_delta = phi - self._prev_phi
        jaccard_overlap = float(
            np.clip(0.40 + 0.30 * self._rng.random() - 0.20 * injection_rate, 0.0, 1.0)
        )
        zetetic_dissonance_gradient = abs(noise) * 2.0
        coherence = float(np.clip(0.81 - 0.10 * injection_rate + noise, 0.0, 1.0))
        drift_score = abs(injection_rate - 0.5) * 0.5 + abs(noise)

        self._prev_phi = phi

        bundle = MetricBundle(
            cycle_index=self._cycle,
            stimulus_id=str(stimulus) if stimulus is not None else None,
            tier1=Tier1Metrics(
                counters={
                    "total_cycles": float(self._cycle),
                    "collapses": float(self._collapses),
                },
                gauges={
                    "phi": phi,
                    "ouroboros_energy_reserve": self._energy,
                    "coherence": coherence,
                },
                timers={"cycle_latency_ns": [latency_ns]},
            ),
            tier2=Tier2Metrics(drift_score=drift_score),
            tier3=Tier3Metrics(
                prime_deformation_delta=prime_deformation_delta,
                jaccard_overlap=jaccard_overlap,
                zetetic_dissonance_gradient=zetetic_dissonance_gradient,
            ),
        )

        raw = {
            "phi": phi,
            "halt_mode": halt_mode,
            "success": not collapsed,
            "ouroboros_energy_reserve": self._energy,
            "coherence": coherence,
            "cycle_latency_ns": latency_ns,
            "prime_deformation_delta": prime_deformation_delta,
            "jaccard_overlap": jaccard_overlap,
            "zetetic_dissonance_gradient": zetetic_dissonance_gradient,
            "drift_score": drift_score,
            "params": dict(params),
        }
        return CycleResult(
            cycle_index=self._cycle,
            success=not collapsed,
            raw=raw,
            halt_mode=halt_mode,
            stimulus_id=str(stimulus) if stimulus is not None else None,
            metric_bundle=bundle,
        )

    def capture_state(self) -> dict[str, Any]:
        return {
            "cycle": self._cycle,
            "energy": self._energy,
            "collapses": self._collapses,
            "prev_phi": self._prev_phi,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "git_commit": self.git_commit(),
            "kind": "mock",
            "seed": self.seed,
            "drift_rate": self.drift_rate,
            "base_phi": self.base_phi,
            "collapse_cells": sorted(str(c) for c in self.collapse_cells),
        }
