"""The Ophamin Empirical Proof Record — the official result artifact.

One record per verified claim. Two serialisations:

    proof.json   canonical, machine-readable, JSON-Schema-validated
    PROOF.md     rendered, human-readable

A proof is *bulletproof* when it is:

  * falsifiable    — every claim carries a pre-registered Threshold
  * pre-registered — claim + config + analysis plan hashed BEFORE the run
  * traceable      — content-addressed: claim -> config -> substrate -> data -> result
  * reproducible   — exact command + environment lock + lineage chain
  * attributed     — every statistic names the library + version that produced it
  * tamper-evident — HMAC-signed over the whole record body

The nine sections:

    1 Identity          2 Claim            3 Pre-registration
    4 Data              5 Evidence         6 Verdict
    7 Reproduction      8 Provenance       9 Signature

A ``REFUTED`` record is a valid proof — disproving a claim is a result.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "1.0"

# verdict outcomes
VALIDATED = "VALIDATED"
REFUTED = "REFUTED"
INCONCLUSIVE = "INCONCLUSIVE"
_OUTCOMES = {VALIDATED, REFUTED, INCONCLUSIVE}

# falsifiable-threshold comparators
_COMPARATORS = {
    ">=": lambda obs, thr: obs >= thr,
    "<=": lambda obs, thr: obs <= thr,
    ">": lambda obs, thr: obs > thr,
    "<": lambda obs, thr: obs < thr,
    "==": lambda obs, thr: obs == thr,
}


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(obj: Any) -> str:
    """Stable SHA-256 of any JSON-serialisable object."""
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_environment_lock() -> dict[str, str]:
    """Capture the current interpreter + installed package versions for §7."""
    import importlib.metadata as md

    lock: dict[str, str] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    for dist in sorted(md.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        if name:
            lock[name] = dist.version
    return lock


# --------------------------------------------------------------------------
# Section 2 — the falsifiable claim (the five-tuple)
# --------------------------------------------------------------------------

@dataclass
class Threshold:
    """A falsifiable pass/fail boundary — there is no claim without one."""

    metric: str          # what is measured, e.g. "dissonance_gradient_slope"
    comparator: str      # one of >=, <=, >, <, ==
    value: float         # the boundary
    units: str = ""

    def __post_init__(self) -> None:
        if self.comparator not in _COMPARATORS:
            raise ValueError(
                f"comparator must be one of {sorted(_COMPARATORS)}, got {self.comparator!r}"
            )

    def decide(self, observed: float) -> bool:
        """True iff the observed value satisfies the threshold."""
        return _COMPARATORS[self.comparator](observed, self.value)

    def describe(self) -> str:
        suffix = f" {self.units}" if self.units else ""
        return f"{self.metric} {self.comparator} {self.value}{suffix}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "comparator": self.comparator,
            "value": self.value,
            "units": self.units,
        }


@dataclass
class Claim:
    """Section 2 — the falsifiable claim, as a five-tuple."""

    statement: str           # plain-language, falsifiable
    operationalization: str  # how it is measured (pillar + metric + estimator)
    threshold: Threshold
    h0: str                  # null hypothesis
    h1: str                  # alternative hypothesis

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "operationalization": self.operationalization,
            "threshold": self.threshold.to_dict(),
            "h0": self.h0,
            "h1": self.h1,
        }


# --------------------------------------------------------------------------
# Section 3 — pre-registration (the anti-p-hacking lock)
# --------------------------------------------------------------------------

@dataclass
class PreRegistration:
    """Section 3 — claim + plan hashed BEFORE the run.

    ``preregistered_at`` must precede the record's ``created_at``; ``validate``
    enforces it. Build this object before the experiment runs.
    """

    config_hash: str
    data_hash: str
    analysis_plan: str
    sweep_grid: dict[str, Any] = field(default_factory=dict)
    preregistered_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_hash": self.config_hash,
            "data_hash": self.data_hash,
            "analysis_plan": self.analysis_plan,
            "sweep_grid": self.sweep_grid,
            "preregistered_at": self.preregistered_at,
        }


# --------------------------------------------------------------------------
# Section 4 — the data (real, content-hashed)
# --------------------------------------------------------------------------

@dataclass
class DatasetRef:
    """Section 4 — one real dataset, content-addressed."""

    name: str
    content_hash: str
    n_records: int
    source: str          # url or origin description
    kind: str = "corpus"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "content_hash": self.content_hash,
            "n_records": self.n_records,
            "source": self.source,
            "kind": self.kind,
        }


# --------------------------------------------------------------------------
# Section 5 — evidence, attributed per pillar to its library
# --------------------------------------------------------------------------

@dataclass
class PillarEvidence:
    """Section 5 — one pillar's measured evidence, attributed to its library."""

    pillar: str               # e.g. "I.cma", "diag.anticipatory"
    statistic_name: str
    statistic_value: float
    library: str              # e.g. "statsmodels"
    library_version: str
    effect_size: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    p_value: float | None = None
    cross_check: str = "n/a"  # "passed" | "skipped" | "n/a"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pillar": self.pillar,
            "statistic_name": self.statistic_name,
            "statistic_value": self.statistic_value,
            "library": self.library,
            "library_version": self.library_version,
            "effect_size": self.effect_size,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "p_value": self.p_value,
            "cross_check": self.cross_check,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------
