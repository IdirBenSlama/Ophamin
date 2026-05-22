"""Reproducibility check — re-run a scenario N times, report what reproduces.

What reproduces is layered, and being honest about the layers is the point of
CR6:

  * **PROTOCOL layer** (Ophamin's own machinery) is deterministic: a fixed
    proof dict always content-hashes to the same ``proof_id`` and signs to the
    same signature (pinned by the canonical-form + wire-format tests).
  * **EVENT layer**: every run is a distinct event — ``proof_id`` embeds
    ``created_at``, so two runs NEVER share a ``proof_id``. proof_id is
    therefore NOT a reproducibility metric; treating it as one would be a
    category error. We report ``proof_ids_distinct`` (expected True) precisely
    to make that explicit.
  * **SUBSTRATE layer** (Kimera's cognitive output) is stochastic across fresh
    runs: Φ and other physics-layer floats drift run-to-run (cold-start warmup
    + float nondeterminism). The CLAIM stays stable even as exact numbers move.

So the reproducibility a falsifiable proof actually promises is: the VERDICT
and the cross-check CONCLUSION reproduce, and the falsifiable metric reproduces
WITHIN a measured drift band — not bit-identical numbers. This module measures
exactly that, instead of claiming "reproducible" without evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY


@dataclass(frozen=True)
class ReproductionReport:
    """The result of re-running one scenario N times.

    ``verdict_reproducible`` / ``cross_check_reproducible`` are the claims that
    must hold. ``observed_drift`` (max−min of the falsifiable metric) is the
    honest measure of substrate float-drift. ``proof_ids_distinct`` documents
    that proof_id is per-event, not a reproducibility signal.
    """

    scenario: str
    n_runs: int
    verdicts: list[str]
    observed_values: list[float]
    cross_checks: list[str]
    proof_ids: list[str]
    threshold_metric: str
    threshold_value: float
    verdict_reproducible: bool
    cross_check_reproducible: bool
    observed_min: float
    observed_max: float
    observed_mean: float
    observed_stdev: float
    observed_drift: float        # max − min
    proof_ids_distinct: bool     # expected True — proof_id embeds created_at
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "n_runs": self.n_runs,
            "verdicts": self.verdicts,
            "observed_values": self.observed_values,
            "cross_checks": self.cross_checks,
            "proof_ids": self.proof_ids,
            "threshold_metric": self.threshold_metric,
            "threshold_value": self.threshold_value,
            "verdict_reproducible": self.verdict_reproducible,
            "cross_check_reproducible": self.cross_check_reproducible,
            "observed_min": self.observed_min,
            "observed_max": self.observed_max,
            "observed_mean": self.observed_mean,
            "observed_stdev": self.observed_stdev,
            "observed_drift": self.observed_drift,
            "proof_ids_distinct": self.proof_ids_distinct,
            "notes": self.notes,
        }


def _primary_cross_check(record: Any) -> str:
    """The flow evidence's cross_check, else the first evidence's, else n/a."""
    evidence = getattr(record, "evidence", None) or []
    for e in evidence:
        detail = getattr(e, "detail", None) or {}
        if detail.get("scope") == "flow":
            return getattr(e, "cross_check", "n/a")
    if evidence:
        return getattr(evidence[0], "cross_check", "n/a")
    return "n/a"


def reproduce(
    scenario: Any,
    substrate: Any = None,
    *,
    n_runs: int = 3,
    sign_key: bytes = DEFAULT_SIGN_KEY,
) -> ReproductionReport:
    """Run ``scenario`` ``n_runs`` times and report what reproduces.

    Each run calls ``scenario.run(substrate, sign_key=sign_key)`` and collects
    the verdict outcome, the falsifiable observed value, the cross-check status,
    and the proof_id. Returns a :class:`ReproductionReport` measuring verdict /
    cross-check stability and the observed-value drift band. Raises
    ``ValueError`` for ``n_runs < 2`` — reproducibility needs at least a pair.
    """
    if n_runs < 2:
        raise ValueError(f"n_runs must be >= 2 to compare, got {n_runs}")

    verdicts: list[str] = []
    observed: list[float] = []
    crosses: list[str] = []
    proof_ids: list[str] = []
    threshold_metric = ""
    threshold_value = 0.0

    for _ in range(n_runs):
        record = scenario.run(substrate, sign_key=sign_key)
        verdicts.append(record.verdict.outcome)
        observed.append(float(record.verdict.observed_value))
        proof_ids.append(record.proof_id)
        crosses.append(_primary_cross_check(record))
        threshold_metric = record.verdict.threshold.metric
        threshold_value = float(record.verdict.threshold.value)

    omin, omax = min(observed), max(observed)
    drift = omax - omin
    verdict_reproducible = len(set(verdicts)) == 1
    cross_check_reproducible = len(set(crosses)) == 1
    proof_ids_distinct = len(set(proof_ids)) == len(proof_ids)

    notes = (
        f"Verdict {'reproduced' if verdict_reproducible else 'DID NOT reproduce'} "
        f"across {n_runs} runs ({'/'.join(dict.fromkeys(verdicts))}); "
        f"cross-check {'stable' if cross_check_reproducible else 'VARIED'} "
        f"({'/'.join(dict.fromkeys(crosses))}); "
        f"{threshold_metric} drift {drift:.4f} over [{omin:.4f}, {omax:.4f}]. "
        "proof_ids are distinct by design (each embeds created_at) — that is "
        "not a reproducibility signal; the verdict + cross-check + bounded "
        "drift are."
    )

    return ReproductionReport(
        scenario=getattr(scenario, "name", scenario.__class__.__name__),
        n_runs=n_runs,
        verdicts=verdicts,
        observed_values=observed,
        cross_checks=crosses,
        proof_ids=proof_ids,
        threshold_metric=threshold_metric,
        threshold_value=threshold_value,
        verdict_reproducible=verdict_reproducible,
        cross_check_reproducible=cross_check_reproducible,
        observed_min=omin,
        observed_max=omax,
        observed_mean=mean(observed),
        observed_stdev=pstdev(observed) if len(observed) > 1 else 0.0,
        observed_drift=drift,
        proof_ids_distinct=proof_ids_distinct,
        notes=notes,
    )
