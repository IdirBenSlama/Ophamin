"""MLflow exporter — Empirical Proof Records + Audit Records → MLflow runs.

MLflow is already an Ophamin dependency (the provenance lineage store uses
it). The interop exporter turns every signed record into a browsable
MLflow run, so any MLflow UI deployment immediately becomes an Ophamin
experiment tracker — search by tags, plot metrics across runs, compare
across substrate commits.

Proof record → MLflow run mapping:
  run.tags:
    ophamin.kind                   = "proof"
    ophamin.outcome                = VALIDATED / REFUTED / INCONCLUSIVE
    ophamin.substrate_name         = substrate name
    ophamin.substrate_git_commit   = substrate commit (full)
    ophamin.claim_h0 / h1          = hypothesis text
    ophamin.signature              = full signature
    ophamin.schema_version
  run.params:
    threshold.metric / comparator / value / units
    n_evidence / n_datasets
    operationalization, reproduction_command
  run.metrics:
    observed_value                 (the verdict's observed value)
    <each evidence statistic_name> = statistic_value
    <each evidence>_ci_low / ci_high (when present)
  run.artifacts:
    the full proof record JSON, attached to the run

Audit record → MLflow run mapping:
  run.tags:
    ophamin.kind                   = "audit"
    ophamin.target                 = the audited path
    ophamin.signature
  run.params:
    target_path, target_content_hash, n_pillars
    pillars_run, pillars_unavailable, pillars_errored (comma-joined)
  run.metrics:
    total_findings
    <each pillar>_findings
    <each severity>_count
  run.artifacts:
    the full audit record JSON

The exporter is safe against missing MLflow (raises ImportError loudly) and
tolerant of optional fields (a record without CI values doesn't crash).

The MLflow tracking URI defaults to ``file:./mlruns`` (the standard local
tracking dir); ``--tracking-uri`` overrides for remote MLflow servers.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

# MLflow is a hard dependency of ophamin (see pyproject.toml), but the
# import is lazy here so unit tests can stub it cleanly.
_MLFLOW_IMPORT_ERROR: ImportError | None = None
mlflow: Any  # rebound to module on successful import, else None
try:
    import mlflow as _mlflow_mod
    mlflow = _mlflow_mod
except ImportError as _exc:
    mlflow = None
    _MLFLOW_IMPORT_ERROR = _exc


DEFAULT_PROOF_EXPERIMENT = "ophamin-proof"
DEFAULT_AUDIT_EXPERIMENT = "ophamin-audit"
DEFAULT_TRACKING_URI = ""  # empty means "use mlflow's default (file:./mlruns)"

# MLflow parameter values must be strings, ≤ 6000 chars each (since MLflow 2.4)
_PARAM_MAX_LEN = 5900
# MLflow tag values: ≤ 5000 chars
_TAG_MAX_LEN = 4900


def _ensure_mlflow() -> None:
    """Raise loudly if MLflow couldn't be imported."""
    if mlflow is None:
        raise ImportError(
            f"MLflow exporter requires the ``mlflow`` package; import failed: "
            f"{_MLFLOW_IMPORT_ERROR}"
        ) from _MLFLOW_IMPORT_ERROR


def _truncate(value: Any, limit: int) -> str:
    """Stringify + truncate to a length limit (with an ellipsis marker)."""
    text = str(value) if value is not None else ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _safe_metric_key(name: str) -> str:
    """MLflow metric keys allow alphanumerics + _-./ + space; we replace the
    rest with underscores to keep keys forgiving of pillar / statistic names
    that include parentheses / slashes / colons / etc."""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                  "0123456789_-./ ")
    return "".join(c if c in allowed else "_" for c in name)


