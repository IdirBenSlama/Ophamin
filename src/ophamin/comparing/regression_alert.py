"""Regression-alert daemon (Move J) — closes gap F from the prior audit.

Detects verdict regressions across two snapshots of a proof corpus
(typically: ``proofs/`` at the prior Kimera commit vs ``proofs/`` at the
new commit). A "regression" is a scenario whose verdict moved from
VALIDATED (or INCONCLUSIVE) to REFUTED — the substrate started failing
a claim it previously satisfied. The detector also flags the inverse
("recovery": REFUTED → VALIDATED) and the lateral cases (different
verdict that's not the substrate's load-bearing regression direction).

The pipeline:

  1. Snapshot a proof corpus at commit A (e.g. via
     :func:`scan_proof_directory`).
  2. Snapshot the proof corpus at commit B.
  3. Run :func:`compute_regression_alert` on the pair.
  4. Inspect the resulting :class:`RegressionAlert` — list of
     :class:`VerdictTransition` rows + headline counts.

The pairing key is the scenario's stable identifier (the proof's
filename family or — when present — the underlying scenario name via
the proof's claim-statement signature). For two proofs of the same
family at two different substrate commits to be paired, both must
carry the same family heuristic; mis-paired entries are surfaced as
``unmatched_in_a`` / ``unmatched_in_b`` for operator inspection.

CLI:

  ophamin watch-proofs --before <dir-a> --after <dir-b> [--out <path>]

Output is a signed :class:`RegressionAlertRecord` (HMAC-SHA256 +
content-addressed `alert_id`), mirroring the shape of every other
Ophamin artifact. A REGRESSION-class alert is exit-code 1; a quiet
(no-change) alert is exit-code 0; a recovery-class alert is exit-code
0 with a notable summary line.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ophamin import __version__
from ophamin.measuring.proof import EmpiricalProofRecord
from ophamin.measuring.proof.codec import (
    ProofDecodeError,
    _family_from_filename,
    iter_proofs,
    load,
)

REGRESSION_ALERT_SCHEMA_VERSION = "regression-alert/1.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


# --- snapshot + transition shapes ------------------------------------------


@dataclass(frozen=True)
class ProofSnapshot:
    """One proof's identity in the corpus — family + verdict + claim
    fingerprint + commit, keyed for cross-snapshot pairing.

    The ``pair_key`` combines the family + the claim's threshold metric
    + the substrate target, so two scenarios in the same family targeting
    different substrate components don't accidentally pair.
    """

    path: Path
    family: str
    verdict: str
    observed_value: float
    threshold_metric: str
    threshold_comparator: str
    threshold_value: float
    substrate_git_commit: str
    claim_statement_hash: str

    @property
    def pair_key(self) -> str:
        return f"{self.family}|{self.threshold_metric}|{self.threshold_comparator}|{self.threshold_value}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "family": self.family,
            "verdict": self.verdict,
            "observed_value": self.observed_value,
            "threshold_metric": self.threshold_metric,
            "threshold_comparator": self.threshold_comparator,
            "threshold_value": self.threshold_value,
            "substrate_git_commit": self.substrate_git_commit,
            "claim_statement_hash": self.claim_statement_hash,
            "pair_key": self.pair_key,
        }


def snapshot_one(record: EmpiricalProofRecord, path: Path) -> ProofSnapshot:
    return ProofSnapshot(
        path=path,
        family=_family_from_filename(path),
        verdict=record.verdict.outcome,
        observed_value=float(record.verdict.observed_value),
        threshold_metric=record.verdict.threshold.metric,
        threshold_comparator=record.verdict.threshold.comparator,
        threshold_value=float(record.verdict.threshold.value),
        substrate_git_commit=record.substrate_git_commit,
        claim_statement_hash=hashlib.sha256(
            record.claim.statement.encode("utf-8")
        ).hexdigest()[:16],
    )


def scan_proof_directory(directory: str | Path) -> tuple[ProofSnapshot, ...]:
    """Walk a proof directory recursively; return one ProofSnapshot per
    decodable record. Undecodable files are skipped silently — the
    pairing surface needs structured records to work with."""
    snapshots: list[ProofSnapshot] = []
    for path in iter_proofs(directory):
        try:
            record = load(path)
        except ProofDecodeError:
            continue
        snapshots.append(snapshot_one(record, path))
    return tuple(snapshots)


@dataclass(frozen=True)
class VerdictTransition:
    """One paired snapshot — its verdict at A vs at B + the transition class."""

    pair_key: str
    family: str
    threshold_metric: str
    before_verdict: str
    before_observed: float
    before_commit: str
    before_path: Path
    after_verdict: str
    after_observed: float
    after_commit: str
    after_path: Path
    transition_class: str  # "regression" | "recovery" | "lateral" | "unchanged"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_key": self.pair_key,
            "family": self.family,
            "threshold_metric": self.threshold_metric,
            "before_verdict": self.before_verdict,
            "before_observed": self.before_observed,
            "before_commit": self.before_commit,
            "before_path": str(self.before_path),
            "after_verdict": self.after_verdict,
            "after_observed": self.after_observed,
            "after_commit": self.after_commit,
            "after_path": str(self.after_path),
            "transition_class": self.transition_class,
        }


def classify_transition(before: str, after: str) -> str:
    """Map a (before, after) verdict pair to a transition class."""
    if before == after:
        return "unchanged"
    if before in ("VALIDATED", "INCONCLUSIVE") and after == "REFUTED":
        return "regression"
    if before == "REFUTED" and after == "VALIDATED":
        return "recovery"
    return "lateral"


# --- RegressionAlertRecord -------------------------------------------------


@dataclass
class RegressionAlertRecord:
    """Signed, content-addressed artifact of one before/after comparison."""

    before_root: str
    after_root: str
    n_before: int
    n_after: int
    transitions: list[VerdictTransition] = field(default_factory=list)
    unmatched_in_before: list[str] = field(default_factory=list)
    unmatched_in_after: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=_now)
    ophamin_version: str = __version__
    ophamin_git_commit: str = ""
    schema_version: str = REGRESSION_ALERT_SCHEMA_VERSION
    signature: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "before_root": self.before_root,
            "after_root": self.after_root,
            "n_before": self.n_before,
            "n_after": self.n_after,
            "generated_at": self.generated_at,
            "ophamin_version": self.ophamin_version,
            "ophamin_git_commit": self.ophamin_git_commit,
            "transitions": [t.to_dict() for t in self.transitions],
            "unmatched_in_before": list(self.unmatched_in_before),
            "unmatched_in_after": list(self.unmatched_in_after),
        }

    @property
    def alert_id(self) -> str:
        return hashlib.sha256(_canonical(self._body()).encode("utf-8")).hexdigest()

    def sign(self, key: bytes) -> "RegressionAlertRecord":
        self.signature = hmac.new(
            key, _canonical(self._body()).encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return self

    def verify_signature(self, key: bytes) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(
            key, _canonical(self._body()).encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    # -- summary helpers ----------------------------------------------------

    @property
    def n_regressions(self) -> int:
        return sum(1 for t in self.transitions if t.transition_class == "regression")

    @property
    def n_recoveries(self) -> int:
        return sum(1 for t in self.transitions if t.transition_class == "recovery")

    @property
    def n_lateral(self) -> int:
        return sum(1 for t in self.transitions if t.transition_class == "lateral")

    @property
    def n_unchanged(self) -> int:
        return sum(1 for t in self.transitions if t.transition_class == "unchanged")

    @property
    def has_regressions(self) -> bool:
        return self.n_regressions > 0

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        body = self._body()
        return {"alert_id": self.alert_id, **body, "signature": self.signature}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegressionAlertRecord":
        record = cls(
            before_root=str(data["before_root"]),
            after_root=str(data["after_root"]),
            n_before=int(data["n_before"]),
            n_after=int(data["n_after"]),
            transitions=[
                VerdictTransition(
                    pair_key=str(t["pair_key"]),
                    family=str(t["family"]),
                    threshold_metric=str(t["threshold_metric"]),
                    before_verdict=str(t["before_verdict"]),
                    before_observed=float(t["before_observed"]),
                    before_commit=str(t["before_commit"]),
                    before_path=Path(t["before_path"]),
                    after_verdict=str(t["after_verdict"]),
                    after_observed=float(t["after_observed"]),
                    after_commit=str(t["after_commit"]),
                    after_path=Path(t["after_path"]),
                    transition_class=str(t["transition_class"]),
                )
                for t in data.get("transitions") or []
            ],
            unmatched_in_before=list(data.get("unmatched_in_before") or []),
            unmatched_in_after=list(data.get("unmatched_in_after") or []),
            generated_at=str(data.get("generated_at", _now())),
            ophamin_version=str(data.get("ophamin_version", __version__)),
            ophamin_git_commit=str(data.get("ophamin_git_commit", "")),
            schema_version=str(data.get("schema_version", REGRESSION_ALERT_SCHEMA_VERSION)),
        )
        record.signature = str(data.get("signature", ""))
        return record

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Regression alert — `{self.alert_id[:16]}...`")
        lines.append("")
        lines.append(f"_Generated: {self.generated_at}_")
        lines.append("")
        lines.append(f"**Before:** `{self.before_root}` ({self.n_before} proof(s))")
        lines.append(f"**After:**  `{self.after_root}` ({self.n_after} proof(s))")
        lines.append("")
        lines.append(
            f"**Transitions:** regression={self.n_regressions} · "
            f"recovery={self.n_recoveries} · "
            f"lateral={self.n_lateral} · "
            f"unchanged={self.n_unchanged}"
        )
        lines.append("")
        if self.has_regressions:
            lines.append("## ⚠ Regressions")
            lines.append("")
            lines.append("| Family | Metric | Before | After | After commit |")
            lines.append("|---|---|---|---|---|")
            for t in self.transitions:
                if t.transition_class != "regression":
                    continue
                lines.append(
                    f"| {t.family} | `{t.threshold_metric}` | "
                    f"{t.before_verdict} ({t.before_observed:.4g}) | "
                    f"{t.after_verdict} ({t.after_observed:.4g}) | "
                    f"`{t.after_commit[:12]}` |"
                )
            lines.append("")
        if self.n_recoveries:
            lines.append("## ✓ Recoveries")
            lines.append("")
            lines.append("| Family | Metric | Before | After |")
            lines.append("|---|---|---|---|")
            for t in self.transitions:
                if t.transition_class != "recovery":
                    continue
                lines.append(
                    f"| {t.family} | `{t.threshold_metric}` | "
                    f"{t.before_verdict} | {t.after_verdict} |"
                )
            lines.append("")
        if self.unmatched_in_before or self.unmatched_in_after:
            lines.append("## Unmatched")
            lines.append("")
            for p in self.unmatched_in_before:
                lines.append(f"- only in before: `{p}`")
            for p in self.unmatched_in_after:
                lines.append(f"- only in after:  `{p}`")
            lines.append("")
        return "\n".join(lines)


# --- the detector ---------------------------------------------------------


def compute_regression_alert(
    before_dir: str | Path,
    after_dir: str | Path,
) -> RegressionAlertRecord:
    """Walk both directories; pair by ``pair_key``; classify transitions.

    Per-pair-key duplicates within one directory: the FIRST snapshot in
    iter_proofs order wins (path-sorted, so this is deterministic).
    Operator should consolidate duplicates before re-running if this
    produces unexpected pairings.

    Returns an unsigned :class:`RegressionAlertRecord`; caller signs.
    """
    before_dir = Path(before_dir)
    after_dir = Path(after_dir)
    before = scan_proof_directory(before_dir)
    after = scan_proof_directory(after_dir)

    before_by_key: dict[str, ProofSnapshot] = {}
    for s in before:
        before_by_key.setdefault(s.pair_key, s)
    after_by_key: dict[str, ProofSnapshot] = {}
    for s in after:
        after_by_key.setdefault(s.pair_key, s)

    transitions: list[VerdictTransition] = []
    matched_keys = sorted(set(before_by_key) & set(after_by_key))
    for key in matched_keys:
        b = before_by_key[key]
        a = after_by_key[key]
        cls = classify_transition(b.verdict, a.verdict)
        transitions.append(
            VerdictTransition(
                pair_key=key,
                family=b.family,
                threshold_metric=b.threshold_metric,
                before_verdict=b.verdict,
                before_observed=b.observed_value,
                before_commit=b.substrate_git_commit,
                before_path=b.path,
                after_verdict=a.verdict,
                after_observed=a.observed_value,
                after_commit=a.substrate_git_commit,
                after_path=a.path,
                transition_class=cls,
            )
        )

    unmatched_b = sorted(
        str(s.path) for k, s in before_by_key.items() if k not in after_by_key
    )
    unmatched_a = sorted(
        str(s.path) for k, s in after_by_key.items() if k not in before_by_key
    )

    return RegressionAlertRecord(
        before_root=str(before_dir),
        after_root=str(after_dir),
        n_before=len(before),
        n_after=len(after),
        transitions=transitions,
        unmatched_in_before=unmatched_b,
        unmatched_in_after=unmatched_a,
    )


# --- IO -------------------------------------------------------------------


def dump_alert(record: RegressionAlertRecord, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record.to_dict(), indent=2, default=str), encoding="utf-8")
    return p


def load_alert(path: str | Path) -> RegressionAlertRecord:
    return RegressionAlertRecord.from_dict(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


__all__ = [
    "REGRESSION_ALERT_SCHEMA_VERSION",
    "ProofSnapshot",
    "RegressionAlertRecord",
    "VerdictTransition",
    "classify_transition",
    "compute_regression_alert",
    "dump_alert",
    "load_alert",
    "scan_proof_directory",
    "snapshot_one",
]
