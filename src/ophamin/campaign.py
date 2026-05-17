"""CampaignRecord + the 6-phase composite-run orchestrator (Move F).

Closes Deficit 2 from
``docs/ARCHITECTURE_EXTENDED_AUDIT_2026_05_16.md`` — the "6 phases"
the owner named are the six wheels of Ophamin's architecture
operating as a single coordinated pass against a substrate:

  1. ``seeing``        — discover the substrate's surface
  2. ``measuring``     — run the requested scenarios; collect signed
                         proof records
  3. ``comparing``     — synthesize the measuring output into a
                         campaign summary; detect verdict flips
  4. ``instrumenting`` — collect per-cycle resource cost (when the
                         substrate was wrapped in InstrumentedSubstrate)
  5. ``auditing``      — static-analysis sweep over the substrate's
                         source (when a source-code path is available)
  6. ``reporting``     — collate every preceding phase's output into
                         one rolled-up Markdown report

Each phase produces a :class:`CampaignPhase` aggregate; the
:class:`CampaignRecord` collects them into a signed,
content-addressed aggregate. A phase can be ``ok`` / ``skipped`` /
``failed``; ``skipped`` is the sanctioned outcome when the substrate
doesn't expose what a phase needs (e.g. ``auditing`` against a
MockSubstrate is skipped because there's no source code to audit).

The orchestrator never silently swallows phase failures — a failed
phase carries its error message into the record so the operator sees
exactly what broke. This is the framework's "loud-failure" stance
applied at the campaign level.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ophamin import __version__
from ophamin.comparing.fwer import (
    CorrectionFamily,
    CorrectionInput,
    apply_correction,
)
from ophamin.measuring.proof import dump as proof_dump
from ophamin.measuring.proof.codec import iter_proofs
from ophamin.measuring.scenarios import SCENARIOS, Scenario
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.seeing.substrate.base import SubstrateUnderTest


#: the wire-format schema version a fresh writer emits.
#:
#: Bumped 1.0 → 2.0 (2026-05-17, RFC 0002 Phase E2) to add FWER /
#: BH correction fields. The bump is **strictly additive**; 1.0 records
#: remain readable + signature-verifiable, see :func:`CampaignRecord._body`.
CAMPAIGN_SCHEMA_VERSION = "2.0"

#: every schema version a reader will accept.
SUPPORTED_CAMPAIGN_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0", "2.0"})

#: the canonical six phases in execution order.
CANONICAL_PHASE_ORDER: tuple[str, ...] = (
    "seeing",
    "measuring",
    "comparing",
    "instrumenting",
    "auditing",
    "reporting",
)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- data model -------------------------------------------------------------


@dataclass(frozen=True)
class CampaignPhase:
    """One wheel's contribution to a composite run.

    Three possible terminal ``status`` values:

    - ``"ok"``       — phase completed; ``artifact_paths`` + ``summary``
                       carry the output.
    - ``"skipped"``  — phase didn't apply (e.g. auditing against a
                       Mock substrate); ``error`` carries the reason.
    - ``"failed"``   — phase raised; ``error`` carries the exception
                       string. The campaign continues to the next
                       phase (loud-failure at the campaign level, not
                       at the per-phase level — operator sees every
                       phase's outcome).
    """

    wheel: str
    started_at: str
    completed_at: str
    status: str
    artifact_paths: tuple[str, ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "wheel": self.wheel,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "artifact_paths": list(self.artifact_paths),
            "summary": dict(self.summary),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignPhase":
        return cls(
            wheel=str(data["wheel"]),
            started_at=str(data["started_at"]),
            completed_at=str(data["completed_at"]),
            status=str(data["status"]),
            artifact_paths=tuple(data.get("artifact_paths") or ()),
            summary=dict(data.get("summary") or {}),
            error=data.get("error"),
        )


@dataclass
class CampaignRecord:
    """Signed, content-addressed aggregate of one full-pass run.

    Schema 2.0 (current) adds two strictly-additive fields:

    * ``corrected_verdicts`` — ``{claim_id → corrected_verdict}`` after
      multiplicity correction (FWER or FDR). Empty dict when no
      correction was applied or when no records carried a p_value.
    * ``multiplicity_correction_method`` — ``"holm"`` / ``"bh"`` /
      ``"none"``. The method the writer used when populating
      ``corrected_verdicts``.

    Schema 1.0 records remain readable: missing additive fields default
    to empty dict / ``"none"`` respectively. Signature verification is
    version-aware — :meth:`_body` includes the additive fields only
    when ``schema_version != "1.0"``, so a 1.0 signature still
    re-canonicalises bit-equal to the original wire form.
    """

    target_name: str
    target_git_commit: str
    phases: list[CampaignPhase] = field(default_factory=list)
    started_at: str = field(default_factory=_now)
    completed_at: str = ""
    ophamin_version: str = __version__
    ophamin_git_commit: str = ""
    schema_version: str = CAMPAIGN_SCHEMA_VERSION
    signature: str = ""
    #: ``{claim_id → corrected_verdict}`` after the multiplicity correction
    #: pass (Phase E2). New in schema 2.0; ignored on schema 1.0.
    corrected_verdicts: dict[str, str] = field(default_factory=dict)
    #: one of ``"holm"`` / ``"bh"`` / ``"none"`` (or other future methods).
    #: New in schema 2.0; defaults to ``"none"``.
    multiplicity_correction_method: str = "none"

    # -- body / id / signing -------------------------------------------------

    def _body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema_version": self.schema_version,
            "target_name": self.target_name,
            "target_git_commit": self.target_git_commit,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "ophamin_version": self.ophamin_version,
            "ophamin_git_commit": self.ophamin_git_commit,
            "phases": [p.to_dict() for p in self.phases],
        }
        # Schema-2.0 additive fields. A 1.0 record signed under the
        # original codec does NOT include these in its canonical form;
        # excluding them here keeps `verify_signature` bit-equal to the
        # original. New records always emit at 2.0 and include the fields.
        if self.schema_version != "1.0":
            body["corrected_verdicts"] = dict(self.corrected_verdicts)
            body["multiplicity_correction_method"] = self.multiplicity_correction_method
        return body

    @property
    def campaign_id(self) -> str:
        """Content-addressed identifier — SHA-256 over the body."""
        return hashlib.sha256(_canonical(self._body()).encode("utf-8")).hexdigest()

    def sign(self, key: bytes) -> "CampaignRecord":
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

    # -- summary helpers -----------------------------------------------------

    @property
    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {"ok": 0, "skipped": 0, "failed": 0}
        for p in self.phases:
            counts.setdefault(p.status, 0)
            counts[p.status] += 1
        return counts

    @property
    def all_ok(self) -> bool:
        return all(p.status == "ok" for p in self.phases)

    @property
    def any_failed(self) -> bool:
        return any(p.status == "failed" for p in self.phases)

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        body = self._body()
        return {"campaign_id": self.campaign_id, **body, "signature": self.signature}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignRecord":
        schema_version = str(data.get("schema_version", CAMPAIGN_SCHEMA_VERSION))
        if schema_version not in SUPPORTED_CAMPAIGN_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported CampaignRecord schema_version {schema_version!r}; "
                f"supported = {sorted(SUPPORTED_CAMPAIGN_SCHEMA_VERSIONS)}"
            )
        # Schema-2.0 additive fields: default to empty / "none" so 1.0
        # records load cleanly. dict values are coerced to str (defensive
        # — same posture as Threshold/Verdict float coercion).
        raw_corrected = data.get("corrected_verdicts") or {}
        corrected_verdicts: dict[str, str] = {
            str(k): str(v) for k, v in raw_corrected.items()
        }
        multiplicity_method = str(data.get("multiplicity_correction_method", "none"))
        record = cls(
            target_name=str(data["target_name"]),
            target_git_commit=str(data.get("target_git_commit", "")),
            phases=[CampaignPhase.from_dict(p) for p in data.get("phases", [])],
            started_at=str(data.get("started_at", _now())),
            completed_at=str(data.get("completed_at", "")),
            ophamin_version=str(data.get("ophamin_version", __version__)),
            ophamin_git_commit=str(data.get("ophamin_git_commit", "")),
            schema_version=schema_version,
            corrected_verdicts=corrected_verdicts,
            multiplicity_correction_method=multiplicity_method,
        )
        record.signature = str(data.get("signature", ""))
        return record

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Campaign — `{self.campaign_id[:16]}...`")
        lines.append("")
        lines.append(f"**Target:** `{self.target_name}` @ `{self.target_git_commit or '(no commit)'}`")
        lines.append(f"**Started:** {self.started_at}")
        lines.append(f"**Completed:** {self.completed_at or '(in flight)'}")
        lines.append(f"**Ophamin:** `{self.ophamin_version}` @ `{self.ophamin_git_commit or '(no commit)'}`")
        lines.append("")
        counts = self.status_counts
        lines.append(
            f"**Phase status:** ok={counts.get('ok', 0)} · "
            f"skipped={counts.get('skipped', 0)} · "
            f"failed={counts.get('failed', 0)}"
        )
        lines.append("")
        lines.append("## Phases (canonical order)")
        lines.append("")
        lines.append("| # | Wheel | Status | Artifacts | Summary |")
        lines.append("|---|---|---|---|---|")
        for i, phase in enumerate(self.phases, start=1):
            artifacts = ", ".join(
                f"`{Path(p).name}`" for p in phase.artifact_paths
            ) or "—"
            summary_str = ", ".join(
                f"{k}={v}" for k, v in sorted(phase.summary.items())
            ) or (phase.error or "—")
            if len(summary_str) > 80:
                summary_str = summary_str[:77] + "..."
            lines.append(
                f"| {i} | {phase.wheel} | {phase.status} | "
                f"{artifacts} | {summary_str} |"
            )
        lines.append("")
        return "\n".join(lines)


# --- orchestrator -----------------------------------------------------------


def run_campaign(
    *,
    substrate: SubstrateUnderTest,
    target_name: str | None = None,
    target_git_commit: str | None = None,
    scenarios: list[type[Scenario]] | None = None,
    enable_phases: set[str] | None = None,
    out_dir: str | Path = "campaigns/latest",
    sign_key: bytes = DEFAULT_SIGN_KEY,
    fwer_method: str = "holm",
    fwer_alpha: float = 0.05,
) -> CampaignRecord:
    """Run the six wheels in canonical order; emit a signed CampaignRecord.

    Args:
        substrate: the substrate the measuring phase will run scenarios
            against. Required.
        target_name: human-facing name for the target (default: the
            substrate's ``name`` attribute).
        target_git_commit: the target's git commit hash (default: the
            substrate's ``git_commit()`` return value).
        scenarios: list of Scenario classes to run in the measuring
            phase. Default: every default-instantiable scenario in
            :data:`SCENARIOS`.
        enable_phases: set of phase names to run. Default: all six.
        out_dir: directory under which per-phase artifacts are written.
        sign_key: HMAC-SHA256 key for signing the final record.
        fwer_method: multiplicity-correction method to apply during the
            comparing phase. One of :data:`ophamin.comparing.fwer.SUPPORTED_METHODS`
            (``"holm"`` / ``"bh"`` / ``"none"``). The default is
            ``"holm"`` — strict FWER control via Holm-Bonferroni. New
            in schema 2.0 (RFC 0002 Phase E2).
        fwer_alpha: family-wise / FDR threshold used when applying the
            correction. Default 0.05.

    Returns:
        A signed :class:`CampaignRecord` with one
        :class:`CampaignPhase` per executed phase, plus, when the
        ``comparing`` phase ran, the schema-2.0
        ``corrected_verdicts`` mapping + ``multiplicity_correction_method``
        populated from the FWER pass.

    The orchestrator NEVER raises on a per-phase failure — it captures
    the error string into the phase's ``error`` field and continues
    to the next phase. The caller inspects ``record.any_failed`` to
    surface to a non-zero exit code if appropriate.
    """
    if enable_phases is None:
        enable_phases = set(CANONICAL_PHASE_ORDER)
    if target_name is None:
        target_name = getattr(substrate, "name", str(type(substrate).__name__))
    if target_git_commit is None:
        try:
            target_git_commit = substrate.git_commit()
        except Exception:
            target_git_commit = ""
    if scenarios is None:
        scenarios = _select_default_instantiable_scenarios()

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    record = CampaignRecord(
        target_name=target_name,
        target_git_commit=target_git_commit,
    )

    for wheel in CANONICAL_PHASE_ORDER:
        if wheel not in enable_phases:
            continue
        runner = _PHASE_RUNNERS.get(wheel)
        if runner is None:
            record.phases.append(
                CampaignPhase(
                    wheel=wheel,
                    started_at=_now(),
                    completed_at=_now(),
                    status="failed",
                    error=f"no runner registered for wheel {wheel!r}",
                )
            )
            continue
        kwargs: dict[str, Any] = dict(
            substrate=substrate,
            scenarios=scenarios,
            out_dir=out_path,
            sign_key=sign_key,
        )
        if wheel == "comparing":
            kwargs["fwer_method"] = fwer_method
            kwargs["fwer_alpha"] = fwer_alpha
        record.phases.append(runner(**kwargs))

    # FWER correction: populate corrected_verdicts on the record itself
    # (schema-2.0 additive). Only when the comparing phase ran AND the
    # proofs directory exists; otherwise the empty defaults remain.
    proofs_dir = out_path / "proofs"
    if "comparing" in enable_phases and proofs_dir.is_dir():
        family = correction_family_from_directory(
            proofs_dir, method=fwer_method, alpha=fwer_alpha
        )
        record.corrected_verdicts = family.verdicts()
        record.multiplicity_correction_method = family.method

    record.completed_at = _now()
    record.sign(sign_key)
    return record


def _select_default_instantiable_scenarios() -> list[type[Scenario]]:
    """Return every registered scenario whose ``__init__`` accepts only
    default arguments — same predicate the generic example runner uses."""
    import inspect

    candidates: list[type[Scenario]] = []
    for cls in SCENARIOS.values():
        try:
            sig = inspect.signature(cls.__init__)
        except (TypeError, ValueError):
            continue
        ok = True
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if param.default is inspect.Parameter.empty:
                ok = False
                break
        if ok:
            candidates.append(cls)
    return candidates


# --- per-phase runners ------------------------------------------------------


def _phase_seeing(*, substrate: SubstrateUnderTest, scenarios: list[type[Scenario]], out_dir: Path, sign_key: bytes) -> CampaignPhase:  # noqa: ARG001
    started = _now()
    # Discovery is meaningful only when the substrate exposes a
    # source-code path — KimeraAdapter does, MockSubstrate doesn't.
    kimera_repo = getattr(substrate, "kimera_repo", "")
    if not kimera_repo:
        return CampaignPhase(
            wheel="seeing",
            started_at=started,
            completed_at=_now(),
            status="skipped",
            error="substrate exposes no kimera_repo attribute — discovery N/A",
        )
    # Lazy import — discovery has heavy transitive deps.
    try:
        from ophamin.seeing.discovery import discover_all
        snapshot = discover_all(Path(kimera_repo))
        out_path = out_dir / "seeing_discovery.json"
        out_path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
        return CampaignPhase(
            wheel="seeing",
            started_at=started,
            completed_at=_now(),
            status="ok",
            artifact_paths=(str(out_path),),
            summary={"n_strata": len(snapshot) if isinstance(snapshot, dict) else 0},
        )
    except Exception as exc:
        return CampaignPhase(
            wheel="seeing",
            started_at=started,
            completed_at=_now(),
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def _phase_measuring(*, substrate: SubstrateUnderTest, scenarios: list[type[Scenario]], out_dir: Path, sign_key: bytes) -> CampaignPhase:
    started = _now()
    proofs_dir = out_dir / "proofs"
    artifact_paths: list[str] = []
    summary: dict[str, Any] = {
        "n_scenarios_attempted": len(scenarios),
        "n_validated": 0,
        "n_refuted": 0,
        "n_inconclusive": 0,
        "n_errored": 0,
    }
    for cls in scenarios:
        try:
            scenario = cls()
            record = scenario.run(substrate)
            tier_value = (
                cls.tier.value if hasattr(cls.tier, "value") else str(cls.tier)
            )
            family_dir = proofs_dir / tier_value / cls.family
            filename = (
                f"{cls.name}_{(record.substrate_git_commit or 'no-commit')[:8]}_"
                f"{record.proof_id[:12]}.json"
            )
            proof_path = family_dir / filename
            proof_dump(record, proof_path)
            artifact_paths.append(str(proof_path))
            outcome = record.verdict.outcome
            key = f"n_{outcome.lower()}"
            summary.setdefault(key, 0)
            summary[key] += 1
        except Exception as exc:  # noqa: BLE001 — surfaced via summary
            summary["n_errored"] += 1
            summary.setdefault("errors", []).append(
                f"{cls.name}: {type(exc).__name__}: {exc}"
            )
    return CampaignPhase(
        wheel="measuring",
        started_at=started,
        completed_at=_now(),
        status="ok" if summary["n_errored"] == 0 else "failed",
        artifact_paths=tuple(artifact_paths),
        summary=summary,
        error=None if summary["n_errored"] == 0 else f"{summary['n_errored']} scenario(s) errored",
    )


def correction_family_from_directory(
    proofs_dir: str | Path,
    *,
    method: str = "holm",
    alpha: float = 0.05,
) -> CorrectionFamily:
    """Walk ``proofs_dir`` recursively + apply multiplicity correction.

    For each loadable proof record, projects to one
    :class:`~ophamin.comparing.fwer.CorrectionInput`:

    * ``claim_id`` = the record's ``proof_id`` (content-addressed,
      stable across re-emission of the same evidence).
    * ``raw_verdict`` = ``record.verdict.outcome``.
    * ``p_value`` = the **minimum** non-``None`` p-value across all
      :class:`~ophamin.measuring.proof.record.PillarEvidence` rows in
      the record. ``None`` if no pillar carries a p-value (the record
      then passes through unchanged but still counts toward family size).

    The minimum-across-pillars projection is Bonferroni-within-record
    — a conservative choice that does not over-state significance
    when a single record reports multiple p-values. Records that fail
    to load are silently skipped (the codec already loud-fails on
    structural issues elsewhere); deduplication by ``proof_id`` makes
    the function idempotent under accidental duplicate writes.

    Args:
        proofs_dir: directory containing signed proof records.
        method: one of ``"holm"`` / ``"bh"`` / ``"none"``.
        alpha: family-wise / FDR threshold.

    Returns:
        A :class:`~ophamin.comparing.fwer.CorrectionFamily`.
    """
    from ophamin.measuring.proof.codec import ProofDecodeError, load

    root = Path(proofs_dir)
    inputs: list[CorrectionInput] = []
    seen_ids: set[str] = set()
    for proof_path in iter_proofs(root):
        try:
            record = load(proof_path)
        except ProofDecodeError:
            continue
        if record.proof_id in seen_ids:
            continue
        seen_ids.add(record.proof_id)
        min_p_value: float | None = None
        for evidence in record.evidence:
            if evidence.p_value is None:
                continue
            if min_p_value is None or float(evidence.p_value) < min_p_value:
                min_p_value = float(evidence.p_value)
        inputs.append(
            CorrectionInput(
                claim_id=record.proof_id,
                raw_verdict=record.verdict.outcome,
                p_value=min_p_value,
            )
        )
    return apply_correction(inputs, method=method, alpha=alpha)


def _phase_comparing(*, substrate: SubstrateUnderTest, scenarios: list[type[Scenario]], out_dir: Path, sign_key: bytes, fwer_method: str = "holm", fwer_alpha: float = 0.05) -> CampaignPhase:  # noqa: ARG001
    started = _now()
    proofs_dir = out_dir / "proofs"
    if not proofs_dir.is_dir():
        return CampaignPhase(
            wheel="comparing",
            started_at=started,
            completed_at=_now(),
            status="skipped",
            error="measuring phase produced no proofs/ subdirectory",
        )
    try:
        from ophamin.comparing.synthesis import summarize_directory
        summary = summarize_directory(proofs_dir)
        # FWER / FDR correction across the campaign's proofs. Always run
        # so the artifact is produced; method="none" if the operator
        # explicitly disabled correction at the run-all CLI level.
        family = correction_family_from_directory(
            proofs_dir, method=fwer_method, alpha=fwer_alpha
        )
        summary_path = out_dir / "SUMMARY.md"
        summary_path.write_text(summary.to_markdown(), encoding="utf-8")
        json_path = out_dir / "SUMMARY.json"
        json_path.write_text(
            json.dumps(
                {
                    "total": summary.total,
                    "by_verdict": summary.by_verdict,
                    "by_family": summary.by_family,
                    "verdict_flips": len(summary.verdict_flips),
                    "fwer": {
                        "method": family.method,
                        "alpha": family.alpha,
                        "family_size": family.family_size,
                        "n_with_p_value": family.n_with_p_value,
                        "n_rejections": family.n_rejections,
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return CampaignPhase(
            wheel="comparing",
            started_at=started,
            completed_at=_now(),
            status="ok",
            artifact_paths=(str(summary_path), str(json_path)),
            summary={
                "n_proofs": summary.total,
                "n_verdict_flips": len(summary.verdict_flips),
                "fwer_method": family.method,
                "fwer_n_rejections": family.n_rejections,
                "fwer_family_size": family.family_size,
            },
        )
    except Exception as exc:
        return CampaignPhase(
            wheel="comparing",
            started_at=started,
            completed_at=_now(),
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def _phase_instrumenting(*, substrate: SubstrateUnderTest, scenarios: list[type[Scenario]], out_dir: Path, sign_key: bytes) -> CampaignPhase:  # noqa: ARG001
    started = _now()
    # The instrumenting phase is meaningful only when the substrate is
    # wrapped in an InstrumentedSubstrate; otherwise there's no
    # per-cycle profile to harvest.
    last_profile_fn = getattr(substrate, "last_profile", None)
    if not callable(last_profile_fn):
        return CampaignPhase(
            wheel="instrumenting",
            started_at=started,
            completed_at=_now(),
            status="skipped",
            error="substrate does not expose last_profile() — wrap in "
                  "InstrumentedSubstrate to enable",
        )
    try:
        profile = last_profile_fn()
        out_path = out_dir / "instrumenting_profile.json"
        out_path.write_text(json.dumps(profile, indent=2, default=str), encoding="utf-8")
        return CampaignPhase(
            wheel="instrumenting",
            started_at=started,
            completed_at=_now(),
            status="ok",
            artifact_paths=(str(out_path),),
            summary=profile if isinstance(profile, dict) else {},
        )
    except Exception as exc:
        return CampaignPhase(
            wheel="instrumenting",
            started_at=started,
            completed_at=_now(),
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def _phase_auditing(*, substrate: SubstrateUnderTest, scenarios: list[type[Scenario]], out_dir: Path, sign_key: bytes) -> CampaignPhase:  # noqa: ARG001
    started = _now()
    kimera_repo = getattr(substrate, "kimera_repo", "")
    if not kimera_repo:
        return CampaignPhase(
            wheel="auditing",
            started_at=started,
            completed_at=_now(),
            status="skipped",
            error="substrate exposes no kimera_repo attribute — audit N/A",
        )
    try:
        from ophamin.auditing import AuditRunner
        runner = AuditRunner()
        record = runner.run(Path(kimera_repo))
        audit_path = out_dir / "auditing_record.json"
        audit_path.write_text(record.to_json(), encoding="utf-8")
        return CampaignPhase(
            wheel="auditing",
            started_at=started,
            completed_at=_now(),
            status="ok",
            artifact_paths=(str(audit_path),),
            summary={
                "n_findings": len(record.findings) if hasattr(record, "findings") else 0,
            },
        )
    except Exception as exc:
        return CampaignPhase(
            wheel="auditing",
            started_at=started,
            completed_at=_now(),
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def _phase_reporting(*, substrate: SubstrateUnderTest, scenarios: list[type[Scenario]], out_dir: Path, sign_key: bytes) -> CampaignPhase:  # noqa: ARG001
    started = _now()
    # Collate every preceding phase's artifact into one rolled-up
    # Markdown report. This is intentionally lightweight — the
    # per-phase artifacts are still on disk for deeper inspection.
    try:
        lines: list[str] = [
            "# Campaign report (rolled-up)",
            "",
            f"_Generated: {_now()}_",
            "",
            "This is the campaign's high-level summary. Per-phase",
            "artifacts are linked below; for deeper inspection see the",
            "individual files in this directory.",
            "",
        ]
        for f in sorted(out_dir.iterdir()):
            if f.is_file() and f.name not in ("REPORT.md", "CAMPAIGN.json"):
                lines.append(f"- `{f.name}`")
            elif f.is_dir():
                count = sum(1 for _ in f.rglob("*") if _.is_file())
                lines.append(f"- `{f.name}/` ({count} file(s))")
        report_path = out_dir / "REPORT.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return CampaignPhase(
            wheel="reporting",
            started_at=started,
            completed_at=_now(),
            status="ok",
            artifact_paths=(str(report_path),),
            summary={"n_artifacts_linked": len(lines) - 8},
        )
    except Exception as exc:
        return CampaignPhase(
            wheel="reporting",
            started_at=started,
            completed_at=_now(),
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


_PHASE_RUNNERS = {
    "seeing": _phase_seeing,
    "measuring": _phase_measuring,
    "comparing": _phase_comparing,
    "instrumenting": _phase_instrumenting,
    "auditing": _phase_auditing,
    "reporting": _phase_reporting,
}


# --- file IO ----------------------------------------------------------------


def dump_campaign(record: CampaignRecord, path: str | Path) -> Path:
    """Write a CampaignRecord to disk as canonical JSON. Returns the path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record.to_dict(), indent=2, default=str), encoding="utf-8")
    return p


def load_campaign(path: str | Path) -> CampaignRecord:
    """Load a CampaignRecord from disk."""
    return CampaignRecord.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


__all__ = [
    "CAMPAIGN_SCHEMA_VERSION",
    "CANONICAL_PHASE_ORDER",
    "SUPPORTED_CAMPAIGN_SCHEMA_VERSIONS",
    "CampaignPhase",
    "CampaignRecord",
    "correction_family_from_directory",
    "dump_campaign",
    "load_campaign",
    "run_campaign",
]
