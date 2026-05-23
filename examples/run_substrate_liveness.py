"""Run the Substrate Liveness scenario against real Kimera-SWM.

Streams a diverse real corpus (flores, multilingual) through the live Kimera
'entity' target and measures what fraction of the emitted numeric signal
surface carries real dynamics vs frozen defaults — the dynamical-aliveness
counterpart to substrate-completeness (which measures structural wiring).
REFUTED is the working state; the proof carries the frozen-signal worklist
(by organ) — the concrete awakening targets for the de-isolation campaign.

    PYTHONPATH=src .venv/bin/python -u examples/run_substrate_liveness.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.substrate_liveness import SubstrateLivenessScenario
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
OUT_DIR = Path("proofs")
LIVENESS_FLOOR = 0.80
N_CYCLES = 64
CORPUS = "flores"


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — SUBSTRATE LIVENESS (dynamical aliveness)")
    print(
        f"Claim under test: >= {LIVENESS_FLOOR:.0%} of the numeric signals "
        "Kimera emits carry real dynamics (vary with the stimulus) rather "
        "than frozen defaults."
    )
    print("A REFUTED verdict surfaces the frozen-signal worklist (the organs")
    print("that are structurally wired but not dynamically alive).")

    scenario = SubstrateLivenessScenario(
        liveness_floor=LIVENESS_FLOOR,
        corpus_name=CORPUS,
        target="entity",
        n_cycles=N_CYCLES,
    )
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=7200.0)
    print(f"\nsubstrate : kimera-swm @ {REPO}")
    print(f"corpus    : {CORPUS} (real, diverse multilingual) — {N_CYCLES} cycles")
    print("probe     : stream cycles, classify each numeric signal live/frozen")
    print("streaming : live Kimera cycles — this is the heavy run…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("SUBSTRATE LIVENESS RAISED")
        traceback.print_exc()
        return 1

    primary = next(e for e in record.evidence if e.statistic_name == "liveness_rate")
    d = primary.detail

    banner("LIVENESS BREAKDOWN")
    print(f"  always-on signals     : {d['always_on_total']}  (present every cycle)")
    print(f"  always-on live        : {d['always_on_live']}")
    print(f"  always-on frozen      : {d['always_on_frozen']}  (genuine dead defaults)")
    print(
        f"  liveness_rate         : {primary.statistic_value:.4f} "
        f"(floor {LIVENESS_FLOOR:.2f}); "
        f"Wilson 95% CI [{primary.ci_low:.4f}, {primary.ci_high:.4f}]"
    )
    print(
        f"  context (artifact-prone): whole-surface "
        f"{d['whole_surface_live']}/{d['whole_surface_total']} "
        f"({d['whole_surface_liveness_rate']:.4f}); scorable "
        f"{d['scorable_live']}/{d['scorable_total']} "
        f"({d['scorable_liveness_rate']:.4f})"
    )
    print("\n  frozen by organ (top 15) — the awakening worklist:")
    for organ, n in list(d["frozen_by_organ_top"].items())[:15]:
        print(f"     {organ:<20} {n}")

    banner("VERDICT")
    print(f"verdict   : {record.verdict.outcome}")
    print(f"reasoning : {record.verdict.reasoning}")

    bundle = persist_proof(
        record,
        root=OUT_DIR,
        tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name,
    )
    print(f"proof     : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