def export_proof_record(
    record: dict[str, Any],
    *,
    tracking_uri: str | None = None,
    experiment_name: str = DEFAULT_PROOF_EXPERIMENT,
    run_name: str | None = None,
) -> str:
    """Create an MLflow run from a proof record. Returns the run_id."""
    _ensure_mlflow()
    if not isinstance(record, dict):
        raise TypeError("export_proof_record expects a dict")
    if "claim" not in record or "verdict" not in record:
        raise ValueError(
            "input does not look like an Empirical Proof Record "
            "(missing 'claim' and/or 'verdict')"
        )

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    claim = record.get("claim", {})
    threshold = claim.get("threshold", {})
    verdict = record.get("verdict", {})
    data = record.get("data", {})
    reproduction = record.get("reproduction", {})
    preregistration = record.get("preregistration", {})
    evidence = record.get("evidence", []) or []
    datasets = data.get("datasets", []) or []

    metric = threshold.get("metric", "primary")
    short_proof_id = (record.get("proof_id", "") or "")[:12]
    final_run_name = run_name or f"{metric}_{short_proof_id}"

    with mlflow.start_run(run_name=final_run_name) as run:
        # tags
        mlflow.set_tags({
            "ophamin.kind": "proof",
            "ophamin.outcome": str(verdict.get("outcome", "")),
            "ophamin.substrate_name": str(data.get("substrate_name", "")),
            "ophamin.substrate_git_commit": _truncate(
                data.get("substrate_git_commit", ""), _TAG_MAX_LEN
            ),
            "ophamin.schema_version": str(record.get("schema_version", "")),
            "ophamin.proof_id": _truncate(record.get("proof_id", ""), _TAG_MAX_LEN),
            "ophamin.signature": _truncate(record.get("signature", ""), _TAG_MAX_LEN),
            "ophamin.claim_h0": _truncate(claim.get("h0", ""), _TAG_MAX_LEN),
            "ophamin.claim_h1": _truncate(claim.get("h1", ""), _TAG_MAX_LEN),
        })

        # params
        mlflow.log_params({
            "threshold_metric": _truncate(threshold.get("metric", ""), _PARAM_MAX_LEN),
            "threshold_comparator": _truncate(threshold.get("comparator", ""), _PARAM_MAX_LEN),
            "threshold_value": _truncate(threshold.get("value", ""), _PARAM_MAX_LEN),
            "threshold_units": _truncate(threshold.get("units", ""), _PARAM_MAX_LEN),
            "operationalization": _truncate(claim.get("operationalization", ""), _PARAM_MAX_LEN),
            "claim_statement": _truncate(claim.get("statement", ""), _PARAM_MAX_LEN),
            "reproduction_command": _truncate(reproduction.get("command", ""), _PARAM_MAX_LEN),
            "preregistered_at": _truncate(preregistration.get("preregistered_at", ""), _PARAM_MAX_LEN),
            "n_evidence": str(len(evidence)),
            "n_datasets": str(len(datasets)),
        })

        # metrics: the verdict's observed value, plus every evidence statistic
        try:
            mlflow.log_metric("observed_value", float(verdict.get("observed_value", 0.0)))
        except (TypeError, ValueError):
            pass
        for ev in evidence:
            stat = _safe_metric_key(str(ev.get("statistic_name", "stat")))
            try:
                mlflow.log_metric(stat, float(ev.get("statistic_value", 0.0)))
            except (TypeError, ValueError):
                continue
            if ev.get("ci_low") is not None:
                try:
                    mlflow.log_metric(f"{stat}_ci_low", float(ev["ci_low"]))
                except (TypeError, ValueError):
                    pass
            if ev.get("ci_high") is not None:
                try:
                    mlflow.log_metric(f"{stat}_ci_high", float(ev["ci_high"]))
                except (TypeError, ValueError):
                    pass

        # artifact: the full proof record as a single JSON file
        _log_record_artifact(record, name=f"proof_record_{short_proof_id}.json")
        return str(run.info.run_id)


