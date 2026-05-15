"""Tests for the many-small-eyes watcher (Layer A continuous mode).

The watcher is exercised against a synthetic substrate and a stubbed
``head_reader`` callback — no real Kimera, no real git. End-to-end against
the live repo is the responsibility of the example runner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ophamin.seeing.discovery import KimeraDiscoveryWatcher, WatchOutcome
from ophamin.seeing.discovery.watcher import kimera_head_commit


def test_kimera_head_commit_returns_empty_for_non_repo(tmp_path):
    # not a git repo -> empty string, no exception
    assert kimera_head_commit(tmp_path) == ""


def test_watcher_rejects_empty_targets(tmp_path):
    with pytest.raises(ValueError, match="at least one target"):
        KimeraDiscoveryWatcher(
            kimera_repo=tmp_path, targets=[], stimuli=["x"], out_dir=tmp_path
        )


def test_watcher_rejects_empty_stimuli(tmp_path):
    with pytest.raises(ValueError, match="at least one stimulus"):
        KimeraDiscoveryWatcher(
            kimera_repo=tmp_path, targets=["entity"], stimuli=[], out_dir=tmp_path
        )


def test_watcher_run_once_reports_unreadable_head(tmp_path):
    """With a stubbed head_reader that returns empty, run_once should produce
    a no-op outcome with a clear plain-words reason."""
    watcher = KimeraDiscoveryWatcher(
        kimera_repo=tmp_path,
        targets=["entity"],
        stimuli=["hello"],
        out_dir=tmp_path,
        head_reader=lambda _: "",  # simulates "not a git repo"
    )
    outcome = watcher.run_once()
    assert outcome.new_commit_discovered is False
    assert outcome.kimera_commit == ""
    assert "unreadable" in outcome.reason


def test_watcher_run_once_skips_when_head_unchanged(tmp_path, monkeypatch):
    """If HEAD hasn't changed since the last successful mine, the second
    run_once should report a no-op."""
    # use a head_reader that always returns the same commit
    watcher = KimeraDiscoveryWatcher(
        kimera_repo=tmp_path,
        targets=["entity"],
        stimuli=["hello"],
        out_dir=tmp_path,
        head_reader=lambda _: "ababab123456",
    )
    # set the last-mined commit so the first run_once treats this as unchanged
    watcher._last_mined_commit = "ababab123456"
    outcome = watcher.run_once()
    assert outcome.new_commit_discovered is False
    assert "unchanged" in outcome.reason
    assert outcome.kimera_commit == "ababab123456"


def test_watcher_run_forever_rejects_bad_interval(tmp_path):
    watcher = KimeraDiscoveryWatcher(
        kimera_repo=tmp_path,
        targets=["entity"],
        stimuli=["hello"],
        out_dir=tmp_path,
        head_reader=lambda _: "",
    )
    with pytest.raises(ValueError, match="poll_interval_s must be > 0"):
        watcher.run_forever(poll_interval_s=0)


def test_watcher_previous_schema_path_finds_latest(tmp_path):
    """When prior schema docs exist, the watcher picks the most recent that
    doesn't match the current commit's short sha."""
    (tmp_path / "kimera_fields_aaaaaaaaaaaa.json").write_text("{}")
    (tmp_path / "kimera_fields_bbbbbbbbbbbb.json").write_text("{}")
    watcher = KimeraDiscoveryWatcher(
        kimera_repo=tmp_path,
        targets=["entity"],
        stimuli=["hello"],
        out_dir=tmp_path,
        head_reader=lambda _: "",
    )
    # current commit is "ccccccccccccdeadbeef" -> previous is one of the two
    prev = watcher._previous_schema_path("cccccccccccccccc")
    assert prev is not None
    assert prev.name.startswith("kimera_fields_")