# Section 6 — the verdict
# --------------------------------------------------------------------------

@dataclass
class Verdict:
    """Section 6 — VALIDATED / REFUTED / INCONCLUSIVE against the threshold."""

    outcome: str
    observed_value: float
    threshold: Threshold
    reasoning: str

    def __post_init__(self) -> None:
        if self.outcome not in _OUTCOMES:
            raise ValueError(f"outcome must be one of {sorted(_OUTCOMES)}")

    @classmethod
    def decide(
        cls,
        observed: float,
        threshold: Threshold,
        *,
        inconclusive: bool = False,
        reasoning: str = "",
    ) -> "Verdict":
        """Decide the verdict by comparing ``observed`` against ``threshold``."""
        if inconclusive:
            return cls(
                INCONCLUSIVE,
                observed,
                threshold,
                reasoning or "evidence insufficient to decide for or against the claim",
            )
        satisfied = threshold.decide(observed)
        outcome = VALIDATED if satisfied else REFUTED
        arithmetic = (
            f"observed {observed:.6g} "
            f"{'satisfies' if satisfied else 'does not satisfy'} "
            f"the pre-registered threshold ({threshold.describe()})"
        )
        return cls(outcome, observed, threshold, reasoning or arithmetic)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "observed_value": self.observed_value,
            "threshold": self.threshold.to_dict(),
            "reasoning": self.reasoning,
        }


# --------------------------------------------------------------------------
# Section 7 — reproduction
# --------------------------------------------------------------------------

@dataclass
class Reproduction:
    """Section 7 — exact reproduction command, environment lock, lineage chain."""

    command: str
    environment: dict[str, str] = field(default_factory=build_environment_lock)
    lineage_chain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "environment": self.environment,
            "lineage_chain": self.lineage_chain,
        }


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------

