"""Wheel 4 — Auditing.

The inner-triad wheel that observes *code structure* rather than substrate
behaviour. Where ``seeing/`` reads what Kimera *emits* (field schemas, cycle
results) and ``instrumenting/`` reads what Kimera *costs* (CPU/RSS/threads),
``auditing/`` reads what Kimera *is* — the static shape of the source tree:
lint, security, type-safety, dead code, complexity, dependency hygiene.

The wheel orchestrates existing tools rather than re-implementing them
(*wrap, don't rewrite*). Each tool is wrapped as an ``AuditPillar`` —
roughly analogous to the existing six measuring-pillars (O · F · A · M · I · N)
but for engineering-debt observation instead of statistical inference:

  ruff_pillar       fast linter (replaces flake8 / pylint / isort)
  bandit_pillar     security linter
  mypy_pillar       static type-checker
  vulture_pillar    dead-code detector
  radon_pillar      cyclomatic complexity + maintainability index
  pip_audit_pillar  dependency-vulnerability scanner

A pillar whose tool is not installed reports ``status="unavailable"`` rather
than failing the whole audit — the framework reports honestly which scans
ran. ``pip install 'ophamin[audit]'`` brings in every tool.

Output:

  AuditRecord       signed, content-addressed descriptive record of one audit
                    run (analogous to EmpiricalProofRecord but descriptive
                    by default — no falsifiable claim required). Carries
                    every PillarResult + a summary.
  Finding           one finding from one tool, normalised across tools.
  PillarResult      one pillar's full output: findings list + counts +
                    distributions + the raw tool output (for forensic recovery).

The ``audit`` CLI:

  ophamin audit <path>                run every available audit pillar
  ophamin audit <path> --pillars=ruff,bandit  only the named pillars
  ophamin audit <path> --out audit.json  write the signed record
"""

from __future__ import annotations

from ophamin.auditing.audit_record import AuditRecord, AuditSummary
from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult
from ophamin.auditing.runner import AuditRunner

__all__ = [
    "AuditPillar",
    "AuditRecord",
    "AuditRunner",
    "AuditSummary",
    "Finding",
    "FindingSeverity",
    "PillarResult",
]
