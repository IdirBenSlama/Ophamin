"""Parallel, capped substrate sweep — ends the single-core/serial bottleneck.

The bottleneck (measured 2026-05-24): run-all streamed scenarios SERIALLY on ONE
of 16 cores, some streaming thousands of records → days. Per warm cycle is ~1s;
the GPU (MPS) is already used by the encoder. So the fix is throughput, not GPU:
run scenarios as SEPARATE PROCESSES across the cores, each with a hard cycle cap.

Each worker builds a real KimeraAdapter (entity target) and runs one scenario,
capped, persisting its signed proof. Failures (non-default-instantiable /
mock-only / odd run() signature) are caught per-scenario and reported, never
crash the sweep.

    PYTHONPATH=src .venv/bin/python -u examples/run_parallel_sweep.py
"""

from __future__ import annotations

import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
import os as _os
CONCURRENCY = max(1, min(10, (_os.cpu_count() or 2) - 2))  # use most cores, RAM-bounded (16c/128GB → 10)
CYCLE_CAP = 40           # hard cap on any scenario's cycle/record count
ADAPTER_TIMEOUT = 900.0  # per-scenario batch timeout: a stuck scenario dies in 15min
CAP_ATTRS = {"n_cycles": CYCLE_CAP, "max_series": 8, "per_corpus_cycles": 15,
             "max_steps": 40, "n_stimuli": CYCLE_CAP, "n_exposures": 3}


def run_one(name: str):
    """Run one scenario in its own process against real Kimera, capped."""
    t0 = time.time()
    try:
        from ophamin.measuring.proof.persistence import persist_proof
        from ophamin.measuring.scenarios import SCENARIOS
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier
        from ophamin.seeing.substrate import KimeraAdapter

        cls = SCENARIOS[name]
        sc = cls()  # default-instantiable only; others raise → caught below
        for attr, cap in CAP_ATTRS.items():
            v = getattr(sc, attr, None)
            if isinstance(v, int) and v > cap:
                setattr(sc, attr, cap)

        adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=ADAPTER_TIMEOUT)
        try:
            rec = sc.run(adapter, sign_key=DEFAULT_SIGN_KEY)
        except TypeError:
            rec = sc.run(adapter)  # scenarios whose run() takes no sign_key kwarg
        tier = getattr(getattr(sc, "tier", None), "value", "scientific")
        persist_proof(rec, root="proofs", tier=tier, scenario_name=name)
        outcome = getattr(rec.verdict, "outcome", "?")
        stat = rec.evidence[0].statistic_value if getattr(rec, "evidence", None) else None
        return (name, str(outcome), round(stat, 3) if isinstance(stat, float) else stat, round(time.time() - t0, 1))
    except Exception as exc:  # noqa: BLE001
        return (name, "ERROR", f"{type(exc).__name__}: {str(exc)[:90]}", round(time.time() - t0, 1))


def main() -> int:
    from ophamin.measuring.scenarios import SCENARIOS

    names = sorted(SCENARIOS)
    print(f"parallel sweep: {len(names)} scenarios, concurrency={CONCURRENCY}, "
          f"cycle_cap={CYCLE_CAP}, target=entity @ real Kimera", flush=True)
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(run_one, n): n for n in names}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            print(f"  [{len(results):>2}/{len(names)}] {r[0]:<34} {str(r[1]):<10} "
                  f"{str(r[2]) if r[2] is not None else '':<10} {r[3]}s", flush=True)

    dur = time.time() - t0
    ok = [r for r in results if r[1] not in ("ERROR",)]
    err = [r for r in results if r[1] == "ERROR"]
    print(f"\n{'=' * 64}\nPARALLEL SWEEP DONE in {dur/60:.1f} min "
          f"({len(ok)} ran, {len(err)} skipped/errored)\n{'=' * 64}")
    print("\nVERDICTS (ran against real Kimera):")
    for r in sorted(ok):
        print(f"  {r[0]:<34} {r[1]:<10} stat={r[2]}  ({r[3]}s)")
    if err:
        print("\nSKIPPED/ERRORED (not default-instantiable or odd interface):")
        for r in sorted(err):
            print(f"  {r[0]:<34} {r[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
