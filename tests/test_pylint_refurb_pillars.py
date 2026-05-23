"""Tests for PylintPillar + RefurbPillar — added in v0.2 plugin-catalog round."""

from __future__ import annotations


import pytest

from ophamin.auditing.base import FindingSeverity
from ophamin.auditing.pillars import (
    DEEP_PILLAR_CLASSES,
    DEFAULT_PILLAR_CLASSES,
    PylintPillar,
    RefurbPillar,
    deep_pillars,
    default_pillars,
)


# --------------------------------------------------------------------------
# Pillar shape + registry
# --------------------------------------------------------------------------


def test_pylint_pillar_shape():
    p = PylintPillar()
    assert p.name == "pylint"
    assert p.tool_binary == "pylint"


def test_refurb_pillar_shape():
    p = RefurbPillar()
    assert p.name == "refurb"
    assert p.tool_binary == "refurb"


def test_pylint_in_deep_pillars_not_default():
    assert PylintPillar in DEEP_PILLAR_CLASSES
    assert PylintPillar not in DEFAULT_PILLAR_CLASSES
    assert any(isinstance(p, PylintPillar) for p in deep_pillars())


def test_refurb_in_default_pillars():
    assert RefurbPillar in DEFAULT_PILLAR_CLASSES
    assert any(isinstance(p, RefurbPillar) for p in default_pillars())


# --------------------------------------------------------------------------
# Synthetic targets
# --------------------------------------------------------------------------


@pytest.fixture
def buggy_module(tmp_path):
    """A Python file with multiple obvious pylint warnings."""
    f = tmp_path / "buggy.py"
    f.write_text(
        "import os, sys\n"           # multiple-imports + unused
        "\n"
        "def Foo(X):\n"               # naming convention violations
        "    return X+1\n"            # bad whitespace
        "\n"
        "y = 1\n"                     # unused variable
    )
    return f


@pytest.fixture
def modernizable_module(tmp_path):
    """A Python file refurb suggests modernizing."""
    f = tmp_path / "old_style.py"
    f.write_text(
        "import os\n"
        "\n"
        "def f(s: str) -> str:\n"
        "    if s.startswith('foo'):\n"
        "        return s[len('foo'):]\n"   # FURB106 / 188 → suggest removeprefix
        "    return s\n"
    )
    return f


# --------------------------------------------------------------------------
# Pylint pillar — happy path
# --------------------------------------------------------------------------


def test_pylint_runs_on_buggy_module(buggy_module):
    p = PylintPillar()
    if not p.is_available():
        pytest.skip("pylint not installed")
    result = p.run(buggy_module, timeout_s=60)
    # Pylint always finds something on this kind of source.
    assert result.status == "ok"
    assert result.finding_count >= 1
    # All findings must have a rule_id and message.
    for f in result.findings:
        assert f.rule_id
        assert f.message
        assert f.path
        assert f.severity in (
            FindingSeverity.HIGH, FindingSeverity.MEDIUM,
            FindingSeverity.LOW, FindingSeverity.INFO, FindingSeverity.CRITICAL,
        )


def test_pylint_returns_unavailable_when_binary_missing(tmp_path, monkeypatch):
    p = PylintPillar()
    monkeypatch.setattr(p, "is_available", lambda: False)
    result = p.run(tmp_path)
    assert result.status == "unavailable"


def test_pylint_severity_mapping_includes_error_high():
    from ophamin.auditing.pillars.pylint_pillar import _TYPE_TO_SEVERITY
    assert _TYPE_TO_SEVERITY["error"] == FindingSeverity.HIGH
    assert _TYPE_TO_SEVERITY["warning"] == FindingSeverity.MEDIUM
    assert _TYPE_TO_SEVERITY["fatal"] == FindingSeverity.CRITICAL


# --------------------------------------------------------------------------
# Refurb pillar — happy path
# --------------------------------------------------------------------------


def test_refurb_runs_on_modernizable_module(modernizable_module):
    p = RefurbPillar()
    if not p.is_available():
        pytest.skip("refurb not installed")
    result = p.run(modernizable_module.parent, timeout_s=60)
    # Refurb may or may not flag this exact case (depends on rule version);
    # just confirm pillar runs ok.
    assert result.status == "ok"
    # If findings, they're all LOW (modernization suggestions, not bugs).
    for f in result.findings:
        assert f.severity == FindingSeverity.LOW
        assert f.rule_id.startswith("FURB")


def test_refurb_returns_unavailable_when_binary_missing(tmp_path, monkeypatch):
    p = RefurbPillar()
    monkeypatch.setattr(p, "is_available", lambda: False)
    result = p.run(tmp_path)
    assert result.status == "unavailable"


def test_refurb_line_regex_parses_canonical_format():
    from ophamin.auditing.pillars.refurb_pillar import _LINE_RE
    line = "/path/to/file.py:10:5 [FURB101]: Use Path.read_text() instead"
    m = _LINE_RE.match(line)
    assert m is not None
    assert m.group("path") == "/path/to/file.py"
    assert m.group("line") == "10"
    assert m.group("col") == "5"
    assert m.group("rule") == "FURB101"
    assert "read_text" in m.group("msg")


def test_refurb_line_regex_rejects_non_finding_lines():
    from ophamin.auditing.pillars.refurb_pillar import _LINE_RE
    for non_finding in ("", "Refurb v2.0.0", "Found 0 issues."):
        assert _LINE_RE.match(non_finding) is None
