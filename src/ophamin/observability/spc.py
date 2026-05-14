"""Statistical Process Control — Shewhart control charts (O pillar).

Pioneered by Walter Shewhart. A control chart graphs time-series data against
control limits derived from historical process data, separating *common cause*
variation (natural systemic noise) from *special cause* variation (anomalous
events needing investigation).

In Ophamin this monitors the measurement pipeline itself: baseline execution
latencies, telemetry stability, subgroup averages — so that an observed shift
in experimental outcomes can be attributed to the treatment rather than to
decaying instrumentation.

Two charts are provided:

    XbarRChart       subgroup means + ranges (subgroup size n >= 2)
    IndividualsChart individuals + moving range (n == 1 streams, e.g. latency)

Both expose Western Electric rule checking for special-cause detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Shewhart control-chart constants: subgroup size -> (d2, d3).
# d2 estimates process sigma from the mean range; d3 gives the range's sigma.
# The classic A2/D3/D4 constants are derived from these (verified in tests).
_CONSTANTS: dict[int, tuple[float, float]] = {
    2: (1.128, 0.853),
    3: (1.693, 0.888),
    4: (2.059, 0.880),
    5: (2.326, 0.864),
    6: (2.534, 0.848),
    7: (2.704, 0.833),
    8: (2.847, 0.820),
    9: (2.970, 0.808),
    10: (3.078, 0.797),
}


@dataclass
class Violation:
    """A special-cause signal: a Western Electric rule fired at an index."""

    rule: int
    index: int
    description: str


@dataclass
class ControlChartResult:
    """A fitted chart plus the evaluation of a series against it."""

    center: float
    ucl: float
    lcl: float
    sigma: float
    values: list[float] = field(default_factory=list)
    out_of_control: list[int] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)

    def classify(self, index: int) -> str:
        """Return ``"special"`` if any rule fired at ``index``, else ``"common"``."""
        if index in self.out_of_control:
            return "special"
        if any(v.index == index for v in self.violations):
            return "special"
        return "common"

    def summary(self) -> str:
        return (
            f"center={self.center:.4g} UCL={self.ucl:.4g} LCL={self.lcl:.4g} "
            f"sigma={self.sigma:.4g} n={len(self.values)} "
            f"special_cause_points={len(set(self.out_of_control) | {v.index for v in self.violations})}"
        )


def western_electric_rules(
    values: np.ndarray, center: float, sigma: float
) -> list[Violation]:
    """Apply the four classic Western Electric special-cause rules.

    Zones are measured in multiples of ``sigma`` from ``center``:
      C within 1s, B in (1s, 2s], A in (2s, 3s], beyond above 3s.

    1. one point beyond 3 sigma
    2. 2 of 3 consecutive points beyond 2 sigma, same side
    3. 4 of 5 consecutive points beyond 1 sigma, same side
    4. 8 consecutive points on one side of the centre line
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    out: list[Violation] = []
    if n == 0 or sigma <= 0:
        return out

    dev = values - center
    side = np.sign(dev)  # +1 above, -1 below, 0 on the line
    z = np.abs(dev) / sigma

    # Rule 1 — single point beyond 3 sigma.
    for i in range(n):
        if z[i] > 3.0:
            out.append(Violation(1, i, "point beyond 3 sigma"))

    # Rule 2 — 2 of 3 consecutive beyond 2 sigma, same side.
    for i in range(2, n):
        window = slice(i - 2, i + 1)
        for s in (1.0, -1.0):
            beyond = (side[window] == s) & (z[window] > 2.0)
            if beyond.sum() >= 2:
                out.append(Violation(2, i, "2 of 3 beyond 2 sigma, same side"))
                break

    # Rule 3 — 4 of 5 consecutive beyond 1 sigma, same side.
    for i in range(4, n):
        window = slice(i - 4, i + 1)
        for s in (1.0, -1.0):
            beyond = (side[window] == s) & (z[window] > 1.0)
            if beyond.sum() >= 4:
                out.append(Violation(3, i, "4 of 5 beyond 1 sigma, same side"))
                break

    # Rule 4 — 8 consecutive on one side of the centre line.
    run = 0
    last_side = 0.0
    for i in range(n):
        if side[i] == 0:
            run = 0
            last_side = 0.0
            continue
        if side[i] == last_side:
            run += 1
        else:
            run = 1
            last_side = side[i]
        if run >= 8:
            out.append(Violation(4, i, "8 consecutive on one side of centre"))

    return out


def _constants(n: int) -> tuple[float, float]:
    if n not in _CONSTANTS:
        raise ValueError(
            f"subgroup size {n} unsupported; control-chart constants are "
            f"tabulated for n in {sorted(_CONSTANTS)}"
        )
    return _CONSTANTS[n]


