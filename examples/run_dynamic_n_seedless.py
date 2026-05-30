"""Run the dynamic-n-seedless scenario (a default substrate finds its own dimension, no seed) + sign.

    PYTHONPATH="src:/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)" \
        .venv/bin/python -u examples/run_dynamic_n_seedless.py
"""
from __future__ import annotations

import time

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def main() -> int:
    from ophamin.measuring.proof.persistence import persist_proof
    from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
    from ophamin.measuring.scenarios.dynamic_n_seedless import DynamicNSeedlessScenario
    from ophamin.seeing.substrate import KimeraAdapter

    t0 = time.time()
    sc = DynamicNSeedlessScenario()
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=600.0)
    rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    persist_proof(rec, root="proofs", tier="scientific", scenario_name=sc.name)

    ev = rec.evidence[0]; d = ev.detail
    print(f"\n{'=' * 72}\nDYNAMIC-N (SEEDLESS) — a default substrate finds its own dimension ({time.time()-t0:.0f}s)\n{'=' * 72}")
    print(f"verdict: {rec.verdict.outcome}")
    print(f"  cold start: N={d['n_start']} learned_geoid={d['learned_start']} (nothing imposed)")
    print(f"  BOOTSTRAP at cycle {d['bootstrapped_at']} → learned-N from its OWN cloud (no seed)")
    print(f"  N path: {d['n_path']}  →  end N={d['n_end']} ({d['n_grows']} grows, {d['geoids_end']} geoids)")
    print(f"  post-bootstrap mean Φ = {ev.statistic_value:.3f}  (>= 0.5 → coherent; min {d['phi_min']})")
    print(f"\n  proof: {rec.proof_id[:16]}…  ({rec.verdict.outcome})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