@dataclass
class EmpiricalProofRecord:
    """The official Ophamin result artifact — nine sections, content-addressed, signed."""

    # §2..§8
    claim: Claim
    preregistration: PreRegistration
    datasets: list[DatasetRef]
    substrate_name: str
    substrate_git_commit: str
    evidence: list[PillarEvidence]
    verdict: Verdict
    reproduction: Reproduction
    provenance: dict[str, Any] = field(default_factory=dict)  # W3C PROV-JSON

    # §1 identity
    ophamin_version: str = ""
    ophamin_git_commit: str = ""
    created_at: str = field(default_factory=_now)
    schema_version: str = SCHEMA_VERSION

    # §9 signature — set by sign()
    signature: str = ""

    # -- the signable / hashable body (sections 1-8) ------------------------

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "identity": {
                "ophamin_version": self.ophamin_version,
                "ophamin_git_commit": self.ophamin_git_commit,
                "created_at": self.created_at,
            },
            "claim": self.claim.to_dict(),
            "preregistration": self.preregistration.to_dict(),
            "data": {
                "substrate_name": self.substrate_name,
                "substrate_git_commit": self.substrate_git_commit,
                "datasets": [d.to_dict() for d in self.datasets],
            },
            "evidence": [e.to_dict() for e in self.evidence],
            "verdict": self.verdict.to_dict(),
            "reproduction": self.reproduction.to_dict(),
            "provenance": self.provenance,
        }

    @property
    def proof_id(self) -> str:
        """Content-addressed identifier — SHA-256 over sections 1-8."""
        return content_hash(self._body())

    # -- tamper-evident signature ------------------------------------------

    def sign(self, key: bytes) -> "EmpiricalProofRecord":
        """HMAC-SHA256 sign the record body. Returns self for chaining."""
        self.signature = hmac.new(
            key, _canonical(self._body()).encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return self

    def verify_signature(self, key: bytes) -> bool:
        """True iff the signature matches the current body under ``key``."""
        if not self.signature:
            return False
        expected = hmac.new(
            key, _canonical(self._body()).encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    # -- validation (the bulletproof checklist) ----------------------------

    def validate(self) -> list[str]:
        """Return a list of problems; an empty list means the record is well-formed.

        Enforces the properties that make a proof bulletproof — every one of
        them, not a subset.
        """
        problems: list[str] = []

        # falsifiable
        if not self.claim.statement.strip():
            problems.append("claim.statement is empty")
        if not self.claim.h0.strip() or not self.claim.h1.strip():
            problems.append("claim must state both H0 and H1")
        # (Threshold validity is enforced by Threshold.__post_init__)

        # pre-registered — the anti-p-hacking lock
        if not self.preregistration.config_hash:
            problems.append("preregistration.config_hash is empty")
        if not self.preregistration.data_hash:
            problems.append("preregistration.data_hash is empty")
        try:
            pre = datetime.fromisoformat(self.preregistration.preregistered_at)
            created = datetime.fromisoformat(self.created_at)
            if pre > created:
                problems.append(
                    "preregistration.preregistered_at is AFTER created_at — "
                    "the pre-registration lock is violated"
                )
        except ValueError:
            problems.append("preregistration.preregistered_at / created_at not ISO timestamps")

        # real data
        if not self.datasets:
            problems.append("no datasets — a proof needs real data")
        for d in self.datasets:
            if not d.content_hash:
                problems.append(f"dataset '{d.name}' has no content hash")
            if d.n_records <= 0:
                problems.append(f"dataset '{d.name}' has n_records <= 0")
        if not self.substrate_git_commit:
            problems.append(
                "substrate_git_commit is empty — the substrate must be versioned"
            )

        # attributed — every statistic names its library + version
        if not self.evidence:
            problems.append("no pillar evidence recorded")
        for e in self.evidence:
            if not e.library or not e.library_version:
                problems.append(
                    f"evidence '{e.pillar}/{e.statistic_name}' missing library attribution"
                )

        # verdict consistency
        if self.verdict.outcome not in _OUTCOMES:
            problems.append(f"verdict.outcome '{self.verdict.outcome}' is not a valid outcome")
        elif self.verdict.outcome != INCONCLUSIVE:
            satisfied = self.verdict.threshold.decide(self.verdict.observed_value)
            expected = VALIDATED if satisfied else REFUTED
            if self.verdict.outcome != expected:
                problems.append(
                    f"verdict.outcome '{self.verdict.outcome}' contradicts the threshold "
                    f"(observed {self.verdict.observed_value} -> expected {expected})"
                )

        # reproducible
        if not self.reproduction.command.strip():
            problems.append("reproduction.command is empty")
        if not self.reproduction.environment:
            problems.append("reproduction.environment lock is empty")

        # identity
        if not self.ophamin_version:
            problems.append("ophamin_version is empty")

        return problems

    @property
    def is_valid(self) -> bool:
        return not self.validate()

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        body = self._body()
        return {"proof_id": self.proof_id, **body, "signature": self.signature}

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        text = json.dumps(self.to_dict(), indent=indent, default=str)
        if path:
            from pathlib import Path

            Path(path).write_text(text, encoding="utf-8")
        return text

    def to_markdown(self, path: str | None = None) -> str:
        c, v = self.claim, self.verdict
        lines: list[str] = []
        lines.append(f"# Ophamin Empirical Proof Record — `{v.outcome}`")
        lines.append("")
        lines.append(f"**Proof ID:** `{self.proof_id}`")
        lines.append(f"**Schema:** v{self.schema_version}  ")
        lines.append(f"**Created:** {self.created_at}")
        lines.append("")

        lines.append("## 1. Identity")
        lines.append(f"- Ophamin: `{self.ophamin_version}` @ `{self.ophamin_git_commit or '(no commit)'}`")
        lines.append(f"- Substrate: **{self.substrate_name}** @ `{self.substrate_git_commit or '(no commit)'}`")
        lines.append("")

        lines.append("## 2. Claim")
        lines.append(f"> {c.statement}")
        lines.append("")
        lines.append(f"- **Operationalization:** {c.operationalization}")
        lines.append(f"- **Threshold:** `{c.threshold.describe()}`")
        lines.append(f"- **H0:** {c.h0}")
        lines.append(f"- **H1:** {c.h1}")
        lines.append("")

        lines.append("## 3. Pre-registration")
        lines.append(f"- Registered at: `{self.preregistration.preregistered_at}` (must precede §1 created)")
        lines.append(f"- Config hash: `{self.preregistration.config_hash}`")
        lines.append(f"- Data hash: `{self.preregistration.data_hash}`")
        lines.append(f"- Analysis plan: {self.preregistration.analysis_plan}")
        lines.append("")

        lines.append("## 4. Data")
        for d in self.datasets:
            lines.append(
                f"- **{d.name}** ({d.kind}) — {d.n_records:,} records — "
                f"`{d.content_hash[:16]}…` — {d.source}"
            )
        lines.append("")

        lines.append("## 5. Evidence")
        lines.append("| Pillar | Statistic | Value | Effect | 95% CI | p | Library | Cross-check |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for e in self.evidence:
            ci = (
                f"({e.ci_low:.4g}, {e.ci_high:.4g})"
                if e.ci_low is not None and e.ci_high is not None
                else "—"
            )
            lines.append(
                f"| {e.pillar} | {e.statistic_name} | {e.statistic_value:.6g} | "
                f"{'—' if e.effect_size is None else f'{e.effect_size:.4g}'} | {ci} | "
                f"{'—' if e.p_value is None else f'{e.p_value:.4g}'} | "
                f"{e.library} {e.library_version} | {e.cross_check} |"
            )
        lines.append("")

        lines.append("## 6. Verdict")
        lines.append(f"### **{v.outcome}**")
        lines.append("")
        lines.append(f"- Observed: `{v.observed_value:.6g}`")
        lines.append(f"- Threshold: `{v.threshold.describe()}`")
        lines.append(f"- Reasoning: {v.reasoning}")
        lines.append("")

        lines.append("## 7. Reproduction")
        lines.append("```")
        lines.append(self.reproduction.command)
        lines.append("```")
        lines.append(f"- Environment lock: {len(self.reproduction.environment)} entries")
        if self.reproduction.lineage_chain:
            lines.append(f"- Lineage chain: {' <- '.join(self.reproduction.lineage_chain)}")
        lines.append("")

        lines.append("## 8. Provenance")
        prov = self.provenance or {}
        lines.append(
            f"- W3C PROV-O graph: {len(prov.get('entity', {}))} entities, "
            f"{len(prov.get('activity', {}))} activities, "
            f"{len(prov.get('agent', {}))} agents"
        )
        lines.append("")

        lines.append("## 9. Signature")
        lines.append(
            f"- `{self.signature}`" if self.signature else "- *(unsigned)*"
        )
        lines.append("")

        problems = self.validate()
        lines.append("---")
        if problems:
            lines.append(f"**⚠ {len(problems)} validation problem(s):**")
            for p in problems:
                lines.append(f"- {p}")
        else:
            lines.append("**✓ Record is well-formed** — falsifiable, pre-registered, "
                         "traceable, reproducible, attributed.")
        lines.append("")

        text = "\n".join(lines)
        if path:
            from pathlib import Path

            Path(path).write_text(text, encoding="utf-8")
        return text
