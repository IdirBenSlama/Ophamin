"""Tests for ``ophamin verify`` — the install self-check."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ophamin.verify import (
    BINARY_CHECKS,
    CLI_SUBCOMMANDS,
    DEP_CHECKS,
    CheckResult,
    check_binary,
    check_cli_subcommands,
    check_dep,
    check_kimera_repo,
    check_python_version,
    has_required_failure,
    render_report,
    render_text,
    run_all_checks,
)


# --------------------------------------------------------------------------
# CheckResult
# --------------------------------------------------------------------------


def test_check_result_is_failure_required_missing():
    r = CheckResult(name="x", severity="required", status="missing", detail="d")
    assert r.is_failure()


def test_check_result_is_failure_required_error():
    r = CheckResult(name="x", severity="required", status="error", detail="d")
    assert r.is_failure()


def test_check_result_is_failure_optional_missing_is_not_failure():
    r = CheckResult(name="x", severity="optional", status="missing", detail="d")
    assert not r.is_failure()


def test_check_result_is_failure_required_ok_is_not_failure():
    r = CheckResult(name="x", severity="required", status="ok", detail="d")
    assert not r.is_failure()


# --------------------------------------------------------------------------
# Per-check functions
# --------------------------------------------------------------------------


def test_check_python_version_ok_on_current_interpreter():
    r = check_python_version()
    assert r.status == "ok"
    assert "Python" in r.detail


def test_check_dep_returns_ok_for_installed_package():
    # numpy is in the [required] band; this test environment must have it
    # for the rest of the suite to run.
    r = check_dep("numpy", "numpy", "required", "", "ndarray")
    assert r.status == "ok"
    assert "v" in r.detail


def test_check_dep_returns_missing_for_unknown_package():
    r = check_dep("totally-not-a-real-pkg-xyz-2026", "no_such_module",
                  "optional", "viz", "fake")
    assert r.status == "missing"
    assert r.extra_to_install == "viz"


def test_check_binary_returns_ok_when_resolves(tmp_path, monkeypatch):
    """A pillar binary present next to sys.executable is found."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_python = bin_dir / "python"
    fake_python.write_text("#!/bin/sh\nexec /usr/bin/env python3 \"$@\"\n")
    fake_python.chmod(0o755)
    fake_tool = bin_dir / "ophamin_test_fake_tool"
    fake_tool.write_text("#!/bin/sh\necho fake-tool 1.0\n")
    fake_tool.chmod(0o755)
    monkeypatch.setattr(sys, "executable", str(fake_python))

    r = check_binary("ophamin_test_fake_tool", "optional", "audit", "fake")
    assert r.status == "ok"
    assert "fake-tool" in r.detail


def test_check_binary_returns_missing_when_not_found(tmp_path, monkeypatch):
    bin_dir = tmp_path / "empty"
    bin_dir.mkdir()
    fake_python = bin_dir / "python"
    fake_python.write_text("#!/bin/sh\nexec /usr/bin/env python3 \"$@\"\n")
    fake_python.chmod(0o755)
    monkeypatch.setattr(sys, "executable", str(fake_python))

    r = check_binary("nonexistent_tool_xyz_2026", "optional", "audit", "x")
    assert r.status == "missing"
    assert r.extra_to_install == "audit"


def test_check_cli_subcommands_finds_every_documented_one():
    r = check_cli_subcommands()
    assert r.status == "ok", r.detail
    # All declared subcommands are present.
    assert "subcommands registered" in r.detail


def test_check_kimera_repo_returns_none_when_no_path():
    assert check_kimera_repo("") is None
    assert check_kimera_repo(None) is None


def test_check_kimera_repo_missing_path_returns_missing(tmp_path):
    r = check_kimera_repo(str(tmp_path / "no_such"))
    assert r is not None
    assert r.status == "missing"


# --------------------------------------------------------------------------
# Catalog structure
# --------------------------------------------------------------------------


def test_dep_checks_catalog_well_formed():
    for entry in DEP_CHECKS:
        assert len(entry) == 5
        pkg, mod, severity, extra, desc = entry
        assert severity in {"required", "optional", "info"}
        assert desc, f"missing description on {pkg!r}"


def test_binary_checks_catalog_well_formed():
    allowed_extras = {
        "audit", "profile", "viz", "well", "hydra", "telemetry", "dev",
        "property_test",  # added 2026-04-26 with schemathesis pillar
        "",
    }
    for name, sev, extra, desc in BINARY_CHECKS:
        assert sev in {"required", "optional", "info"}
        assert extra in allowed_extras, f"{name}: extra={extra!r} not in {allowed_extras}"


def test_cli_subcommands_includes_known_commands():
    for cmd in ("verify", "inventory", "wiring", "audit", "scrape",
                "discover-fields"):
        assert cmd in CLI_SUBCOMMANDS


# --------------------------------------------------------------------------
# Orchestrator + reporting
# --------------------------------------------------------------------------


def test_run_all_checks_returns_results_for_every_dep_and_binary():
    results = run_all_checks()
    # python version + every dep + every binary + cli_subcommands
    expected_min = 1 + len(DEP_CHECKS) + len(BINARY_CHECKS) + 1
    assert len(results) >= expected_min


def test_run_all_checks_includes_kimera_when_path_passed(tmp_path):
    # A nonexistent path produces a "missing" check.
    results = run_all_checks(kimera_repo=str(tmp_path / "fake_kimera"))
    kimera_checks = [r for r in results if r.name == "kimera_repo"]
    assert len(kimera_checks) == 1


def test_render_text_includes_summary_line():
    results = [
        CheckResult(name="a", severity="required", status="ok", detail="ok"),
        CheckResult(name="b", severity="optional", status="missing",
                    detail="m", extra_to_install="audit"),
    ]
    text = render_text(results)
    assert "summary:" in text
    assert "ok=1" in text
    assert "missing=1" in text


def test_render_report_emits_markdown_table():
    results = [
        CheckResult(name="a", severity="required", status="ok", detail="ok"),
    ]
    md = render_report(results)
    assert "# Ophamin install verification" in md
    assert "| status | name | severity | detail | install hint |" in md


def test_render_text_lists_required_failures_with_install_hint():
    results = [
        CheckResult(name="missing_pkg", severity="required", status="missing",
                    detail="not installed", extra_to_install="dev"),
    ]
    text = render_text(results)
    assert "REQUIRED-check failures" in text
    assert "missing_pkg" in text
    assert "pip install" in text


def test_has_required_failure_true_when_required_missing():
    results = [
        CheckResult(name="x", severity="required", status="missing", detail="m"),
        CheckResult(name="y", severity="optional", status="missing", detail="m"),
    ]
    assert has_required_failure(results)


def test_has_required_failure_false_when_only_optional_missing():
    results = [
        CheckResult(name="x", severity="optional", status="missing", detail="m"),
        CheckResult(name="y", severity="info", status="missing", detail="m"),
    ]
    assert not has_required_failure(results)


def test_run_all_checks_against_current_install_has_no_required_failures():
    """Smoke test: this very test environment must satisfy every required
    check (it's the same venv pytest is running in)."""
    results = run_all_checks()
    failures = [r for r in results if r.is_failure()]
    assert not failures, (
        f"Required check(s) failing in this venv: "
        f"{[(r.name, r.detail) for r in failures]}"
    )
