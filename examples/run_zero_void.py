"""Run the zero-void scenario against real Kimera + persist the signed proof.

    PYTHONPATH=src .venv/bin/python -u examples/run_zero_void.py
"""
from __future__ import annotations

import time

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def main() -> int:
    from ophamin.measuring.proof.persistence import persist_proof
    from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
    from ophamin.measuring.scenarios.zero_void import ZeroVoidScenario
    from ophamin.seeing.substrate import KimeraAdapter

    t0 = time.time()
    sc = ZeroVoidScenario(cycles_per_condition=8, target="entity")
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=900.0)
    rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    persist_proof(rec, root="proofs", tier="scientific", scenario_name=sc.name)

    ev = rec.evidence[0]
    det = ev.detail
    print(f"\n{'=' * 64}\nZERO-VOID — measured on real Kimera ({time.time()-t0:.0f}s)\n{'=' * 64}")
    print(f"verdict: {rec.verdict.outcome}")
    print(f"  primary  zero_void_proximity = {ev.statistic_value:+.3f}  "
          f"(>0 → zero nearer the void than rest)")
    print(f"  rung1 void REAL   dist(void, rest)        = {det['rung1_void_real_dist']:.3f}")
    print(f"  rung2 PLENUM      entropy(void)/entropy(rest) = {det['rung2_plenum_entropy_ratio']:.3f}  "
          f"(>1 → plenum; ~1 → stillness)")
    print(f"  rung3 zero-seat   dist(zero,rest)={det['rung3_zero_to_rest']:.3f}  "
          f"dist(zero,void)={det['rung3_zero_to_void']:.3f}")
    print(f"  zero sits nearest: {det['zero_nearest']}")
    print(f"  void/entropy fields used: {det['n_void_entropy_fields']}")
    print(f"  entropy means: {det['entropy_means']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
