"""Hardening tests for the cross-wheel composition flags on PrimitiveInspector
(Move K — closes gap G).

The ``with_comparing`` + ``with_instrumenting`` flags need an adapter to be
reachable, so the end-to-end runtime behaviour is exercised against a
KimeraAdapter that isn't there (loud-fail with a note in profile.notes
instead of crashing the inspection). The structural fields added to
PrimitiveProfile + the CLI plumbing are exercised directly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ophamin.inspecting import (
    PrimitiveCatalog,
    PrimitiveEntry,
    PrimitiveInspector,
    PrimitiveProfile,
)


# --- new PrimitiveProfile fields ------------------------------------------


def test_profile_has_new_comparing_fields():
    p = PrimitiveProfile(name="x", canonical_class="X")
    assert p.comparing_n_drift_events is None
    assert p.comparing_detector_name == ""
    assert p.comparing_stream_name == ""


def test_profile_has_new_instrumenting_fields():
    p = PrimitiveProfile(name="x", canonical_class="X")
    assert p.instrumenting_n_cycles_observed is None
    assert p.instrumenting_rss_peak_bytes is None


def test_profile_to_dict_includes_new_fields():
    p = PrimitiveProfile(
        name="x", canonical_class="X",
        comparing_n_drift_events=2,
        comparing_detector_name="adwin",
        comparing_stream_name="phi_value",
        instrumenting_n_cycles_observed=5,
        instrumenting_rss_peak_bytes=1024 * 1024,
    )
    d = p.to_dict()
    dyn = d["dynamic"]
    assert dyn["comparing_n_drift_events"] == 2
    assert dyn["comparing_detector_name"] == "adwin"
    assert dyn["comparing_stream_name"] == "phi_value"
    assert dyn["instrumenting_n_cycles_observed"] == 5
    assert dyn["instrumenting_rss_peak_bytes"] == 1024 * 1024


def test_profile_markdown_renders_comparing_when_set():
    p = PrimitiveProfile(
        name="x", canonical_class="X",
        comparing_n_drift_events=3,
        comparing_detector_name="adwin",
        comparing_stream_name="phi_value",
    )
    md = p.to_markdown()
    assert "Comparing (drift)" in md
    assert "adwin" in md
    assert "phi_value" in md


def test_profile_markdown_renders_instrumenting_with_rss():
    p = PrimitiveProfile(
        name="x", canonical_class="X",
        instrumenting_wall_time_p50_s=0.25,
        instrumenting_cpu_time_p50_s=0.20,
        instrumenting_n_cycles_observed=10,
        instrumenting_rss_peak_bytes=512 * 1024 * 1024,
    )
    md = p.to_markdown()
    assert "Instrumenting" in md
    assert "10 cycle(s)" in md
    assert "512 MB" in md


def test_profile_markdown_omits_dynamic_section_when_all_none():
    """No dynamic section when every dynamic field is None."""
    p = PrimitiveProfile(name="x", canonical_class="X")
    md = p.to_markdown()
    assert "## Dynamic readings" not in md


# --- inspect() kwargs ------------------------------------------------------


@pytest.fixture
def fake_kimera_repo(tmp_path) -> Path:
    """Build a minimal directory tree that passes PrimitiveLocator's
    ``looks like a Kimera repo`` check (presence of a ``kimera_swm/``
    subdirectory). No actual Kimera modules — adapter ctor still fails
    (which is exactly the failure path the composition tests want)."""
    (tmp_path / "kimera_swm").mkdir()
    (tmp_path / "kimera_swm" / "__init__.py").write_text("", encoding="utf-8")
    return tmp_path


def test_inspect_accepts_with_comparing_kwarg(fake_kimera_repo):
    """The new keyword must not be rejected by ``inspect()``."""
    inspector = PrimitiveInspector(fake_kimera_repo)
    profile = inspector.inspect(
        "Walker", with_comparing=True, with_instrumenting=True,
    )
    assert isinstance(profile, PrimitiveProfile)
    assert profile.comparing_n_drift_events is None
    assert profile.instrumenting_n_cycles_observed is None


def test_inspect_all_accepts_with_comparing_kwarg(fake_kimera_repo):
    inspector = PrimitiveInspector(fake_kimera_repo, catalog=PrimitiveCatalog([
        PrimitiveEntry(
            name="X", canonical_class="X", canonical_module="x",
            family_tags=("test",), description="x",
        ),
    ]))
    profiles = inspector.inspect_all(
        with_comparing=True, with_instrumenting=True,
    )
    assert len(profiles) == 1


def test_inspect_with_comparing_records_failure_note_on_bad_repo(fake_kimera_repo):
    """When the kimera_repo isn't a real Kimera tree, the inspector
    captures the adapter failure as a note, not raise."""
    inspector = PrimitiveInspector(fake_kimera_repo)
    profile = inspector.inspect("Walker", with_comparing=True)
    notes_text = " ".join(profile.notes)
    assert "comparing" in notes_text


def test_inspect_with_instrumenting_records_failure_note_on_bad_repo(fake_kimera_repo):
    inspector = PrimitiveInspector(fake_kimera_repo)
    profile = inspector.inspect("Walker", with_instrumenting=True)
    notes_text = " ".join(profile.notes)
    assert "instrumenting" in notes_text


# --- CLI flag plumbing -----------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", *args],
        capture_output=True, text=True,
    )


def test_cli_inspect_help_documents_new_flags():
    result = _run_cli("inspect", "--help")
    assert result.returncode == 0
    assert "--with-comparing" in result.stdout
    assert "--with-instrumenting" in result.stdout


def test_cli_inspect_all_help_documents_new_flags():
    result = _run_cli("inspect-all", "--help")
    assert result.returncode == 0
    assert "--with-comparing" in result.stdout
    assert "--with-instrumenting" in result.stdout


def test_cli_inspect_runs_with_new_flags_against_fake_repo(tmp_path):
    """End-to-end smoke: CLI accepts the flags; inspection produces a
    profile JSON + Markdown; the dynamic fields stay None because the
    adapter ctor fails (captured as notes)."""
    repo = tmp_path / "fake_repo"
    repo.mkdir()
    (repo / "kimera_swm").mkdir()
    (repo / "kimera_swm" / "__init__.py").write_text("", encoding="utf-8")
    out_dir = tmp_path / "out"
    result = _run_cli(
        "inspect", str(repo), "Walker",
        "--with-comparing", "--with-instrumenting",
        "--out-dir", str(out_dir),
    )
    assert result.returncode == 0
    json_files = list(out_dir.glob("*.json"))
    assert len(json_files) == 1
    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    dyn = payload["dynamic"]
    assert "comparing_n_drift_events" in dyn
    assert "instrumenting_n_cycles_observed" in dyn
