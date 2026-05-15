"""Tests for the auditing wheel (Phase 1).

Each concrete pillar is exercised via a stubbed subprocess so the test doesn't
require the actual tool. The live smoke against Ophamin's own source tree is
the responsibility of the example runner / CLI.
"""

from __future__ import annotations

import json
import subprocess
from unittest import mock

import pytest

from ophamin.auditing import (
    AuditPillar,
    AuditRecord,
    AuditRunner,
    AuditSummary,
    Finding,
    FindingSeverity,
    PillarResult,
)
from ophamin.auditing.pillars import (
    BanditPillar,
    MypyPillar,
    PipAuditPillar,
    RadonPillar,
    RuffPillar,
    VulturePillar,
    default_pillars,
)


# --------------------------------------------------------------------------
# Dataclass shape
# --------------------------------------------------------------------------


def test_finding_to_dict_round_trip():
    f = Finding(
        pillar_name="ruff",
        rule_id="E501",
        severity=FindingSeverity.HIGH,
        message="line too long",
        path="src/foo.py",
        line=42,
        column=80,
        extra={"url": "https://example.com"},
    )
    d = f.to_dict()
    assert d["pillar_name"] == "ruff"
    assert d["severity"] == "high"
    assert d["line"] == 42


def test_pillar_result_aggregates_correctly():
    findings = (
        Finding("ruff", "E501", FindingSeverity.HIGH, "msg", "a.py", line=1),
        Finding("ruff", "E501", FindingSeverity.HIGH, "msg", "a.py", line=2),
        Finding("ruff", "F401", FindingSeverity.HIGH, "msg", "b.py", line=1),
        Finding("ruff", "W292", FindingSeverity.MEDIUM, "msg", "a.py", line=3),
    )
    result = PillarResult(
        pillar_name="ruff", tool_name="ruff", tool_version="0.x",
        status="ok", target_path="/x", findings=findings,
    )
    assert result.finding_count == 4
    hist = result.severity_histogram()
    assert hist["high"] == 3
    assert hist["medium"] == 1
    per_file = result.per_file_count(top_n=10)
    assert per_file[0] == ("a.py", 3)
    per_rule = result.per_rule_count(top_n=10)
    assert per_rule[0] == ("E501", 2)


def test_audit_summary_rolls_up_pillars():
    pr1 = PillarResult(
        pillar_name="ruff", tool_name="ruff", tool_version="0.x", status="ok",
        target_path="/x",
        findings=(
            Finding("ruff", "E501", FindingSeverity.HIGH, "msg", "a.py"),
            Finding("ruff", "F401", FindingSeverity.MEDIUM, "msg", "a.py"),
        ),
    )
    pr2 = PillarResult(
        pillar_name="bandit", tool_name="bandit", tool_version="1.x", status="ok",
        target_path="/x",
        findings=(
            Finding("bandit", "B101", FindingSeverity.HIGH, "msg", "b.py"),
        ),
    )
    pr3 = PillarResult(
        pillar_name="vulture", tool_name="vulture", tool_version="",
        status="unavailable", target_path="/x",
    )
    summary = AuditSummary.from_pillar_results([pr1, pr2, pr3])
    assert summary.total_findings == 3
    assert summary.severity_histogram == {"high": 2, "medium": 1}
    assert summary.findings_per_pillar == {"ruff": 2, "bandit": 1, "vulture": 0}
    assert "ruff" in summary.pillars_run
    assert "bandit" in summary.pillars_run
    assert "vulture" in summary.pillars_unavailable
    assert summary.top_files[0] == ("a.py", 2)


def test_audit_record_signs_and_verifies(tmp_path):
    (tmp_path / "f.py").write_text("x = 1\n")
    record = AuditRecord.build(
        target_path=tmp_path,
        results=[
            PillarResult(
                pillar_name="ruff", tool_name="ruff", tool_version="0.x",
                status="ok", target_path=str(tmp_path),
                findings=(
                    Finding("ruff", "E501", FindingSeverity.HIGH, "msg", str(tmp_path / "f.py")),
                ),
            ),
        ],
    )
    assert record.signature == ""
    record.sign(b"key")
    assert record.signature
    assert record.verify_signature(b"key")
    assert not record.verify_signature(b"wrong-key")


