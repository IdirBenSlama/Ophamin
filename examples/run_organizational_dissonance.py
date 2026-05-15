"""Run the Organizational Dissonance scenario against real Kimera-SWM.

Streams real Enron emails through Kimera's entity target (Takwin) and
measures the dissonance-machinery's active rate on GWF-cleared cycles.

Pre-registered claim: on routine organizational email that clears the GWF,
the dissonance layer fires (dissonance_events_count >= 1) in >= 90% of
cycles (the architectural active-dissonance floor).

A REFUTED verdict would surface a wiring or calibration gap in the
dissonance layer's coupling to real-world organizational signal. A VALIDATED
verdict pins a useful operating point. Secondary descriptive evidence
characterizes the distribution.

    PYTHONPATH=src .venv/bin/python -u examples/run_organizational_dissonance.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.scenarios import OrganizationalDissonanceScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate import KimeraAdapter

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
N_CYCLES = 1000
ACTIVE_FLOOR = 0.90
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — CATASTROPHIC SCENARIO #3: ORGANIZATIONAL DISSONANCE")
    print(
        f"Claim under test: on routine organizational email that clears Kimera's "
        f"GWF, the dissonance machinery fires (dissonance_events_count >= 1) in "
        f">= {ACTIVE_FLOOR:.0%} of cycles."
    )
    print("A REFUTED verdict is the framework working — it names a real debt.")

    # entity target — real Takwin, ~1.5-3 s/cycle in batch mode. 2h batch
    # timeout covers the worst-case 1000-cycle run with thermal throttling.
    substrate = KimeraAdapter(
        REPO, target="entity", mode="batch", batch_timeout=7200.0
    )
    scenario = OrganizationalDissonanceScenario(
        n_cycles=N_CYCLES, active_floor=ACTIVE_FLOOR
    )
    print(f"corpus    : {scenario.corpus_name} (Enron CMU release)")
    print(f"substrate : {substrate.name} @ {substrate.git_commit()[:12]}")
    print(f"target    : entity  ({substrate.metadata()['target_class']})")
    print(f"streaming : up to {N_CYCLES} emails (body 100-4000 chars; may take ~30-90 min)")

    try:
        record = scenario.run(substrate, sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("ORGANIZATIONAL DISSONANCE RAISED")
        traceback.print_exc()
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    short = record.proof_id[:16]
    json_path = OUT_DIR / f"organizational_dissonance_{short}.json"
    md_path = OUT_DIR / f"organizational_dissonance_{short}.md"
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
        if e.statistic_name == "dissonance_active_rate_on_cleared"
    )
    diss_intensity = next(
        e for e in record.evidence
        if e.statistic_name == "dissonance_events_count_median"
    )
    pds = next(
        e for e in record.evidence
        if e.statistic_name == "productive_dissonance_score_median"
    )
    gwf_block = next(
        e for e in record.evidence
        if e.statistic_name == "gwf_block_rate_on_enron"
    )
    manip = next(
        e for e in record.evidence
        if e.statistic_name == "manipulation_detected_rate_on_enron"
    )

    banner("DESCRIPTIVE EVIDENCE")
    d_dist = diss_intensity.detail["distribution"]
    p_dist = pds.detail["distribution"]
    print(f"GWF block rate on Enron        : {gwf_block.statistic_value:.1%}")
    print(f"manipulation_detected rate     : {manip.statistic_value:.1%}")
    print(f"dissonance_events (cleared)    : "
          f"n={d_dist['n']}  median={d_dist['median']:.0f}  "
          f"mean={d_dist['mean']:.1f}  range=[{d_dist['min']:.0f}, {d_dist['max']:.0f}]  "
          f"p10/p90={d_dist['p10']:.0f}/{d_dist['p90']:.0f}")
    print(f"productive_dissonance_score    : "
          f"n={p_dist['n']}  median={p_dist['median']:.3f}  "
          f"mean={p_dist['mean']:.3f}  range=[{p_dist['min']:.3f}, {p_dist['max']:.3f}]")

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"observed    : {primary.statistic_value:.1%} active on cleared")
    print(f"             ({primary.detail['cleared_active']}/"
          f"{primary.detail['cleared_total']} cleared cycles)")
    print(f"reasoning   : {record.verdict.reasoning}")
    print(f"proof       : {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
