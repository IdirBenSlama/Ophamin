"""Run the Memory-as-Deformation Flow scenario against real Kimera-SWM.

Ophamin's first FLOW-scope proof. Builds a trajectory where each Kimera
genesis concept is shown three times, spaced so every re-exposure lands
after intervening cycles have deformed the manifold, then tests the
temporal-logic invariant:

    ALWAYS( jaccard(concepts_i, concepts_j) >= theta )  over re-exposures

A REFUTED verdict means recognition is collapsing under deformation — a
real dynamics defect. theta is anchored to Kimera's own documented floor.

    PYTHONPATH=src .venv/bin/python -u examples/run_memory_deformation_flow.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios import MemoryDeformationFlowScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_EXPOSURES = 3
RECOGNITION_FLOOR = 0.80
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — FLOW SCOPE: MEMORY-AS-DEFORMATION (recognition stability)")
    print(
        "Invariant under test: ALWAYS( jaccard(concepts_i, concepts_j) >= "
        f"{RECOGNITION_FLOOR:.2f} ) across same-stimulus re-exposures."
    )
    print("This is a TRAJECTORY property — flow, not a single point.")

    scenario = MemoryDeformationFlowScenario(
        n_exposures=N_EXPOSURES,
        recognition_floor=RECOGNITION_FLOOR,
    )
    schedule = scenario.build_schedule()
    print(
        f"\nschedule  : {len(scenario.stimuli)} stimuli x {N_EXPOSURES} "
        f"exposures = {len(schedule)} cycles (gap = {len(scenario.stimuli)})"
    )

    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=3600.0
    )
    print(f"substrate : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming : {len(schedule)} cycles (may take a few minutes)")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("MEMORY-DEFORMATION FLOW RAISED")
        traceback.print_exc()
        return 1

    primary = next(
        e for e in record.evidence
        if e.statistic_name == "recognition_jaccard_floor"
    )
    d = primary.detail

    banner("RECOGNITION STABILITY OVER THE TRAJECTORY")
    print(f"  re-exposure pairs measured : {d['n_pairs']}")
    print(f"  exposures with no concepts : {d['n_failed_exposures']}")
    print(f"  recognition floor (worst)  : {primary.statistic_value:.4f} "
          f"(theta {RECOGNITION_FLOOR:.2f})")
    print(f"  recognition mean           : {d['recognition_jaccard_mean']:.4f}")
    if d.get("worst_pair"):
        w = d["worst_pair"]
        print(f"  worst pair                 : stimulus {w['stimulus_index']} "
              f"cycles {w['cycle_a']}<->{w['cycle_b']} = {w['jaccard']:.4f}")
    print("  per-stimulus floor         :")
    for k, v in sorted(d["per_stimulus_floor"].items(), key=lambda kv: kv[1]):
        print(f"      stimulus {k}: {v:.4f}  | {scenario.stimuli[int(k)][:54]}")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"reasoning   : {record.verdict.reasoning}")

    bundle = persist_proof(
        record,
        root=OUT_DIR,
        tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name,
    )
    print(f"proof       : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