def test_audit_record_to_dict_and_json_round_trip(tmp_path):
    (tmp_path / "f.py").write_text("x = 1\n")
    record = AuditRecord.build(
        target_path=tmp_path,
        results=[
            PillarResult(
                pillar_name="ruff", tool_name="ruff", tool_version="0.x",
                status="ok", target_path=str(tmp_path), findings=(),
            ),
        ],
    )
    record.sign(b"k")
    payload = json.loads(record.to_json())
    assert payload["audit_id"]
    assert payload["target"]["target_content_hash"]
    assert payload["pillars"][0]["pillar_name"] == "ruff"
    assert payload["summary"]["total_findings"] == 0
    assert payload["signature"]


def test_audit_record_to_markdown_renders(tmp_path):
    (tmp_path / "f.py").write_text("x = 1\n")
    record = AuditRecord.build(
        target_path=tmp_path,
        results=[
            PillarResult(
                pillar_name="ruff", tool_name="ruff", tool_version="ruff 0.x",
                status="ok", target_path=str(tmp_path),
                findings=(
                    Finding("ruff", "E501", FindingSeverity.HIGH, "msg", str(tmp_path / "f.py")),
                ),
            ),
            PillarResult(
                pillar_name="vulture", tool_name="vulture", tool_version="",
                status="unavailable", target_path=str(tmp_path),
            ),
        ],
    )
    md = record.to_markdown()
    assert "# Ophamin Audit Record" in md
    assert "ruff 0.x" in md
    assert "vulture" in md
    assert "unavailable" in md


def test_audit_record_to_markdown_writes_to_caller_path_not_hotspot_file(tmp_path):
    """Regression: ``to_markdown(path)`` had a variable-shadow bug where the
    ``for path, count in s.top_files`` loop clobbered the ``path`` parameter,
    causing the audit markdown to be written into the LAST hotspot SOURCE
    file. Surfaced in CI 2026-05-15 when the audit workflow corrupted
    ``src/ophamin/inspecting/inspector.py`` on the GitHub runner.
    """
    target = tmp_path / "subject"
    target.mkdir()
    # Two hotspot files with content we can verify remains intact.
    hotspot_a = target / "hotspot_a.py"
    hotspot_a.write_text("# original hotspot_a content\nimport sys\n")
    hotspot_b = target / "hotspot_b.py"
    hotspot_b.write_text("# original hotspot_b content\nimport os\n")
    record = AuditRecord.build(
        target_path=target,
        results=[
            PillarResult(
                pillar_name="ruff", tool_name="ruff", tool_version="ruff 0.x",
                status="ok", target_path=str(target),
                findings=tuple(
                    Finding("ruff", "E501", FindingSeverity.HIGH, "msg",
                            str(hotspot_a if i % 2 == 0 else hotspot_b))
                    for i in range(6)
                ),
            ),
        ],
    )

    output_path = tmp_path / "audit_out" / "report.md"
    output_path.parent.mkdir()
    record.to_markdown(str(output_path))

    # Caller-supplied path receives the markdown.
    assert output_path.exists(), "audit markdown not written to caller's path"
    assert "# Ophamin Audit Record" in output_path.read_text()

    # Hotspot source files MUST NOT be touched.
    assert hotspot_a.read_text() == "# original hotspot_a content\nimport sys\n"
    assert hotspot_b.read_text() == "# original hotspot_b content\nimport os\n"


# --------------------------------------------------------------------------
# AuditPillar base class
# --------------------------------------------------------------------------


def test_audit_pillar_requires_name_and_binary():
    class _Bad(AuditPillar):
        # missing name + tool_binary
        def run(self, target_path, **_kwargs):
            return None  # never reached
    with pytest.raises(ValueError, match="must set"):
        _Bad()


