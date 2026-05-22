"""Run the Memory-Horizon Flow scenario on real Enron email at scale.

The first proof aimed at the infinite-context-memory gap — observational: it
streams N real experiences ONCE (default 400, past a 256-item ≈128K-token
reference window), re-probes a spread of earlier items, and measures recall vs
LAG. The lag→recall curve is the substrate's memory horizon, revealed. We do
not predict it; Kimera tells us.

    PYTHONPATH=src N_STREAM=400 WINDOW_REF=256 .venv/bin/python -u examples/run_memory_horizon_flow.py
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

from ophamin.authoring.materialize import _select_corpus_stimuli
from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.memory_horizon_flow import (
    MemoryHorizonFlowScenario,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_STREAM = int(os.environ.get("N_STREAM", "400"))
N_PROBES = int(os.environ.get("N_PROBES", "20"))
WINDOW_REF = int(os.environ.get("WINDOW_REF", "256"))
RECALL_FLOOR = float(os.environ.get("RECALL_FLOOR", "0.50"))
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — memory horizon on REAL Enron email (infinite-context gap)")

    stimuli = tuple(_select_corpus_stimuli("enron", n=N_STREAM))
    print(f"corpus     : enron (real) — {len(stimuli)} distinct email bodies")
    n_cycles = len(stimuli) + N_PROBES
    print(f"stream     : {len(stimuli)} items once + {N_PROBES} re-probes "
          f"= {n_cycles} cycles (single pass)")
    print(f"window_ref : {WINDOW_REF} items (recall beyond this = beyond a "
          "fixed window of that size)")
    print(f"floor      : recall_floor_beyond_window ≥ {RECALL_FLOOR:.2f}")

    scenario = MemoryHorizonFlowScenario(
        stimuli=stimuli, n_probes=N_PROBES, window_ref=WINDOW_REF,
        recall_floor=RECALL_FLOOR, corpus_label="enron (real)",
    )
    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=10800.0
    )
    print(f"substrate  : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming  : {n_cycles} cycles on live Kimera — observational…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("MEMORY-HORIZON RUN RAISED")
        traceback.print_exc()
        return 1

    ev = record.evidence[0]
    d = ev.detail

    banner("THE MEMORY HORIZON (what Kimera told us)")
    print(f"  memory horizon      : {d['memory_horizon']} cycles "
          f"(max lag with recall ≥ {RECALL_FLOOR:.2f})")
    print(f"  max lag measured    : {d['max_lag_measured']}")
    print(f"  beyond-window floor : {ev.statistic_value:.4f} "
          f"(threshold {RECALL_FLOOR:.2f}, window_ref {WINDOW_REF})")
    print(f"  beyond-window mean  : {d['recall_mean_beyond_window']:.4f}")
    print(f"  beyond-window probes: {d['n_beyond_window']}")
    print(f"  failed probes       : {d['n_failed_probes']}")

    banner("LAG → RECALL CURVE")
    for p in sorted(d["lag_curve"], key=lambda x: x["lag"]):
        flag = " (beyond window)" if p["beyond_window"] else ""
        print(f"  lag {p['lag']:>5}  recall {p['recall']:.4f}  "
              f"(stimulus {p['stimulus_index']}){flag}")

    ctl = d.get("control", {}) or {}
    banner("NEGATIVE CONTROL (recall beyond window is real, not coincidence)")
    print(f"  status              : {ev.cross_check}")
    print(f"  beyond-window median: {ctl.get('beyond_median')}")
    print(f"  cross-item median   : {ctl.get('cross_median')}")
    print(f"  Mann-Whitney p      : {ev.p_value}")

    banner("VERDICT")
    print(f"verdict    : {record.verdict.outcome}")
    print(f"reasoning  : {record.verdict.reasoning}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name,
    )
    print(f"proof      : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
