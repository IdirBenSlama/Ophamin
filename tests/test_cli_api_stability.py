"""In-process tests for ``cmd_api_stability`` (the handler behind
``ophamin api-stability {list,check}``).

The earlier subprocess-based smoke tests exercised the CLI end-to-end
but coverage.py at the parent test process can't see branches executed
inside `subprocess.run(...)` children. To restore the coverage gate
without losing the smoke signal, this module:

* invokes ``cmd_api_stability`` **directly with constructed
  ``argparse.Namespace`` objects** for the branch-coverage payoff;
* keeps a single subprocess test at the end as an integration smoke
  for argparse dispatch.

Three exit-code contracts are pinned:

  ``list``           → 0 always.
  ``check <ok>``     → 0 when no @Deprecated / @Internal Ophamin
                       imports are reachable in the target directory.
  ``check <bad>``    → 2 when the target directory doesn't exist.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

# Importing the handler directly — this is the load-bearing change
# vs the previous subprocess-only approach. Coverage.py now sees every
# branch under cmd_api_stability when these tests run.
from ophamin.cli import cmd_api_stability


def _ns(**kwargs: Any) -> argparse.Namespace:
    """Helper: build an argparse.Namespace from kwargs.

    Defaults match what argparse would populate from the parser
    definitions in `ophamin.cli` — keeps each test focused on the
    handler's actual branch logic rather than rebuilding argparse.
    """
    return argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# list subcommand
# ---------------------------------------------------------------------------


class TestList:
    def test_list_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = _ns(subcommand="list", json=False)
        rc = cmd_api_stability(args)
        assert rc == 0

    def test_list_shows_stable_group(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = _ns(subcommand="list", json=False)
        cmd_api_stability(args)
        output = capsys.readouterr().out
        assert "## Stable" in output
        # The Stable group must be populated; sanity-check the framework's
        # most-load-bearing symbols.
        assert "EmpiricalProofRecord" in output
        assert "CampaignRecord" in output
        assert "run_campaign" in output
        assert "apply_correction" in output

    def test_list_json_emits_parseable_structure(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = _ns(subcommand="list", json=True)
        rc = cmd_api_stability(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        # Every tier should be a key with a list value.
        assert isinstance(payload.get("Stable"), list)
        assert isinstance(payload.get("Provisional"), list)
        assert isinstance(payload.get("Deprecated"), list)
        assert isinstance(payload.get("Internal"), list)
        # Each Stable entry carries the StabilityInfo fields.
        assert payload["Stable"], "Stable list should be non-empty"
        first = payload["Stable"][0]
        for field in ("name", "since", "removal_version", "replacement", "notes"):
            assert field in first


# ---------------------------------------------------------------------------
# check subcommand — clean directory paths
# ---------------------------------------------------------------------------


class TestCheckClean:
    def test_check_empty_directory_exits_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "harmless.py").write_text(
            "x = 1\n"
            "def foo():\n"
            "    return x + 1\n"
        )
        args = _ns(subcommand="check", directory=str(tmp_path), json=False)
        rc = cmd_api_stability(args)
        assert rc == 0
        output = capsys.readouterr().out
        assert "OK" in output or "0 deprecated" in output.lower()

    def test_check_only_stable_imports_exits_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "consumer.py").write_text(
            dedent(
                """
                from ophamin import EmpiricalProofRecord, Claim, Threshold
                from ophamin.campaign import run_campaign
                from ophamin.comparing.fwer import holm_bonferroni
                """
            ).lstrip()
        )
        args = _ns(subcommand="check", directory=str(tmp_path), json=False)
        rc = cmd_api_stability(args)
        assert rc == 0

    def test_check_json_clean_emits_empty_list(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "empty.py").write_text("# nothing here\n")
        args = _ns(subcommand="check", directory=str(tmp_path), json=True)
        rc = cmd_api_stability(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload == []

    def test_check_skips_non_python_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "README.md").write_text(
            "from ophamin._stability import Stable  # this is markdown, not Python"
        )
        args = _ns(subcommand="check", directory=str(tmp_path), json=False)
        rc = cmd_api_stability(args)
        assert rc == 0

    def test_check_ignores_non_ophamin_imports(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "uses_other.py").write_text(
            "import json\n"
            "from pathlib import Path\n"
            "from collections import deque\n"
        )
        args = _ns(subcommand="check", directory=str(tmp_path), json=False)
        rc = cmd_api_stability(args)
        assert rc == 0


# ---------------------------------------------------------------------------
# check subcommand — failure modes
# ---------------------------------------------------------------------------


class TestCheckErrors:
    def test_check_nonexistent_directory_exits_two(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _ns(
            subcommand="check",
            directory="/nonexistent/path/that/should/not/exist/xyz",
            json=False,
        )
        rc = cmd_api_stability(args)
        assert rc == 2
        captured = capsys.readouterr()
        assert "is not a directory" in captured.err

    def test_unknown_subcommand_exits_64(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _ns(subcommand="bogus")
        rc = cmd_api_stability(args)
        assert rc == 64
        captured = capsys.readouterr()
        assert "unknown subcommand" in captured.err

    def test_check_handles_syntactically_invalid_python_gracefully(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The AST walker should skip files it can't parse; one bad file
        # must not abort the whole audit.
        (tmp_path / "bad.py").write_text("this is not valid Python (")
        (tmp_path / "good.py").write_text("import os\n")
        args = _ns(subcommand="check", directory=str(tmp_path), json=False)
        rc = cmd_api_stability(args)
        assert rc == 0  # bad.py skipped; good.py has no ophamin imports


# ---------------------------------------------------------------------------
# Self-audit: the framework's own tests/ must report 0 violations
# ---------------------------------------------------------------------------


def test_check_on_frameworks_own_tests_directory_is_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The framework's own test corpus must not import any @Deprecated
    or @Internal Ophamin symbol — the API stability contract applies
    transitively to tests, too."""
    tests_dir = Path(__file__).parent
    args = _ns(subcommand="check", directory=str(tests_dir), json=False)
    rc = cmd_api_stability(args)
    output = capsys.readouterr().out
    assert rc == 0, (
        f"Framework's own tests/ imports a non-Stable Ophamin symbol:\n"
        f"  stdout: {output}\n"
    )


# ---------------------------------------------------------------------------
# Subprocess integration smoke (one test, for argparse dispatch path)
# ---------------------------------------------------------------------------


def test_argparse_dispatches_list_subcommand_via_subprocess() -> None:
    """Final smoke: confirm `python -m ophamin.cli api-stability list`
    actually wires through argparse to the handler. Covers the
    parser-setup side of the contract that the in-process tests skip."""
    result = subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "api-stability", "list"],
        capture_output=True,
        text=True,
        env={
            "PYTHONPATH": str(Path(__file__).parent.parent / "src"),
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(Path.home()),
        },
    )
    assert result.returncode == 0, result.stderr
    assert "## Stable" in result.stdout
