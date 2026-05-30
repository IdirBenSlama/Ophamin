"""Run the dynamic-n-live-refit scenario (runtime dynamic-N) + persist the signed proof.

    PYTHONPATH="src:/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)" \
        .venv/bin/python -u examples/run_dynamic_n_live_refit.py
"""
from __future__ import annotations

import time

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def main() -> int:
    from ophamin.measuring.proof.persistence import persist_proof
    from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
    from ophamin.measuring.scenarios.dynamic_n_live_refit import DynamicNLiveRefitScenario
    from ophamin.seeing.substrate import KimeraAdapter

    t0 = time.time()
    sc = DynamicNLiveRefitScenario()
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=600.0)
    rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    persist_proof(rec, root="proofs", tier="scientific", scenario_name=sc.name)

    ev = rec.evidence[0]; d = ev.detail
    print(f"\n{'=' * 70}\nDYNAMIC-N (LIVE RE-FIT) — N grows mid-session, cycle coherent ({time.time()-t0:.0f}s)\n{'=' * 70}")
    print(f"verdict: {rec.verdict.outcome}")
    print(f"  N grew mid-session: {d['n_pre']} → {d['n_post']}  (IPR {d['ipr']:.1f}, "
          f"{d['reprojected']} geoids re-projected, grew={d['grew']})")
    print(f"  post-grow mean Φ = {ev.statistic_value:.3f}  (>= 0.5 → coherent; naive swap → Φ=0)")
    print(f"  pre-grow Φ {[round(p, 3) for p in d['pre_grow_phi']]}")
    print(f"  post-grow Φ {[round(p, 3) for p in d['post_grow_phi']]}")
    print(f"\n  proof: {rec.proof_id[:16]}…  ({rec.verdict.outcome})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
