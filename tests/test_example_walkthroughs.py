"""Smoke tests for the concept walkthroughs under ``examples/``.

Three walkthroughs ship under ``examples/walkthrough_*.py``, one per
load-bearing RFC-0002 phase (E2 / E4 / E8). Each:

* Has a rich docstring explaining the concept;
* Runs end-to-end as ``python examples/walkthrough_X.py``;
* Asserts its own invariants via ``assert`` statements at the bottom
  of ``main()``;
* Prints rich annotated output for the reader.

These tests run each walkthrough as a subprocess (so the
``if __name__ == "__main__":`` block fires) and assert exit code 0
+ the expected closing-line marker in stdout. Failures here mean a
walkthrough's behaviour drifted away from its documented contract
— a CI gate that keeps the consumer-facing demos honest.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


_WALKTHROUGHS = (
    "walkthrough_fwer_correction.py",
    "walkthrough_reproducibility_audit.py",
    "walkthrough_api_stability.py",
    "walkthrough_cross_framework.py",
)


@pytest.mark.parametrize("walkthrough", _WALKTHROUGHS)
def test_walkthrough_runs_end_to_end_with_exit_zero(walkthrough: str) -> None:
    """Each walkthrough must run as `python examples/walkthrough_X.py`
    with exit code 0. The script's own assertions inside main() are
    the load-bearing checks; this test just shells out + verifies the
    process exits cleanly."""
    script = _EXAMPLES_DIR / walkthrough
    assert script.is_file(), f"walkthrough missing: {script}"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env={
            "PYTHONPATH": str(_EXAMPLES_DIR.parent / "src"),
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(Path.home()),
        },
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Walkthrough {walkthrough!r} exited with code {result.returncode}:\n"
        f"  stdout (last 500 chars): {result.stdout[-500:]}\n"
        f"  stderr (last 500 chars): {result.stderr[-500:]}"
    )


@pytest.mark.parametrize("walkthrough", _WALKTHROUGHS)
def test_walkthrough_emits_closing_success_marker(walkthrough: str) -> None:
    """Each walkthrough ends with a ``✓ ... complete`` line. The marker
    pins that all in-script invariants passed AND main() ran to
    completion (no silent early-return / exception-swallowing)."""
    script = _EXAMPLES_DIR / walkthrough
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env={
            "PYTHONPATH": str(_EXAMPLES_DIR.parent / "src"),
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(Path.home()),
        },
        timeout=120,
    )
    assert "✓" in result.stdout and "complete" in result.stdout, (
        f"Walkthrough {walkthrough!r} didn't emit the closing-success line "
        f"(expected '✓ ... complete' in stdout). Got tail:\n"
        f"  {result.stdout[-300:]}"
    )


def test_examples_readme_indexes_every_walkthrough() -> None:
    """Drift detector: the examples/README.md must reference each
    walkthrough script. When a new walkthrough is added but the README
    isn't updated, this test catches it at PR time."""
    readme = _EXAMPLES_DIR / "README.md"
    assert readme.is_file(), "examples/README.md missing"
    content = readme.read_text(encoding="utf-8")
    missing = [w for w in _WALKTHROUGHS if w not in content]
    assert not missing, (
        f"examples/README.md doesn't reference these walkthroughs: {missing}. "
        "Add a row to the 'Concept walkthroughs' section."
    )
