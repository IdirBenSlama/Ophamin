"""End-to-end tests for the orchestration layer — pillars wired together."""

from ophamin.config.sweep import SweepSpec
from ophamin.comparing.orchestration.experiment import ExperimentRunner
from ophamin.comparing.provenance.lineage import LineageStore
from ophamin.seeing.substrate.mock import MockSubstrate

_VALID_STATUSES = {"ok", "alert", "skipped"}


def _config(tmp_path, cycles=80, with_variants=False):
    cfg = {
        "experiment": {"cycles_per_run": cycles, "warmup_cycles": 2, "seed": 1},
        "substrate": {"kind": "mock", "params": {}},
        "observability": {"spc": {"sigma_limit": 3.0}},
        "adaptive": {"msprt_mixing_variance": 1.0, "msprt_alpha": 0.05},
        "robustness": {"n_iterations": 50, "train_fraction": 0.7},
        "provenance": {"lineage_root": str(tmp_path / "runs")},
    }
    if with_variants:
        cfg["substrate"]["params"]["variant_split"] = {"control": 0.5, "treatment": 0.5}
        cfg["observability"]["srm"] = {
            "expected_ratios": {"control": 0.5, "treatment": 0.5},
            "alpha": 0.001,
        }
    return cfg


def test_run_single_produces_per_run_pillars(tmp_path):
    store = LineageStore(tmp_path / "runs")
    runner = ExperimentRunner(store)
    result = runner.run_single(MockSubstrate(seed=1), _config(tmp_path), stimuli=["a", "b"])

    pillar_names = {p.pillar for p in result.pillars}
    assert {"O.spc", "O.srm", "A.msprt", "N.mccv"} <= pillar_names
    for p in result.pillars:
        assert p.status in _VALID_STATUSES

    # without a variant split, SRM is not applicable — reported skipped, not faked
    srm = next(p for p in result.pillars if p.pillar == "O.srm")
    assert srm.status == "skipped"

    # the run was recorded with a provenance graph
    assert result.run_id in store.list_runs()
    manifest = store.get_run(result.run_id).manifest
    assert manifest["provenance"] is not None
    assert manifest["substrate"]["name"] == "mock"


def test_run_single_srm_active_with_variant_split(tmp_path):
    runner = ExperimentRunner(LineageStore(tmp_path / "runs"))
    result = runner.run_single(
        MockSubstrate(seed=1), _config(tmp_path, with_variants=True), stimuli=["a"]
    )
    srm = next(p for p in result.pillars if p.pillar == "O.srm")
    assert srm.status in ("ok", "alert")  # applicable now, not skipped


def test_run_sweep_produces_children_and_parent_pillars(tmp_path):
    store = LineageStore(tmp_path / "runs")
    runner = ExperimentRunner(store)
    sweep = SweepSpec(
        base_config=_config(tmp_path, cycles=80),
        parent_name="test-sweep",
        grid={
            "substrate.params.injection_rate": [0.1, 0.5, 0.9],
            "substrate.params.immune_threshold": [0.4, 0.9],
        },
        stimuli=["a", "b"],
        diagnostics={"anticipatory_failure": True, "cognitive_inertia": True},
    )
    experiment = runner.run_sweep(MockSubstrate(seed=1), sweep)

    assert len(experiment.children) == 6
    parent_pillars = {p.pillar for p in experiment.pillars}
    assert {"I.cma", "M.mixed_effects", "M.mea"} <= parent_pillars
    for p in experiment.pillars:
        assert p.status in _VALID_STATUSES

    cma = next(p for p in experiment.pillars if p.pillar == "I.cma")
    assert cma.status == "ok"
    assert "trajectory" in cma.detail and len(cma.detail["trajectory"]) == 6

    me = next(p for p in experiment.pillars if p.pillar == "M.mixed_effects")
    assert me.status == "ok"
    assert "icc" in me.detail

    # diagnostics ran on each child
    child_pillars = {p.pillar for p in experiment.children[0].pillars}
    assert "diag.anticipatory" in child_pillars
    assert "diag.inertia" in child_pillars

    # lineage: one parent + six children
    runs = store.list_runs()
    assert experiment.parent_run_id in runs
    assert len(runs) == 7
    chain = store.lineage_of(experiment.children[0].run_id)
    assert [r.run_id for r in chain] == [
        experiment.children[0].run_id,
        experiment.parent_run_id,
    ]
