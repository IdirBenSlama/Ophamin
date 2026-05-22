"""CR6 — measure what a flow proof reproduces, on live Kimera.

Re-runs the recognition flow N times (default 3) on Kimera and reports the
honest reproducibility a falsifiable proof actually promises:

  * the VERDICT reproduces (same VALIDATED / REFUTED outcome),
  * the cross-check CONCLUSION reproduces (same passed / failed / skipped),
  * the falsifiable metric reproduces WITHIN a measured drift band,

and explicitly NOT bit-identical proof_ids — each embeds created_at, so every
run is a distinct event. That is the category-correct way to talk about
reproducibility on a stochastic substrate.

    PYTHONPATH=src N_RUNS=3 .venv/bin/python -u examples/run_reproducibility.py
"""

from __future__ import annotations

import os
import traceback

from ophamin.measuring.scenarios import MemoryDeformationFlowScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.reproducing import reproduce
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_RUNS = int(os.environ.get("N_RUNS", "3"))


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — CR6: reproducibility of a flow proof on live Kimera")
    scenario = MemoryDeformationFlowScenario(n_exposures=3)
    n_cycles = scenario.n_cycles
    print(f"scenario   : {scenario.name}")
    print(f"per-run    : {len(scenario.stimuli)} stimuli × {scenario.n_exposures} "
          f"exposures = {n_cycles} cycles")
    print(f"re-runs    : {N_RUNS} (total {n_cycles * N_RUNS} live cycles)")

    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=3600.0
    )
    print(f"substrate  : {adapter.name} @ {adapter.git_commit()[:12]}")

    try:
        rep = reproduce(scenario, adapter, n_runs=N_RUNS, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("REPRODUCIBILITY RUN RAISED")
        traceback.print_exc()
        return 1

    banner("WHAT REPRODUCED")
    print(f"  verdicts            : {rep.verdicts}")
    print(f"  verdict reproducible: {rep.verdict_reproducible}")
    print(f"  cross-checks        : {rep.cross_checks}")
    print(f"  cross-check stable  : {rep.cross_check_reproducible}")
    print(f"  {rep.threshold_metric} per run : {[round(v, 4) for v in rep.observed_values]}")
    print(f"  drift (max−min)     : {rep.observed_drift:.4f} "
          f"over [{rep.observed_min:.4f}, {rep.observed_max:.4f}] "
          f"(threshold {rep.threshold_value:.2f})")
    print(f"  observed stdev      : {rep.observed_stdev:.4f}")

    banner("PROOF IDENTITY (not a reproducibility signal)")
    print(f"  proof_ids distinct  : {rep.proof_ids_distinct} "
          "(expected True — each embeds created_at)")
    for i, pid in enumerate(rep.proof_ids):
        print(f"    run {i}: {pid[:16]}…")

    banner("HONEST READING")
    print(rep.notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
