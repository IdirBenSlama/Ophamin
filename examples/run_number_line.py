"""Run the number-line scenario (production number sense) + persist the signed proof.

    PYTHONPATH=src .venv/bin/python -u examples/run_number_line.py
"""
from __future__ import annotations

import sys
import time

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def main() -> int:
    from ophamin.measuring.proof.persistence import persist_proof
    from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
    from ophamin.measuring.scenarios.number_line import NumberLineScenario
    from ophamin.seeing.substrate import KimeraAdapter

    value_range = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0e4
    max_numbers = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    t0 = time.time()
    sc = NumberLineScenario(value_range=value_range, max_numbers=max_numbers)
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=300.0)
    rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    persist_proof(rec, root="proofs", tier="scientific", scenario_name=sc.name)

    ev = rec.evidence[0]; d = ev.detail
    print(f"\n{'=' * 64}\nNUMBER-LINE — production number sense on real FRED numbers ({time.time()-t0:.0f}s)\n{'=' * 64}")
    print(f"verdict: {rec.verdict.outcome}")
    print(f"  Spearman(value, prime) = {ev.statistic_value:.4f}  (>= 0.90 → real number line)")
    print(f"  real numbers           = {d['n_numbers']}  range [{d['range_lo']:g}, {d['range_hi']:g}]")
    print(f"  distinct primes        = {d['distinct_fraction']:.3f}")
    print(f"  neighbour-locality     = {d['neighbour_locality_ratio']:.4f}  (adj/random; «1 → neighbours stay near)")
    print(f"  zero → prime           = {d['zero_prime']}  (the distinct origin)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
