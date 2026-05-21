"""Run the Interface Contract Stability scenario against real Kimera-SWM — engineering facet.

The second structural check of the Build Cockpit. Fully static — does not
import Kimera, runs no substrate cycle. It parses every module in the
interface stratum and measures the fraction that keep their declared
contract (parseable, importable shape, public surface intact). The signed
proof lands in the corpus so the Cockpit's ``interface`` check turns from
"no proof yet" into a real per-commit data point.

    PYTHONPATH=src .venv/bin/python -u examples/run_interface_contract_stability.py
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios import InterfaceContractStabilityScenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier

# Same Kimera worktree as the other engineering-facet proofs, so the
# Cockpit's per-commit timeline stays on one substrate.
REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
COMPLIANCE_THRESHOLD = 0.95
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — ENGINEERING FACET: INTERFACE CONTRACT STABILITY")
    print(
        "Claim under test: at least "
        f"{COMPLIANCE_THRESHOLD:.0%} of Kimera's interface-stratum modules "
        "keep their declared contract (parseable + public surface intact)."
    )
    print("A REFUTED verdict surfaces interface drift — the substrate")
    print("breaking its own API.")

    scenario = InterfaceContractStabilityScenario(
        kimera_repo=REPO,
        threshold=COMPLIANCE_THRESHOLD,
    )
    print(f"\nsubstrate : kimera-swm @ {scenario.kimera_repo}")
    print("probe     : fully static parse of the interface stratum (no cycle)")

    try:
        record = scenario.run(sign_key=DEFAULT_SIGN_KEY)
    except Exception:  # noqa: BLE001
        banner("INTERFACE CONTRACT STABILITY RAISED")
        traceback.print_exc()
        return 1

    primary = next(
        e for e in record.evidence
        if e.statistic_name == "contract_compliance_rate"
    )

    banner("CONTRACT-COMPLIANCE RESULT")
    print(
        f"  contract compliance rate : {primary.statistic_value:.4f} "
        f"(threshold {COMPLIANCE_THRESHOLD:.2f}); "
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
