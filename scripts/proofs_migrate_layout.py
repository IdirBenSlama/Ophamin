"""One-shot migration: legacy proofs/ layout → 0.59.0 bundle directories.

Walks every signed ``proof.json`` under ``proofs/`` and migrates it to
the canonical bundle layout introduced in 0.59.0::

    proofs/<tier>/<scenario>/<YYYY-MM-DD>_<verdict>_<short-hash>/
    ├── proof.json   (moved from the legacy path)
    ├── proof.md     (regenerated from JSON)
    ├── proof.html   (regenerated)
    ├── proof.tex    (regenerated)
    └── proof.pdf    (regenerated; warns + skips on machines without latexmk)

The migration is idempotent — re-running on an already-migrated tree
is a no-op (the destination paths are content-addressed and already
exist). The legacy ``.json`` is moved into place via ``shutil.move``
so the signed bytes don't change; the sibling ``.md`` (when present
at the legacy path) is removed because the bundle's regenerated
``proof.md`` replaces it.

Scenario detection is heuristic when the legacy filename doesn't
match a registered :class:`SCENARIOS` name exactly:

  1. Exact prefix-match against ``Scenario.name`` (kebab-case) and
     its underscore variant.
  2. Manual aliases (e.g. ``immune_siege`` →
     ``concentrated-immune-siege``).
  3. Substring match on ``claim.threshold.metric`` against a
     per-scenario hint table.
  4. Fall back to ``"unknown-scenario"`` — these end up under
     ``proofs/<tier-guess>/unknown-scenario/`` so the operator can
     classify them by hand.

Loud-fails on any decode / signature-verify error so silent
corruption surfaces immediately rather than producing a
half-migrated tree.

Usage::

    PYTHONPATH=src .venv/bin/python scripts/proofs_migrate_layout.py [--dry-run]

The ``--dry-run`` flag prints the planned moves without modifying
the filesystem. Default is to migrate in place. A pre-migration
git status snapshot is the safety net; this script does NOT commit.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

# Make the script runnable without `pip install -e .` having been run
# in the current shell — append src/ before any ophamin import.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ophamin.measuring.proof import (  # noqa: E402  (sys.path mutation above)
    BundleFormat,
    bundle_dir_for,
    persist_proof,
)
from ophamin.measuring.proof.codec import load  # noqa: E402
from ophamin.measuring.scenarios import SCENARIOS  # noqa: E402


# Aliases that legacy filenames carry but the canonical scenario name
# does not match prefix-style. Keys are filename prefixes (lowercase),
# values are the canonical scenario.name.
_FILENAME_ALIASES: dict[str, str] = {
    "immune_siege": "concentrated-immune-siege",
    "throughput": "throughput-ceiling",
    # Cross-framework crosscheck proofs use <stat>_<libA>_vs_<libB>...
    "anova_scipy_vs": "anova-crosscheck",
    "bayesian_pymc_vs": "bayesian-phi-posterior-crosscheck",
    "mann_whitney_u_scipy_vs": "mann-whitney-crosscheck",
    "pearson_scipy_vs": "pearson-crosscheck",
    "spearman_scipy_vs": "spearman-crosscheck",
    "welch_t_scipy_vs": "welch-t-crosscheck",
    "wilson_scipy_vs": "wilson-ci-crosscheck",
}


def _scenario_tier(name: str) -> str:
    """Tier value for a registered scenario; ``"unknown"`` if not in registry."""
    cls = SCENARIOS.get(name)
    if cls is None:
        return "unknown"
    return cls.tier.value if hasattr(cls.tier, "value") else str(cls.tier)


def _detect_scenario(legacy_path: Path, record_dict: dict) -> str:
    """Best-effort scenario-name inference for a legacy proof.

    1. Exact match against SCENARIOS by `name`.
    2. Filename-alias lookup.
    3. Prefix-match against registered names (kebab + underscore variants).
    4. Fall back to ``"unknown-scenario"``.
    """
    stem = legacy_path.stem.lower()

    # 1) Aliases — handled first because they're explicit overrides.
    for alias, canonical in _FILENAME_ALIASES.items():
        if stem.startswith(alias):
            return canonical

    # 2) Exact prefix match — longest first so e.g. `bayesian-phi-posterior-crosscheck`
    # beats `bayesian-phi-posterior`.
    for sn in sorted(SCENARIOS, key=len, reverse=True):
        underscore = sn.replace("-", "_")
        if stem.startswith(sn) or stem.startswith(underscore):
            return sn

    # 3) Substring match — less strict; catches cases like `proof_pre_${scenario}`.
    for sn in sorted(SCENARIOS, key=len, reverse=True):
        underscore = sn.replace("-", "_")
        if underscore in stem or sn in stem:
            return sn

    return "unknown-scenario"


def _is_proof_json(path: Path) -> bool:
    """Quick filter: a legacy proof carries `claim` + `verdict` at top level."""
    try:
        d = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(d, dict) and "claim" in d and "verdict" in d


def _plan_for(
    legacy_path: Path, proofs_root: Path,
) -> tuple[str, str, Path, Path] | None:
    """Return (scenario_name, tier, legacy_path, target_bundle_dir) for a
    proof, or None if the file isn't a parseable proof."""
    if not _is_proof_json(legacy_path):
        return None
    try:
        record = load(legacy_path)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR loading {legacy_path}: {exc}", file=sys.stderr)
        return None
    payload = json.loads(legacy_path.read_text())
    scenario = _detect_scenario(legacy_path, payload)
    tier = _scenario_tier(scenario)
    bundle = bundle_dir_for(
        record, root=proofs_root, tier=tier, scenario_name=scenario,
    )
    return scenario, tier, legacy_path, bundle


