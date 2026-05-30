"""Run the interoception-fidelity scenario (live internal-event chain: real Takwin
builders → faithful door) + persist the signed proof.

    PYTHONPATH="src:/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)" \
        .venv/bin/python -u examples/run_interoception_fidelity.py [value_range] [max_numbers]
"""
from __future__ import annotations

import sys
import time

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def main() -> int:
    from ophamin.measuring.proof.persistence import persist_proof
    from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
    from ophamin.measuring.scenarios.interoception_fidelity import InteroceptionFidelityScenario
    from ophamin.seeing.substrate import KimeraAdapter

    value_range = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0e4
    max_numbers = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    t0 = time.time()
    sc = InteroceptionFidelityScenario(value_range=value_range, max_numbers=max_numbers)
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=300.0)
    rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    persist_proof(rec, root="proofs", tier="scientific", scenario_name=sc.name)

    ev = rec.evidence[0]; d = ev.detail
    print(f"\n{'=' * 70}\nINTEROCEPTION-FIDELITY — live chain (real builders → door) ({time.time()-t0:.0f}s)\n{'=' * 70}")
    print(f"verdict: {rec.verdict.outcome}")
    print(f"  door min-Spearman(mag, prime) = {ev.statistic_value:.4f}  (>= 0.95 → faithful)")
    print(f"  fingerprint baseline mean      = {d['fingerprint_mean_spearman']:.4f}  (legacy name-fingerprint)")
    print(f"  real magnitudes                = {d['n_magnitudes']}  range [{d['range_lo']:g}, {d['range_hi']:g}]")
    for k, v in d["per_builder"].items():
        print(f"  {k:<26} door ρ={v['door_rho']:.4f} ({v['door_distinct']:.3f} distinct)  "
              f"vs fingerprint ρ={v['fingerprint_rho']:.4f} ({v['fingerprint_distinct']:.3f} distinct)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
