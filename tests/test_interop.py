"""Tests for the interop wheel — SARIF + JUnit XML exporters.

Each exporter is tested against a synthetic record dict that matches what
the producing wheel emits via to_dict(). The XML / SARIF outputs are
parsed back and the load-bearing fields are pinned.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest

from ophamin.interop import (
    JUnitXMLExporter,
    SARIFExporter,
    audit_record_to_sarif,
    proof_record_to_junit_xml,
)


# --------------------------------------------------------------------------
# Synthetic record builders (same shape as the producing wheels emit)
# --------------------------------------------------------------------------


def _audit_record() -> dict:
    return {
        "audit_id": "f" * 64,
        "schema_version": "audit/1.0",
        "identity": {"ophamin_version": "0.1.0", "captured_at": "2026-05-15T13:00Z"},
        "target": {"target_path": "/tmp/proj", "target_content_hash": "a" * 64},
        "pillars": [
            {
                "pillar_name": "ruff", "tool_name": "ruff", "tool_version": "ruff 0.15.7",
                "status": "ok", "target_path": "/tmp/proj", "finding_count": 2,
                "findings": [
                    {
                        "pillar_name": "ruff", "rule_id": "E501",
                        "severity": "high", "message": "line too long",
                        "path": "/tmp/proj/a.py", "line": 10, "column": 80,
                        "extra": {"url": "https://docs.astral.sh/ruff/E501"},
                    },
                    {
                        "pillar_name": "ruff", "rule_id": "F401",
                        "severity": "medium", "message": "imported but unused",
                        "path": "/tmp/proj/b.py", "line": 1, "column": 1,
                        "extra": {},
                    },
                ],
                "severity_histogram": {"high": 1, "medium": 1},
                "per_file_top10": [["/tmp/proj/a.py", 1], ["/tmp/proj/b.py", 1]],
                "per_rule_top10": [["E501", 1], ["F401", 1]],
                "raw_stdout_bytes": 200, "raw_stderr_bytes": 0,
                "exit_code": 0, "wall_time_s": 0.05, "error_message": "",
            },
            {
                "pillar_name": "vulture", "tool_name": "vulture", "tool_version": "",
                "status": "unavailable", "target_path": "/tmp/proj", "finding_count": 0,
                "findings": [], "severity_histogram": {}, "per_file_top10": [],
                "per_rule_top10": [], "raw_stdout_bytes": 0, "raw_stderr_bytes": 0,
                "exit_code": None, "wall_time_s": 0.0,
                "error_message": "vulture not installed",
            },
        ],
        "summary": {"total_findings": 2, "severity_histogram": {"high": 1, "medium": 1},
                    "findings_per_pillar": {"ruff": 2, "vulture": 0},
                    "top_files": [["/tmp/proj/a.py", 1]],
                    "pillars_run": ["ruff"], "pillars_unavailable": ["vulture"],
                    "pillars_errored": []},
        "reproduction": {"command": "ophamin audit /tmp/proj"},
        "signature": "5" * 64,
    }


def _proof_record(*, outcome: str = "VALIDATED") -> dict:
    return {
        "proof_id": "d" * 64,
        "schema_version": "proof/1.0",
        "identity": {
            "ophamin_version": "0.1.0", "ophamin_git_commit": "abc123",
            "created_at": "2026-05-15T12:00Z",
        },
        "claim": {
            "statement": "On X, Kimera does Y in ≥ 90% of cycles.",
            "operationalization": "fraction of X for which Y",
            "threshold": {"metric": "x_rate", "comparator": ">=",
                          "value": 0.90, "units": "fraction"},
            "h0": "P(Y|X) < 0.90", "h1": "P(Y|X) >= 0.90",
        },
        "preregistration": {
            "config_hash": "c" * 32, "data_hash": "d" * 32,
            "analysis_plan": "stream X", "sweep_grid": {},
            "preregistered_at": "2026-05-15T11:00Z",
        },
        "data": {"substrate_name": "kimera-swm", "substrate_git_commit": "8" * 40,
                 "datasets": []},
        "evidence": [
            {"pillar": "O.x.rate", "statistic_name": "x_rate",
             "statistic_value": 0.974, "library": "statsmodels", "library_version": "0.14",
             "ci_low": 0.962, "ci_high": 0.983, "p_value": None,
             "effect_size": None, "cross_check": "n/a",
             "detail": {}},
            {"pillar": "O.x.distribution", "statistic_name": "x_distribution_median",
             "statistic_value": 21.0, "library": "python-stdlib", "library_version": "3.14",
             "ci_low": None, "ci_high": None, "p_value": None,
             "effect_size": None, "cross_check": "n/a", "detail": {}},
        ],
        "verdict": {
            "outcome": outcome, "observed_value": 0.974,
            "threshold": {"metric": "x_rate", "comparator": ">=",
                          "value": 0.90, "units": "fraction"},
            "reasoning": "rate 0.974 satisfies the threshold",
        },
        "reproduction": {"command": "ophamin scenario test-scenario", "environment": {}},
        "provenance": {},
        "signature": "1" * 64,
    }


# --------------------------------------------------------------------------
# SARIF exporter
# --------------------------------------------------------------------------


def test_audit_record_to_sarif_basic_shape():
    sarif = audit_record_to_sarif(_audit_record())
    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif
    assert "runs" in sarif
    assert isinstance(sarif["runs"], list)


def test_audit_record_to_sarif_emits_one_run_per_pillar_with_findings():
    sarif = audit_record_to_sarif(_audit_record())
    # 2 pillars, both surface as runs (one with findings, one unavailable)
    assert len(sarif["runs"]) == 2
    tool_names = {r["tool"]["driver"]["name"] for r in sarif["runs"]}
    assert tool_names == {"ruff", "vulture"}


def test_audit_record_to_sarif_results_carry_severity_mapping():
    sarif = audit_record_to_sarif(_audit_record())
    ruff_run = next(r for r in sarif["runs"] if r["tool"]["driver"]["name"] == "ruff")
    results = ruff_run["results"]
    assert len(results) == 2
    e501 = next(r for r in results if r["ruleId"] == "E501")
    f401 = next(r for r in results if r["ruleId"] == "F401")
    # high -> error
    assert e501["level"] == "error"
    # medium -> warning
    assert f401["level"] == "warning"
    # security-severity numeric carried
    assert "security-severity" in e501["properties"]


def test_audit_record_to_sarif_preserves_ophamin_signature():
    record = _audit_record()
    sarif = audit_record_to_sarif(record)
    assert sarif["properties"]["ophamin_signature"] == record["signature"]
    assert sarif["properties"]["ophamin_audit_id"] == record["audit_id"]
    # signature also lands in each run's invocations
    for run in sarif["runs"]:
        assert run["invocations"][0]["properties"]["ophamin_signature"] == record["signature"]


def test_audit_record_to_sarif_unavailable_pillar_marked_unsuccessful():
    sarif = audit_record_to_sarif(_audit_record())
    vulture = next(r for r in sarif["runs"] if r["tool"]["driver"]["name"] == "vulture")
    assert vulture["invocations"][0]["executionSuccessful"] is False
    assert vulture["invocations"][0]["properties"]["ophamin_status"] == "unavailable"
    assert "ophamin_error_message" in vulture["invocations"][0]["properties"]
    # no results since the tool didn't run
    assert vulture["results"] == []


def test_audit_record_to_sarif_rejects_non_audit_input():
    with pytest.raises(ValueError, match="does not look like an Audit Record"):
        audit_record_to_sarif({"foo": "bar"})


def test_audit_record_to_sarif_rejects_non_dict():
    with pytest.raises(TypeError):
        audit_record_to_sarif("not a dict")  # type: ignore[arg-type]


def test_sarif_exporter_writes_sarif_file(tmp_path):
    out = SARIFExporter().export(_audit_record(), tmp_path / "audit")
    assert out == tmp_path / "audit.sarif"
    parsed = json.loads(out.read_text())
    assert parsed["version"] == "2.1.0"


def test_sarif_exporter_respects_existing_extension(tmp_path):
    out = SARIFExporter().export(_audit_record(), tmp_path / "audit.sarif")
    assert out == tmp_path / "audit.sarif"
    assert out.exists()


# --------------------------------------------------------------------------
# JUnit XML exporter
# --------------------------------------------------------------------------


def test_proof_record_to_junit_xml_validated_passes():
    root = proof_record_to_junit_xml(_proof_record(outcome="VALIDATED"))
    assert root.tag == "testsuites"
    suite = root.find("testsuite")
    assert suite is not None
    # primary testcase is the threshold metric
    cases = suite.findall("testcase")
    assert len(cases) >= 1
    primary = next(c for c in cases if c.get("name") == "x_rate")
    # VALIDATED -> no failure/skipped/error child
    assert primary.find("failure") is None
    assert primary.find("skipped") is None
    assert primary.find("error") is None


def test_proof_record_to_junit_xml_refuted_fails():
    root = proof_record_to_junit_xml(_proof_record(outcome="REFUTED"))
    suite = root.find("testsuite")
    primary = next(c for c in suite.findall("testcase") if c.get("name") == "x_rate")
    failure = primary.find("failure")
    assert failure is not None
    assert failure.get("type") == "ophamin.REFUTED"
    assert "does NOT satisfy" in failure.get("message", "")
    # testsuite counters
    assert suite.get("failures") == "1"


def test_proof_record_to_junit_xml_inconclusive_skipped():
    root = proof_record_to_junit_xml(_proof_record(outcome="INCONCLUSIVE"))
    suite = root.find("testsuite")
    primary = next(c for c in suite.findall("testcase") if c.get("name") == "x_rate")
    skipped = primary.find("skipped")
    assert skipped is not None
    assert skipped.get("type") == "ophamin.INCONCLUSIVE"
    assert suite.get("skipped") == "1"
    assert suite.get("failures") == "0"


def test_proof_record_to_junit_xml_emits_one_case_per_evidence_statistic():
    root = proof_record_to_junit_xml(_proof_record(outcome="VALIDATED"))
    suite = root.find("testsuite")
    cases = suite.findall("testcase")
    # 1 primary (x_rate) + 1 evidence (x_distribution_median) = 2
    assert len(cases) == 2
    names = {c.get("name") for c in cases}
    assert names == {"x_rate", "x_distribution_median"}


def test_proof_record_to_junit_xml_properties_include_provenance():
    root = proof_record_to_junit_xml(_proof_record())
    suite = root.find("testsuite")
    props = {p.get("name"): p.get("value") for p in suite.find("properties")}
    assert props["ophamin_signature"] == "1" * 64
    assert props["ophamin_proof_id"] == "d" * 64
    assert props["claim_statement"].startswith("On X")


def test_proof_record_to_junit_xml_scenario_name_extracted_from_command():
    root = proof_record_to_junit_xml(_proof_record())
    suite = root.find("testsuite")
    assert suite.get("name") == "test-scenario"


def test_proof_record_to_junit_xml_rejects_non_proof_input():
    with pytest.raises(ValueError, match="does not look like an Empirical Proof Record"):
        proof_record_to_junit_xml({"foo": "bar"})


def test_proof_record_to_junit_xml_rejects_non_dict():
    with pytest.raises(TypeError):
        proof_record_to_junit_xml(["a", "list"])  # type: ignore[arg-type]


def test_junit_exporter_writes_xml_file(tmp_path):
    out = JUnitXMLExporter().export(_proof_record(), tmp_path / "proof")
    assert out == tmp_path / "proof.xml"
    # parsed back cleanly
    tree = ET.parse(out)
    assert tree.getroot().tag == "testsuites"


def test_junit_exporter_respects_junit_extension(tmp_path):
    out = JUnitXMLExporter().export(_proof_record(), tmp_path / "proof.junit")
    assert out == tmp_path / "proof.junit"


# --------------------------------------------------------------------------
# Cross-format invariants
# --------------------------------------------------------------------------


def test_both_exporters_preserve_signatures():
    """Both exporters MUST land the original Ophamin signature somewhere
    discoverable so downstream tools can trace back."""
    audit_sarif = audit_record_to_sarif(_audit_record())
    proof_junit = proof_record_to_junit_xml(_proof_record())
    # SARIF: top-level properties.ophamin_signature
    assert audit_sarif["properties"]["ophamin_signature"]
    # JUnit: testsuite properties
    suite = proof_junit.find("testsuite")
    props = {p.get("name"): p.get("value") for p in suite.find("properties")}
    assert props["ophamin_signature"]


# --------------------------------------------------------------------------
# MLflow exporter
# --------------------------------------------------------------------------


@pytest.fixture
def mlflow_tracking_dir(tmp_path, monkeypatch):
    """Point MLflow at a tmp_path so tests don't pollute mlruns/."""
    tracking_dir = tmp_path / "mlruns"
    tracking_dir.mkdir()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file:{tracking_dir}")
    return tracking_dir


