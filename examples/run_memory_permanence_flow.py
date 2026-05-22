"""Run the Memory-Permanence proof on real Kimera — measure the MEMORY ITSELF.

Owner correction (2026-05-22): *"Kimera SWM is the Memory itself, the scars,
the S4 manifold is the memory."* Every prior memory proof measured the
concept-set (recognition) layer — content-deterministic by design, not memory.
This one reads Kimera's own permanent accumulators off OrchestratorResult and
tests the decisive memory-vs-re-derivation discriminator:

  When an identically-recognised probe is re-exposed, does it land on a
  strictly-deeper (more-scarred) manifold every time?

    memory_path_dependence
      = (recognised re-exposure transitions with Δ permanent-scars > 0)
      / (recognised re-exposure transitions)

  >= 1.0 + whole-run scar monotonicity → path-dependent permanent memory in
  the scar/S4 substrate (impossible for a stateless re-deriver).
  < 1.0 or a scar reset → the substrate re-derives / forgets (an honest
  refutation: a Kimera construction brief).

    PYTHONPATH=src N_EXPOSURES=3 .venv/bin/python -u examples/run_memory_permanence_flow.py
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.memory_permanence_flow import (
    MemoryPermanenceFlowScenario,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_EXPOSURES = int(os.environ.get("N_EXPOSURES", "3"))
RECOGNITION_FLOOR = float(os.environ.get("RECOGNITION_FLOOR", "0.80"))
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — memory-permanence proof on REAL Kimera (the scars + S4 manifold)")

    scenario = MemoryPermanenceFlowScenario(
        n_exposures=N_EXPOSURES, recognition_floor=RECOGNITION_FLOOR,
        corpus_label="kimera-genesis",
    )
    n_cycles = len(scenario.stimuli) * scenario.n_exposures
    print(f"stimuli     : {len(scenario.stimuli)} genesis probes")
    print(f"schedule    : {len(scenario.stimuli)} x {N_EXPOSURES} interleaved "
          f"= {n_cycles} cycles (gap = {len(scenario.stimuli)})")
    print(f"recognition : floor {RECOGNITION_FLOOR:.0%} (same-probe gate)")
    print("reading     : vault_stats.total_scars_stored, "
          "arachne_web_coupling_frobenius, alexandria_knowledge_mass_cumulative")

    # batch mode is REQUIRED — the substrate must accumulate across the batch;
    # that accumulation IS the memory under test.
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=10800.0)
    print(f"substrate   : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming   : {n_cycles} cycles on live Kimera — the decisive test…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("MEMORY-PERMANENCE RUN RAISED")
        traceback.print_exc()
        return 1

    ev = record.evidence[0]
    d = ev.detail
    acc = d["accumulation"]
    banner("MEMORY SUBSTRATE — what Kimera told us (the scars + manifold)")
    print(f"  permanence (a scar cannot be reset): "
          f"{'HOLDS' if d['permanence_holds'] else 'VIOLATED'} "
          f"({len(d['scar_monotonicity_violations'])} decreases)")
    s = acc["total_scars_stored"]
    print(f"  total_scars_stored        : {s['start']} → {s['end']} "
          f"(+{s['delta']}, {s['per_cycle']}/cycle)")
    c = acc["arachne_web_coupling_frobenius"]
    print(f"  manifold coupling (Frob)  : {c['start']} → {c['end']} (+{c['delta']})")
    m = acc["alexandria_knowledge_mass_cumulative"]
    print(f"  cumulative semantic mass  : {m['start']} → {m['end']} (+{m['delta']})")
    print(f"  recognition floor observed: {d['recognition_floor_observed']} "
          f"(threshold {d['recognition_floor_threshold']}) — same-probe control")
    print(f"  phi |delta| mean          : {d['phi_delta_abs_mean']} "
          f"(Φ-rigid → memory is in the scars, not Φ)")
    print(f"  halt-flip rate            : {d['halt_flip_rate']} ({d['n_halt_flips']} flips)")

    banner("DECISIVE: path-dependent memory (recognised re-exposure lands deeper)")
    print(f"  memory_path_dependence    : {d['memory_path_dependence']:.4f} "
          f"= {d['n_confirmed_transitions']}/{d['n_recognised_transitions']}")
    ctl = d.get("control", {}) or {}
    print(f"  scar-depth vs ordinal     : Spearman rho={ctl.get('rho')} "
          f"p={ctl.get('p_value')} (significant: {ctl.get('significant')})")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"reasoning   : {record.verdict.reasoning}")
    print(f"\ninterpretation: {d['interpretation']}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name)
    print(f"proof       : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
