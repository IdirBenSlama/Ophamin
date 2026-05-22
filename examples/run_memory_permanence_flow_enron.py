"""Run the Memory-Permanence proof on REAL business email (Enron).

The genesis run (run_memory_permanence_flow.py) established the property on 8
curated Kimera-vocabulary probes. This runs the *same* decisive discriminator
on a real corpus — substantial Enron emails as the re-exposed probes — to
answer the honest caveat: does path-dependent permanent memory (the scars + S4
manifold) hold on messy real-world business text, or only on hand-picked
vocabulary?

    memory_path_dependence
      = (recognised re-exposure transitions with Δ permanent-scars > 0)
      / (recognised re-exposure transitions)

Same scar/manifold reading, same recognition-held-constant control, real data.

    PYTHONPATH=src N_STIMULI=12 N_EXPOSURES=3 .venv/bin/python -u examples/run_memory_permanence_flow_enron.py
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
from ophamin.seeing.corpus import get_corpus
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_STIMULI = int(os.environ.get("N_STIMULI", "12"))
N_EXPOSURES = int(os.environ.get("N_EXPOSURES", "3"))
RECOGNITION_FLOOR = float(os.environ.get("RECOGNITION_FLOOR", "0.80"))
# Real business prose is messier than curated vocabulary; clamp length so a
# single email doesn't dominate cycle cost, and require enough body to yield
# a concept set.
MIN_BODY, MAX_BODY = 200, 1500
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def select_stimuli() -> list[str]:
    """Pick N substantial, distinct Enron emails as re-exposure probes."""
    corpus = get_corpus("enron")
    out: list[str] = []
    seen: set[str] = set()
    for rec in corpus.records():
        body = (rec.text or "").strip()
        if MIN_BODY <= len(body) <= MAX_BODY and body not in seen:
            seen.add(body)
            out.append(body)
        if len(out) >= N_STIMULI:
            break
    return out


def main() -> int:
    banner("OPHAMIN — memory-permanence on REAL business email (Enron): does the "
           "scar/manifold memory hold on real data?")

    stimuli = select_stimuli()
    if len(stimuli) < N_STIMULI:
        print(f"\nERROR: only {len(stimuli)} suitable Enron emails found "
              f"(need {N_STIMULI}).")
        return 1

    scenario = MemoryPermanenceFlowScenario(
        stimuli=tuple(stimuli), n_exposures=N_EXPOSURES,
        recognition_floor=RECOGNITION_FLOOR, corpus_label="enron (real business email)",
    )
    n_cycles = len(stimuli) * N_EXPOSURES
    print(f"stimuli     : {len(stimuli)} Enron emails ({MIN_BODY}-{MAX_BODY} chars)")
    print(f"schedule    : {len(stimuli)} x {N_EXPOSURES} interleaved = {n_cycles} cycles")
    print(f"recognition : floor {RECOGNITION_FLOOR:.0%} (same-probe gate)")

    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=10800.0)
    print(f"substrate   : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming   : {n_cycles} cycles on live Kimera — real-data memory test…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("ENRON MEMORY-PERMANENCE RUN RAISED")
        traceback.print_exc()
        return 1

    ev = record.evidence[0]
    d = ev.detail
    acc = d["accumulation"]
    banner("MEMORY SUBSTRATE on REAL email — what Kimera told us")
    print(f"  permanence (a scar cannot be reset): "
          f"{'HOLDS' if d['permanence_holds'] else 'VIOLATED'} "
          f"({len(d['scar_monotonicity_violations'])} decreases)")
    s = acc["total_scars_stored"]
    print(f"  total_scars_stored        : {s['start']} → {s['end']} (+{s['delta']})")
    c = acc["arachne_web_coupling_frobenius"]
    print(f"  manifold coupling (Frob)  : {c['start']} → {c['end']} (+{c['delta']})")
    print(f"  recognition floor observed: {d['recognition_floor_observed']} "
          f"(threshold {d['recognition_floor_threshold']})")
    print(f"  recognition failures      : {d['n_recognition_failures']} transitions excluded")
    print(f"  phi |delta| mean          : {d['phi_delta_abs_mean']}")
    print(f"  halt-flip rate            : {d['halt_flip_rate']} ({d['n_halt_flips']} flips)")

    banner("DECISIVE: path-dependent memory on real data")
    print(f"  memory_path_dependence    : {d['memory_path_dependence']:.4f} "
          f"= {d['n_confirmed_transitions']}/{d['n_recognised_transitions']}")
    ctl = d.get("control", {}) or {}
    print(f"  scar-depth vs ordinal     : Spearman rho={ctl.get('rho')} "
          f"p={ctl.get('p_value')} (significant: {ctl.get('significant')})")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"reasoning   : {record.verdict.reasoning}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name)
    print(f"proof       : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