def test_mlflow_export_proof_record_creates_run(mlflow_tracking_dir):
    from ophamin.interop import export_proof_record
    run_id = export_proof_record(
        _proof_record(outcome="VALIDATED"),
        experiment_name="test-ophamin-proof",
    )
    assert isinstance(run_id, str)
    assert len(run_id) > 0

    import mlflow
    run = mlflow.get_run(run_id)
    # tags carry the outcome + signature
    assert run.data.tags["ophamin.kind"] == "proof"
    assert run.data.tags["ophamin.outcome"] == "VALIDATED"
    assert run.data.tags["ophamin.signature"] == "1" * 64
    # params carry the threshold
    assert run.data.params["threshold_metric"] == "x_rate"
    assert run.data.params["threshold_comparator"] == ">="
    # metrics carry the observed value
    assert "observed_value" in run.data.metrics
    assert run.data.metrics["observed_value"] == pytest.approx(0.974)
    # CI metrics for the primary statistic
    assert "x_rate" in run.data.metrics
    assert "x_rate_ci_low" in run.data.metrics
    assert "x_rate_ci_high" in run.data.metrics


def test_mlflow_export_audit_record_creates_run(mlflow_tracking_dir):
    from ophamin.interop import export_audit_record
    run_id = export_audit_record(
        _audit_record(),
        experiment_name="test-ophamin-audit",
    )
    assert isinstance(run_id, str)

    import mlflow
    run = mlflow.get_run(run_id)
    assert run.data.tags["ophamin.kind"] == "audit"
    assert run.data.tags["ophamin.target"] == "/tmp/proj"
    # per-pillar metrics
    assert run.data.metrics["total_findings"] == pytest.approx(2)
    assert run.data.metrics["findings_ruff"] == pytest.approx(2)
    assert run.data.metrics["findings_vulture"] == pytest.approx(0)
    # severity metrics
    assert run.data.metrics["severity_high"] == pytest.approx(1)
    assert run.data.metrics["severity_medium"] == pytest.approx(1)


