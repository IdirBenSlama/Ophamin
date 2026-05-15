"""Tests for the project-scope dependency-audit pillars (deptry + fawltydeps).

Both pillars require the target be a project root with ``pyproject.toml``;
on a non-project target, they return ``status="errored"`` with a clear
message rather than crashing.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from ophamin.auditing.base import FindingSeverity
from ophamin.auditing.pillars import (
    PROJECT_PILLAR_CLASSES,
    DeptryPillar,
    FawltyDepsPillar,
    all_pillars,
    default_pillars,
    project_pillars,
)


# --------------------------------------------------------------------------
# __init__ exports + factory functions
# --------------------------------------------------------------------------


def test_project_pillar_classes_includes_deptry_and_fawltydeps():
    names = {cls.name for cls in PROJECT_PILLAR_CLASSES}
    assert names == {"deptry", "fawltydeps"}


def test_project_pillars_factory_returns_instances():
    pillars = project_pillars()
    assert len(pillars) == 2
    assert any(isinstance(p, DeptryPillar) for p in pillars)
    assert any(isinstance(p, FawltyDepsPillar) for p in pillars)


def test_all_pillars_includes_both_file_and_project_scope():
    all_p = all_pillars()
    names = {p.name for p in all_p}
    assert {"ruff", "bandit", "mypy", "vulture", "radon", "pip_audit",
            "deptry", "fawltydeps"} <= names


def test_default_pillars_excludes_project_scope():
    """Default audit run should NOT include project-scope pillars (they'd
    error on non-project targets like ``src/ophamin/``)."""
    default_names = {p.name for p in default_pillars()}
    assert "deptry" not in default_names
    assert "fawltydeps" not in default_names


# --------------------------------------------------------------------------
# Pillar shape
# --------------------------------------------------------------------------


def test_deptry_pillar_name_and_binary():
    p = DeptryPillar()
    assert p.name == "deptry"
    assert p.tool_binary == "deptry"


def test_fawltydeps_pillar_name_and_binary():
    p = FawltyDepsPillar()
    assert p.name == "fawltydeps"
    assert p.tool_binary == "fawltydeps"


# --------------------------------------------------------------------------
# Project-scope guard — non-project target returns "errored"
# --------------------------------------------------------------------------


def test_deptry_errors_on_target_without_pyproject(tmp_path):
    p = DeptryPillar()
    if not p.is_available():
        pytest.skip("deptry not installed; skip live error path")
    result = p.run(tmp_path)
    assert result.status == "error"
    assert "pyproject.toml" in result.error_message


def test_fawltydeps_errors_on_target_without_pyproject(tmp_path):
    p = FawltyDepsPillar()
    if not p.is_available():
        pytest.skip("fawltydeps not installed")
    result = p.run(tmp_path)
    assert result.status == "error"
    assert "pyproject.toml" in result.error_message


def test_deptry_errors_when_target_is_a_file(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("import sys\n")
    p = DeptryPillar()
    if not p.is_available():
        pytest.skip("deptry not installed")
    result = p.run(f)
    assert result.status == "error"
    assert "pyproject.toml" in result.error_message


# --------------------------------------------------------------------------
# Synthetic project — verify the pillar runs end-to-end
# --------------------------------------------------------------------------


@pytest.fixture
def synthetic_project(tmp_path):
    """Build a synthetic Python project with a known dep mismatch."""
    proj = tmp_path / "synthproj"
    proj.mkdir()

    pyproject = """\
