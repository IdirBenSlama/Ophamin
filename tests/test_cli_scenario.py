"""Hardening tests for the ``ophamin scenario`` CLI surface (Move E).

Exercises the three actions (`list` / `show` / `info`) end-to-end via
``python -m ophamin.cli scenario <action>``. Pins the contract that
the registry-backed discovery surface is reachable from the CLI and
produces the documented metadata for every scenario.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from ophamin.measuring.scenarios import SCENARIOS


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "scenario", *args],
        capture_output=True,
        text=True,
    )


def test_scenario_list_human_smoke():
    result = _run_cli("list")
    assert result.returncode == 0
    assert "name" in result.stdout
    assert "tier" in result.stdout
    assert "family" in result.stdout
    assert "concentrated-immune-siege" in result.stdout
    assert "(19 scenario(s) registered)" in result.stdout


def test_scenario_list_json_emits_every_registered_scenario():
    result = _run_cli("list", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    names = {entry["name"] for entry in payload}
    assert names == set(SCENARIOS.keys())
    # every entry has the metadata fields we promise
    for entry in payload:
        assert "tier" in entry
        assert "family" in entry
        assert "goal" in entry
        assert entry["goal"]  # non-empty


def test_scenario_list_with_tier_filter():
    result = _run_cli("list", "--tier", "empirical_deep", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert all(e["tier"] == "empirical_deep" for e in payload)
    expected_count = sum(
        1
        for cls in SCENARIOS.values()
        if cls.tier.value == "empirical_deep"
    )
    assert len(payload) == expected_count


def test_scenario_list_with_unknown_tier_returns_zero_entries():
    result = _run_cli("list", "--tier", "no-such-tier")
    assert result.returncode == 0
    assert "no scenarios registered" in result.stdout


def test_scenario_show_known_name():
    result = _run_cli("show", "memory-as-deformation")
    assert result.returncode == 0
    assert "name:                        memory-as-deformation" in result.stdout
    assert "tier:                        scientific" in result.stdout
    assert "family:                      memory" in result.stdout
    assert "goal:" in result.stdout
    assert "explanation:" in result.stdout


def test_scenario_show_unknown_name_returns_2():
    result = _run_cli("show", "totally-fictional-scenario")
    assert result.returncode == 2
    assert "unknown scenario" in result.stderr
    assert "available:" in result.stderr


def test_scenario_info_is_alias_for_show():
    """The `info` action is documented as an alias for `show`."""
    a = _run_cli("show", "concentrated-immune-siege")
    b = _run_cli("info", "concentrated-immune-siege")
    assert a.returncode == 0 and b.returncode == 0
    assert a.stdout == b.stdout


def test_scenario_list_required_action_missing_fails():
    """The subparser requires an action — bare `ophamin scenario` exits non-zero."""
    result = subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "scenario"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_every_registered_scenario_renders_via_show():
    """Every scenario in SCENARIOS must be displayable by `show` — this
    is the regression guard that catches accidental coupling between
    `show`'s rendering code and any scenario's metadata shape."""
    for name in SCENARIOS:
        result = _run_cli("show", name)
        assert result.returncode == 0, (
            f"show failed for {name!r}: {result.stderr}"
        )
        assert f"name:                        {name}" in result.stdout
