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
