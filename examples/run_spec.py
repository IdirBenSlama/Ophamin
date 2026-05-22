"""Run a grounded ScenarioSpec end-to-end: spec file → proof.

Closes the authoring pipeline:

    describe → ScenarioSpec (JSON file) → [grounding gate] → materialize
    → run on real substrate → signed proof → persisted bundle

The grounding gate refuses a synthetic or ungrounded spec before anything
runs. Flow / cycle scenarios are run against the live Kimera substrate.

    PYTHONPATH=src .venv/bin/python -u examples/run_spec.py path/to/spec.json
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from ophamin.authoring import (
    MaterializationError,
    ScenarioSpec,
    materialize_spec,
)
from ophamin.measuring.proof.persistence import persist_proof
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Tier

REPO = "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)"
OUT_DIR = Path("proofs")


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    spec_path = Path(sys.argv[1])
    if not spec_path.is_file():
        print(f"spec file not found: {spec_path}")
        return 2

    spec = ScenarioSpec.from_dict(json.loads(spec_path.read_text(encoding="utf-8")))
    banner(f"OPHAMIN — RUN SPEC: {spec.title}")
    print(f"scope/facet : {spec.scope} / {spec.facet}")
    print(f"template    : {spec.invariant_template}")
    print(f"data source : {spec.data_source.kind}:{spec.data_source.name}")
    print(f"threshold   : {spec.threshold.metric} {spec.threshold.comparator} {spec.threshold.value}")
    print(f"grounding   : {[g.ref for g in spec.grounding]}")

    # The grounding gate runs inside materialize_spec — an ungrounded or
    # synthetic spec is refused here, before anything executes.
    try:
        mat = materialize_spec(spec)
    except MaterializationError as exc:
        banner("SPEC REFUSED BY THE GROUNDING GATE")
        print(exc)
        for v in exc.violations:
            print(f"  [{v['severity'].upper()}] {v['code']}: {v['message']}")
        return 1

    print(f"\nmaterialised: {mat.scenario_name} ({type(mat.scenario).__name__})")
    print(f"build plan  : {json.dumps(mat.plan)}")

    # Run. Flow / cycle scenarios need the live substrate adapter.
    run_kwargs: dict = {"sign_key": DEFAULT_SIGN_KEY}
    if mat.needs_substrate:
        from ophamin.seeing.substrate import KimeraAdapter
        adapter = KimeraAdapter(REPO, target="entity", mode="batch", batch_timeout=3600.0)
        print(f"substrate   : {adapter.name} @ {adapter.git_commit()[:12]}")
        print(f"running     : {mat.scenario.n_cycles} cycles (may take a few minutes)")
        try:
            record = mat.scenario.run(adapter, **run_kwargs)
        except Exception:  # noqa: BLE001
            banner("RUN RAISED")
            traceback.print_exc()
            return 1
    else:
        record = mat.scenario.run(**run_kwargs)

    banner("VERDICT")
    print(f"verdict   : {record.verdict.outcome}")
    print(f"reasoning : {record.verdict.reasoning}")

    bundle = persist_proof(
        record, root=OUT_DIR, tier=Tier.SCIENTIFIC.value,
        scenario_name=mat.scenario_name,
    )
    print(f"proof     : {bundle.bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
