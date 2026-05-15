"""Live verification of the multi-component KimeraAdapter against the real repo.

Runnable with the Ophamin venv:

    PYTHONPATH=src .venv/bin/python -u examples/verify_kimera_adapter.py

It executes Kimera for real (heavy imports, real wall-time):
  1. probe()             — which of the 11 targets are reachable
  2. measure_throughput  — arachne (cheap component), batch mode
  3. measure_throughput  — rosetta, batch mode
  4. measure_throughput  — entity (Takwin, the integrated cycle), tiny batch
  5. one entity cycle    — to see the raw result shape

Performance is measured here, never assumed.
"""

from __future__ import annotations

import json
import sys

from ophamin.seeing.substrate import KIMERA_TARGETS, KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    sys.stdout.flush()


def main() -> None:
    # 1. PROBE -------------------------------------------------------------
    section("1. PROBE — target reachability in the connected Kimera repo")
    adapter = KimeraAdapter(REPO, target="entity")
    report = adapter.probe()
    print(f"runner_ok={report['runner_ok']}  git_commit={report.get('git_commit', '')[:12]}")
    targets = report.get("targets", {})
    reachable = []
    for name, info in targets.items():
        ok = info.get("import_ok")
        if ok:
            reachable.append(name)
        detail = info.get("init_sig", info.get("error", ""))
        print(f"  {name:11s} {'OK  ' if ok else 'FAIL'} {str(detail)[:78]}")
    print(f"\nreachable: {len(reachable)}/{len(KIMERA_TARGETS)} targets")
    sys.stdout.flush()

    # 2. THROUGHPUT — arachne (cheap component) ----------------------------
    section("2. THROUGHPUT — arachne (prime registry), batch mode, n=40")
    ad_arachne = KimeraAdapter(REPO, target="arachne", mode="batch")
    result = ad_arachne.measure_throughput([f"concept number {i}" for i in range(40)])
    print(json.dumps(result, indent=1))
    sys.stdout.flush()

    # 3. THROUGHPUT — rosetta ----------------------------------------------
    section("3. THROUGHPUT — rosetta (semantic translator), batch mode, n=40")
    ad_rosetta = KimeraAdapter(REPO, target="rosetta", mode="batch")
    result = ad_rosetta.measure_throughput([f"water flows downhill {i}" for i in range(40)])
    print(json.dumps(result, indent=1))
    sys.stdout.flush()

    # 4. THROUGHPUT — entity (Takwin) --------------------------------------
    section("4. THROUGHPUT — entity (Takwin, the integrated cycle), batch mode, n=3")
    ad_entity = KimeraAdapter(REPO, target="entity", mode="batch")
    result = ad_entity.measure_throughput(
        [f"memory is structure not data ({i})" for i in range(3)]
    )
    print(json.dumps(result, indent=1))
    sys.stdout.flush()

    # 5. one entity cycle — raw result shape -------------------------------
    section("5. ENTITY single cycle (subprocess mode) — raw result shape")
    ad_single = KimeraAdapter(REPO, target="entity", mode="subprocess")
    cycle = ad_single.run_cycle("the substrate causes intelligence")
    print(f"success={cycle.success}  halt_mode={cycle.halt_mode}")
    print(f"raw keys ({len(cycle.raw)}): {sorted(cycle.raw)[:20]}")
    if not cycle.success:
        print(f"error: {cycle.error}")
    sys.stdout.flush()

    print("\n" + "=" * 72)
    print("LIVE VERIFICATION COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
