"""Run the Throughput Ceiling scenario against real Kimera-SWM — engineering-tier.

The first engineering-tier scenario in Ophamin: pre-registers a per-cycle
wall-time ceiling and measures p95 across a real Kimera batch wrapped in
``InstrumentedSubstrate``. A REFUTED verdict surfaces a throughput
regression; a VALIDATED verdict pins the substrate's engineering operating
point.

    PYTHONPATH=src .venv/bin/python -u examples/run_throughput_ceiling.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.instrumenting import InstrumentedSubstrate
from ophamin.measuring.scenarios import ThroughputCeilingScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_CYCLES = 200
P95_CEILING_S = 4.0     # the 5-cycle smoke showed ~2.5s/cycle; 4.0s ceiling is informative
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — ENGINEERING-TIER SCENARIO: THROUGHPUT CEILING")
    print(
        f"Claim under test: under sustained load on a balanced text corpus, "
        f"Kimera's entity target completes each cycle in under "
        f"{P95_CEILING_S:.2f}s at the 95th percentile."
    )
    print("A REFUTED verdict surfaces a real engineering regression.")

    adapter = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=3600.0
    )
    # The scenario wraps the adapter in InstrumentedSubstrate internally; we
    # could pass an already-instrumented substrate here too — the scenario
    # detects and reuses.
    scenario = ThroughputCeilingScenario(
        n_cycles=N_CYCLES,
        p95_wall_time_ceiling_s=P95_CEILING_S,
    )
    print(f"corpus    : {scenario.corpus_name}")
    print(f"substrate : {adapter.name} @ {adapter.git_commit()[:12]}")
    print(f"target    : entity  ({adapter.metadata()['target_class']})")
    print(f"streaming : up to {N_CYCLES} cycles (may take ~5-15 min)")

    try:
        record = scenario.run(adapter, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("THROUGHPUT CEILING RAISED")
        traceback.print_exc()
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    short = record.proof_id[:16]
    json_path = OUT_DIR / f"throughput_ceiling_{short}.json"
    md_path = OUT_DIR / f"throughput_ceiling_{short}.md"
    record.to_json(str(json_path))
    record.to_markdown(str(md_path))

    primary = next(
        e for e in record.evidence
        if e.statistic_name == "p95_cycle_wall_time_s"
    )
    dist = next(
        e for e in record.evidence
        if e.statistic_name == "cycle_wall_time_distribution"
    )
    cpu = next(
        (e for e in record.evidence if e.statistic_name == "batch_cpu_total_s"),
        None,
    )
    rss = next(
        (e for e in record.evidence if e.statistic_name == "rss_peak_bytes"),
        None,
    )

    banner("PER-CYCLE WALL-TIME DISTRIBUTION")
    d = dist.detail
    print(f"  n cycles measured  : {d['n']}")
    print(f"  min                : {d['min']:.3f}s")
    print(f"  median (p50)       : {d['median']:.3f}s")
    print(f"  mean               : {d['mean']:.3f}s")
    print(f"  p95 (primary)      : {d['p95']:.3f}s  (ceiling: {P95_CEILING_S:.2f}s)")
    print(f"  p99                : {d['p99']:.3f}s")
    print(f"  max                : {d['max']:.3f}s")

    if cpu is not None and rss is not None:
        banner("BATCH RESOURCE PROFILE")
        cpu_detail = cpu.detail
        rss_detail = rss.detail
        print(f"  batch cpu total      : {cpu.statistic_value:.2f}s "
              f"(user {cpu_detail['user_s']:.2f} + system {cpu_detail['system_s']:.2f})")
        print(f"  cpu source           : {cpu_detail['cpu_source']} "
              f"({cpu_detail['sampler_polls']} polls)")
        print(f"  rss before / after   : "
              f"{rss_detail['rss_before_bytes']/1e6:.1f}MB / "
              f"{rss_detail['rss_after_bytes']/1e6:.1f}MB")
        print(f"  rss peak             : {rss.statistic_value/1e6:.1f}MB")
        print(f"  max threads          : {rss_detail['threads_max']}")
        print(f"  max process tree     : {rss_detail['process_count_max']}")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"observed    : p95 cycle wall-time = {primary.statistic_value:.3f}s "
          f"(ceiling {P95_CEILING_S:.2f}s)")
    print(f"reasoning   : {record.verdict.reasoning}")
    print(f"proof       : {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
