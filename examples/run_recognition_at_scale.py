"""CR4 — recognition flow AT SCALE on real business email (Enron), with control.

Beyond the 8 curated genesis stimuli: this runs the memory-as-deformation
recognition invariant on N real Enron emails (default 100), each re-exposed
``N_EXPOSURES`` times and interleaved, through live Kimera. It carries the
negative control — same-stimulus vs cross-stimulus concept-set Jaccard +
Mann-Whitney — so a recognition verdict is backed by evidence that recognition
is REAL (not lexical-overlap noise) AT SCALE, where the control has far more
cross-stimulus pairs and thus far more statistical power than the 8-stimulus run.

Two questions, both honest:
  1. Does the strict worst-pair recognition floor hold across N real emails?
     (a single hard email can refute it — that's the invariant's bar.)
  2. Does the control still discriminate same- from cross-stimulus at scale?
     (the more robust claim: recognition is a real signal.)

    PYTHONPATH=src N_STIMULI=100 .venv/bin/python -u examples/run_recognition_at_scale.py
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

from ophamin.authoring.materialize import _select_corpus_stimuli
from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios import MemoryDeformationFlowScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_STIMULI = int(os.environ.get("N_STIMULI", "100"))
N_EXPOSURES = int(os.environ.get("N_EXPOSURES", "3"))
RECOGNITION_FLOOR = float(os.environ.get("RECOGNITION_FLOOR", "0.80"))
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — CR4: recognition AT SCALE on REAL Enron email")

    stimuli = tuple(_select_corpus_stimuli("enron", n=N_STIMULI))
    print(f"corpus     : enron (real) — {len(stimuli)} distinct email bodies")
    if len(stimuli) < N_STIMULI:
        print(f"WARNING    : corpus yielded only {len(stimuli)} (< {N_STIMULI})")
    n_cycles = len(stimuli) * N_EXPOSURES
    print(f"schedule   : {len(stimuli)} stimuli × {N_EXPOSURES} exposures "
          f"= {n_cycles} cycles (interleaved re-exposure)")
    print(f"threshold  : recognition_jaccard_floor ≥ {RECOGNITION_FLOOR:.2f}")

    scenario = MemoryDeformationFlowScenario(
        stimuli=stimuli,
        n_exposures=N_EXPOSURES,
        recognition_floor=RECOGNITION_FLOOR,
        corpus_label="enron (real)",
    )
    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=7200.0
    )
    print(f"substrate  : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming  : {n_cycles} cycles on live Kimera — the massive run…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("RECOGNITION-AT-SCALE RUN RAISED")
        traceback.print_exc()
        return 1

    ev = next(
        e for e in record.evidence
        if e.statistic_name == "recognition_jaccard_floor"
    )
    d = ev.detail

    banner("RECOGNITION AT SCALE")
    print(f"  floor (worst pair) : {ev.statistic_value:.4f} "
          f"(θ {RECOGNITION_FLOOR:.2f})")
    mean_j = d.get("recognition_jaccard_mean")
    print(f"  mean Jaccard       : {mean_j:.4f}" if mean_j is not None else "  mean Jaccard       : —")
    print(f"  pairs measured     : {d.get('n_pairs')}")
    print(f"  failed exposures   : {d.get('n_failed_exposures', 0)}")
    if d.get("worst_pair"):
        w = d["worst_pair"]
        print(f"  worst pair         : stimulus {w.get('stimulus_index')} "
              f"@ cycles {w.get('cycle_a')}↔{w.get('cycle_b')} "
              f"= {w.get('jaccard'):.4f}")

    ctl = d.get("control", {}) or {}
    banner("NEGATIVE CONTROL (recognition is real, not lexical noise) — AT SCALE")
    print(f"  cross-check status : {ev.cross_check}")
    print(f"  same-stimulus med  : {ctl.get('same_median')}")
    print(f"  cross-stimulus med : {ctl.get('cross_median')}")
    print(f"  Mann-Whitney p     : {ev.p_value}")
    print(f"  effect size (CL)   : {ctl.get('cl_effect_size')}  "
          "(P(same > cross))")

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
