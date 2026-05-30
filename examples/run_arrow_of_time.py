"""Run the Arrow of Time scenario against real Kimera-SWM.

Streams real FRED macro/market series and their EXACT time-reversals through the
live substrate and tests whether Kimera can recover the true temporal direction
from its own path-dependent entropy production — a discrimination that is
0.5-by-construction for any order-blind reader (the forward and reversed streams
share the identical multiset of values).

    PYTHONPATH=src .venv/bin/python -u examples/run_arrow_of_time.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.arrow_of_time import ArrowOfTimeScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
OUT_DIR = Path("proofs")
WINDOW = 48
MAX_SERIES = 12
FLOOR = 0.65


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — ARROW OF TIME (does the substrate feel time's direction?)")
    print(
        f"Claim: across {MAX_SERIES} real FRED series, the substrate recovers the "
        f"true temporal direction (vs the exact reversal) at rate >= {FLOOR:.0%}."
    )
    print("Order-blind baseline = 0.500 by construction (identical value multiset).")

    scenario = ArrowOfTimeScenario(window=WINDOW, max_series=MAX_SERIES, accuracy_floor=FLOOR)
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=14400.0)
    print(f"\nsubstrate : kimera-swm @ {REPO}")
    print(f"data      : real FRED series — last {WINDOW} z-scored values, forward vs exact reversal")
    print("streaming : live Kimera cycles, both directions per series — heavy…")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("ARROW OF TIME RAISED")
        traceback.print_exc()
        return 1

    primary = record.evidence[0]
    d = primary.detail
    banner("ARROW-DETECTION BREAKDOWN")
    print(f"  series used           : {d['n_series']}  ({', '.join(d['series_used'][:12])})")
    print(f"  best observable       : {d['best_observable']}")
    print(
        f"  arrow_detection_rate  : {primary.statistic_value:.3f} "
        f"(floor {FLOOR:.2f}, chance 0.500); Wilson 95% CI "
        f"[{primary.ci_low:.3f}, {primary.ci_high:.3f}]"
    )
    print(f"  effect vs chance      : {primary.effect_size:+.3f}")
    print("\n  top arrow-carrying observables:")
    for k, r in list(d["top_observables"].items())[:10]:
        print(f"     {r:.3f}  {k}")

    banner("VERDICT")
    print(f"verdict   : {record.verdict.outcome}")
    print(f"reasoning : {record.verdict.reasoning}")

    bundle = persist_proof(record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value, scenario_name=scenario.name)
    print(f"proof     : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
