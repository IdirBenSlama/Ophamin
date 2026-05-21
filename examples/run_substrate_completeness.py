"""Run the Substrate Completeness scenario against real Kimera-SWM — engineering facet.

The structural half of the Build Cockpit. Unlike the cognitive-tier
scenarios, this one runs NO Kimera cycle — it walks Kimera's source tree,
builds a repo-wide import graph, scans WIRED / WIRE_CANDIDATE / ARCHIVED
annotations, and emits a falsifiable claim about the aggregate orphan rate
(Kimera's hidden dead code). The signed proof carries the orphan +
WIRE_CANDIDATE *action lists* — the concrete completion work the operator
picks up.

The proof lands in the corpus bundle layout so the Build Cockpit's
``completeness`` check turns from "no proof yet" into a real per-commit
data point.

    PYTHONPATH=src .venv/bin/python -u examples/run_substrate_completeness.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios import SubstrateCompletenessScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier

# Same Kimera worktree the throughput-ceiling engineering proof was measured
# against, so the Cockpit's per-commit timeline stays on one substrate.
REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
ORPHAN_RATE_CEILING = 0.20
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — ENGINEERING FACET: SUBSTRATE COMPLETENESS")
    print(
        "Claim under test: across all 9 Kimera inventory strata, the "
        f"aggregate orphan rate is <= {ORPHAN_RATE_CEILING:.0%} — at least "
        "80% of inventoried surfaces are wired, WIRE_CANDIDATE, or archived."
    )
    print("A REFUTED verdict surfaces unwired load-bearing infrastructure;")
    print("the proof carries the per-surface completion action list.")

    scenario = SubstrateCompletenessScenario(
        kimera_repo=REPO,
        orphan_rate_ceiling=ORPHAN_RATE_CEILING,
    )
    print(f"\nsubstrate : kimera-swm @ {scenario.kimera_repo}")
    print("probe     : static import-graph + annotation scan (no cycle)")

    try:
        record = scenario.run(sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("SUBSTRATE COMPLETENESS RAISED")
        traceback.print_exc()
        return 1

    primary = next(
        e for e in record.evidence
        if e.statistic_name == "aggregate_orphan_rate"
    )
    d = primary.detail

    banner("ORPHAN-RATE BREAKDOWN")
    print(f"  python surfaces total : {d['n_python_surfaces_total']}")
    print(f"  wired                 : {d['n_wired_total']}")
    print(f"  wire_candidate        : {d['n_wire_candidate_total']}")
    print(f"  archived              : {d['n_archived_total']}")
    print(f"  orphan                : {d['n_orphan_total']}")
    print(f"  parse_error           : {d['n_parse_error_total']}")
    print(
        f"  aggregate orphan rate : {primary.statistic_value:.4f} "
        f"(ceiling {ORPHAN_RATE_CEILING:.2f}); "
        f"Wilson 95% CI [{primary.ci_low:.4f}, {primary.ci_high:.4f}]"
    )

    banner("VERDICT")
    print(f"verdict     : {record.verdict.outcome}")
    print(f"reasoning   : {record.verdict.reasoning}")

    bundle = persist_proof(
        record,
        root=OUT_DIR,
        tier=Tier.SCIENTIFIC.value,
        scenario_name=scenario.name,
    )
    print(f"proof       : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