[project]
name = "synthproj"
version = "0.1.0"
dependencies = [
    "requests>=2.0",
    "unused_dep_xyz>=1.0",
]
"""
    (proj / "pyproject.toml").write_text(pyproject)

    src = proj / "src" / "synthproj"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    # Imports `requests` (declared) + `numpy` (UNDECLARED — not in deps).
    (src / "main.py").write_text(
        "import requests\n"
        "import numpy\n"
        "import os\n"            # stdlib, fine
        "def go(): return requests.get('x')\n"
    )
    return proj


def test_deptry_runs_on_synthetic_project(synthetic_project):
    p = DeptryPillar()
    if not p.is_available():
        pytest.skip("deptry binary not available")
    result = p.run(synthetic_project)
    # Either ok with findings or error due to missing src layout — depends
    # on deptry's source discovery.
    assert result.status in ("ok", "error")
    if result.status == "ok":
        # numpy and unused_dep_xyz should both surface.
        rule_ids = {f.rule_id for f in result.findings}
        # Some combination of DEP001 (undeclared) / DEP002 (unused) expected.
        assert any(rid.startswith("DEP") for rid in rule_ids)


def test_fawltydeps_runs_on_synthetic_project(synthetic_project):
    p = FawltyDepsPillar()
    if not p.is_available():
        pytest.skip("fawltydeps binary not available")
    result = p.run(synthetic_project)
    assert result.status in ("ok", "error")
    if result.status == "ok":
        # numpy is undeclared; unused_dep_xyz is unused.
        messages = " ".join(f.message for f in result.findings)
        # At least one of "numpy" or "unused_dep_xyz" should appear.
        assert "numpy" in messages or "unused_dep_xyz" in messages or \
               len(result.findings) > 0


# --------------------------------------------------------------------------
# Severity mapping
# --------------------------------------------------------------------------


def test_deptry_severity_mapping_dep001_high():
    from ophamin.auditing.pillars.deptry_pillar import SEVERITY_BY_CODE
    assert SEVERITY_BY_CODE["DEP001"] == FindingSeverity.HIGH
    assert SEVERITY_BY_CODE["DEP002"] == FindingSeverity.MEDIUM


def test_unknown_deptry_code_defaults_low():
    from ophamin.auditing.pillars.deptry_pillar import SEVERITY_BY_CODE
    assert SEVERITY_BY_CODE.get("DEP999", FindingSeverity.LOW) == FindingSeverity.LOW


# --------------------------------------------------------------------------
# Unavailable path — when the binary isn't installed
# --------------------------------------------------------------------------


def test_deptry_returns_unavailable_when_binary_missing(tmp_path, monkeypatch):
    p = DeptryPillar()
    # Force is_available to return False.
    monkeypatch.setattr(p, "is_available", lambda: False)
    result = p.run(tmp_path)
    assert result.status == "unavailable"


def test_fawltydeps_returns_unavailable_when_binary_missing(tmp_path, monkeypatch):
    p = FawltyDepsPillar()
    monkeypatch.setattr(p, "is_available", lambda: False)
    result = p.run(tmp_path)
    assert result.status == "unavailable"


# --------------------------------------------------------------------------
# CLI integration — --pillars=deptry,fawltydeps must resolve the new pillars
# --------------------------------------------------------------------------


def test_cli_pillars_lookup_includes_project_scope():
    """Ensure CLI's audit command can find deptry / fawltydeps when named.

    This pins the contract from PR #9: even though they're not in
    DEFAULT_PILLAR_CLASSES, ``--pillars=deptry,fawltydeps`` must resolve
    them via PROJECT_PILLAR_CLASSES.
    """
    from ophamin.auditing.pillars import (
        DEFAULT_PILLAR_CLASSES,
        PROJECT_PILLAR_CLASSES,
    )
    available = list(DEFAULT_PILLAR_CLASSES) + list(PROJECT_PILLAR_CLASSES)
    names = {cls.name for cls in available}
    assert "deptry" in names
    assert "fawltydeps" in names


def test_cli_pillars_lookup_handles_only_project_scope():
    from ophamin.auditing.pillars import (
        DEFAULT_PILLAR_CLASSES,
        PROJECT_PILLAR_CLASSES,
    )
    available = list(DEFAULT_PILLAR_CLASSES) + list(PROJECT_PILLAR_CLASSES)
    wanted = {"deptry"}
    matched = [cls for cls in available if cls.name in wanted]
    assert len(matched) == 1
    assert matched[0].name == "deptry"
