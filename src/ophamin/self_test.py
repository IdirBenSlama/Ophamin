"""Ophamin self-dogfood — run substrate-free scenarios against the framework itself.

Closes the empirical-loop question: *can the observatory observe
itself?* For the subset of scenarios that don't require a Kimera
substrate (statistical crosschecks + measurement-machinery
validators + the Bayesian Φ posterior on synthetic data), the
answer is yes — and this module is the canonical runner.

Three things this delivers:

1. The :data:`SELF_TEST_SCENARIOS` list — the curated set of
   scenarios proven to run cleanly against ``MockSubstrate``
   without needing Kimera-shape input. Edit this list when adding
   new substrate-free scenarios to the framework.

2. :func:`run_self_test` — runs every scenario, persists a signed
   bundle per result under ``proofs_root/<tier>/<scenario>/...``
   (the standard 0.59.0+ layout). Returns a structured
   :class:`SelfTestResult` so CI / the CLI can branch on the
   outcome.

3. The ``ophamin self-test`` CLI subcommand (wired in
   :mod:`ophamin.cli`) — operator-facing entry point. Exits with
   code = number of REFUTED scenarios so CI fails-fast on
   regression.

Out of scope:

- The 20 cognitive-tier scenarios (immune-siege, sinew-*, prime-*,
  etc.) measure Kimera substrate behavior; running them against
  Ophamin would be measuring the wrong substrate.
- ``substrate-completeness`` + ``interface-contract-stability``
  are Kimera-inventory-shape-aware. Running them against Ophamin
  produces vacuous 0/0 results until an Ophamin-shape adapter
  lands.
- ``sonarqube-scan`` IS substrate-agnostic but needs a live
  SonarQube + a fresh scan first; that loop already runs in the
  0.51.0 / 0.58.0 sonar.yml workflow against ``project_key=ophamin``
  and emits its own signed proof artefact — keeping it separate
  preserves the clean failure-mode.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ophamin.measuring.proof import BundleFormat, PersistedBundle


#: The scenarios proven to run cleanly against MockSubstrate, in
#: alphabetical-within-tier order. Add scenarios HERE — the runner
#: + CLI + tests pick up the change automatically.
#:
#: Each tuple is ``(scenario_name, kwargs_for_constructor)``. The
#: vast majority take no kwargs; the tuple form is forward-compatible
#: for scenarios that grow optional knobs.
SELF_TEST_SCENARIOS: tuple[tuple[str, dict[str, Any]], ...] = (
    # Empirical-deep tier — single substrate-free probe
    ("bayesian-phi-posterior", {}),
    # Measurement-machinery tier — statistical crosschecks across libraries
    ("anova-crosscheck", {}),
    ("bayesian-phi-posterior-crosscheck", {}),
    ("crdt-laws", {}),
    ("deterministic-seed-audit", {}),
    ("mann-whitney-crosscheck", {}),
    ("pearson-crosscheck", {}),
    ("spearman-crosscheck", {}),
    ("welch-t-crosscheck", {}),
    ("wilson-ci-crosscheck", {}),
)


@dataclass(frozen=True)
class ScenarioRunResult:
    """One scenario's outcome from a self-test run."""

    scenario_name: str
    verdict: str                # VALIDATED / REFUTED / INCONCLUSIVE / ERROR
    proof_id: str               # empty when verdict=ERROR
    bundle_path: str            # relative path; empty when ERROR
    duration_seconds: float
    error: str = ""             # populated only when verdict=ERROR