def export_audit_record(
    record: dict[str, Any],
    *,
    tracking_uri: str | None = None,
    experiment_name: str = DEFAULT_AUDIT_EXPERIMENT,
    run_name: str | None = None,
) -> str:
    """Create an MLflow run from an audit record. Returns the run_id."""
    _ensure_mlflow()
    if not isinstance(record, dict):
        raise TypeError("export_audit_record expects a dict")
    if "audit_id" not in record or "pillars" not in record:
        raise ValueError(
            "input does not look like an Audit Record "
            "(missing 'audit_id' and/or 'pillars')"
        )

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    target = record.get("target", {})
    pillars = record.get("pillars", []) or []
    summary = record.get("summary", {})
    short_audit_id = (record.get("audit_id", "") or "")[:12]
    target_path = str(target.get("target_path", ""))
    final_run_name = run_name or f"audit_{Path(target_path).name}_{short_audit_id}"

    with mlflow.start_run(run_name=final_run_name) as run:
        # tags
        mlflow.set_tags({
            "ophamin.kind": "audit",
            "ophamin.target": _truncate(target_path, _TAG_MAX_LEN),
            "ophamin.audit_id": _truncate(record.get("audit_id", ""), _TAG_MAX_LEN),
            "ophamin.signature": _truncate(record.get("signature", ""), _TAG_MAX_LEN),
            "ophamin.schema_version": str(record.get("schema_version", "")),
        })

        # params
        mlflow.log_params({
            "target_path": _truncate(target_path, _PARAM_MAX_LEN),
            "target_content_hash": _truncate(
                target.get("target_content_hash", ""), _PARAM_MAX_LEN
            ),
            "n_pillars": str(len(pillars)),
            "pillars_run": ",".join(summary.get("pillars_run", []))[:_PARAM_MAX_LEN],
            "pillars_unavailable": ",".join(summary.get("pillars_unavailable", []))[
                :_PARAM_MAX_LEN
            ],
            "pillars_errored": ",".join(summary.get("pillars_errored", []))[:_PARAM_MAX_LEN],
        })

        # metrics
        mlflow.log_metric("total_findings", float(summary.get("total_findings", 0)))
        for pillar_name, count in (summary.get("findings_per_pillar") or {}).items():
            try:
                mlflow.log_metric(
                    f"findings_{_safe_metric_key(pillar_name)}", float(count)
                )
            except (TypeError, ValueError):
                continue
        for sev, count in (summary.get("severity_histogram") or {}).items():
            try:
                mlflow.log_metric(f"severity_{_safe_metric_key(sev)}", float(count))
            except (TypeError, ValueError):
                continue

        # artifact: the full audit record
        _log_record_artifact(record, name=f"audit_record_{short_audit_id}.json")
        return str(run.info.run_id)


def _log_record_artifact(record: dict[str, Any], *, name: str) -> None:
    """Write the record JSON to a temp file and log it as an MLflow artifact."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / name
        path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        mlflow.log_artifact(str(path))


class MLflowExporter:
    """Wrap the export functions in a class for symmetric CLI dispatch."""

    def __init__(
        self,
        *,
        tracking_uri: str | None = None,
        experiment_name: str | None = None,
    ) -> None:
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name

    def export(self, record: dict[str, Any], *, kind: str | None = None) -> str:
        """Export a proof or audit record. ``kind`` is auto-detected if None.

        Returns the MLflow run_id.
        """
        if kind is None:
            kind = self._classify(record)
        if kind == "proof":
            return export_proof_record(
                record,
                tracking_uri=self.tracking_uri,
                experiment_name=self.experiment_name or DEFAULT_PROOF_EXPERIMENT,
            )
        if kind == "audit":
            return export_audit_record(
                record,
                tracking_uri=self.tracking_uri,
                experiment_name=self.experiment_name or DEFAULT_AUDIT_EXPERIMENT,
            )
        raise ValueError(
            f"unknown record kind: {kind!r}; expected 'proof' or 'audit'"
        )

    @staticmethod
    def _classify(record: dict[str, Any]) -> str:
        if "audit_id" in record and "pillars" in record:
            return "audit"
        if "claim" in record and "verdict" in record:
            return "proof"
        raise ValueError(
            "record does not look like a proof (claim+verdict) or audit "
            "(audit_id+pillars)"
        )
