"""Coverage-closure tests for the many-small-eyes watcher (Phase S2).

The existing :mod:`test_discovery_watcher` suite covers constructor
guards + run_once early returns + previous_schema_path. The watcher's
non-substrate static helpers (_write_diff_markdown, _write_drift_report,
the run_forever loop itself) were under-covered; this file pins them
without spinning up a real KimeraAdapter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ophamin.seeing.discovery.schema_diff import FieldChange, SchemaDiff
from ophamin.seeing.discovery.schema_document import SchemaDocument
from ophamin.seeing.discovery.watcher import KimeraDiscoveryWatcher, WatchOutcome


def _empty_schema(commit: str = "deadbeefcafe", captured: str = "2026-05-16T00:00:00Z") -> SchemaDocument:
    return SchemaDocument(
        ophamin_version="0.6.0",
        ophamin_git_commit="",
        kimera_git_commit=commit,
        stimulus_set_hash="0" * 64,
        n_stimuli=0,
        targets=(),
        captured_at=captured,
    )


def test_write_diff_markdown_empty_diff(tmp_path: Path) -> None:
    """An empty diff produces a "no structural changes" report."""
    before = _empty_schema("aaaaaaaaaaaa", "2026-05-15T00:00:00Z")
    after = _empty_schema("bbbbbbbbbbbb", "2026-05-16T00:00:00Z")
    diff = SchemaDiff(before=before, after=after)
    out = tmp_path / "diff.md"
    KimeraDiscoveryWatcher._write_diff_markdown(diff, out, before, after)
    body = out.read_text()
    assert "No structural changes" in body
    assert "aaaaaaaaaaaa" in body
    assert "bbbbbbbbbbbb" in body


def test_write_diff_markdown_with_changes(tmp_path: Path) -> None:
    """A diff with field changes renders a table row per change."""
    before = _empty_schema("aaaaaaaaaaaa")
    after = _empty_schema("bbbbbbbbbbbb")
    diff = SchemaDiff(
        before=before,
        after=after,
        field_changes=(
            FieldChange(
                kind="added",
                target="entity",
                path="state",
                types_before=(),
                types_after=("str",),
            ),
            FieldChange(
                kind="removed",
                target="entity",
                path="legacy_field",
                types_before=("int",),
                types_after=(),
            ),
            FieldChange(
                kind="type_changed",
                target="walker",
                path="energy",
                types_before=("int",),
                types_after=("float",),
            ),
        ),
        targets_added=("new_arm",),
        targets_removed=("retired_arm",),
    )
    out = tmp_path / "diff.md"
    KimeraDiscoveryWatcher._write_diff_markdown(diff, out, before, after)
    body = out.read_text()
    assert "Field changes" in body
    assert "| added | entity | `state` |" in body
    assert "| removed | entity | `legacy_field` |" in body
    assert "| type_changed | walker | `energy` |" in body
    assert "new_arm" in body
    assert "retired_arm" in body


def test_write_drift_report_against_empty_proofs_dir(tmp_path: Path) -> None:
    """An empty proofs/ dir produces an empty (but valid) drift report."""
    proofs = tmp_path / "proofs"
    proofs.mkdir()
    out_dir = tmp_path / "discovery"
    out_dir.mkdir()
    watcher = KimeraDiscoveryWatcher(
        kimera_repo=tmp_path,
        targets=["entity"],
        stimuli=["hello"],
        out_dir=out_dir,
        proofs_dir=proofs,
        head_reader=lambda _: "abcabcabcabc",
    )
    path = watcher._write_drift_report("abcabcabcabc")
    assert path.is_file()
    payload = json.loads(path.read_text())
    # Empty proofs → empty drift report. Just confirm the codec runs cleanly.
    assert isinstance(payload, (list, dict))


def test_watcher_run_forever_sleeps_and_invokes_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_forever calls run_once + on_outcome until interrupted.

    We monkeypatch time.sleep to raise KeyboardInterrupt on the second call,
    so the loop runs run_once exactly twice and then exits cleanly. The
    callback must receive both outcomes.
    """
    calls = {"sleep": 0}

    def fake_sleep(interval: float) -> None:
        calls["sleep"] += 1
        if calls["sleep"] >= 2:
            raise KeyboardInterrupt

    monkeypatch.setattr("ophamin.seeing.discovery.watcher.time.sleep", fake_sleep)

    head_calls = iter(["aaaaaaaaaaaa", "aaaaaaaaaaaa"])

    watcher = KimeraDiscoveryWatcher(
        kimera_repo=tmp_path,
        targets=["entity"],
        stimuli=["hello"],
        out_dir=tmp_path,
        head_reader=lambda _: next(head_calls),
    )
    # mark the commit as already mined so run_once short-circuits — keeps
    # the test off the KimeraAdapter path
    watcher._last_mined_commit = "aaaaaaaaaaaa"

    seen: list[WatchOutcome] = []
    watcher.run_forever(poll_interval_s=0.001, on_outcome=seen.append)

    assert len(seen) == 2
    assert calls["sleep"] == 2
    assert all(o.new_commit_discovered is False for o in seen)


def test_watcher_run_forever_without_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_forever with no on_outcome callback still loops correctly."""
    calls = {"sleep": 0}

    def fake_sleep(interval: float) -> None:
        calls["sleep"] += 1
        if calls["sleep"] >= 1:
            raise KeyboardInterrupt

    monkeypatch.setattr("ophamin.seeing.discovery.watcher.time.sleep", fake_sleep)

    watcher = KimeraDiscoveryWatcher(
        kimera_repo=tmp_path,
        targets=["entity"],
        stimuli=["hello"],
        out_dir=tmp_path,
        head_reader=lambda _: "",  # always-empty HEAD short-circuits run_once
    )
    # Should not raise — KeyboardInterrupt is the documented exit path
    watcher.run_forever(poll_interval_s=0.001)


def test_kimera_head_commit_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A subprocess TimeoutExpired returns empty string, not an exception."""
    import subprocess as sp
    from ophamin.seeing.discovery import watcher as watcher_mod

    def fake_run(*args: Any, **kwargs: Any) -> None:
        raise sp.TimeoutExpired(cmd=["git"], timeout=10)

    monkeypatch.setattr(watcher_mod.subprocess, "run", fake_run)
    assert watcher_mod.kimera_head_commit("/tmp") == ""


def test_kimera_head_commit_handles_non_zero_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """git rev-parse with a non-zero exit returns empty string, not the partial stdout."""
    from subprocess import CompletedProcess
    from ophamin.seeing.discovery import watcher as watcher_mod

    def fake_run(*args: Any, **kwargs: Any) -> CompletedProcess:
        return CompletedProcess(args=("git",), returncode=128, stdout="garbage", stderr="")

    monkeypatch.setattr(watcher_mod.subprocess, "run", fake_run)
    assert watcher_mod.kimera_head_commit("/tmp") == ""
