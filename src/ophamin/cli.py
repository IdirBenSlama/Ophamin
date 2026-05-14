"""Ophamin command-line interface.

    ophamin demo                     run the end-to-end mock experiment
    ophamin run <config.yaml>        run one experiment from a base config
    ophamin sweep <experiment.yaml>  run a parameter sweep (parent + children)
    ophamin probe-kimera <repo>      self-test the Kimera adapter
    ophamin lineage --list           list recorded runs
    ophamin lineage <run-id>         show a run's lineage chain
"""

from __future__ import annotations

import argparse
import json
import sys

from ophamin import __version__
from ophamin.config.sweep import SweepSpec, get_in, load_config, load_sweep
from ophamin.orchestration.experiment import ExperimentRunner
from ophamin.provenance.lineage import LineageStore
from ophamin.substrate.kimera_adapter import KimeraAdapter, KimeraAdapterError
from ophamin.substrate.mock import MockSubstrate


def build_substrate(config: dict):
    """Construct the substrate under test from a config's ``substrate`` block."""
    kind = get_in(config, "substrate.kind", "mock")
    if kind == "mock":
        return MockSubstrate(
            seed=int(get_in(config, "experiment.seed", 0)),
            collapse_cells=list(get_in(config, "substrate.collapse_cells", []) or []),
        )
    if kind == "kimera":
        repo = get_in(config, "substrate.kimera_repo", "")
        if not repo:
            raise SystemExit(
                "substrate.kimera_repo must be set when substrate.kind == 'kimera'"
            )
        python_exe = get_in(config, "substrate.kimera_python", "") or None
        try:
            return KimeraAdapter(repo, python_exe=python_exe)
        except KimeraAdapterError as exc:
            raise SystemExit(f"Kimera adapter could not be constructed: {exc}")
    raise SystemExit(f"unknown substrate.kind: {kind!r} (expected 'mock' or 'kimera')")


def cmd_demo(args: argparse.Namespace) -> int:
    """Run a small mock sweep end-to-end — no external system required."""
    base = {
        "experiment": {"cycles_per_run": 120, "warmup_cycles": 2, "seed": 20260514},
        "substrate": {"kind": "mock", "params": {}},
        "observability": {"spc": {"sigma_limit": 3.0}},
        "adaptive": {"msprt_mixing_variance": 1.0, "msprt_alpha": 0.05},
        "robustness": {"n_iterations": 150, "train_fraction": 0.7},
        "provenance": {"lineage_root": args.root},
    }
    sweep = SweepSpec(
        base_config=base,
        parent_name="ophamin-demo",
        parent_description="End-to-end mock experiment exercising all six pillars.",
        grid={
            "substrate.params.injection_rate": [0.1, 0.4, 0.7, 0.95],
            "substrate.params.immune_threshold": [0.45, 0.9],
        },
        stimuli=["alpha stimulus", "beta stimulus", "gamma stimulus"],
        diagnostics={"anticipatory_failure": True, "cognitive_inertia": True},
    )
    sut = MockSubstrate(seed=base["experiment"]["seed"])
    runner = ExperimentRunner(LineageStore(args.root))
    experiment = runner.run_sweep(sut, sweep)
    print(experiment.summary())
    print(f"\nlineage written to: {args.root}/")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    sut = build_substrate(config)
    lineage = LineageStore(get_in(config, "provenance.lineage_root", args.root))
    runner = ExperimentRunner(lineage)
    stimuli = args.stimuli.split(",") if args.stimuli else [None]
    result = runner.run_single(sut, config, stimuli=stimuli)
    print(f"run {result.run_id}  ({result.n_cycles} cycles)")
    for pillar in result.pillars:
        print(f"  {pillar.pillar:<18} [{pillar.status}] {pillar.summary}")
    print(f"\nlineage written to: {lineage.root}/{result.run_id}/")
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    sweep = load_sweep(args.config)
    sut = build_substrate(sweep.base_config)
    lineage = LineageStore(
        get_in(sweep.base_config, "provenance.lineage_root", args.root)
    )
    runner = ExperimentRunner(lineage)
    experiment = runner.run_sweep(sut, sweep)
    print(experiment.summary())
    print(f"\nlineage written to: {lineage.root}/")
    return 0


def cmd_probe_kimera(args: argparse.Namespace) -> int:
    try:
        adapter = KimeraAdapter(args.repo, python_exe=args.python or None)
    except KimeraAdapterError as exc:
        print(f"adapter misconfigured: {exc}", file=sys.stderr)
        return 2
    report = adapter.probe()
    print(json.dumps(report, indent=2))
    return 0 if report.get("runner_ok") and report.get("takwin_construct_ok") else 1


def cmd_lineage(args: argparse.Namespace) -> int:
    store = LineageStore(args.root)
    if args.list or not args.run_id:
        runs = store.list_runs()
        if not runs:
            print(f"(no runs recorded in {store.root})")
            return 0
        for run_id in runs:
            record = store.get_run(run_id)
            parent = record.parent_run_id or "-"
            print(f"{run_id}  parent={parent}  substrate={record.substrate_git_commit}")
        return 0
    chain = store.lineage_of(args.run_id)
    for depth, record in enumerate(chain):
        indent = "  " * depth
        print(f"{indent}{record.run_id}")
        print(f"{indent}  created   : {record.manifest.get('created_at')}")
        print(f"{indent}  substrate : {record.manifest.get('substrate', {}).get('name')} "
              f"@ {record.substrate_git_commit or '(no commit)'}")
        print(f"{indent}  config#   : {record.config_hash[:12]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ophamin",
        description="Ophamin — empirical framework for iterative experimentation.",
    )
    parser.add_argument("--version", action="version", version=f"ophamin {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="run the end-to-end mock experiment")
    p_demo.add_argument("--root", default="runs", help="lineage store directory")
    p_demo.set_defaults(func=cmd_demo)

    p_run = sub.add_parser("run", help="run one experiment from a base config")
    p_run.add_argument("config", help="path to a base config YAML")
    p_run.add_argument("--root", default="runs", help="lineage store directory")
    p_run.add_argument("--stimuli", default="", help="comma-separated stimuli")
    p_run.set_defaults(func=cmd_run)

    p_sweep = sub.add_parser("sweep", help="run a parameter sweep")
    p_sweep.add_argument("config", help="path to a sweep YAML (experiment_vars.yaml)")
    p_sweep.add_argument("--root", default="runs", help="lineage store directory")
    p_sweep.set_defaults(func=cmd_sweep)

    p_probe = sub.add_parser("probe-kimera", help="self-test the Kimera adapter")
    p_probe.add_argument("repo", help="path to the Kimera-SWM repository")
    p_probe.add_argument("--python", default="", help="path to the Kimera venv python")
    p_probe.set_defaults(func=cmd_probe_kimera)

    p_lin = sub.add_parser("lineage", help="inspect the lineage store")
    p_lin.add_argument("run_id", nargs="?", default="", help="run id to trace")
    p_lin.add_argument("--list", action="store_true", help="list all recorded runs")
    p_lin.add_argument("--root", default="runs", help="lineage store directory")
    p_lin.set_defaults(func=cmd_lineage)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
