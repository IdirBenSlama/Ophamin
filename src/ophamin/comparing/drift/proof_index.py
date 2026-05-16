"""ProofIndex — load and group every signed proof record under ``proofs/``.

A drift detector needs to find every proof record for a given primary claim
across Kimera commits. The index loads each ``proofs/*.json``, validates the
shape, and exposes queries:

  - ``index.statistic_names()``        every primary statistic ever measured
  - ``index.records_for(stat)``        all records for one primary statistic
  - ``index.records_by_commit(stat)``  the same, grouped by Kimera commit
  - ``index.commits_for(stat)``        the Kimera commits where the statistic
                                       was measured, sorted by capture time

The index is read-only — it never mutates proof records or writes to disk.
Adapter-error verdicts and INCONCLUSIVE records are kept in the index (their
exclusion is a drift-report decision, not an indexing one).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from ophamin.measuring.proof import EmpiricalProofRecord


@dataclass(frozen=True)
class ProofIndexEntry:
    """One entry in the index — a proof record + its derived index keys."""

    path: Path
    record: EmpiricalProofRecord

    @property
    def primary_statistic_name(self) -> str:
        return self.record.claim.threshold.metric

    @property
    def primary_observed_value(self) -> float:
        # the verdict's observed value is the source of truth for the primary
        # statistic — pull from the verdict rather than re-scanning evidence
        return float(self.record.verdict.observed_value)

    @property
    def primary_ci(self) -> tuple[float | None, float | None]:
        """Wilson 95% CI for the primary statistic if its PillarEvidence carries one."""
        stat = self.primary_statistic_name
        for ev in self.record.evidence:
            if ev.statistic_name == stat:
                return (ev.ci_low, ev.ci_high)
        return (None, None)

    @property
    def kimera_git_commit(self) -> str:
        return self.record.substrate_git_commit or ""

    @property
    def captured_at(self) -> str:
        return self.record.created_at

    @property
    def verdict_outcome(self) -> str:
        return self.record.verdict.outcome


class ProofIndex:
    """Load and group every signed proof record under a directory."""

    def __init__(self, entries: Iterable[ProofIndexEntry]) -> None:
        self._entries: list[ProofIndexEntry] = list(entries)

    @classmethod
    def from_directory(cls, root: str | Path) -> ProofIndex:
        """Build an index by scanning ``root`` for ``*.json`` proof records.

        A file that doesn't deserialise as an EmpiricalProofRecord is skipped
        with a warning rather than failing the whole index — the directory
        may contain other JSON artefacts.
        """
        root_path = Path(root)
        if not root_path.is_dir():
            raise NotADirectoryError(f"proof-record root is not a directory: {root}")
        entries: list[ProofIndexEntry] = []
        for path in sorted(root_path.glob("*.json")):
            try:
                record = _load_proof_record(path)
            except (json.JSONDecodeError, ValueError, KeyError):
                # not a proof record — skip silently (other JSON may live here)
                continue
            entries.append(ProofIndexEntry(path=path, record=record))
        return cls(entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> "Iterator[ProofIndexEntry]":
        return iter(self._entries)

    def all_entries(self) -> tuple[ProofIndexEntry, ...]:
        return tuple(self._entries)

    def statistic_names(self) -> tuple[str, ...]:
        return tuple(sorted({e.primary_statistic_name for e in self._entries}))

    def records_for(self, statistic_name: str) -> tuple[ProofIndexEntry, ...]:
        return tuple(
            sorted(
                (e for e in self._entries if e.primary_statistic_name == statistic_name),
                key=lambda e: e.captured_at,
            )
        )

    def records_by_commit(
        self, statistic_name: str
    ) -> dict[str, tuple[ProofIndexEntry, ...]]:
        grouped: dict[str, list[ProofIndexEntry]] = defaultdict(list)
        for entry in self.records_for(statistic_name):
            grouped[entry.kimera_git_commit].append(entry)
        return {k: tuple(v) for k, v in grouped.items()}

    def commits_for(self, statistic_name: str) -> tuple[str, ...]:
        seen: dict[str, str] = {}
        for entry in self.records_for(statistic_name):
            seen.setdefault(entry.kimera_git_commit, entry.captured_at)
        # sort by *first-seen* capture time so the order matches what was
        # actually measured first vs. later, not a lexicographic commit-sha sort
        return tuple(c for c, _ in sorted(seen.items(), key=lambda kv: kv[1]))


def _load_proof_record(path: Path) -> EmpiricalProofRecord:
    """Best-effort loader — strict enough to reject non-proof JSON, lenient
    enough to surface real proof records that may carry extra fields.

    The on-disk JSON shape (per ``EmpiricalProofRecord._body``):
      claim / evidence / verdict at top level; substrate_name +
      substrate_git_commit nested under ``data``. We check both halves so a
      truncated or unrelated JSON is rejected cleanly.
    """
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: not a proof-record dict")
    required_top = {"claim", "evidence", "verdict", "data"}
    missing = required_top - set(data)
    if missing:
        raise ValueError(f"{path}: missing required proof-record keys {sorted(missing)}")
    if "substrate_name" not in (data.get("data") or {}):
        raise ValueError(f"{path}: missing data.substrate_name")
    return EmpiricalProofRecord.from_dict(data)


# --------------------------------------------------------------------------
# Convenience entry point: index → drift report per primary statistic
# --------------------------------------------------------------------------


def detect_drift(
    index: ProofIndex,
    *,
    require_distinct_commits: bool = True,
) -> dict[str, Any]:
    """Build a drift report for every primary statistic in the index.

    Returns ``{statistic_name: DriftReport.to_dict()}``. A statistic with
    proof records on only one Kimera commit is reported as
    ``status="single_commit"`` (no drift possible) when
    ``require_distinct_commits`` is True (default).
    """
    from ophamin.comparing.drift.delta_report import DriftReport

    report: dict[str, Any] = {}
    for stat in index.statistic_names():
        entries = index.records_for(stat)
        commits = index.commits_for(stat)
        if require_distinct_commits and len(commits) < 2:
            report[stat] = {
                "status": "single_commit",
                "commit": commits[0] if commits else "",
                "n_records": len(entries),
            }
            continue
        # compare the oldest commit's most-recent record vs the newest
        # commit's most-recent record — common drift question is "is there
        # drift between then and now", not all pairwise
        oldest_commit = commits[0]
        newest_commit = commits[-1]
        records_by_commit = index.records_by_commit(stat)
        before = records_by_commit[oldest_commit][-1]
        after = records_by_commit[newest_commit][-1]
        drift = DriftReport.from_proofs(before, after)
        report[stat] = drift.to_dict()
    return report
