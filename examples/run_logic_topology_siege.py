"""Run the Logic-Topology Siege scenario against real Kimera-SWM.

Streams Linux kernel commit messages (~1.4M commits, real torvalds/linux
mirror) through Kimera's entity target (Takwin) and measures whether the
substrate's walker reaches sustained traversal (halt_mode == 'exhausted') on
technical-reasoning content, rather than collapsing to amplitude_death.

Pre-registered claim: on GWF-cleared Linux kernel commits, the walker
reaches sustained traversal in >= 60% of cycles (the architectural
sustained-traversal floor).

A REFUTED verdict would surface a walker calibration gap on technical
content; a VALIDATED verdict pins the substrate's engagement profile on
technical-reasoning text. Secondary evidence reports the full halt-mode
distribution, the amplitude_death rate, GWF block rate, dissonance and Φ
distributions.

    PYTHONPATH=src .venv/bin/python -u examples/run_logic_topology_siege.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.scenarios import LogicTopologySiegeScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_CYCLES = 1000
SUSTAINED_FLOOR = 0.60
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — CATASTROPHIC SCENARIO #4: LOGIC-TOPOLOGY SIEGE")
    print(
        f"Claim under test: on GWF-cleared Linux kernel commits, the walker "
        f"reaches sustained traversal (halt_mode == 'exhausted') in "
        f">= {SUSTAINED_FLOOR:.0%} of cycles."
    )
    print("A REFUTED verdict is the framework working — it names a real debt.")

    substrate = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=7200.0
    )
    scenario = LogicTopologySiegeScenario(
        n_cycles=N_CYCLES, sustained_floor=SUSTAINED_FLOOR
    )
    print(f"corpus    : {scenario.corpus_name} (Linux kernel commits, real torvalds/linux mirror)")
    print(f"substrate : {substrate.name} @ {substrate.git_commit()[:12]}")
    print(f"target    : entity  ({substrate.metadata()['target_class']})")
    print(f"streaming : up to {N_CYCLES} kernel commits (body 80-4000 chars; may take ~30-90 min)")

    try:
        record = scenario.run(substrate, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("LOGIC-TOPOLOGY SIEGE RAISED")
        traceback.print_exc()
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    short = record.proof_id[:16]
    json_path = OUT_DIR / f"logic_topology_siege_{short}.json"
    md_path = OUT_DIR / f"logic_topology_siege_{short}.md"
    record.to_json(str(json_path))
    record.to_markdown(str(md_path))

    print(record.to_markdown())
    problems = record.validate()
    sig_ok = record.verify_signature(DEFAULT_SIGN_KEY)
    print(f"\nvalidate()        : {'WELL-FORMED' if not problems else problems}")
    print(f"signature verifies: {sig_ok}")
    print(f"written           : {json_path}")
    print(f"                    {md_path}")

    primary = next(
        e for e in record.evidence
        if e.statistic_name == "sustained_traversal_rate_on_cleared"
    )
    ad = next(
        e for e in record.evidence
        if e.statistic_name == "amplitude_death_rate_on_cleared"
    )
    halt_dist = next(
        e for e in record.evidence
        if e.statistic_name == "halt_modes_observed_count"
    )
    gwf_block = next(
        e for e in record.evidence
        if e.statistic_name == "gwf_block_rate_on_linux"
    )
    diss = next(
        e for e in record.evidence
        if e.statistic_name == "dissonance_events_count_median"
    )
    phi = next(
        e for e in record.evidence
        if e.statistic_name == "phi_value_median"
    )

    banner("DESCRIPTIVE EVIDENCE")
    print(f"GWF block rate on Linux        : {gwf_block.statistic_value:.1%}")
    print(f"amplitude_death rate           : {ad.statistic_value:.1%}")
    print(f"halt mode distribution         :")
    for mode, count in sorted(halt_dist.detail["distribution"].items(),
                              key=lambda x: -x[1]):
        denom = halt_dist.detail["denominator"]
        rate = count / denom if denom else 0
        print(f"    {mode:>20}  {count:>4}  ({rate:.1%})")
    diss_dist = diss.detail["distribution"]
    phi_dist = phi.detail["distribution"]
    print(f"dissonance_events (cleared)    : "
          f"n={diss_dist['n']}  median={diss_dist['median']:.0f}  "
          f"mean={diss_dist['mean']:.1f}  range=[{diss_dist['min']:.0f}, {diss_dist['max']:.0f}]")
    print(f"phi_value (cleared)            : "
          f"n={phi_dist['n']}  median={phi_dist['median']:.3f}  "
          f"mean={phi_dist['mean']:.3f}  range=[{phi_dist['min']:.3f}, {phi_dist['max']:.3f}]")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"observed    : {primary.statistic_value:.1%} sustained on cleared")
    print(f"             ({primary.detail['cleared_exhausted']}/"
          f"{primary.detail['cleared_total']} cleared cycles)")
    print(f"reasoning   : {record.verdict.reasoning}")
    print(f"proof       : {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
