"""Run the Cued-Recall memory proof on real Enron email.

The decisive test the memory-horizon proof set up: does a PARTIAL cue of a
SEEN email recall its full content better than a partial cue of a NEVER-SEEN
email? Both arms get the same impoverished input, so this isolates
path-dependent memory from deterministic re-derivation.

  memory_lift = mean(recall | seen) − mean(recall | never-seen)

lift ≤ 0  → the horizon's perfect recall was re-derivation, NOT memory (an
            honest refutation — a Kimera flow/wiring construction brief).
lift > 0 + significant → real path-dependent memory.

    PYTHONPATH=src N_SEEN=80 N_CONTROL=25 .venv/bin/python -u examples/run_memory_cued_recall_flow.py
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

from ophamin.authoring.materialize import _select_corpus_stimuli
from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.memory_cued_recall_flow import (
    MemoryCuedRecallFlowScenario,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_SEEN = int(os.environ.get("N_SEEN", "80"))
N_CONTROL = int(os.environ.get("N_CONTROL", "25"))
CUE_FRACTION = float(os.environ.get("CUE_FRACTION", "0.4"))
N_PROBES = int(os.environ.get("N_PROBES", "25"))
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — cued-recall memory proof on REAL Enron (memory vs re-derivation)")

    pool = _select_corpus_stimuli("enron", n=N_SEEN + N_CONTROL)
    seen = tuple(pool[:N_SEEN])
    control = tuple(pool[N_SEEN:N_SEEN + N_CONTROL])
    print(f"corpus      : enron (real) — {len(seen)} seen + {len(control)} never-seen")
    print(f"cue         : first {CUE_FRACTION:.0%} of words (partial cue)")
    n_cycles = len(seen) + N_PROBES + 2 * len(control)
    print(f"schedule    : {len(seen)} stream + {N_PROBES} seen-cue + "
          f"{len(control)}×(cue+full) = {n_cycles} cycles")

    scenario = MemoryCuedRecallFlowScenario(
        stimuli=seen, control_stimuli=control, n_probes=N_PROBES,
        cue_fraction=CUE_FRACTION, corpus_label="enron (real)",
    )
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=10800.0)
    print(f"substrate   : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming   : {n_cycles} cycles on live Kimera — the decisive test…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("CUED-RECALL RUN RAISED")
        traceback.print_exc()
        return 1

    ev = record.evidence[0]
    d = ev.detail
    banner("MEMORY vs RE-DERIVATION (what Kimera told us)")
    print(f"  seen partial-cue recall    : {d['seen_recall_mean']:.4f} "
          f"(median {d['seen_recall_median']:.4f}, n={d['n_seen_probes']})")
    print(f"  never-seen partial-cue recall: {d['control_recall_mean']:.4f} "
          f"(median {d['control_recall_median']:.4f}, n={d['n_control_probes']})")
    print(f"  MEMORY LIFT                : {ev.statistic_value:+.4f}  (threshold > 0)")
    ctl = d.get("control", {}) or {}
    print(f"  seen>control Mann-Whitney  : p={ev.p_value}  "
          f"(significant: {ctl.get('significant')})")

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
