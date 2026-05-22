"""Run the Memory-Order-Hysteresis proof on real Kimera — Kimera vs RAG.

The investor question: how is Kimera's memory different from retrieval-augmented
memory (RAG), which the industry already has? This proof answers it on the one
axis where the architectures structurally diverge — ORDER of experience.

A set-based retriever (TF-IDF here; dense/BM25/FAISS behave identically) returns
the same ranking no matter what order documents were ingested (order divergence
= 0, by construction; demonstrated in-run). Kimera claims hysteresis. Per
held-out probe we measure, against a determinism control:

    order_hysteresis = mean(1 − Jaccard(prime_chain|A, prime_chain|B))
                     − mean(1 − Jaccard(prime_chain|A1, prime_chain|A2))

> 0 + significant ⇒ Kimera carries the ORDER of experience where RAG carries
only the inventory. ≤ 0 ⇒ accumulation is commutative (the differentiator is
permanence, not hysteresis) — an honest refutation.

    PYTHONPATH=src .venv/bin/python -u examples/run_memory_order_hysteresis.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.memory_order_hysteresis import (
    MemoryOrderHysteresisScenario,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — memory-order-hysteresis: Kimera vs order-invariant retrieval")

    scenario = MemoryOrderHysteresisScenario(corpus_label="kimera-genesis")
    print(f"documents   : {len(scenario.documents)} (re-ordered between runs)")
    print(f"probes      : {len(scenario.probes)} held-out queries (asked identically)")
    print(f"schedule    : 3 batches (order A, A again, B) × "
          f"({len(scenario.documents)}+{len(scenario.probes)}) = {scenario.n_cycles} cycles")
    print("observable  : prime_chain (the probe's prime-address)")
    print("baseline    : TF-IDF retrieval order-divergence (order-invariant by construction)")

    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=10800.0)
    print(f"substrate   : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"streaming   : {scenario.n_cycles} cycles on live Kimera…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("ORDER-HYSTERESIS RUN RAISED")
        traceback.print_exc()
        return 1

    ev = record.evidence[0]
    d = ev.detail
    banner("KIMERA vs RAG — order of experience")
    print(f"  Kimera order-divergence (A vs B)  : {d['kimera_order_divergence_mean']:.4f}")
    print(f"  Kimera noise floor (A vs A)       : {d['kimera_noise_floor_mean']:.4f}  "
          f"(determinism control)")
    print(f"  RAG (TF-IDF) order-divergence     : {d['rag_baseline_order_divergence_mean']:.4f}  "
          f"(order-invariant by construction)")
    print(f"  manifold-state order effect       : coupling Δ="
          f"{d['manifold_state_order_effect'].get('coupling')}, "
          f"mass Δ={d['manifold_state_order_effect'].get('mass')}")
    print(f"  manifold-state noise floor        : coupling Δ="
          f"{d['manifold_state_noise_floor'].get('coupling')}")

    banner("DECISIVE: order_hysteresis (Kimera order-effect beyond run-noise)")
    print(f"  order_hysteresis : {d['order_hysteresis']:+.4f} (threshold > 0)")
    ctl = d.get("control", {}) or {}
    print(f"  paired order>noise Wilcoxon       : p={ctl.get('p_value')} "
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
