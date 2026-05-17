"""Subprocess-mocked tests for KimeraAdapter (Phase A4, 0.8.3).

The adapter's full pipeline calls a Kimera Python interpreter via
``subprocess.run``. Real subprocess invocation needs a real Kimera repo
on disk (integration-test territory). These tests mock ``subprocess.run``
to cover the dispatch / parse / decode-error branches — they pin every
branch of ``_invoke`` and ``_to_cycle_result`` that exists between the
subprocess boundary and the returned ``CycleResult`` / dict.

The 0.7.0 Phase-S2 tests already cover the constructor's loud-failure
branches; this file is the orthogonal coverage closure on the
post-construction code paths.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ophamin.seeing.substrate.base import CycleResult
from ophamin.seeing.substrate.kimera_adapter import (
    KIMERA_TARGETS,
    KimeraAdapter,
)


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture
def fake_kimera_repo(tmp_path: Path) -> Path:
    """Build a synthetic 'Kimera repo' with the minimum layout the adapter
    accepts. Same shape as test_kimera_adapter_coverage.py."""
    (tmp_path / "kimera_swm").mkdir()
    (tmp_path / "kimera_swm" / "__init__.py").touch()
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    python = venv_bin / "python"
    python.write_text("#!/usr/bin/env true\n")
    python.chmod(0o755)
    return tmp_path


@pytest.fixture
def adapter(fake_kimera_repo: Path) -> KimeraAdapter:
    return KimeraAdapter(
        kimera_repo=fake_kimera_repo,
        target=next(iter(KIMERA_TARGETS)),
        mode="subprocess",
        timeout=30.0,
        batch_timeout=120.0,
    )


def _mock_completed(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess that subprocess.run returns."""
    return subprocess.CompletedProcess(
        args=("python",), returncode=returncode, stdout=stdout, stderr=stderr
    )


# ----------------------------------------------------------------------------
# _invoke — the dispatch boundary
# ----------------------------------------------------------------------------


def test_invoke_happy_path_returns_parsed_dict(adapter: KimeraAdapter) -> None:
    expected = {"ok": True, "raw": {"phi": 0.42}, "cycle_seconds": 0.123}
    with patch("subprocess.run", return_value=_mock_completed(json.dumps(expected))):
        result = adapter._invoke({"stimulus": "hello"})
    assert result == expected


def test_invoke_uses_last_jsonl_line(adapter: KimeraAdapter) -> None:
    """The runner emits one JSON object per line. The adapter parses the LAST
    non-empty line as the result; intermediate log lines are ignored."""
    stdout = "INFO startup\nINFO running\n" + json.dumps({"ok": True, "raw": {"a": 1}})
    with patch("subprocess.run", return_value=_mock_completed(stdout)):
        result = adapter._invoke({})
    assert result == {"ok": True, "raw": {"a": 1}}


def test_invoke_empty_stdout_returns_subprocess_error(adapter: KimeraAdapter) -> None:
    with patch(
        "subprocess.run",
        return_value=_mock_completed(stdout="", stderr="boom\n", returncode=42),
    ):
        result = adapter._invoke({})
    assert result["ok"] is False
    assert result["stage"] == "subprocess"
    assert "exit 42" in result["error"]
    assert "boom" in result["traceback"]


def test_invoke_invalid_json_returns_decode_error(adapter: KimeraAdapter) -> None:
    with patch(
        "subprocess.run",
        return_value=_mock_completed(stdout="not json at all", stderr="ctx\n"),
    ):
        result = adapter._invoke({})
    assert result["ok"] is False
    assert result["stage"] == "decode"
    assert "JSON" in result["error"]
    assert "not json at all" in result["traceback"]
    assert "ctx" in result["traceback"]


def test_invoke_non_object_json_returns_decode_error(adapter: KimeraAdapter) -> None:
    """If the runner outputs valid JSON but a non-dict (e.g. a bare list),
    the adapter must refuse loudly rather than passing the list downstream."""
    with patch("subprocess.run", return_value=_mock_completed(stdout="[1, 2, 3]")):
        result = adapter._invoke({})
    assert result["ok"] is False
    assert result["stage"] == "decode"
    assert "not a JSON object" in result["error"]
    assert "list" in result["error"]