@dataclass(frozen=True)
class SelfTestResult:
    """Aggregate of a full self-test invocation."""

    results: tuple[ScenarioRunResult, ...]
    proofs_root: str
    total_duration_seconds: float

    @property
    def n_total(self) -> int:
        return len(self.results)

    @property
    def n_validated(self) -> int:
        return sum(1 for r in self.results if r.verdict == "VALIDATED")

    @property
    def n_refuted(self) -> int:
        return sum(1 for r in self.results if r.verdict == "REFUTED")

    @property
    def n_inconclusive(self) -> int:
        return sum(1 for r in self.results if r.verdict == "INCONCLUSIVE")

    @property
    def n_errored(self) -> int:
        return sum(1 for r in self.results if r.verdict == "ERROR")

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_total": self.n_total,
            "n_validated": self.n_validated,
            "n_refuted": self.n_refuted,
            "n_inconclusive": self.n_inconclusive,
            "n_errored": self.n_errored,
            "proofs_root": self.proofs_root,
            "total_duration_seconds": self.total_duration_seconds,
            "results": [
                {
                    "scenario_name": r.scenario_name,
                    "verdict": r.verdict,
                    "proof_id": r.proof_id,
                    "bundle_path": r.bundle_path,
                    "duration_seconds": r.duration_seconds,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def run_self_test(
    proofs_root: str | Path = "proofs/ophamin-self",
    *,
    formats: frozenset[BundleFormat] | None = None,
    seed: int = 1,
) -> SelfTestResult:
    """Run every scenario in :data:`SELF_TEST_SCENARIOS` and persist bundles.

    Parameters
    ----------
    proofs_root:
        Where to write bundles. Defaults to ``proofs/ophamin-self``.
        Bundles land at the standard 0.59.0+ layout:
        ``<proofs_root>/<tier>/<scenario>/<date>_<verdict>_<short>/``.
    formats:
        Bundle formats to emit per scenario. Defaults to all five
        (JSON + MD + HTML + LaTeX + PDF) when PDF toolchain is
        available; pass :meth:`BundleFormat.json_only` for fast
        runs that skip rendering entirely.
    seed:
        Random seed for ``MockSubstrate``. Reproducible runs use
        the same seed; CI uses seed=1 by default.

    Returns
    -------
    SelfTestResult
        Per-scenario outcomes + aggregate counts. Errors are
        caught + reported (verdict="ERROR") so a single failing
        scenario doesn't abort the whole loop — the user wants
        the full report.
    """
    # Imports local to keep this module's import cost low — only
    # paid when self-test actually runs.
    from ophamin.measuring.scenarios import SCENARIOS
    from ophamin.seeing.substrate import MockSubstrate

    if formats is None:
        formats = BundleFormat.all()

    results: list[ScenarioRunResult] = []
    overall_start = time.perf_counter()

    for scenario_name, kwargs in SELF_TEST_SCENARIOS:
        cls = SCENARIOS.get(scenario_name)
        if cls is None:
            results.append(ScenarioRunResult(
                scenario_name=scenario_name,
                verdict="ERROR",
                proof_id="",
                bundle_path="",
                duration_seconds=0.0,
                error="scenario not in registry",
            ))
            continue

        per_start = time.perf_counter()
        try:
            scenario = cls(**kwargs)
            substrate = MockSubstrate(seed=seed)
            bundle: PersistedBundle = scenario.run_and_persist(
                substrate=substrate,
                proofs_root=str(proofs_root),
                formats=formats,
            )
            # Read verdict back off the signed JSON inside the bundle
            from ophamin.measuring.proof.codec import load
            record = load(bundle.proof_json)
            results.append(ScenarioRunResult(
                scenario_name=scenario_name,
                verdict=record.verdict.outcome,
                proof_id=record.proof_id,
                bundle_path=str(bundle.bundle_dir),
                duration_seconds=time.perf_counter() - per_start,
            ))
        except Exception as exc:  # noqa: BLE001
            results.append(ScenarioRunResult(
                scenario_name=scenario_name,
                verdict="ERROR",
                proof_id="",
                bundle_path="",
                duration_seconds=time.perf_counter() - per_start,
                error=f"{type(exc).__name__}: {exc}",
            ))

    return SelfTestResult(
        results=tuple(results),
        proofs_root=str(proofs_root),
        total_duration_seconds=time.perf_counter() - overall_start,
    )
