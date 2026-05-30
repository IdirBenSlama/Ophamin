"""Run the percept-door scenario (faithful rich-vector→prime door) + persist the signed proof.

    PYTHONPATH="src:/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)" \
        .venv/bin/python -u examples/run_percept_door.py
"""
from __future__ import annotations

import time

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def main() -> int:
    from ophamin.measuring.proof.persistence import persist_proof
    from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
    from ophamin.measuring.scenarios.percept_door import PerceptDoorScenario
    from ophamin.seeing.substrate import KimeraAdapter

    t0 = time.time()
    sc = PerceptDoorScenario()
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=300.0)
    rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    persist_proof(rec, root="proofs", tier="scientific", scenario_name=sc.name)

    ev = rec.evidence[0]; d = ev.detail
    print(f"\n{'=' * 66}\nPERCEPT-DOOR — faithful rich-vector→prime door ({time.time()-t0:.0f}s)\n{'=' * 66}")
    print(f"verdict: {rec.verdict.outcome}")
    print(f"  deposited-chain prec@5 = {ev.statistic_value:.4f}  (>= 0.80 → faithful; chance {d['chance']:.3f})")
    print(f"  address ceiling prec@5 = {d['address_prec5']:.4f}")
    print(f"  retention (chain/addr) = {d['retention']:.2f}  (vs web-feel readout ~0.40)")
    print(f"  real Heimdall percepts = {d['n_percepts']}  ({d['n_classes']} classes, LSH planes {d['n_planes']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
