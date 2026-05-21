"""Run a flow invariant on any real corpus — the parametric flow runner.

One runner, any invariant, any corpus. This is the platform thesis as a
tool: the same temporal-logic flow invariants (memory-as-deformation
recognition stability, Φ non-collapse) can be measured on any of Ophamin's
real corpora (enron / linux / flores / cyber / financial), each tagged so
the Console Flow screen keeps them distinct. Build a cross-domain map of
where Kimera's dynamics hold and where they weaken.

    PYTHONPATH=src .venv/bin/python -u examples/run_flow_on_corpus.py recognition linux
    PYTHONPATH=src .venv/bin/python -u examples/run_flow_on_corpus.py phi enron

Args:
    invariant : "recognition" (memory-as-deformation) | "phi" (Φ-stability)
    corpus    : enron | linux | flores | cyber | financial
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios import (
    MemoryDeformationFlowScenario,
    PhiStabilityFlowScenario,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.seeing.corpus import get_corpus, list_corpus_names
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_STIMULI = 8
MIN_BODY, MAX_BODY = 120, 1500
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def select_stimuli(corpus_name: str) -> list[str]:
    corpus = get_corpus(corpus_name)
    out: list[str] = []
    seen: set[str] = set()
    for rec in corpus.records():
        body = (rec.text or "").strip()
        if MIN_BODY <= len(body) <= MAX_BODY and body not in seen:
            out.append(body)
            seen.add(body)
        if len(out) >= N_STIMULI:
            break
    return out


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        print(f"\navailable corpora: {list_corpus_names()}")
        return 2
    invariant = sys.argv[1].lower()
    corpus_name = sys.argv[2].lower()
    if invariant not in {"recognition", "phi"}:
        print(f"unknown invariant {invariant!r} (recognition | phi)")
        return 2
    if corpus_name not in list_corpus_names():
        print(f"unknown corpus {corpus_name!r}; available: {list_corpus_names()}")
        return 2

    label = f"{corpus_name} (real)"
    banner(f"OPHAMIN — FLOW SCOPE: {invariant} on REAL corpus '{corpus_name}'")

    stimuli = select_stimuli(corpus_name)
    if len(stimuli) < N_STIMULI:
        print(f"ERROR: only {len(stimuli)} suitable records in {corpus_name}.")
        return 1
    print(f"stimuli   : {len(stimuli)} {corpus_name} records "
          f"({MIN_BODY}-{MAX_BODY} chars each)")

    if invariant == "recognition":
        scenario = MemoryDeformationFlowScenario(
            stimuli=tuple(stimuli), n_exposures=3,
            recognition_floor=0.80, corpus_label=label,
        )
        primary_stat = "recognition_jaccard_floor"
    else:
        scenario = PhiStabilityFlowScenario(
            stimuli=tuple(stimuli), n_passes=3,
            phi_floor=0.05, corpus_label=label,
        )
        primary_stat = "phi_floor"

    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=3600.0
    )
    print(f"substrate : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"cycles    : {scenario.n_cycles}")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("RAISED")
        traceback.print_exc()
        return 1

    primary = next(e for e in record.evidence if e.statistic_name == primary_stat)
    d = primary.detail

    banner("RESULT")
    print(f"  metric  : {primary_stat}")
    print(f"  floor   : {primary.statistic_value:.4f}")
    print(f"  mean    : {d.get('recognition_jaccard_mean', d.get('flow_mean')):.4f}")
    print(f"  verdict : {record.verdict.outcome}")
    print(f"  reason  : {record.verdict.reasoning}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name,
    )
    print(f"  proof   : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