def test_invoke_timeout_returns_timeout_error(adapter: KimeraAdapter) -> None:
    timeout_exc = subprocess.TimeoutExpired(cmd=("python",), timeout=30.0)
    with patch("subprocess.run", side_effect=timeout_exc):
        result = adapter._invoke({}, timeout=30.0)
    assert result["ok"] is False
    assert result["stage"] == "timeout"


def test_invoke_passes_probe_flag(adapter: KimeraAdapter) -> None:
    """When ``probe=True``, the adapter appends ``--probe`` to the command."""
    captured = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["args"] = args[0] if args else kwargs.get("args")
        return _mock_completed(stdout=json.dumps({"ok": True}))

    with patch("subprocess.run", side_effect=fake_run):
        adapter._invoke(None, probe=True)
    assert "--probe" in captured["args"]


def test_invoke_passes_batch_flag(adapter: KimeraAdapter) -> None:
    captured = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["args"] = args[0] if args else kwargs.get("args")
        return _mock_completed(stdout=json.dumps({"ok": True, "batch": []}))

    with patch("subprocess.run", side_effect=fake_run):
        adapter._invoke({}, batch=True)
    assert "--batch" in captured["args"]


def test_invoke_merges_env_with_os_environ(
    adapter: KimeraAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXISTING_VAR", "from-os")
    adapter.env = {"OPHAMIN_TEST_FLAG": "set"}
    captured = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["env"] = kwargs.get("env", {})
        return _mock_completed(stdout=json.dumps({"ok": True}))

    with patch("subprocess.run", side_effect=fake_run):
        adapter._invoke({})
    assert captured["env"].get("OPHAMIN_TEST_FLAG") == "set"
    assert captured["env"].get("EXISTING_VAR") == "from-os"


def test_invoke_uses_default_timeout_when_none(adapter: KimeraAdapter) -> None:
    captured = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["timeout"] = kwargs.get("timeout")
        return _mock_completed(stdout=json.dumps({"ok": True}))

    with patch("subprocess.run", side_effect=fake_run):
        adapter._invoke({}, timeout=None)
    assert captured["timeout"] == adapter.timeout


def test_invoke_uses_explicit_timeout_when_set(adapter: KimeraAdapter) -> None:
    captured = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["timeout"] = kwargs.get("timeout")
        return _mock_completed(stdout=json.dumps({"ok": True}))

    with patch("subprocess.run", side_effect=fake_run):
        adapter._invoke({}, timeout=5.0)
    assert captured["timeout"] == 5.0


# ----------------------------------------------------------------------------
# run_cycle — adapter → CycleResult
# ----------------------------------------------------------------------------


def test_run_cycle_success(adapter: KimeraAdapter) -> None:
    runner_out = {
        "ok": True,
        "success": True,
        "raw": {"phi": 0.5, "halt_mode": "ok"},
        "halt_mode": "ok",
        "cycle_seconds": 0.234,
    }
    with patch("subprocess.run", return_value=_mock_completed(json.dumps(runner_out))):
        cycle = adapter.run_cycle("hello world")
    assert isinstance(cycle, CycleResult)
    assert cycle.success is True
    assert cycle.cycle_index == 0
    assert cycle.stimulus_id == "hello world"
    assert cycle.raw["phi"] == 0.5
    assert cycle.raw["cycle_seconds"] == 0.234
    assert cycle.halt_mode == "ok"


def test_run_cycle_propagates_cycle_seconds_into_raw(adapter: KimeraAdapter) -> None:
    """Regression guard for the 2026-05-15 fix where cycle_seconds wasn't
    being surfaced into raw, breaking the ThroughputCeilingScenario."""
    runner_out = {
        "ok": True,
        "success": True,
        "raw": {"phi": 0.5},  # NO cycle_seconds here
        "cycle_seconds": 0.789,  # at the top level
    }
    with patch("subprocess.run", return_value=_mock_completed(json.dumps(runner_out))):
        cycle = adapter.run_cycle("x")
    assert cycle.raw["cycle_seconds"] == 0.789, (
        "cycle_seconds must be surfaced from the top level into raw"
    )


def test_run_cycle_does_not_overwrite_cycle_seconds_in_raw(
    adapter: KimeraAdapter,
) -> None:
    """If raw already has its own cycle_seconds, the top-level value must NOT
    overwrite it (raw is authoritative when present)."""
    runner_out = {
        "ok": True,
        "success": True,
        "raw": {"cycle_seconds": 0.111},
        "cycle_seconds": 0.999,
    }
    with patch("subprocess.run", return_value=_mock_completed(json.dumps(runner_out))):
        cycle = adapter.run_cycle("x")
    assert cycle.raw["cycle_seconds"] == 0.111


def test_run_cycle_adapter_error_path(adapter: KimeraAdapter) -> None:
    """When _invoke returns ok=False, run_cycle wraps it as an
    adapter-error CycleResult, NOT a successful one."""
    with patch("subprocess.run", return_value=_mock_completed(stdout="bad json")):
        cycle = adapter.run_cycle("x")
    assert cycle.success is False
    assert cycle.halt_mode == "adapter_error"
    assert cycle.error is not None
    assert "JSON" in cycle.error


def test_run_cycle_non_dict_raw_gets_wrapped(adapter: KimeraAdapter) -> None:
    """If the runner returns a non-dict ``raw`` (e.g. a string), the adapter
    wraps it as ``{"result": <value>}`` rather than crashing."""
    runner_out = {"ok": True, "success": True, "raw": "scalar-result"}
    with patch("subprocess.run", return_value=_mock_completed(json.dumps(runner_out))):
        cycle = adapter.run_cycle("x")
    assert cycle.raw == {"result": "scalar-result"}


# ----------------------------------------------------------------------------
# run_batch — subprocess mode delegates to per-cycle run
# ----------------------------------------------------------------------------


def test_run_batch_subprocess_mode_runs_cycles_individually(
    fake_kimera_repo: Path,
) -> None:
    """In ``mode="subprocess"``, run_batch falls back to the base class's
    per-cycle loop — one ``_invoke`` per stimulus."""
    adapter = KimeraAdapter(
        kimera_repo=fake_kimera_repo,
        target=next(iter(KIMERA_TARGETS)),
        mode="subprocess",
    )
    call_count = {"n": 0}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        call_count["n"] += 1
        return _mock_completed(
            stdout=json.dumps({"ok": True, "success": True, "raw": {"i": call_count["n"]}})
        )

    with patch("subprocess.run", side_effect=fake_run):
        cycles = adapter.run_batch(["a", "b", "c"])
    assert len(cycles) == 3
    assert call_count["n"] == 3
    assert [c.raw["i"] for c in cycles] == [1, 2, 3]


# ----------------------------------------------------------------------------
# run_batch — batch mode happy path
# ----------------------------------------------------------------------------


def test_run_batch_batch_mode_happy_path(fake_kimera_repo: Path) -> None:
    """In ``mode="batch"``, the runner returns a single response with a
    ``batch`` array of per-cycle entries. Each entry becomes a CycleResult."""
    adapter = KimeraAdapter(
        kimera_repo=fake_kimera_repo,
        target=next(iter(KIMERA_TARGETS)),
        mode="batch",
    )
    # Each batch entry carries its own ``ok=True`` — matches what the
    # real runner emits at line 310 of the embedded _RUNNER_SOURCE.
    runner_out = {
        "ok": True,
        "batch": [
            {"cycle_index": 0, "ok": True, "success": True, "raw": {"phi": 0.1}, "cycle_seconds": 0.05},
            {"cycle_index": 1, "ok": True, "success": True, "raw": {"phi": 0.2}, "cycle_seconds": 0.06},
            {"cycle_index": 2, "ok": True, "success": True, "raw": {"phi": 0.3}, "cycle_seconds": 0.07},
        ],
    }
    with patch("subprocess.run", return_value=_mock_completed(json.dumps(runner_out))):
        cycles = adapter.run_batch(["x", "y", "z"])
    assert len(cycles) == 3
    assert [c.cycle_index for c in cycles] == [0, 1, 2]
    assert [c.raw["phi"] for c in cycles] == [0.1, 0.2, 0.3]
    assert all(c.raw["cycle_seconds"] > 0 for c in cycles)
