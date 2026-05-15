"""Concrete audit pillars — each wraps one external static-analysis tool.

Pillars provided in Phase 1:

  ruff_pillar         fast Python linter           (system-wide install)
  bandit_pillar       security linter              (system-wide install)
  mypy_pillar         static type-checker          (system-wide install)
  vulture_pillar      dead-code detector           (`pip install ophamin[audit]`)
  radon_pillar        complexity + maintainability (`pip install ophamin[audit]`)
  pip_audit_pillar    dependency-vuln scanner      (`pip install ophamin[audit]`)

Each pillar reports ``status="unavailable"`` when its tool isn't on PATH,
rather than failing the whole audit. ``AuditRunner.default_pillars()``
returns every concrete pillar; pass an explicit list to ``AuditRunner(...)``
to restrict.
"""

from __future__ import annotations

from ophamin.auditing.pillars.bandit_pillar import BanditPillar
from ophamin.auditing.pillars.mypy_pillar import MypyPillar
from ophamin.auditing.pillars.pip_audit_pillar import PipAuditPillar
from ophamin.auditing.pillars.radon_pillar import RadonPillar
from ophamin.auditing.pillars.ruff_pillar import RuffPillar
from ophamin.auditing.pillars.vulture_pillar import VulturePillar

DEFAULT_PILLAR_CLASSES = (
    RuffPillar,
    BanditPillar,
    MypyPillar,
    VulturePillar,
    RadonPillar,
    PipAuditPillar,
)


def default_pillars() -> list:
    """Instantiate every concrete pillar in declaration order."""
    return [cls() for cls in DEFAULT_PILLAR_CLASSES]


__all__ = [
    "DEFAULT_PILLAR_CLASSES",
    "BanditPillar",
    "MypyPillar",
    "PipAuditPillar",
    "RadonPillar",
    "RuffPillar",
    "VulturePillar",
    "default_pillars",
]
