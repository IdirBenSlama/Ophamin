"""Generic Ophamin scenario runner — dispatches by name into SCENARIOS.

Single template that runs any registered scenario whose ``__init__``
accepts no required arguments beyond the default values. Per-scenario
example runners (``run_immune_siege.py`` etc.) remain in this
directory as illustrative templates for scenarios that need
non-default configuration.

Usage:

    python examples/run_scenario.py <scenario-name> [--target T] [--n-cycles N]

For the list of registered scenarios:

    ophamin scenario list

For one scenario's full metadata block:

    ophamin scenario show <name>

Most empirical-deep scenarios require a captured-trajectory path; this
runner skips them with a clear error rather than guessing the path.
Use the dedicated capture scripts in the Kimera-SWM observatory tree
to produce the trajectory, then construct the scenario directly in
Python (the runner is a convenience for the trajectory-free cases).
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

from ophamin.measuring.proof import dump as proof_dump
from ophamin.measuring.scenarios import SCENARIOS
from ophamin.seeing.substrate import MockSubstrate


def _select_scenario(name: str):
    cls = SCENARIOS.get(name)
    if cls is None:
        available = ", ".join(sorted(SCENARIOS))
        sys.exit(
            f"run_scenario.py: unknown scenario {name!r}\n"
            f"  available: {available}\n"
            f"  see also: `ophamin scenario list`"
        )
    return cls


def _scenario_needs_required_args(cls) -> tuple[bool, list[str]]:
    """Inspect the scenario's ``__init__`` for required positional/keyword args.

    Returns ``(needs_args, names)``. A scenario whose constructor has any
    parameter without a default (besides ``self``) is not safe to
    instantiate from this generic runner.
    """
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return False, []
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    return bool(required), required


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a registered Ophamin scenario by name."
    )
    parser.add_argument(
        "name",
        help="scenario name (e.g. concentrated-immune-siege; see `ophamin scenario list`)",
    )
    parser.add_argument(
        "--n-cycles",
        type=int,
        default=None,
        help="optional override for the scenario's default cycle count",
    )
    parser.add_argument(
        "--out",
        default="",
        help="output path for the signed proof JSON (default: print to stdout)",
    )
    args = parser.parse_args(argv)

    cls = _select_scenario(args.name)
    needs_args, names = _scenario_needs_required_args(cls)
    if needs_args:
        sys.exit(
            f"run_scenario.py: {args.name!r} requires constructor argument(s): "
            f"{', '.join(names)}\n"
            f"  this scenario is not safe to run from the generic template — "
            f"construct it directly in Python with the required argument(s) provided.\n"
            f"  see `ophamin scenario show {args.name}` for context."
        )

    scenario_kwargs: dict[str, object] = {}
    if args.n_cycles is not None:
        scenario_kwargs["n_cycles"] = args.n_cycles
    try:
        scenario = cls(**scenario_kwargs)
    except TypeError as exc:
        sys.exit(
            f"run_scenario.py: could not instantiate {args.name!r}: {exc}\n"
            f"  see `ophamin scenario show {args.name}` for the expected signature."
        )

    substrate = MockSubstrate(seed=1)
    record = scenario.run(substrate)

    if args.out:
        out_path = Path(args.out)
        proof_dump(record, out_path)
        print(f"OK: ran {args.name} ({record.verdict.outcome}); wrote {out_path}")
    else:
        print(record.to_markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main())