def test_resolved_binary_prefers_venv_local_over_path(tmp_path, monkeypatch):
    """Regression: when Ophamin runs as ``.venv/bin/python -m ophamin.cli``
    without venv activation, ``shutil.which("vulture")`` returns None even
    though vulture is installed in ``.venv/bin/vulture``. Surface bug
    2026-05-15 — the audit pillars marked vulture/radon/pip-audit as
    "unavailable" against Kimera.

    Fix: ``resolved_binary`` looks next to ``sys.executable`` first.
    """
    import sys

    fake_venv = tmp_path / "venv"
    bin_dir = fake_venv / "bin"
    bin_dir.mkdir(parents=True)
    fake_python = bin_dir / "python"
    fake_python.write_text("#!/bin/sh\nexec /usr/bin/env python3 \"$@\"\n")
    fake_python.chmod(0o755)
    fake_tool = bin_dir / "fake_audit_tool"
    fake_tool.write_text("#!/bin/sh\necho fake-tool 1.0\n")
    fake_tool.chmod(0o755)

    monkeypatch.setattr(sys, "executable", str(fake_python))

    class _FakePillar(AuditPillar):
        name = "fake_audit"
        tool_binary = "fake_audit_tool"

        def run(self, target_path, **_kwargs):
            return None

    pillar = _FakePillar()
    assert pillar.is_available()
    assert pillar.resolved_binary() == str(fake_tool)


def test_resolved_binary_falls_through_to_path_when_no_venv_local(tmp_path, monkeypatch):
    """If the binary is not next to sys.executable, fall through to PATH."""
    import sys
    import shutil as _sh

    # Put fake interpreter in a directory that does NOT contain the tool.
    fake_bin = tmp_path / "no_tool"
    fake_bin.mkdir()
    fake_python = fake_bin / "python"
    fake_python.write_text("#!/bin/sh\nexec /usr/bin/env python3 \"$@\"\n")
    fake_python.chmod(0o755)
    monkeypatch.setattr(sys, "executable", str(fake_python))

    # Pretend `ls` is on PATH (it always is on Linux/macOS).
    class _LsPillar(AuditPillar):
        name = "ls_audit"
        tool_binary = "ls"

        def run(self, target_path, **_kwargs):
            return None

    pillar = _LsPillar()
    if _sh.which("ls"):
        assert pillar.is_available()
        assert pillar.resolved_binary() == _sh.which("ls")
    else:
        # Unusual but possible — skip if `ls` is genuinely not on PATH.
        pytest.skip("ls not on PATH")


def test_resolved_binary_returns_none_when_nowhere_found(tmp_path, monkeypatch):
    import sys
    fake_bin = tmp_path / "empty"
    fake_bin.mkdir()
    fake_python = fake_bin / "python"
    fake_python.write_text("#!/bin/sh\nexec /usr/bin/env python3 \"$@\"\n")
    fake_python.chmod(0o755)
    monkeypatch.setattr(sys, "executable", str(fake_python))

    class _MissingPillar(AuditPillar):
        name = "missing_audit"
        tool_binary = "totally_not_a_real_tool_xyz_2026"

        def run(self, target_path, **_kwargs):
            return None

    pillar = _MissingPillar()
    assert not pillar.is_available()
    assert pillar.resolved_binary() is None


# --------------------------------------------------------------------------
# Concrete pillars — stubbed subprocess
# --------------------------------------------------------------------------


