"""Run the Substrate Liveness BATTERY against real Kimera-SWM.

Streams a diverse stimulus battery (multilingual + financial + code + adversarial)
through the live Kimera 'entity' target and measures liveness on the value-level
union — separating genuine dead wires (frozen across EVERY corpus) from
correctly-conditional organs (frozen on benign text only because that corpus
never exercised their trigger). The frozen worklist here is the TRUSTWORTHY B1
target list.

    PYTHONPATH=src .venv/bin/python -u examples/run_substrate_liveness_battery.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.measuring.scenarios.substrate_liveness_battery import (
    SubstrateLivenessBatteryScenario,
)
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
OUT_DIR = Path("proofs")
LIVENESS_FLOOR = 0.80
CORPORA = ("flores", "financial", "linux", "cyber")
PER_CORPUS = 40


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — SUBSTRATE LIVENESS BATTERY (dead-wire vs unexercised)")
    print(
        f"Claim: >= {LIVENESS_FLOOR:.0%} of always-on signals are live across "
        f"a diverse battery {list(CORPORA)} ({PER_CORPUS} cycles each)."
    )
    print("Frozen-across-ALL = genuine dead wire; varies-under-any = conditional.")

    scenario = SubstrateLivenessBatteryScenario(
        liveness_floor=LIVENESS_FLOOR,
        corpus_names=CORPORA,
        target="entity",
        per_corpus_cycles=PER_CORPUS,
    )
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=14400.0)
    print(f"\nsubstrate : kimera-swm @ {REPO}")
    print(f"battery   : {list(CORPORA)} × {PER_CORPUS} = {PER_CORPUS * len(CORPORA)} cycles")
    print("streaming : live Kimera cycles across all corpora — the heavy run…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("BATTERY RAISED")
        traceback.print_exc()
        return 1

    primary = next(e for e in record.evidence if e.statistic_name == "liveness_rate")
    d = primary.detail

    banner("UNION LIVENESS BREAKDOWN")
    print(f"  always-on signals     : {d['always_on_total']}  (present in every cycle of every corpus)")
    print(f"  always-on live        : {d['always_on_live']}")
    print(f"  always-on frozen      : {d['always_on_frozen']}  (GENUINE dead wires — frozen across all corpora)")
    print(
        f"  union liveness_rate   : {primary.statistic_value:.4f} "
        f"(floor {LIVENESS_FLOOR:.2f}); Wilson 95% CI [{primary.ci_low:.4f}, {primary.ci_high:.4f}]"
    )
    print("\n  genuine dead wires by organ (the trustworthy B1 worklist):")
    for organ, n in list(d["frozen_by_organ_top"].items())[:20]:
        print(f"     {organ:<20} {n}")

    banner("VERDICT")
    print(f"verdict   : {record.verdict.outcome}")
    print(f"reasoning : {record.verdict.reasoning}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value, scenario_name=scenario.name
    )
    print(f"proof     : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