def test_mlflow_export_refuted_proof_lands_correct_outcome(mlflow_tracking_dir):
    from ophamin.interop import export_proof_record
    run_id = export_proof_record(
        _proof_record(outcome="REFUTED"),
        experiment_name="test-ophamin-proof",
    )
    import mlflow
    run = mlflow.get_run(run_id)
    assert run.data.tags["ophamin.outcome"] == "REFUTED"


def test_mlflow_exporter_classifies_proof_vs_audit():
    from ophamin.interop import MLflowExporter
    assert MLflowExporter._classify(_proof_record()) == "proof"
    assert MLflowExporter._classify(_audit_record()) == "audit"
    with pytest.raises(ValueError, match="does not look like"):
        MLflowExporter._classify({"foo": "bar"})


def test_mlflow_export_rejects_non_proof_input(mlflow_tracking_dir):
    from ophamin.interop import export_proof_record
    with pytest.raises(ValueError, match="does not look like an Empirical Proof Record"):
        export_proof_record({"foo": "bar"})


def test_mlflow_export_rejects_non_audit_input(mlflow_tracking_dir):
    from ophamin.interop import export_audit_record
    with pytest.raises(ValueError, match="does not look like an Audit Record"):
        export_audit_record({"foo": "bar"})


def test_mlflow_exporter_class_dispatches_correctly(mlflow_tracking_dir):
    from ophamin.interop import MLflowExporter
    exp = MLflowExporter(experiment_name="test-dispatch")
    proof_run_id = exp.export(_proof_record())
    audit_run_id = exp.export(_audit_record())
    import mlflow
    proof_run = mlflow.get_run(proof_run_id)
    audit_run = mlflow.get_run(audit_run_id)
    assert proof_run.data.tags["ophamin.kind"] == "proof"
    assert audit_run.data.tags["ophamin.kind"] == "audit"