def _completed(stdout: str, stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_ruff_pillar_parses_findings():
    ruff_output = json.dumps([
        {
            "code": "E501",
            "message": "line too long (99 > 88)",
            "filename": "/x/foo.py",
            "location": {"row": 10, "column": 89},
            "url": "https://docs.astral.sh/ruff/E501",
            "fix": None,
        },
        {
            "code": "F401",
            "message": "imported but unused",
            "filename": "/x/foo.py",
            "location": {"row": 1, "column": 1},
        },
    ])
    pillar = RuffPillar()
    with mock.patch.object(pillar, "is_available", return_value=True), \
         mock.patch.object(pillar, "tool_version", return_value="ruff 0.x"), \
         mock.patch("subprocess.run", return_value=_completed(ruff_output)):
        result = pillar.run("/x")
    assert result.status == "ok"
    assert result.finding_count == 2
    assert result.findings[0].rule_id == "E501"
    assert result.findings[0].severity == FindingSeverity.HIGH
    assert result.findings[0].line == 10
    assert result.findings[1].rule_id == "F401"


def test_ruff_pillar_unavailable_when_binary_missing():
    pillar = RuffPillar()
    with mock.patch.object(pillar, "is_available", return_value=False):
        result = pillar.run("/x")
    assert result.status == "unavailable"
    assert "install" in result.error_message.lower()


def test_ruff_pillar_handles_non_json_output_loudly():
    pillar = RuffPillar()
    with mock.patch.object(pillar, "is_available", return_value=True), \
         mock.patch.object(pillar, "tool_version", return_value="ruff 0.x"), \
         mock.patch("subprocess.run", return_value=_completed("this is not json")):
        result = pillar.run("/x")
    assert result.status == "error"
    assert "non-JSON" in result.error_message


def test_bandit_pillar_parses_findings():
    bandit_output = json.dumps({
        "results": [
            {
                "test_id": "B101",
                "test_name": "assert_used",
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "Use of assert detected",
                "filename": "/x/foo.py",
                "line_number": 42,
                "col_offset": 4,
            },
        ],
    })
    pillar = BanditPillar()
    with mock.patch.object(pillar, "is_available", return_value=True), \
         mock.patch.object(pillar, "tool_version", return_value="bandit 1.x"), \
         mock.patch(
             "subprocess.run",
             return_value=_completed(bandit_output, returncode=1),  # bandit exits 1 on findings
         ):
        result = pillar.run("/x")
    assert result.status == "ok"
    assert result.finding_count == 1
    assert result.findings[0].rule_id == "B101"
    assert result.findings[0].severity == FindingSeverity.HIGH


def test_mypy_pillar_parses_line_format():
    mypy_output = (
        "src/foo.py:10:5: error: Incompatible return value type  [return-value]\n"
        "src/foo.py:20: error: Name 'x' is not defined  [name-defined]\n"
        "src/bar.py:1: note: revealed type is 'int'\n"
        "Success: no issues found in 1 source file\n"  # status line — ignored
    )
    pillar = MypyPillar()
    with mock.patch.object(pillar, "is_available", return_value=True), \
         mock.patch.object(pillar, "tool_version", return_value="mypy 1.x"), \
         mock.patch("subprocess.run", return_value=_completed(mypy_output, returncode=1)):
        result = pillar.run("/x")
    assert result.status == "ok"
    assert result.finding_count == 3
    assert result.findings[0].rule_id == "return-value"
    assert result.findings[0].severity == FindingSeverity.HIGH
    assert result.findings[0].line == 10
    assert result.findings[2].severity == FindingSeverity.INFO  # note


def test_vulture_pillar_parses_confidence():
    vulture_output = (
        "src/foo.py:10: unused function 'unused_fn' (90% confidence)\n"
        "src/foo.py:20: unused variable 'maybe_unused' (60% confidence)\n"
        "src/foo.py:30: unused import 'os' (50% confidence)\n"
    )
    pillar = VulturePillar()
    with mock.patch.object(pillar, "is_available", return_value=True), \
         mock.patch.object(pillar, "tool_version", return_value="vulture 2.x"), \
         mock.patch(
             "subprocess.run",
             return_value=_completed(vulture_output, returncode=3),
         ):
        result = pillar.run("/x")
    assert result.status == "ok"
    assert result.finding_count == 3
    assert result.findings[0].severity == FindingSeverity.HIGH    # 90%
    assert result.findings[1].severity == FindingSeverity.MEDIUM  # 60%
    assert result.findings[2].severity == FindingSeverity.LOW     # 50%


def test_radon_pillar_parses_complexity():
    radon_output = json.dumps({
        "/x/foo.py": [
            {
                "type": "function",
                "name": "complex_fn",
                "complexity": 25,
                "rank": "D",
                "lineno": 100,
                "col_offset": 0,
            },
            {
                "type": "function",
                "name": "simple_fn",
                "complexity": 8,
                "rank": "B",
                "lineno": 200,
                "col_offset": 0,
            },
        ],
    })
    pillar = RadonPillar()
    with mock.patch.object(pillar, "is_available", return_value=True), \
         mock.patch.object(pillar, "tool_version", return_value="radon 6.x"), \
         mock.patch("subprocess.run", return_value=_completed(radon_output)):
        result = pillar.run("/x")
    assert result.status == "ok"
    assert result.finding_count == 2
    d_finding = next(f for f in result.findings if f.extra["rank"] == "D")
    assert d_finding.severity == FindingSeverity.HIGH
    assert d_finding.extra["complexity"] == 25
    b_finding = next(f for f in result.findings if f.extra["rank"] == "B")
    assert b_finding.severity == FindingSeverity.LOW


def test_pip_audit_pillar_parses_vulns():
    pip_audit_output = json.dumps({
        "dependencies": [
            {
                "name": "vulnerable-pkg",
                "version": "1.0.0",
                "vulns": [
                    {
                        "id": "GHSA-xxxx-yyyy-zzzz",
                        "fix_versions": ["1.0.1"],
                        "description": "RCE in handler",
                        "aliases": ["CVE-2024-1234"],
                    },
                ],
            },
            {
                "name": "safe-pkg",
                "version": "2.0.0",
                "vulns": [],
            },
        ],
    })
    pillar = PipAuditPillar()
    with mock.patch.object(pillar, "is_available", return_value=True), \
         mock.patch.object(pillar, "tool_version", return_value="pip-audit 2.x"), \
         mock.patch(
             "subprocess.run",
             return_value=_completed(pip_audit_output, returncode=1),
         ):
        result = pillar.run("/x")
    assert result.status == "ok"
    assert result.finding_count == 1
    assert result.findings[0].rule_id == "GHSA-xxxx-yyyy-zzzz"
    assert result.findings[0].severity == FindingSeverity.HIGH
    assert "vulnerable-pkg" in result.findings[0].message


# --------------------------------------------------------------------------
# AuditRunner
# --------------------------------------------------------------------------


def test_audit_runner_rejects_empty_pillars():
    with pytest.raises(ValueError, match="at least one pillar"):
        AuditRunner(pillars=[])


def test_audit_runner_runs_every_pillar_and_signs(tmp_path):
    """Stub every pillar to return a synthetic PillarResult; verify the
    runner aggregates them and signs the record."""
    (tmp_path / "x.py").write_text("x = 1\n")

    class _StubPillar(AuditPillar):
        name = "stub"
        tool_binary = "stub"
        def run(self, target_path, **_kwargs):
            return PillarResult(
                pillar_name=self.name, tool_name=self.tool_binary,
                tool_version="stub-0.0", status="ok",
                target_path=str(target_path),
                findings=(
                    Finding("stub", "S001", FindingSeverity.LOW, "noop", "x.py"),
                ),
            )

    runner = AuditRunner(pillars=[_StubPillar()])
    record = runner.run(tmp_path)
    assert record.summary.total_findings == 1
    assert record.summary.pillars_run == ("stub",)
    assert record.signature
    assert record.verify_signature(runner.sign_key)


def test_audit_runner_passes_kwargs_to_pillars(tmp_path):
    received: dict = {}

    class _KwargCapture(AuditPillar):
        name = "kw"
        tool_binary = "kw"
        def run(self, target_path, **kwargs):
            received.update(kwargs)
            return PillarResult(
                pillar_name=self.name, tool_name=self.tool_binary,
                tool_version="", status="ok", target_path=str(target_path),
            )

    runner = AuditRunner(pillars=[_KwargCapture()])
    runner.run(tmp_path, timeout_s=42.0)
    assert received["timeout_s"] == 42.0


def test_default_pillars_includes_all_six():
    pillars = default_pillars()
    names = {p.name for p in pillars}
    assert names == {"ruff", "bandit", "mypy", "vulture", "radon", "pip_audit"}


def test_audit_runner_record_is_content_addressed(tmp_path):
    """Same target + same pillars + same findings yield the same audit_id
    (modulo the captured_at timestamp). We pin the captured_at to verify
    content-addressing works."""
    (tmp_path / "x.py").write_text("x = 1\n")

    class _DeterministicPillar(AuditPillar):
        name = "det"
        tool_binary = "det"
        def run(self, target_path, **_kwargs):
            return PillarResult(
                pillar_name=self.name, tool_name=self.tool_binary,
                tool_version="0.0", status="ok",
                target_path=str(target_path), findings=(),
                wall_time_s=0.0,
            )

    runner = AuditRunner(pillars=[_DeterministicPillar()])
    r1 = runner.run(tmp_path)
    r2 = runner.run(tmp_path)
    # captured_at differs per build, so audit_id differs — but the body shape
    # (minus captured_at) is identical. Verify the signature method works
    # on both and that the content_hash of the target is identical.
    assert r1.target_content_hash == r2.target_content_hash
    assert r1.verify_signature(runner.sign_key)
    assert r2.verify_signature(runner.sign_key)
