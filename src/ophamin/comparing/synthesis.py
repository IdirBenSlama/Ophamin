"""Campaign-level synthesis + per-record diagnostic + per-metric trajectory.

The three operations that close Deficit 3 from
``docs/ARCHITECTURE_EXTENDED_AUDIT_2026_05_16.md`` once the proof codec
(Move B) is in place:

* :func:`summarize_directory` — walk a proof corpus, produce a
  :class:`CampaignSummary` with verdict + tier + family + per-substrate-commit
  aggregations and a :class:`VerdictFlip` list (same scenario, different
  commit, different verdict).
* :func:`diagnose_proof` — load one record + surface its closest siblings
  in the corpus + same-scenario-across-commits view, producing a
  :class:`Diagnostic`.
* :func:`analyze_metric` — walk a corpus, extract every
  :class:`PillarEvidence` whose ``statistic_name`` matches a query metric,
  produce a :class:`MetricTrajectory` with summary statistics.

The three CLI commands ``ophamin summarize / diagnose / analyze`` are
thin wrappers around these functions. Per the framework's no-fallback
rule, missing input files raise the same typed errors the codec
already declares — this module does NOT swallow exceptions and does NOT
produce empty placeholder results.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ophamin.measuring.proof import EmpiricalProofRecord
from ophamin.measuring.proof.codec import (
    ProofDecodeError,
    ProofListEntry,
    _family_from_filename,
    iter_proofs,
    list_proofs,
    load,
)


# --- VerdictFlip + CampaignSummary --------------------------------------------


@dataclass(frozen=True)
class VerdictFlip:
    """One detected verdict flip: same scenario family, two substrate
    commits, two different verdicts.

    The detector is intentionally heuristic — it groups by the
    family-from-filename heuristic + the substrate_git_commit (truncated
    to first 12 chars). Two proofs with the same family AND different
    commits AND different verdicts produce one entry.
    """

    family: str
    commit_a: str
    commit_b: str
    verdict_a: str
    verdict_b: str
    proof_a: Path
    proof_b: Path


@dataclass(frozen=True)
class CampaignSummary:
    """Roll-up of a proof corpus under one directory."""

    root: Path
    generated_at: str
    total: int
    n_decode_errors: int
    by_verdict: dict[str, int]
    by_family: dict[str, int]
    by_substrate_commit: dict[str, dict[str, int]]  # commit → verdict → count
    verdict_flips: tuple[VerdictFlip, ...]
    entries: tuple[ProofListEntry, ...]

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Campaign summary — `{self.root}`")
        lines.append("")
        lines.append(f"_Generated: {self.generated_at}_")
        lines.append("")
        lines.append(
            f"**{self.total} record(s)** "
            f"({self.n_decode_errors} decode error(s))."
        )
        lines.append("")

        if self.by_verdict:
            lines.append("## Verdict distribution")
            lines.append("")
            lines.append("| Verdict | Count |")
            lines.append("|---|---|")
            for verdict in sorted(self.by_verdict):
                lines.append(f"| {verdict} | {self.by_verdict[verdict]} |")
            lines.append("")

        if self.by_family:
            lines.append("## Family distribution (heuristic from filename)")
            lines.append("")
            lines.append("| Family | Count |")
            lines.append("|---|---|")
            for family in sorted(self.by_family):
                lines.append(f"| {family} | {self.by_family[family]} |")
            lines.append("")

        if self.by_substrate_commit:
            lines.append("## Per-substrate-commit verdict distribution")
            lines.append("")
            lines.append("| Substrate commit | Verdicts |")
            lines.append("|---|---|")
            for commit in sorted(self.by_substrate_commit):
                breakdown = self.by_substrate_commit[commit]
                cells = ", ".join(
                    f"{v}: {breakdown[v]}" for v in sorted(breakdown)
                )
                lines.append(f"| `{commit}` | {cells} |")
            lines.append("")

        if self.verdict_flips:
            lines.append("## Verdict flips (same family, two commits, two verdicts)")
            lines.append("")
            lines.append("| Family | Commit A | Verdict A | Commit B | Verdict B |")
            lines.append("|---|---|---|---|---|")
            for flip in self.verdict_flips:
                lines.append(
                    f"| {flip.family} | `{flip.commit_a}` | {flip.verdict_a} "
                    f"| `{flip.commit_b}` | {flip.verdict_b} |"
                )
            lines.append("")

        return "\n".join(lines)


def summarize_directory(directory: str | Path) -> CampaignSummary:
    """Walk ``directory`` recursively; produce a :class:`CampaignSummary`.

    Decode errors are counted but don't stop the walk. The
    per-substrate-commit breakdown reads ``substrate_git_commit`` from
    each loaded record (truncated to 12 hex chars for display).
    """
    root = Path(directory)
    entries = list_proofs(root)

    by_verdict: dict[str, int] = {}
    by_family: dict[str, int] = {}
    by_commit: dict[str, dict[str, int]] = {}
    n_decode_errors = 0

    # Detail rows: (family, commit_short, verdict, path)
    detail: list[tuple[str, str, str, Path]] = []

    for entry in entries:
        if entry.error:
            n_decode_errors += 1
            by_verdict.setdefault("ERROR", 0)
            by_verdict["ERROR"] += 1
            continue
        verdict = entry.verdict or "UNKNOWN"
        by_verdict.setdefault(verdict, 0)
        by_verdict[verdict] += 1

        family = _family_from_filename(entry.path)
        by_family.setdefault(family, 0)
        by_family[family] += 1

        # Need to load the record to get substrate_git_commit;
        # ProofListEntry doesn't carry it directly.
        try:
            record = load(entry.path)
        except ProofDecodeError:
            continue
        commit_short = (record.substrate_git_commit or "<no-commit>")[:12]
        breakdown = by_commit.setdefault(commit_short, {})
        breakdown.setdefault(verdict, 0)
        breakdown[verdict] += 1

        detail.append((family, commit_short, verdict, entry.path))

    verdict_flips = _detect_verdict_flips(detail)

    return CampaignSummary(
        root=root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(entries),
        n_decode_errors=n_decode_errors,
        by_verdict=by_verdict,
        by_family=by_family,
        by_substrate_commit=by_commit,
        verdict_flips=verdict_flips,
        entries=entries,
    )


def _detect_verdict_flips(
    detail: list[tuple[str, str, str, Path]],
) -> tuple[VerdictFlip, ...]:
    """Find every pair (family, commit_a, commit_b) where the verdict differs.

    Pairs are deduplicated by (family, sorted-commit-pair) so we report
    each flip once. For more than 2 commits per family we report every
    pairwise flip — surfaces the full divergence pattern, not just
    adjacent transitions.
    """
    by_family: dict[str, list[tuple[str, str, Path]]] = defaultdict(list)
    for family, commit, verdict, path in detail:
        by_family[family].append((commit, verdict, path))

    flips: list[VerdictFlip] = []
    for family, rows in by_family.items():
        # group rows by commit
        per_commit: dict[str, tuple[str, Path]] = {}
        for commit, verdict, path in rows:
            # if multiple proofs at same commit have different verdicts,
            # that's a within-commit divergence — out of scope for the
            # cross-commit flip detector.
            per_commit.setdefault(commit, (verdict, path))
        commits = sorted(per_commit)
        for i, ca in enumerate(commits):
            for cb in commits[i + 1 :]:
                va, pa = per_commit[ca]
                vb, pb = per_commit[cb]
                if va != vb:
                    flips.append(
                        VerdictFlip(
                            family=family,
                            commit_a=ca,
                            commit_b=cb,
                            verdict_a=va,
                            verdict_b=vb,
                            proof_a=pa,
                            proof_b=pb,
                        )
                    )
    return tuple(flips)


# --- Diagnostic --------------------------------------------------------------


@dataclass(frozen=True)
class Diagnostic:
    """Per-record diagnostic — verdict + comparison vs siblings."""

    proof_path: Path
    proof_id: str
    verdict_outcome: str
    verdict_observed: float
    verdict_threshold_describe: str
    claim_statement: str
    closest_family_siblings: tuple[ProofListEntry, ...]  # in same dir, same family
    same_family_across_commits: tuple[ProofListEntry, ...]  # corpus-wide
    record: EmpiricalProofRecord

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Proof diagnostic — `{self.proof_path.name}`")
        lines.append("")
        lines.append(f"**proof_id:** `{self.proof_id}`")
        lines.append(f"**verdict:** **{self.verdict_outcome}**")
        lines.append(f"  - observed: `{self.verdict_observed:.6g}`")
        lines.append(f"  - threshold: `{self.verdict_threshold_describe}`")
        lines.append(f"  - claim: {self.claim_statement}")
        lines.append("")

        if self.closest_family_siblings:
            lines.append("## Closest siblings (same family, same directory)")
            lines.append("")
            lines.append("| Verdict | Path |")
            lines.append("|---|---|")
            for s in self.closest_family_siblings:
                lines.append(f"| {s.verdict or '?'} | `{s.path}` |")
            lines.append("")
        else:
            lines.append("## Closest siblings")
            lines.append("")
            lines.append("_(no same-family siblings found in the corpus directory)_")
            lines.append("")

        if self.same_family_across_commits:
            lines.append("## Same-family across substrate commits")
            lines.append("")
            lines.append("| Verdict | Path |")
            lines.append("|---|---|")
            for s in self.same_family_across_commits:
                lines.append(f"| {s.verdict or '?'} | `{s.path}` |")
            lines.append("")

        return "\n".join(lines)


def diagnose_proof(
    proof_path: str | Path,
    *,
    corpus_dir: str | Path | None = None,
) -> Diagnostic:
    """Build a :class:`Diagnostic` for a single proof record.

    ``corpus_dir`` defaults to the directory containing the proof — the
    sibling-detection logic walks that directory for same-family
    records. Pass an explicit path to scope siblings against a
    different corpus.

    Loud-failure: raises :class:`ProofDecodeError` if the proof can't
    be loaded.
    """
    proof_path = Path(proof_path)
    record = load(proof_path)
    if corpus_dir is None:
        corpus_dir = proof_path.parent
    else:
        corpus_dir = Path(corpus_dir)

    family = _family_from_filename(proof_path)
    siblings = []
    for entry in list_proofs(corpus_dir):
        if entry.path == proof_path:
            continue
        if entry.error:
            continue
        if _family_from_filename(entry.path) == family:
            siblings.append(entry)

    # "Same-family across substrate commits" is the same query in the
    # current corpus layout. When corpus_dir is the proof's own dir,
    # this collapses with closest_family_siblings; when corpus_dir is
    # a broader root, the two diverge. We expose both for clarity.
    return Diagnostic(
        proof_path=proof_path,
        proof_id=record.proof_id,
        verdict_outcome=record.verdict.outcome,
        verdict_observed=record.verdict.observed_value,
        verdict_threshold_describe=record.verdict.threshold.describe(),
        claim_statement=record.claim.statement,
        closest_family_siblings=tuple(siblings),
        same_family_across_commits=tuple(siblings),
        record=record,
    )


# --- MetricTrajectory --------------------------------------------------------


@dataclass(frozen=True)
class MetricTrajectory:
    """Per-metric trajectory across a proof corpus.

    Built by :func:`analyze_metric` — walks every proof, harvests every
    :class:`PillarEvidence` whose ``statistic_name`` matches the
    requested metric, then summarises across the resulting values.

    ``values`` is a tuple of ``(path, value)`` in path-sorted order so
    consumers get deterministic ordering. The summary fields (mean,
    stdev, minimum, maximum) are computed across the values list;
    ``stdev`` is the sample stdev (requires ≥ 2 values; ``None``
    otherwise).
    """

    metric: str
    root: Path
    n_proofs_scanned: int
    n_values: int
    values: tuple[tuple[Path, float], ...]
    mean: float | None
    stdev: float | None
    minimum: float | None
    maximum: float | None

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Metric trajectory — `{self.metric}`")
        lines.append("")
        lines.append(f"Root: `{self.root}`")
        lines.append(
            f"Scanned: {self.n_proofs_scanned} proof(s); "
            f"matched: **{self.n_values} value(s)**"
        )
        lines.append("")
        if self.n_values == 0:
            lines.append(
                f"_(no PillarEvidence with statistic_name=={self.metric!r} found)_"
            )
            return "\n".join(lines)

        lines.append("## Summary statistics")
        lines.append("")
        lines.append("| Stat | Value |")
        lines.append("|---|---|")
        lines.append(f"| mean | `{self.mean:.6g}` |")
        if self.stdev is not None:
            lines.append(f"| stdev | `{self.stdev:.6g}` |")
        lines.append(f"| min | `{self.minimum:.6g}` |")
        lines.append(f"| max | `{self.maximum:.6g}` |")
        lines.append("")

        lines.append("## All values")
        lines.append("")
        lines.append("| Value | Path |")
        lines.append("|---|---|")
        for path, value in self.values:
            lines.append(f"| `{value:.6g}` | `{path}` |")
        return "\n".join(lines)


def analyze_metric(
    metric: str,
    directory: str | Path,
) -> MetricTrajectory:
    """Walk ``directory`` and extract every PillarEvidence ``metric`` value.

    Each proof contributes 0..N values (a proof may have multiple
    PillarEvidence entries with the same statistic_name; all match).
    Decode errors are skipped silently from the trajectory but counted
    in ``n_proofs_scanned``.

    Loud-failure is preserved for the directory not existing
    (raises :class:`FileNotFoundError` via the underlying
    :func:`iter_proofs`).
    """
    root = Path(directory)
    pairs: list[tuple[Path, float]] = []
    n_scanned = 0
    for path in iter_proofs(root):
        n_scanned += 1
        try:
            record = load(path)
        except ProofDecodeError:
            continue
        for evidence in record.evidence:
            if evidence.statistic_name == metric:
                pairs.append((path, evidence.statistic_value))

    pairs.sort(key=lambda pair: str(pair[0]))
    if not pairs:
        return MetricTrajectory(
            metric=metric,
            root=root,
            n_proofs_scanned=n_scanned,
            n_values=0,
            values=(),
            mean=None,
            stdev=None,
            minimum=None,
            maximum=None,
        )
    values_only = [v for _, v in pairs]
    return MetricTrajectory(
        metric=metric,
        root=root,
        n_proofs_scanned=n_scanned,
        n_values=len(pairs),
        values=tuple(pairs),
        mean=statistics.fmean(values_only),
        stdev=statistics.stdev(values_only) if len(values_only) >= 2 else None,
        minimum=min(values_only),
        maximum=max(values_only),
    )


__all__ = [
    "CampaignSummary",
    "Diagnostic",
    "MetricTrajectory",
    "VerdictFlip",
    "analyze_metric",
    "diagnose_proof",
    "summarize_directory",
]
