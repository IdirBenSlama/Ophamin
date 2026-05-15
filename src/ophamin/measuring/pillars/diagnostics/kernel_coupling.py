"""Oracle Kernel-Coupling Diagnostic — variable isolation under collapse.

When a substrate exhibits unexpected state collapses, two interpretations
compete:

    A  the collapse is an *intrinsic* exploration behaviour of the substrate
    B  the collapse is an artefact of *miscalibrated boundary logic* (a setting)

This diagnostic isolates the root cause by sweeping the entropy coefficient
across a predetermined spectrum (e.g. {0.005, 0.01, 0.05, 0.20}) at the known
collapse-prone topological cells, with repetitions. The decision rule:

    collapse persists across the WHOLE spectrum  -> Interpretation A (intrinsic)
    collapse appears at SOME coefficients only   -> Interpretation B (miscalibrated)
    collapse never appears                       -> no collapse at these cells

``collapse_signal`` is substrate-defined; a generic default is provided.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

INTRINSIC_EXPLORATION = "intrinsic_exploration"
MISCALIBRATED_BOUNDARY_LOGIC = "miscalibrated_boundary_logic"
NO_COLLAPSE = "no_collapse"

CollapseSignal = Callable[[CycleResult], bool]

_COLLAPSE_HALTS = {"amplitude_death", "rollback", "collapse", "halt"}


def default_collapse_signal(result: CycleResult) -> bool:
    """Generic collapse detector: a failed cycle, or a collapse-flavoured halt."""
    if not result.success:
        return True
    if result.halt_mode in _COLLAPSE_HALTS:
        return True
    return False


@dataclass
class CellSweep:
    """The coefficient sweep at one topological cell, with a verdict."""

    cell: Any
    collapse_rate_by_coefficient: dict[float, float]
    verdict: str

    def summary(self) -> str:
        rates = ", ".join(
            f"{c:g}->{r:.2f}" for c, r in self.collapse_rate_by_coefficient.items()
        )
        return f"cell {self.cell!r}: {self.verdict}  [{rates}]"


@dataclass
class KernelCouplingResult:
    """The full diagnostic across all probed cells."""

    cells: list[CellSweep] = field(default_factory=list)
    entropy_coefficients: list[float] = field(default_factory=list)
    n_reps: int = 0
    persist_threshold: float = 0.5

    def verdict_for(self, cell: Any) -> str:
        for cs in self.cells:
            if cs.cell == cell:
                return cs.verdict
        raise KeyError(f"cell {cell!r} was not probed")

    def summary(self) -> str:
        lines = [
            f"OracleKernelCoupling: {len(self.cells)} cells, "
            f"coefficients={self.entropy_coefficients}, n_reps={self.n_reps}"
        ]
        for cs in self.cells:
            lines.append("  " + cs.summary())
        return "\n".join(lines)


class OracleKernelCouplingDiagnostic:
    """Sweeps the entropy coefficient at collapse-prone cells to isolate cause."""

    def __init__(
        self,
        entropy_coefficients=(0.005, 0.01, 0.05, 0.20),
        n_reps: int = 5,
        persist_threshold: float = 0.5,
    ) -> None:
        coeffs = [float(c) for c in entropy_coefficients]
        if len(coeffs) < 2:
            raise ValueError("need at least 2 entropy coefficients to sweep")
        if n_reps < 1:
            raise ValueError("n_reps must be >= 1")
        if not (0.0 < persist_threshold <= 1.0):
            raise ValueError("persist_threshold must be in (0, 1]")
        self.entropy_coefficients = coeffs
        self.n_reps = int(n_reps)
        self.persist_threshold = float(persist_threshold)

    def _classify(self, rates: dict[float, float]) -> str:
        values = list(rates.values())
        if all(r >= self.persist_threshold for r in values):
            return INTRINSIC_EXPLORATION
        if any(r >= self.persist_threshold for r in values):
            return MISCALIBRATED_BOUNDARY_LOGIC
        return NO_COLLAPSE

    def sweep(
        self,
        sut: SubstrateUnderTest,
        cells,
        *,
        collapse_signal: CollapseSignal = default_collapse_signal,
        base_params: dict[str, Any] | None = None,
        stimulus: Any = None,
    ) -> KernelCouplingResult:
        """Run the coefficient sweep across ``cells`` on the substrate ``sut``."""
        cells = list(cells)
        if not cells:
            raise ValueError("at least one collapse-prone cell must be provided")
        cell_sweeps: list[CellSweep] = []
        for cell in cells:
            rates: dict[float, float] = {}
            for coeff in self.entropy_coefficients:
                collapses = 0
                for _ in range(self.n_reps):
                    sut.reset()
                    params = dict(base_params or {})
                    params["entropy_coefficient"] = coeff
                    params["cell"] = cell
                    result = sut.run_cycle(stimulus, params)
                    if collapse_signal(result):
                        collapses += 1
                rates[coeff] = collapses / self.n_reps
            cell_sweeps.append(CellSweep(cell, rates, self._classify(rates)))
        return KernelCouplingResult(
            cells=cell_sweeps,
            entropy_coefficients=list(self.entropy_coefficients),
            n_reps=self.n_reps,
            persist_threshold=self.persist_threshold,
        )
