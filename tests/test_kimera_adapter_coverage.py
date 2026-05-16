"""Coverage-closure tests for KimeraAdapter constructor + helper paths (Phase S2).

The adapter's full subprocess + batch pipeline requires a real Kimera repo
and is exercised by the integration tests that run only when one is available
on disk. This file pins the loud-failure paths in the constructor + the
non-subprocess helper methods, which are pure-Python and reachable without
spinning a Kimera python interpreter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ophamin.seeing.substrate.kimera_adapter import (
    KIMERA_TARGETS,
    KimeraAdapter,
    KimeraAdapterError,
)


# Fixture: a fake Kimera repo with the minimum directory layout that the
# adapter's existence checks accept (kimera_swm/__init__.py + a .venv/bin/python).
@pytest.fixture
def fake_kimera_repo(tmp_path: Path) -> Path:
    """Build a synthetic 'Kimera repo' that passes the adapter's path checks
    but does NOT have a runnable python — every adapter method that actually
    spawns a subprocess will fail (which is fine: this file tests the
    pre-subprocess validation paths)."""
    (tmp_path / "kimera_swm").mkdir()
    (tmp_path / "kimera_swm" / "__init__.py").touch()
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    python = venv_bin / "python"
    # an empty file is enough — adapter only needs the path to exist
    python.write_text("#!/usr/bin/env true\n")
    python.chmod(0o755)
    return tmp_path


# ----------------------------------------------------------------------------
# Constructor validation — every loud-failure branch
# ----------------------------------------------------------------------------


def test_unknown_target_raises(fake_kimera_repo: Path) -> None:
    with pytest.raises(KimeraAdapterError, match="unknown target"):
        KimeraAdapter(kimera_repo=fake_kimera_repo, target="nonexistent_arm")


def test_unknown_mode_raises(fake_kimera_repo: Path) -> None:
    with pytest.raises(KimeraAdapterError, match="mode must be"):
        KimeraAdapter(
            kimera_repo=fake_kimera_repo,
            target=next(iter(KIMERA_TARGETS)),
            mode="invalid",  # type: ignore[arg-type]
        )


def test_missing_repo_raises(tmp_path: Path) -> None:
    missing = tmp_path / "definitely-not-a-repo"
    with pytest.raises(KimeraAdapterError, match="not found"):
        KimeraAdapter(kimera_repo=missing, target=next(iter(KIMERA_TARGETS)))


def test_repo_without_kimera_swm_dir_raises(tmp_path: Path) -> None:
    # exists but not Kimera-shaped
    with pytest.raises(KimeraAdapterError, match="does not look like a Kimera repo"):
        KimeraAdapter(kimera_repo=tmp_path, target=next(iter(KIMERA_TARGETS)))


def test_missing_python_exe_raises(fake_kimera_repo: Path, tmp_path: Path) -> None:
    """Explicit python_exe pointing at a non-existent path raises."""
    missing_python = tmp_path / "definitely-not-python"
    with pytest.raises(KimeraAdapterError, match="python interpreter not found"):
        KimeraAdapter(
            kimera_repo=fake_kimera_repo,
            target=next(iter(KIMERA_TARGETS)),
            python_exe=missing_python,
        )


def test_missing_runner_script_raises(fake_kimera_repo: Path, tmp_path: Path) -> None:
    """Explicit runner_script pointing at a non-existent path raises."""
    missing_runner = tmp_path / "definitely-not-a-runner.py"
    with pytest.raises(KimeraAdapterError, match="runner script not found"):
        KimeraAdapter(
            kimera_repo=fake_kimera_repo,
            target=next(iter(KIMERA_TARGETS)),
            runner_script=missing_runner,
        )


# ----------------------------------------------------------------------------
# Non-subprocess helper methods
# ----------------------------------------------------------------------------


def test_reset_is_noop(fake_kimera_repo: Path) -> None:
    """reset() is documented as a no-op for both modes."""
    adapter = KimeraAdapter(kimera_repo=fake_kimera_repo, target=next(iter(KIMERA_TARGETS)))
    # returns None; no side effects to observe; idempotent on repeated calls
    assert adapter.reset() is None
    assert adapter.reset() is None


def test_write_runner_template_emits_runner_source(tmp_path: Path) -> None:
    """The static template dumper writes the same runner source the adapter
    bundles itself, so a downstream consumer can edit + reuse it."""
    out = tmp_path / "runner.py"
    written = KimeraAdapter.write_runner_template(out)
    assert written == out
    assert out.is_file()
    text = out.read_text()
    # The bundled runner is a small script. Sanity-check that what came out
    # is a Python source file, not an empty or corrupted artefact.
    assert text.lstrip().startswith(("\"", "'", "#", "from", "import"))
    assert len(text) > 100  # not empty


def test_adapter_constructs_with_default_runner(fake_kimera_repo: Path) -> None:
    """When no runner_script is passed, the adapter materialises the bundled
    runner to a temp file and uses that — _owns_runner is True."""
    adapter = KimeraAdapter(kimera_repo=fake_kimera_repo, target=next(iter(KIMERA_TARGETS)))
    assert adapter._owns_runner is True
    assert adapter.runner_script.exists()


def test_adapter_accepts_env_override(fake_kimera_repo: Path) -> None:
    """The ``env`` argument captures arbitrary extra-environment keys."""
    adapter = KimeraAdapter(
        kimera_repo=fake_kimera_repo,
        target=next(iter(KIMERA_TARGETS)),
        env={"KIMERA_GPU_ACCELERATION_ENABLED": "1"},
    )
    assert adapter.env["KIMERA_GPU_ACCELERATION_ENABLED"] == "1"


def test_adapter_defaults_env_to_empty_dict(fake_kimera_repo: Path) -> None:
    """env defaults to an empty dict, not None — callers can mutate safely."""
    adapter = KimeraAdapter(kimera_repo=fake_kimera_repo, target=next(iter(KIMERA_TARGETS)))
    assert adapter.env == {}
    # mutating doesn't leak into the next instance
    adapter.env["FOO"] = "bar"
    other = KimeraAdapter(kimera_repo=fake_kimera_repo, target=next(iter(KIMERA_TARGETS)))
    assert other.env == {}


def test_adapter_default_mode_is_subprocess(fake_kimera_repo: Path) -> None:
    """The default mode is 'subprocess'; callers opt into batch explicitly."""
    adapter = KimeraAdapter(kimera_repo=fake_kimera_repo, target=next(iter(KIMERA_TARGETS)))
    assert adapter.mode == "subprocess"


def test_adapter_subprocess_mode_accepted(fake_kimera_repo: Path) -> None:
    adapter = KimeraAdapter(
        kimera_repo=fake_kimera_repo,
        target=next(iter(KIMERA_TARGETS)),
        mode="subprocess",
    )
    assert adapter.mode == "subprocess"


def test_adapter_records_timeouts(fake_kimera_repo: Path) -> None:
    """Custom timeouts are coerced to float and surfaced as attributes."""
    adapter = KimeraAdapter(
        kimera_repo=fake_kimera_repo,
        target=next(iter(KIMERA_TARGETS)),
        timeout=123,
        batch_timeout=456,
    )
    assert isinstance(adapter.timeout, float)
    assert isinstance(adapter.batch_timeout, float)
    assert adapter.timeout == 123.0
    assert adapter.batch_timeout == 456.0
