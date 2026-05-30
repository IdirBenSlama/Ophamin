"""Run the ear-discrimination scenario (learned ear on real ESC-50) + persist the signed proof.

    PYTHONPATH="src:/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)" \
        .venv/bin/python -u examples/run_ear_discrimination.py
"""
from __future__ import annotations

import time

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def main() -> int:
    from ophamin.measuring.proof.persistence import persist_proof
    from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
    from ophamin.measuring.scenarios.ear_discrimination import EarDiscriminationScenario
    from ophamin.seeing.substrate import KimeraAdapter

    t0 = time.time()
    sc = EarDiscriminationScenario()
    adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=300.0)
    rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    persist_proof(rec, root="proofs", tier="scientific", scenario_name=sc.name)

    ev = rec.evidence[0]; d = ev.detail
    print(f"\n{'=' * 66}\nEAR-DISCRIMINATION — learned ear on real ESC-50 ({time.time()-t0:.0f}s)\n{'=' * 66}")
    print(f"verdict: {rec.verdict.outcome}")
    print(f"  learned-ear held-out prec@5 = {ev.statistic_value:.4f}  (>= 0.33 → faithful; chance {d['chance']:.3f})")
    print(f"  5-stat ear prec@5           = {d['fivestat_prec5']:.4f}  (margin {d['fivestat_margin']:.3f} ≈ random)")
    print(f"  raw log-mel prec@5          = {d['raw_logmel_prec5']:.4f}")
    print(f"  learned-ear margin          = {d['learned_margin']:.4f}  (real cluster structure)")
    print(f"  held-out fold {d['held_out_fold']}: {d['n_heldout']} clips, {d['n_classes']} classes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
