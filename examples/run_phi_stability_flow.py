"""Run the Phi-Stability Flow scenario against real Kimera-SWM.

Ophamin's second FLOW-scope proof. Streams several passes over substantive
stimuli and tests the temporal-logic invariant:

    ALWAYS( phi >= phi_floor )  over the sustained-load trajectory

A REFUTED verdict means Φ (integrated information) collapsed below the
non-collapse floor somewhere in the run — the substrate went cognitively
dark on at least one cycle. phi_floor is anchored to Kimera's Φ record.

    PYTHONPATH=src .venv/bin/python -u examples/run_phi_stability_flow.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios import PhiStabilityFlowScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
# 5 passes over 8 stimuli = 40 cycles. The CR1 cross-check confirms the
# substrate is CONFIDENTLY alive via a Wilson 95% CI on the non-collapse
# rate; that needs ~40 real-input cycles for the lower bound to clear the
# 0.90 alive floor on a clean run (a smaller run is honestly 'skipped:
# underpowered', not 'passed').
N_PASSES = 5
PHI_FLOOR = 0.05
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — FLOW SCOPE: Φ-STABILITY (cognitive non-collapse)")
    print(
        "Invariant under test: ALWAYS( phi >= "
        f"{PHI_FLOOR:.2f} ) across a sustained-load trajectory."
    )
    print("Does the substrate stay cognitively alive as it runs?")

    scenario = PhiStabilityFlowScenario(n_passes=N_PASSES, phi_floor=PHI_FLOOR)
    schedule = scenario.build_schedule()
    print(
        f"\nschedule  : {N_PASSES} passes x {len(scenario.stimuli)} stimuli "
        f"= {len(schedule)} cycles"
    )

    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=3600.0
    )
    print(f"substrate : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming : {len(schedule)} cycles (may take a few minutes)")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("Φ-STABILITY FLOW RAISED")
        traceback.print_exc()
        return 1

    primary = next(
        e for e in record.evidence if e.statistic_name == "phi_floor"
    )
    d = primary.detail

    banner("Φ OVER THE SUSTAINED-LOAD TRAJECTORY")
    print(f"  cycles measured  : {d['n_measured']}")
    print(f"  cycles with no Φ : {d['n_failed_cycles']}")
    print(f"  Φ band           : [{d['phi_min']:.4f}, {d['phi_max']:.4f}] "
          f"mean {d['flow_mean']:.4f} stdev {d['phi_stdev']:.4f}")
    print(f"  Φ floor (worst)  : {primary.statistic_value:.4f} "
          f"(floor {PHI_FLOOR:.2f})")
    print(f"  non-collapse rate: {d['non_collapse_rate']:.1%}")
    print(f"  per-pass mean Φ  : {d['per_pass_mean']}")
    if d.get("worst_unit"):
        w = d["worst_unit"]
        print(f"  worst cycle      : stimulus {w['stimulus_index']} @ cycle "
              f"{w['cycle']} (pass {w['pass']}) = {w['value']:.4f}")

    ctl = d.get("control", {})
    if ctl:
        banner("CROSS-CHECK (CR1 statistical confirmation)")
        print(f"  status           : {ctl.get('status')}")
        if ctl.get("ci_low") is not None:
            print(f"  non-collapse CI  : Wilson 95% "
                  f"[{ctl['ci_low']:.3f}, {ctl.get('ci_high', 0.0):.3f}] "
                  f"(alive floor 0.90 → "
                  f"{'confidently alive' if ctl.get('alive_confident') else 'underpowered'})")
        if ctl.get("p_value") is not None:
            print(f"  Φ real>empty     : Mann-Whitney p={ctl['p_value']:.2e} "
                  f"({'discriminates' if ctl.get('phi_discriminates') else 'no discrimination'})")
        elif ctl.get("reason"):
            print(f"  reason           : {ctl['reason']}")

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
