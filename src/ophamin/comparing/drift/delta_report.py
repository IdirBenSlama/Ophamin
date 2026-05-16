"""DriftReport — per-claim, per-commit delta between two proof records.

A drift report compares one "before" proof record against one "after" proof
record for the *same primary statistic*. It computes:

  - primary statistic delta (observed_after - observed_before)
  - whether the two Wilson 95% CIs overlap (non-overlap = significant drift)
  - per-evidence-pillar delta on every shared statistic name
  - verdict change (did the verdict flip between commits?)

Distribution-shape drift (median / mean / p10 / p90 shifts of a descriptive
secondary evidence channel) is reported as a separate DeltaEntry per
distribution statistic. Layer C is descriptive — it produces deltas; the
human decides whether the drift is meaningful given the substrate change
that caused it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ophamin.comparing.drift.proof_index import ProofIndexEntry


def ci_overlaps(
    ci_a: tuple[float | None, float | None],
    ci_b: tuple[float | None, float | None],
) -> bool | None:
    """Do two Wilson CIs overlap? Returns None if either CI is missing.

    Two intervals [a_lo, a_hi] and [b_lo, b_hi] overlap iff a_lo <= b_hi
    AND b_lo <= a_hi. Non-overlap is conservative evidence of significant
    behavioural drift — when the CIs don't overlap, the difference is at
    least Wilson-CI-wide on both sides.
    """
    a_lo, a_hi = ci_a
    b_lo, b_hi = ci_b
    if a_lo is None or a_hi is None or b_lo is None or b_hi is None:
        return None
    return a_lo <= b_hi and b_lo <= a_hi


@dataclass(frozen=True)
class DeltaEntry:
    """One statistic's cross-commit delta + significance marker."""

    statistic_name: str
    value_before: float
    value_after: float
    delta: float                                    # after - before
    ci_before: tuple[float | None, float | None] = (None, None)
    ci_after: tuple[float | None, float | None] = (None, None)
    ci_overlap: bool | None = None                  # None when either CI missing
    significant: bool = False                       # CI non-overlap → significant

    def to_dict(self) -> dict[str, Any]:
        return {
            "statistic_name": self.statistic_name,
            "value_before": self.value_before,
            "value_after": self.value_after,
            "delta": self.delta,
            "ci_before": list(self.ci_before),
            "ci_after": list(self.ci_after),
            "ci_overlap": self.ci_overlap,
            "significant": self.significant,
        }


@dataclass(frozen=True)
class DriftReport:
    """Per-statistic deltas between two proof records on different Kimera commits."""

    statistic_name: str                             # primary statistic being tracked
    kimera_commit_before: str
    kimera_commit_after: str
    captured_at_before: str
    captured_at_after: str
    verdict_before: str
    verdict_after: str
    primary_delta: DeltaEntry
    pillar_deltas: tuple[DeltaEntry, ...]          # every shared statistic name

    def verdict_changed(self) -> bool:
        return self.verdict_before != self.verdict_after

    def has_significant_drift(self) -> bool:
        return self.primary_delta.significant or any(
            d.significant for d in self.pillar_deltas
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "statistic_name": self.statistic_name,
            "kimera_commit_before": self.kimera_commit_before,
            "kimera_commit_after": self.kimera_commit_after,
            "captured_at_before": self.captured_at_before,
            "captured_at_after": self.captured_at_after,
            "verdict_before": self.verdict_before,
            "verdict_after": self.verdict_after,
            "verdict_changed": self.verdict_changed(),
            "has_significant_drift": self.has_significant_drift(),
            "primary_delta": self.primary_delta.to_dict(),
            "pillar_deltas": [d.to_dict() for d in self.pillar_deltas],
        }

    @classmethod
    def from_proofs(cls, before: "ProofIndexEntry", after: "ProofIndexEntry") -> DriftReport:
        """Build a DriftReport from two ProofIndexEntry objects."""
        if before.primary_statistic_name != after.primary_statistic_name:
            raise ValueError(
                f"cannot compare proofs for different primary statistics: "
                f"{before.primary_statistic_name!r} vs "
                f"{after.primary_statistic_name!r}"
            )
        stat = before.primary_statistic_name
        primary_delta = _build_delta_entry(
            statistic_name=stat,
            value_before=before.primary_observed_value,
            value_after=after.primary_observed_value,
            ci_before=before.primary_ci,
            ci_after=after.primary_ci,
        )

        # also delta every shared statistic in the evidence sections
        evidence_before = {ev.statistic_name: ev for ev in before.record.evidence}
        evidence_after = {ev.statistic_name: ev for ev in after.record.evidence}
        shared = sorted(set(evidence_before) & set(evidence_after) - {stat})
        pillar_deltas: list[DeltaEntry] = []
        for stat_name in shared:
            ev_b = evidence_before[stat_name]
            ev_a = evidence_after[stat_name]
            pillar_deltas.append(
                _build_delta_entry(
                    statistic_name=stat_name,
                    value_before=float(ev_b.statistic_value),
                    value_after=float(ev_a.statistic_value),
                    ci_before=(ev_b.ci_low, ev_b.ci_high),
                    ci_after=(ev_a.ci_low, ev_a.ci_high),
                )
            )

        return cls(
            statistic_name=stat,
            kimera_commit_before=before.kimera_git_commit,
            kimera_commit_after=after.kimera_git_commit,
            captured_at_before=before.captured_at,
            captured_at_after=after.captured_at,
            verdict_before=before.verdict_outcome,
            verdict_after=after.verdict_outcome,
            primary_delta=primary_delta,
            pillar_deltas=tuple(pillar_deltas),
        )


def _build_delta_entry(
    *,
    statistic_name: str,
    value_before: float,
    value_after: float,
    ci_before: tuple[float | None, float | None],
    ci_after: tuple[float | None, float | None],
) -> DeltaEntry:
    overlap = ci_overlaps(ci_before, ci_after)
    return DeltaEntry(
        statistic_name=statistic_name,
        value_before=value_before,
        value_after=value_after,
        delta=value_after - value_before,
        ci_before=ci_before,
        ci_after=ci_after,
        ci_overlap=overlap,
        # significant ⇔ overlap == False (CI non-overlap = drift signal);
        # overlap=None (CI missing) → not significant by default
        significant=(overlap is False),
    )