def test_mlflow_safe_metric_key_replaces_disallowed_chars():
    from ophamin.interop.mlflow_export import _safe_metric_key
    # parens / colon / @ → underscore
    assert _safe_metric_key("O.x.rate(95%)") == "O.x.rate_95__"
    assert _safe_metric_key("a:b@c") == "a_b_c"
    # allowed chars stay
    assert _safe_metric_key("a-b_c.d") == "a-b_c.d"


def test_mlflow_export_truncates_long_param_values(mlflow_tracking_dir):
    """Claims with absurdly long statements MUST still log without raising
    (MLflow's per-param length limit is ~6000 chars)."""
    from ophamin.interop import export_proof_record
    record = _proof_record()
    record["claim"]["statement"] = "Very long claim. " * 1000  # ~17000 chars
    # should NOT raise
    run_id = export_proof_record(record, experiment_name="test-truncation")
    assert isinstance(run_id, str)


# --------------------------------------------------------------------------
# CycloneDX SBOM exporter
# --------------------------------------------------------------------------


def test_cyclonedx_sbom_from_env_basic_shape():
    from ophamin.interop import build_cyclonedx_sbom_from_env
    sbom = build_cyclonedx_sbom_from_env()
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["serialNumber"].startswith("urn:uuid:")
    assert sbom["metadata"]["component"]["name"] == "ophamin"
    assert isinstance(sbom["components"], list)
    # the venv has actual packages; at least our deps should be there
    names = {c["name"].lower() for c in sbom["components"]}
    assert "numpy" in names or "scipy" in names  # at least one dep visible


