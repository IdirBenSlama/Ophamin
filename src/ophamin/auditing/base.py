"""The audit-pillar contract — Finding, FindingSeverity, PillarResult, AuditPillar.

A pillar wraps one external static-analysis tool. The contract is small:

  * ``name`` and ``tool_name`` identify the pillar (e.g. "ruff", "bandit")
  * ``is_available()`` reports whether the underlying binary is installed
  * ``run(target_path)`` returns a ``PillarResult`` carrying the findings + raw output

Findings are normalised across tools — every tool's output is parsed into the
same ``Finding`` dataclass — so downstream code (aggregation, reporting,
threshold-mode claims) doesn't need to know which pillar produced what.
"""

from __future__ import annotations

import abc
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class FindingSeverity(str, Enum):
    """Normalised severity across heterogeneous tools.

    Each pillar maps its tool's native severity scale onto these five buckets;
    the mapping is documented per-pillar.
    """

    CRITICAL = "critical"     # tool says this is must-fix
    HIGH = "high"             # tool says this is should-fix
    MEDIUM = "medium"         # tool says this is consider-fixing
    LOW = "low"               # tool says this is a style nit
    INFO = "info"             # tool says this is purely informational


@dataclass(frozen=True)
class Finding:
    """One static-analysis finding, normalised across tools.

    Every field except ``path`` and ``message`` may be empty if the producing
    tool doesn't carry it — but the dataclass shape is stable so downstream
    code can rely on it.
    """

    pillar_name: str            # which audit pillar produced this finding
    rule_id: str                # tool-native rule code (e.g. "E501", "B101")
    severity: FindingSeverity
    message: str
    path: str                   # path to the file the finding is about
    line: int = 0
    column: int = 0
    extra: dict[str, Any] = field(default_factory=dict)  # tool-specific payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "pillar_name": self.pillar_name,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "extra": self.extra,
        }


@dataclass(frozen=True)
class PillarResult:
    """One pillar's full output."""

    pillar_name: str
    tool_name: str
    tool_version: str
    status: str                          # "ok" | "unavailable" | "error"
    target_path: str
    findings: tuple[Finding, ...] = ()
    raw_stdout_bytes: int = 0            # for forensics — we don't keep the raw text in-memory
    raw_stderr_bytes: int = 0
    exit_code: int | None = None
    wall_time_s: float = 0.0
    error_message: str = ""              # only when status != "ok"

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def severity_histogram(self) -> dict[str, int]:
        """``{severity_value: count}`` — bucket counts across all findings."""
        return dict(Counter(f.severity.value for f in self.findings))

    def per_file_count(self, top_n: int = 10) -> list[tuple[str, int]]:
        """Top-N files by finding count."""
        counter = Counter(f.path for f in self.findings)
        return counter.most_common(top_n)

    def per_rule_count(self, top_n: int = 10) -> list[tuple[str, int]]:
        counter = Counter(f.rule_id for f in self.findings)
        return counter.most_common(top_n)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pillar_name": self.pillar_name,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "status": self.status,
            "target_path": self.target_path,
            "finding_count": self.finding_count,
            "findings": [f.to_dict() for f in self.findings],
            "severity_histogram": self.severity_histogram(),
            "per_file_top10": self.per_file_count(10),
            "per_rule_top10": self.per_rule_count(10),
            "raw_stdout_bytes": self.raw_stdout_bytes,
            "raw_stderr_bytes": self.raw_stderr_bytes,
            "exit_code": self.exit_code,
            "wall_time_s": self.wall_time_s,
            "error_message": self.error_message,
        }


# --------------------------------------------------------------------------
# AuditPillar — abstract base
# --------------------------------------------------------------------------


class AuditPillar(abc.ABC):
    """Wraps one external static-analysis tool as an audit pillar.

    A subclass implements ``tool_binary`` (the CLI name to look up on PATH),
    ``tool_version`` (a way to ask the tool its version), and ``run`` (the
    actual invocation + parse). Tool absence is reported as
    ``status="unavailable"`` — never silently skipped.
    """

    #: human-readable pillar name, e.g. "ruff"
    name: str = ""
    #: the CLI binary name to look up on PATH, e.g. "ruff"
    tool_binary: str = ""

    def __init__(self) -> None:
        if not self.name or not self.tool_binary:
            raise ValueError(
                f"AuditPillar subclass {type(self).__name__} must set "
                f"`name` and `tool_binary` class attributes"
            )

    @classmethod
    def _venv_binary(cls) -> str | None:
        """Look for ``cls.tool_binary`` next to the running Python interpreter.

        When Ophamin is invoked via ``.venv/bin/python -m ophamin.cli ...``
        without first activating the venv, ``shutil.which`` doesn't see
        venv-local binaries (the venv's bin/ isn't on PATH). Fall through
        to inspecting ``sys.executable``'s directory so audit pillars that
        the user installed via ``pip install -e '.[audit]'`` work without
        requiring an explicit venv activation.
        """
        import os
        import sys
        bin_dir = os.path.dirname(sys.executable)
        candidate = os.path.join(bin_dir, cls.tool_binary)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
        return None

    @classmethod
    def resolved_binary(cls) -> str | None:
        """Resolve the tool binary — venv-local first, then PATH."""
        local = cls._venv_binary()
        if local:
            return local
        return shutil.which(cls.tool_binary)

    @classmethod
    def is_available(cls) -> bool:
        """Is the wrapped tool resolvable (venv-local OR on PATH)?"""
        return cls.resolved_binary() is not None

    def tool_version(self, timeout_s: float = 10.0) -> str:
        """Best-effort ``<tool> --version`` capture; empty string on failure."""
        binary = self.resolved_binary()
        if binary is None:
            return ""
        try:
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
        return (result.stdout + result.stderr).strip().split("\n")[0]

    def unavailable_result(self, target_path: str) -> PillarResult:
        """Standard `unavailable` result for when the tool isn't installed."""
        return PillarResult(
            pillar_name=self.name,
            tool_name=self.tool_binary,
            tool_version="",
            status="unavailable",
            target_path=str(target_path),
            error_message=(
                f"{self.tool_binary} is not installed on PATH. "
                f"Install via pip install 'ophamin[audit]'."
            ),
        )

    def error_result(
        self,
        target_path: str,
        message: str,
        *,
        exit_code: int | None = None,
        wall_time_s: float = 0.0,
        raw_stdout_bytes: int = 0,
        raw_stderr_bytes: int = 0,
    ) -> PillarResult:
        return PillarResult(
            pillar_name=self.name,
            tool_name=self.tool_binary,
            tool_version=self.tool_version(),
            status="error",
            target_path=str(target_path),
            error_message=message,
            exit_code=exit_code,
            wall_time_s=wall_time_s,
            raw_stdout_bytes=raw_stdout_bytes,
            raw_stderr_bytes=raw_stderr_bytes,
        )

    @abc.abstractmethod
    def run(self, target_path: str | Path, **kwargs: Any) -> PillarResult:
        """Run the tool against ``target_path`` and return a PillarResult.

        Pillars MUST handle missing-tool cleanly via ``unavailable_result``
        and runtime failures via ``error_result``. Never silently swallow
        a failure.
        """
        ...