class XbarRChart:
    """X-bar and R chart for subgrouped data (subgroup size 2..10).

    Fit on historical subgroups, then evaluate new subgroups. ``sigma_limit`` is
    the control-limit width L; L=3 reproduces the classic A2/D3/D4 limits.
    """

    def __init__(self, sigma_limit: float = 3.0) -> None:
        if sigma_limit <= 0:
            raise ValueError("sigma_limit must be positive")
        self.sigma_limit = float(sigma_limit)
        self._fitted = False
        self.subgroup_size: int = 0
        self.xbarbar: float = 0.0
        self.rbar: float = 0.0
        self.sigma_hat: float = 0.0  # estimated process sigma
        self.sigma_xbar: float = 0.0  # standard error of a subgroup mean

    def fit(self, subgroups: np.ndarray) -> "XbarRChart":
        """Fit limits from historical subgroups, shape ``(k, n)``."""
        sg = np.asarray(subgroups, dtype=float)
        if sg.ndim != 2 or sg.shape[0] < 1:
            raise ValueError("subgroups must be a 2-D array of shape (k, n)")
        k, n = sg.shape
        d2, _ = _constants(n)
        self.subgroup_size = n
        means = sg.mean(axis=1)
        ranges = sg.max(axis=1) - sg.min(axis=1)
        self.xbarbar = float(means.mean())
        self.rbar = float(ranges.mean())
        self.sigma_hat = self.rbar / d2
        self.sigma_xbar = self.sigma_hat / np.sqrt(n)
        self._fitted = True
        return self

    @property
    def x_limits(self) -> tuple[float, float, float]:
        """(LCL, centre, UCL) for the X-bar chart."""
        self._require_fit()
        half = self.sigma_limit * self.sigma_xbar
        return (self.xbarbar - half, self.xbarbar, self.xbarbar + half)

    @property
    def r_limits(self) -> tuple[float, float, float]:
        """(LCL, centre, UCL) for the R chart."""
        self._require_fit()
        _, d3 = _constants(self.subgroup_size)
        half = self.sigma_limit * d3 * self.sigma_hat
        return (max(0.0, self.rbar - half), self.rbar, self.rbar + half)

    def evaluate(self, subgroups: np.ndarray) -> ControlChartResult:
        """Evaluate new subgroups against the fitted X-bar limits."""
        self._require_fit()
        sg = np.asarray(subgroups, dtype=float)
        if sg.ndim != 2 or sg.shape[1] != self.subgroup_size:
            raise ValueError(
                f"subgroups must have shape (k, {self.subgroup_size}) to match the fit"
            )
        means = sg.mean(axis=1)
        lcl, center, ucl = self.x_limits
        out_of_control = [i for i, m in enumerate(means) if m > ucl or m < lcl]
        violations = western_electric_rules(means, center, self.sigma_xbar)
        return ControlChartResult(
            center=center,
            ucl=ucl,
            lcl=lcl,
            sigma=self.sigma_xbar,
            values=[float(m) for m in means],
            out_of_control=out_of_control,
            violations=violations,
        )

    def _require_fit(self) -> None:
        if not self._fitted:
            raise RuntimeError("XbarRChart.fit must be called before use")


class IndividualsChart:
    """Individuals (I-MR) chart for ungrouped streams — e.g. per-cycle latency.

    Process sigma is estimated from the average moving range (|x_i - x_{i-1}|),
    which uses the n=2 d2 constant (1.128).
    """

    _D2_N2 = _CONSTANTS[2][0]  # 1.128

    def __init__(self, sigma_limit: float = 3.0) -> None:
        if sigma_limit <= 0:
            raise ValueError("sigma_limit must be positive")
        self.sigma_limit = float(sigma_limit)
        self._fitted = False
        self.center: float = 0.0
        self.mr_bar: float = 0.0
        self.sigma_hat: float = 0.0

    def fit(self, values: np.ndarray) -> "IndividualsChart":
        v = np.asarray(values, dtype=float).ravel()
        if v.size < 2:
            raise ValueError("IndividualsChart needs at least 2 values to fit")
        moving_range = np.abs(np.diff(v))
        self.center = float(v.mean())
        self.mr_bar = float(moving_range.mean())
        self.sigma_hat = self.mr_bar / self._D2_N2
        self._fitted = True
        return self

    @property
    def limits(self) -> tuple[float, float, float]:
        """(LCL, centre, UCL) for the individuals chart."""
        if not self._fitted:
            raise RuntimeError("IndividualsChart.fit must be called before use")
        half = self.sigma_limit * self.sigma_hat
        return (self.center - half, self.center, self.center + half)

    def evaluate(self, values: np.ndarray) -> ControlChartResult:
        if not self._fitted:
            raise RuntimeError("IndividualsChart.fit must be called before use")
        v = np.asarray(values, dtype=float).ravel()
        lcl, center, ucl = self.limits
        out_of_control = [i for i, x in enumerate(v) if x > ucl or x < lcl]
        violations = western_electric_rules(v, center, self.sigma_hat)
        return ControlChartResult(
            center=center,
            ucl=ucl,
            lcl=lcl,
            sigma=self.sigma_hat,
            values=[float(x) for x in v],
            out_of_control=out_of_control,
            violations=violations,
        )