def test_cyclonedx_sbom_from_env_components_are_deterministic_ordered():
    from ophamin.interop import build_cyclonedx_sbom_from_env
    sbom = build_cyclonedx_sbom_from_env()
    names = [c["name"].lower() for c in sbom["components"]]
    assert names == sorted(names)


def test_cyclonedx_sbom_from_env_each_component_has_purl():
    from ophamin.interop import build_cyclonedx_sbom_from_env
    sbom = build_cyclonedx_sbom_from_env()
    for c in sbom["components"]:
        assert c["purl"].startswith("pkg:pypi/")
        assert c["bom-ref"] == c["purl"]
        assert c["type"] == "library"


def test_cyclonedx_sbom_from_record_uses_environment_dict():
    from ophamin.interop import build_cyclonedx_sbom_from_record
    record = _proof_record()
    record["reproduction"]["environment"] = {
        "numpy": "1.26.0",
        "scipy": "1.14.0",
        "statsmodels": "0.14.0",
    }
    sbom = build_cyclonedx_sbom_from_record(record)
    assert sbom["bomFormat"] == "CycloneDX"
    assert len(sbom["components"]) == 3
    names = {c["name"].lower() for c in sbom["components"]}
    assert names == {"numpy", "scipy", "statsmodels"}
    # the application component references the record's proof_id
    proof_id = record["proof_id"]
    assert proof_id[:12] in sbom["metadata"]["component"]["version"]


def test_cyclonedx_sbom_from_record_rejects_empty_environment():
    from ophamin.interop import build_cyclonedx_sbom_from_record
    record = _proof_record()
    record["reproduction"] = {"command": "ophamin x"}  # no environment
    with pytest.raises(ValueError, match="environment is missing"):
        build_cyclonedx_sbom_from_record(record)


def test_cyclonedx_sbom_from_record_rejects_non_dict():
    from ophamin.interop import build_cyclonedx_sbom_from_record
    with pytest.raises(TypeError):
        build_cyclonedx_sbom_from_record("not a dict")  # type: ignore[arg-type]


def test_cyclonedx_exporter_writes_cdx_json(tmp_path):
    from ophamin.interop import CycloneDXExporter
    out = CycloneDXExporter().export_env(tmp_path / "sbom")
    assert out.suffix == ".json"
    assert ".cdx" in out.name or out.name.endswith(".json")
    parsed = json.loads(out.read_text())
    assert parsed["bomFormat"] == "CycloneDX"


def test_cyclonedx_exporter_preserves_explicit_json_extension(tmp_path):
    from ophamin.interop import CycloneDXExporter
    out = CycloneDXExporter().export_env(tmp_path / "sbom.json")
    assert out == tmp_path / "sbom.json"


def test_cyclonedx_purl_handles_underscore_to_hyphen():
    from ophamin.interop.cyclonedx import _pypi_purl
    # pypi canonical names are lowercase + hyphen, even when import-name has _
    assert _pypi_purl("scikit_learn", "1.3.0") == "pkg:pypi/scikit-learn@1.3.0"
    assert _pypi_purl("NumPy", "1.26.0") == "pkg:pypi/numpy@1.26.0"
