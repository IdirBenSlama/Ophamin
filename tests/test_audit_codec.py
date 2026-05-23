"""Hardening tests for the AuditRecord codec module (Move H).

Mirrors :file:`tests/test_proof_codec.py` for the audit-record path.
Covers every typed-error path + the directory-walking helpers + the
CLI surface end-to-end.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ophamin import __version__
from ophamin.auditing.audit_record import (
    AuditRecord,
    AuditSummary,
)
from ophamin.auditing.base import Finding, FindingSeverity, PillarResult
from ophamin.auditing.codec import (
    AuditCodecError,
    AuditDecodeError,
    AuditListEntry,
    AuditSchemaVersionMismatchError,
    AuditSignatureError,
    AuditValidationReport,
    dump,
    ingest,
    iter_audits,
    list_audits,
    load,
    validate,
    validate as _validate_unused,  # noqa: F401 — guards alias presence
    verify_signature,
)


_TEST_KEY = b"audit-codec-test-key"


def _make_pillar_result(name: str = "test_pillar", n_findings: int = 0) -> PillarResult:
    findings: tuple[Finding, ...] = tuple(
        Finding(
            pillar_name=name,
            rule_id=f"R{i}",
            severity=FindingSeverity.LOW,
            message=f"finding {i}",
            path=f"file_{i}.py",
            line=i + 1,
            column=1,
        )
        for i in range(n_findings)
    )
    return PillarResult(
        pillar_name=name,
        tool_name="dummy-tool",
        tool_version="1.0",
        status="ok",
        target_path="/tmp/dummy",
        findings=findings,
        wall_time_s=0.01,
    )


def _make_record(n_findings: int = 2) -> AuditRecord:
    pillars = [_make_pillar_result("pillar_a", n_findings)]
    record = AuditRecord(
        target_path="/tmp/dummy/audit/target",
        target_content_hash="deadbeef" * 8,
        pillars=pillars,
        summary=AuditSummary.from_pillar_results(pillars),
        ophamin_version=__version__,
        ophamin_git_commit="cafebabe" * 5,
        captured_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        reproduction_command="pytest tests/test_audit_codec.py",
    )
    return record


@pytest.fixture
def signed_audit(tmp_path) -> Path:
    record = _make_record().sign(_TEST_KEY)
    return dump(record, tmp_path / "audit_signed.json")


@pytest.fixture
def unsigned_audit(tmp_path) -> Path:
    record = _make_record()
    return dump(record, tmp_path / "audit_unsigned.json")


# --- dump / load round-trip ------------------------------------------------


def test_dump_creates_parent_directories(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    out = tmp_path / "deeper" / "audit.json"
    path = dump(record, out)
    assert path == out
    assert out.exists()


def test_dump_load_round_trip(tmp_path):
    record = _make_record(n_findings=3).sign(_TEST_KEY)
    path = dump(record, tmp_path / "rt.json")
    loaded = load(path)
    assert loaded.audit_id == record.audit_id
    assert loaded.signature == record.signature
    assert loaded.verify_signature(_TEST_KEY)
    assert loaded.summary.total_findings == 3


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(AuditDecodeError):
        load(tmp_path / "missing.json")


def test_load_malformed_json_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{{{ not json", encoding="utf-8")
    with pytest.raises(AuditDecodeError):
        load(p)


def test_load_missing_required_keys_raises(tmp_path):
    p = tmp_path / "partial.json"
    p.write_text(json.dumps({"audit_id": "abc"}), encoding="utf-8")
    with pytest.raises(AuditDecodeError):
        load(p)


# --- signature verification ------------------------------------------------


def test_verify_signature_correct_key(signed_audit):
    assert verify_signature(signed_audit, _TEST_KEY) is True


def test_verify_signature_wrong_key(signed_audit):
    assert verify_signature(signed_audit, b"wrong-key") is False


def test_verify_signature_unsigned_returns_false(unsigned_audit):
    assert verify_signature(unsigned_audit, _TEST_KEY) is False


# --- validate report -------------------------------------------------------


def test_validate_happy_path(signed_audit):
    report = validate(signed_audit, key=_TEST_KEY)
    assert isinstance(report, AuditValidationReport)
    assert report.record_ok is True
    assert report.signature_ok is True
    assert report.all_ok is True


def test_validate_no_key_skips_signature(signed_audit):
    report = validate(signed_audit)
    assert report.signature_ok is None
    assert report.all_ok is True


def test_validate_decode_error_surfaces_in_problems(tmp_path):
    p = tmp_path / "garbage.json"
    p.write_text("not json", encoding="utf-8")
    report = validate(p)
    assert report.record_ok is False
    assert any("could not read" in prob for prob in report.record_problems)


def test_validate_report_is_frozen():
    r = AuditValidationReport(
        record_ok=True, record_problems=(), signature_ok=None
    )
    with pytest.raises(Exception):
        r.record_ok = False  # type: ignore[misc]


def test_validate_all_ok_false_when_signature_wrong(signed_audit):
    report = validate(signed_audit, key=b"different-key")
    assert report.signature_ok is False
    assert report.all_ok is False


# --- ingest ---------------------------------------------------------------


def test_ingest_happy_path(signed_audit):
    record = ingest(signed_audit)
    assert isinstance(record, AuditRecord)


def test_ingest_strict_signature_correct_key(signed_audit):
    record = ingest(signed_audit, key=_TEST_KEY, strict_signature=True)
    assert isinstance(record, AuditRecord)


def test_ingest_strict_signature_without_key_raises(signed_audit):
    with pytest.raises(AuditSignatureError):
        ingest(signed_audit, strict_signature=True)


def test_ingest_strict_signature_wrong_key_raises(signed_audit):
    with pytest.raises(AuditSignatureError):
        ingest(signed_audit, key=b"wrong-key", strict_signature=True)


def test_ingest_wrong_schema_version_raises(signed_audit):
    with pytest.raises(AuditSchemaVersionMismatchError):
        ingest(signed_audit, require_schema_version="audit/99.0")


def test_ingest_allow_any_schema_version(signed_audit):
    record = ingest(signed_audit, require_schema_version=None)
    assert isinstance(record, AuditRecord)


def test_ingest_decode_error_propagates(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("garbage", encoding="utf-8")
    with pytest.raises(AuditCodecError):
        ingest(p)


# --- iter / list / shipped audits -----------------------------------------


def test_iter_audits_sorted(tmp_path):
    for n in ("b.json", "a.json", "c.json"):
        (tmp_path / n).write_text("{}", encoding="utf-8")
    paths = [p.name for p in iter_audits(tmp_path)]
    assert paths == ["a.json", "b.json", "c.json"]


def test_list_audits_returns_entries(tmp_path):
    record = _make_record(n_findings=4).sign(_TEST_KEY)
    dump(record, tmp_path / "audit.json")
    entries = list_audits(tmp_path, key=_TEST_KEY)
    assert len(entries) == 1
    e = entries[0]
    assert isinstance(e, AuditListEntry)
    assert e.total_findings == 4
    assert e.signature_ok is True


def test_list_audits_continues_past_broken_file(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "good.json")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    entries = list_audits(tmp_path)
    assert len(entries) == 2
    by_name = {e.path.name: e for e in entries}
    assert by_name["good.json"].error is None
    assert by_name["broken.json"].error is not None


def test_list_audits_signature_ok_none_when_no_key(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "audit.json")
    entries = list_audits(tmp_path)
    assert entries[0].signature_ok is None


def test_list_audits_empty_directory(tmp_path):
    assert list_audits(tmp_path) == ()


def test_shipped_audits_load_cleanly():
    """All 2 shipped audits in `audits/` must load cleanly via the codec."""
    audits_dir = Path(__file__).parent.parent / "audits"
    if not audits_dir.exists():
        pytest.skip("audits/ directory not present in this checkout")
    failures = []
    for p in iter_audits(audits_dir):
        try:
            load(p)
        except AuditDecodeError as exc:
            failures.append((p.name, str(exc)))
    assert not failures, f"{len(failures)} shipped audits failed to load: {failures}"


# --- structural problems ---------------------------------------------------


def test_structural_problem_pillars_summary_mismatch(tmp_path):
    """If the pillars list and summary's pillar names diverge, validate
    reports the inconsistency."""
    record = _make_record()
    record.summary = AuditSummary(
        total_findings=0,
        severity_histogram={},
        findings_per_pillar={},
        top_files=[],
        pillars_run=("ghost_pillar",),  # doesn't match the actual pillar
        pillars_unavailable=(),
        pillars_errored=(),
    )
    record.sign(_TEST_KEY)
    path = dump(record, tmp_path / "mismatched.json")
    report = validate(path)
    assert report.record_ok is False
    assert any("pillar" in prob for prob in report.record_problems)


# --- CLI smoke tests -------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "audit-record", *args],
        capture_output=True, text=True,
    )


def test_cli_audit_record_show(signed_audit):
    result = _run_cli("show", str(signed_audit))
    assert result.returncode == 0
    assert "# Ophamin Audit Record" in result.stdout


def test_cli_audit_record_verify_correct_key(signed_audit):
    result = _run_cli("verify", str(signed_audit), "--key=audit-codec-test-key")
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_audit_record_verify_wrong_key(signed_audit):
    result = _run_cli("verify", str(signed_audit), "--key=wrong-key")
    assert result.returncode == 1


def test_cli_audit_record_validate(signed_audit):
    result = _run_cli(
        "validate", str(signed_audit), "--with-signature",
        "--key=audit-codec-test-key",
    )
    assert result.returncode == 0
    assert "all_ok:         True" in result.stdout


def test_cli_audit_record_ingest_strict(signed_audit):
    result = _run_cli(
        "ingest", str(signed_audit), "--strict-signature",
        "--key=audit-codec-test-key",
    )
    assert result.returncode == 0
    assert "OK: ingested" in result.stdout


def test_cli_audit_record_ingest_bad_signature_fails(signed_audit):
    result = _run_cli(
        "ingest", str(signed_audit), "--strict-signature", "--key=wrong-key"
    )
    assert result.returncode == 1


def test_cli_audit_record_list(tmp_path):
    record = _make_record(n_findings=5).sign(_TEST_KEY)
    dump(record, tmp_path / "a.json")
    dump(record, tmp_path / "b.json")
    result = _run_cli("list", str(tmp_path))
    assert result.returncode == 0
    assert "findings" in result.stdout


def test_cli_audit_record_list_json(tmp_path):
    record = _make_record(n_findings=3).sign(_TEST_KEY)
    dump(record, tmp_path / "a.json")
    result = _run_cli("list", str(tmp_path), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload[0]["total_findings"] == 3


def test_cli_audit_record_list_nonexistent_dir(tmp_path):
    result = _run_cli("list", str(tmp_path / "missing"))
    assert result.returncode == 2


# --- AuditSummary serde -----------------------------------------------------


def test_audit_summary_from_dict_round_trip():
    """AuditSummary serde round-trips cleanly via to_dict / from_dict."""
    pillars = [_make_pillar_result("p1", 2), _make_pillar_result("p2", 3)]
    summary = AuditSummary.from_pillar_results(pillars)
    back = AuditSummary.from_dict(summary.to_dict())
    assert back == summary
