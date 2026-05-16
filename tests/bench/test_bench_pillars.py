"""Phase S3 — pillar micro-benches.

Pinned baselines for the load-bearing per-pillar primitives:

- SPC ``IndividualsChart.fit + evaluate`` on N=10⁴ samples
- SPRT update per observation (Gaussian)
- River ADWIN update per observation
- Cumulative meta-analysis ``accumulate`` per (effect, variance) pair
"""

from __future__ import annotations

import numpy as np
import pytest


def test_bench_spc_individuals_chart_n10000(benchmark) -> None:
    from ophamin.measuring.pillars.observability.spc import IndividualsChart

    rng = np.random.default_rng(42)
    historical = rng.normal(loc=0.0, scale=1.0, size=10_000)
    new = rng.normal(loc=0.05, scale=1.0, size=10_000)

    def _fit_eval() -> None:
        chart = IndividualsChart(sigma_limit=3.0)
        chart.fit(historical)
        chart.evaluate(new)

    benchmark(_fit_eval)


def test_bench_sprt_update_per_observation(benchmark) -> None:
    from ophamin.measuring.pillars.adaptive.sprt import GaussianSPRT

    sprt = GaussianSPRT(mu0=0.0, mu1=0.5, sigma=1.0, alpha=0.05, beta=0.20)
    benchmark(sprt.update, 0.3)


def test_bench_river_adwin_update_per_observation(benchmark) -> None:
    try:
        from river.drift import ADWIN
    except ImportError:
        pytest.skip("river not installed")
    detector = ADWIN()
    benchmark(detector.update, 0.5)


def test_bench_cma_add_50(benchmark) -> None:
    from ophamin.measuring.pillars.synthesis.cma import CumulativeMetaAnalysis

    def _add_50() -> None:
        cma = CumulativeMetaAnalysis(random_effects=True)
        for _ in range(50):
            cma.add(effect=0.1, variance=0.01)

    benchmark(_add_50)
