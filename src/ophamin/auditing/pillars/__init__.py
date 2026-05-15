"""Concrete audit pillars — each wraps one external static-analysis tool.

File-scope pillars (Phase 1) — work on any source path:

  ruff_pillar         fast Python linter           (system-wide install)
  bandit_pillar       security linter              (system-wide install)
  mypy_pillar         static type-checker          (system-wide install)
  vulture_pillar      dead-code detector           (`pip install ophamin[audit]`)
  radon_pillar        complexity + maintainability (`pip install ophamin[audit]`)
  pip_audit_pillar    dependency-vuln scanner      (`pip install ophamin[audit]`)

Project-scope pillars (Phase 2 — PR #9 from plugin catalog) — require the
target path to be a project root with pyproject.toml:

  deptry_pillar       declared-vs-imported deps    (`pip install ophamin[audit]`)
  fawltydeps_pillar   undeclared / unused deps     (`pip install ophamin[audit]`)

Each pillar reports ``status="unavailable"`` when its tool isn't on PATH,
``status="errored"`` when the target doesn't fit (e.g. a project-scope
pillar on a non-project target), or ``status="ok"`` with findings otherwise.
``DEFAULT_PILLAR_CLASSES`` excludes the project-scope ones so file-scope
audits don't produce noisy "errored" lines; opt in with
``--pillars=...,deptry,fawltydeps``.
"""

from __future__ import annotations

from ophamin.auditing.pillars.bandit_pillar import BanditPillar
from ophamin.auditing.pillars.coverage_pillar import CoveragePillar
from ophamin.auditing.pillars.deptry_pillar import DeptryPillar
from ophamin.auditing.pillars.fawltydeps_pillar import FawltyDepsPillar
from ophamin.auditing.pillars.interrogate_pillar import InterrogatePillar
from ophamin.auditing.pillars.mypy_pillar import MypyPillar
from ophamin.auditing.pillars.pip_audit_pillar import PipAuditPillar
from ophamin.auditing.pillars.pylint_pillar import PylintPillar
from ophamin.auditing.pillars.radon_pillar import RadonPillar
from ophamin.auditing.pillars.refurb_pillar import RefurbPillar
from ophamin.auditing.pillars.ruff_pillar import RuffPillar
from ophamin.auditing.pillars.semgrep_pillar import SemgrepPillar
from ophamin.auditing.pillars.vulture_pillar import VulturePillar

#: file-scope pillars — work on any source path. Default in audit runs.
#: Pylint is intentionally NOT in defaults (slow + opinionated; opt-in
#: via ``--pillars=...,pylint``). Refurb is fast enough for default.
DEFAULT_PILLAR_CLASSES = (
    RuffPillar,
    BanditPillar,
    MypyPillar,
    VulturePillar,
    RadonPillar,
    PipAuditPillar,
    InterrogatePillar,
    RefurbPillar,
)

#: deeper file-scope pillars — slower but richer. Opt-in via --pillars.
DEEP_PILLAR_CLASSES = (
    PylintPillar,
    SemgrepPillar,
)

#: project-scope pillars — require the target to be a project-root directory
#: with pyproject.toml. Opt-in via ``--pillars=...,deptry,fawltydeps``.
PROJECT_PILLAR_CLASSES = (
    DeptryPillar,
    FawltyDepsPillar,
    CoveragePillar,
)


def default_pillars() -> list:
    """Instantiate every file-scope pillar in declaration order."""
    return [cls() for cls in DEFAULT_PILLAR_CLASSES]


def project_pillars() -> list:
    """Instantiate every project-scope pillar."""
    return [cls() for cls in PROJECT_PILLAR_CLASSES]


def deep_pillars() -> list:
    """Instantiate every deeper opt-in file-scope pillar."""
    return [cls() for cls in DEEP_PILLAR_CLASSES]


def all_pillars() -> list:
    """Instantiate every pillar — file-scope, deep, and project-scope."""
    return default_pillars() + deep_pillars() + project_pillars()


__all__ = [
    "DEFAULT_PILLAR_CLASSES",
    "DEEP_PILLAR_CLASSES",
    "PROJECT_PILLAR_CLASSES",
    "BanditPillar",
    "CoveragePillar",
    "DeptryPillar",
    "FawltyDepsPillar",
    "InterrogatePillar",
    "MypyPillar",
    "PipAuditPillar",
    "PylintPillar",
    "RadonPillar",
    "RefurbPillar",
    "RuffPillar",
    "SemgrepPillar",
    "VulturePillar",
    "all_pillars",
    "deep_pillars",
    "default_pillars",
    "project_pillars",
]
