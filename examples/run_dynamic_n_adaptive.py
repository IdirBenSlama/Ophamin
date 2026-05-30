"""Run the dynamic-n-adaptive scenario (meaning finds its own dimension) + persist the signed proof.

    PYTHONPATH="src:/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)" \
        .venv/bin/python -u examples/run_dynamic_n_adaptive.py
"""
from __future__ import annotations

import time

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def main() -> int:
    from ophamin.measuring.proof.persistence import persist_proof
    from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
    from ophamin.measuring.scenarios.dynamic_n_adaptive import DynamicNAdaptiveScenario
    from ophamin.seeing.substrate import KimeraAdapter

    t0 = time.time()
    sc = DynamicNAdaptiveScenario()
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=300.0)
    rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    persist_proof(rec, root="proofs", tier="scientific", scenario_name=sc.name)

    ev = rec.evidence[0]; d = ev.detail
    print(f"\n{'=' * 70}\nDYNAMIC-N (ADAPTIVE) — meaning finds its own dimension ({time.time()-t0:.0f}s)\n{'=' * 70}")
    print(f"verdict: {rec.verdict.outcome}")
    print(f"  N trajectory (self-found, =round IPR): {d['N_trajectory']}  (grew={d['N_grew']})")
    print(f"  min(adaptive/generous recall@5) = {ev.statistic_value:.4f}  (>= 0.95 → near-optimal)")
    print(f"  min(adaptive − fixed5)          = {d['gap_min_adaptive_over_fixed5']:+.3f}  (beats the live default)")
    print(f"\n  {'size':>5}{'N_adapt':>9}{'IPR':>7}{'r5_adapt':>10}{'r5_fix5':>9}{'r5_gen':>8}{'N_gen':>7}")
    for s in d["stages"]:
        print(f"  {s['size']:>5}{s['N_adaptive']:>9}{s['ipr']:>7.1f}{s['recall5_adaptive']:>10.3f}"
              f"{s['recall5_fixed5']:>9.3f}{s['recall5_generous']:>8.3f}{s['N_generous']:>7}")
    print(f"\n  proof: {rec.proof_id[:16]}…  ({rec.verdict.outcome})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