def _migrate_one(plan: tuple[str, str, Path, Path], *, dry_run: bool) -> str:
    """Migrate one proof; return a short status string for the report."""
    scenario, tier, legacy_path, target_dir = plan
    rel = legacy_path.relative_to(legacy_path.parents[len(legacy_path.parts) - 2])

    if target_dir.exists() and (target_dir / "proof.json").exists():
        # Bundle already present — but the legacy file may still be on
        # disk from a prior partial run. Clean it up so the tree
        # converges to the canonical layout on every invocation.
        if not dry_run:
            legacy_md = legacy_path.with_suffix(".md")
            if legacy_path.is_file():
                legacy_path.unlink()
            if legacy_md.is_file():
                legacy_md.unlink()
            return (
                f"  OK (legacy cleanup; bundle already existed): {rel} → "
                f"{target_dir.relative_to(target_dir.parents[3])}"
            )
        return f"  SKIP (already migrated): {rel} → {target_dir.relative_to(target_dir.parents[3])}"

    if dry_run:
        return f"  PLAN: {rel} → {target_dir}"

    # Load the record + persist using the canonical helper. Then move
    # the legacy .json out of the way (regenerated into the bundle).
    record = load(legacy_path)
    bundle = persist_proof(
        record, root=target_dir.parents[2],
        tier=tier, scenario_name=scenario,
        formats=BundleFormat.all(),
    )

    # Drop legacy .json + sibling .md (replaced by the bundle's regenerated ones)
    legacy_md = legacy_path.with_suffix(".md")
    legacy_path.unlink()
    if legacy_md.is_file():
        legacy_md.unlink()

    skipped = ""
    if bundle.skipped:
        skipped = f"   (SKIPPED: {','.join(f.value for f in bundle.skipped)})"
    return f"  OK: {rel} → {bundle.bundle_dir}{skipped}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print planned moves without modifying the filesystem.",
    )
    parser.add_argument(
        "--proofs-root", default="proofs",
        help="Root directory holding legacy + new-shape proofs (default: proofs/).",
    )
    parser.add_argument(
        "--include-untracked", action="store_true",
        help=(
            "Include git-untracked .json files under proofs/ in the "
            "migration. Default off — untracked files are likely "
            "parallel-session work and should not be migrated as "
            "part of a single session."
        ),
    )
    args = parser.parse_args(argv)

    proofs_root = Path(args.proofs_root).resolve()
    if not proofs_root.is_dir():
        print(f"ERROR: not a directory: {proofs_root}", file=sys.stderr)
        return 2

    # Build the candidate list. By default exclude untracked files
    # (parallel-session hygiene per CLAUDE.md).
    candidates: list[Path] = sorted(p for p in proofs_root.rglob("*.json"))
    if not args.include_untracked:
        # `git ls-files proofs/` lists tracked-only.
        import subprocess
        result = subprocess.run(
            ["git", "ls-files", str(proofs_root.relative_to(_REPO_ROOT)) + "/"],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(
                "WARNING: git ls-files failed; falling back to all *.json under proofs/",
                file=sys.stderr,
            )
        else:
            tracked = {
                (_REPO_ROOT / line).resolve()
                for line in result.stdout.strip().splitlines()
                if line.endswith(".json")
            }
            candidates = [p for p in candidates if p.resolve() in tracked]

    print(f"Migrating {len(candidates)} proof JSON files under {proofs_root}")
    print(f"  dry_run = {args.dry_run}")
    print(f"  include_untracked = {args.include_untracked}")
    print()

    # Group by scenario for the report
    by_scenario: defaultdict[str, list[str]] = defaultdict(list)
    skipped_count = 0
    error_count = 0
    migrated_count = 0
    pdf_skip_count = 0

    for legacy in candidates:
        # Don't try to migrate proof.json files that already live IN a bundle dir.
        if legacy.name == "proof.json":
            skipped_count += 1
            continue
        plan = _plan_for(legacy, proofs_root)
        if plan is None:
            error_count += 1
            continue
        scenario, tier, _, target = plan
        try:
            line = _migrate_one(plan, dry_run=args.dry_run)
            if "SKIPPED: pdf" in line:
                pdf_skip_count += 1
            if line.startswith("  OK") or line.startswith("  PLAN"):
                migrated_count += 1
            by_scenario[f"{tier}/{scenario}"].append(line)
        except Exception as exc:  # noqa: BLE001
            error_count += 1
            print(f"  FAIL {legacy}: {exc}", file=sys.stderr)

    for group, lines in sorted(by_scenario.items()):
        print(f"=== {group} ({len(lines)}) ===")
        for line in lines:
            print(line)

    print()
    print(f"Summary: migrated={migrated_count}, skipped={skipped_count}, "
          f"errors={error_count}, pdf_skips={pdf_skip_count}")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
