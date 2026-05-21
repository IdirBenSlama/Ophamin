"""Run the Memory-as-Deformation Flow invariant on REAL business email (Enron).

The genesis run (run_memory_deformation_flow.py) tests recognition stability
on curated Kimera-vocabulary stimuli. This runs the *same* temporal-logic
invariant on a real corpus — substantial Enron emails — to answer: does
memory-as-deformation hold on messy real-world business text, or only on
hand-picked vocabulary?

Same invariant, real data. The proof is tagged corpus_label="enron (real
business email)" so the Console Flow screen distinguishes it from the
genesis run.

    PYTHONPATH=src .venv/bin/python -u examples/run_memory_deformation_flow_enron.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios import MemoryDeformationFlowScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.seeing.corpus import get_corpus
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_STIMULI = 8
N_EXPOSURES = 3
RECOGNITION_FLOOR = 0.80
# Real business prose is messier than curated vocabulary; clamp length so a
# single email doesn't dominate cycle cost, and require enough body to yield
# a concept set.
MIN_BODY, MAX_BODY = 200, 1500
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def select_stimuli() -> list[str]:
    """Pick N substantial Enron emails as re-exposure probes."""
    corpus = get_corpus("enron")
    out: list[str] = []
    for rec in corpus.records():
        body = (rec.text or "").strip()
        if MIN_BODY <= len(body) <= MAX_BODY:
            out.append(body)
        if len(out) >= N_STIMULI:
            break
    return out


def main() -> int:
    banner("OPHAMIN — FLOW SCOPE: MEMORY-AS-DEFORMATION on REAL business email")
    print(
        "Invariant under test: ALWAYS( jaccard(concepts_i, concepts_j) >= "
        f"{RECOGNITION_FLOOR:.2f} ) across re-exposures — on real Enron email."
    )
    print("Does memory-as-deformation hold on messy real text, not just")
    print("curated Kimera vocabulary? This is the real-use-case validation.")

    stimuli = select_stimuli()
    if len(stimuli) < N_STIMULI:
        print(f"\nERROR: only {len(stimuli)} suitable Enron emails found.")
        return 1
    print(f"\nstimuli   : {len(stimuli)} Enron emails "
          f"({MIN_BODY}-{MAX_BODY} chars each)")

    scenario = MemoryDeformationFlowScenario(
        stimuli=tuple(stimuli),
        n_exposures=N_EXPOSURES,
        recognition_floor=RECOGNITION_FLOOR,
        corpus_label="enron (real business email)",
    )
    schedule = scenario.build_schedule()
    print(f"schedule  : {len(stimuli)} stimuli x {N_EXPOSURES} = "
          f"{len(schedule)} cycles")

    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=3600.0
    )
    print(f"substrate : {adapter.name} @ {adapter.git_commit()[:12]}")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("ENRON MEMORY-DEFORMATION FLOW RAISED")
        traceback.print_exc()
        return 1

    primary = next(
        e for e in record.evidence
        if e.statistic_name == "recognition_jaccard_floor"
    )
    d = primary.detail

    banner("RECOGNITION STABILITY ON REAL BUSINESS EMAIL")
    print(f"  re-exposure pairs measured : {d['n_pairs']}")
    print(f"  exposures with no concepts : {d['n_failed_exposures']}")
    print(f"  recognition floor (worst)  : {primary.statistic_value:.4f} "
          f"(theta {RECOGNITION_FLOOR:.2f})")
    print(f"  recognition mean           : {d['recognition_jaccard_mean']:.4f}")
    if d.get("worst_pair"):
        w = d["worst_pair"]
        print(f"  worst pair                 : stimulus {w['stimulus_index']} "
              f"cycles {w['cycle_a']}<->{w['cycle_b']} = {w['jaccard']:.4f}")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"reasoning   : {record.verdict.reasoning}")
    if record.verdict.outcome == "VALIDATED":
        print("\n=> Memory-as-deformation GENERALISES to real business text.")
    elif record.verdict.outcome == "REFUTED":
        print("\n=> Recognition is weaker on real text than curated vocabulary "
              "— an honest finding, surfaced as the worst pair (a construction "
              "brief, not just a red mark).")

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
