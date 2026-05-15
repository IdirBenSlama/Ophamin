"""End-to-end Ophamin experiment on the MockSubstrate.

Runnable with no external system:

    PYTHONPATH=src python examples/run_mock_experiment.py

It exercises every OFAMIN pillar and the three substrate diagnostics, then shows
what the lineage store recorded. Swapping the MockSubstrate for a KimeraAdapter
(see the README) points the exact same machinery at Kimera-SWM.
"""

from __future__ import annotations

import tempfile

from ophamin.config.sweep import SweepSpec
from ophamin.measuring.pillars.diagnostics.kernel_coupling import OracleKernelCouplingDiagnostic
from ophamin.comparing.orchestration.experiment import ExperimentRunner
from ophamin.comparing.provenance.lineage import LineageStore
from ophamin.seeing.substrate.mock import MockSubstrate


def main() -> None:
    lineage_root = tempfile.mkdtemp(prefix="ophamin_demo_")

    # ----------------------------------------------------------------- sweep
    base_config = {
        "experiment": {"cycles_per_run": 160, "warmup_cycles": 3, "seed": 20260514},
        "substrate": {
            "kind": "mock",
            # a variant split makes the O.srm pillar applicable
            "params": {"variant_split": {"control": 0.5, "treatment": 0.5}},
        },
        "observability": {
            "spc": {"sigma_limit": 3.0},
            "srm": {"expected_ratios": {"control": 0.5, "treatment": 0.5}, "alpha": 0.001},
        },
        "adaptive": {"msprt_mixing_variance": 1.0, "msprt_alpha": 0.05},
        "robustness": {"n_iterations": 200, "train_fraction": 0.7},
        "provenance": {"lineage_root": lineage_root},
    }

    sweep = SweepSpec(
        base_config=base_config,
        parent_name="organizational-dissonance-sweep",
        parent_description="Injection rate x immune threshold on the MockSubstrate.",
        grid={
            "substrate.params.injection_rate": [0.1, 0.4, 0.7, 0.95],
            "substrate.params.immune_threshold": [0.45, 0.9],
        },
        stimuli=["alpha stimulus", "beta stimulus", "gamma stimulus"],
        diagnostics={"anticipatory_failure": True, "cognitive_inertia": True},
    )

    sut = MockSubstrate(seed=base_config["experiment"]["seed"])
    lineage = LineageStore(lineage_root)
    runner = ExperimentRunner(lineage)

    print("=" * 78)
    print("OPHAMIN — end-to-end mock experiment")
    print("=" * 78)
    print(f"sweep: {len(sweep)} child runs "
          f"({base_config['experiment']['cycles_per_run']} cycles each)\n")

    experiment = runner.run_sweep(sut, sweep)

    # ------------------------------------------------------- per-child pillars
    print("PER-CHILD PILLARS (O observability, A adaptive, N robustness)")
    print("-" * 78)
    for child in experiment.children:
        print(f"\n  child {child.run_id}")
        print(f"    sweep point: {child.sweep_point}")
        for pillar in child.pillars:
            print(f"    {pillar.pillar:<18} [{pillar.status:^7}] {pillar.summary}")

    # ----------------------------------------------------- parent-level pillars
    print()
    print("PARENT-LEVEL PILLARS (I synthesis, M effects)")
    print("-" * 78)
    for pillar in experiment.pillars:
        print(f"  {pillar.pillar:<18} [{pillar.status:^7}] {pillar.summary}")

    # --------------------------------------------- kernel-coupling diagnostic
    print()
    print("ORACLE KERNEL-COUPLING DIAGNOSTIC (variable isolation)")
    print("-" * 78)
    collapse_sut = MockSubstrate(seed=7, collapse_cells=["C_3,7", "C_8,2"])
    diagnostic = OracleKernelCouplingDiagnostic(
        entropy_coefficients=[0.005, 0.01, 0.05, 0.20], n_reps=8
    )
    kc = diagnostic.sweep(collapse_sut, cells=["C_3,7", "C_8,2", "C_0,0"])
    print(kc.summary())

    # ----------------------------------------------------------- provenance
    print()
    print("LINEAGE STORE")
    print("-" * 78)
    runs = lineage.list_runs()
    print(f"  {len(runs)} runs recorded under {lineage_root}")
    parent = lineage.get_run(experiment.parent_run_id)
    print(f"  parent run {parent.run_id}")
    print(f"    substrate    : {parent.manifest['substrate']['name']} "
          f"@ {parent.substrate_git_commit or '(no commit)'}")
    print(f"    config hash  : {parent.config_hash[:16]}")
    print(f"    ophamin@     : {parent.manifest['ophamin_git_commit'] or '(not a git repo)'}")
    sample_child = lineage.get_run(experiment.children[0].run_id)
    prov = sample_child.manifest.get("provenance") or {}
    print(f"  sample child {sample_child.run_id}")
    print(f"    PROV-O nodes : {len(prov.get('entity', {}))} entities, "
          f"{len(prov.get('activity', {}))} activities, "
          f"{len(prov.get('agent', {}))} agents")
    print(f"    lineage chain: "
          f"{' <- '.join(r.run_id for r in lineage.lineage_of(sample_child.run_id))}")

    print()
    print("=" * 78)
    print("done — all six pillars + three diagnostics exercised on the MockSubstrate.")
    print(f"inspect the manifests under: {lineage_root}")
    print("=" * 78)


if __name__ == "__main__":
    main()
