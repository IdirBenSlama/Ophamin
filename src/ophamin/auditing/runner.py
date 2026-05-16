"""AuditRunner — orchestrates audit pillars against a target path.

Two surfaces:

  AuditRunner()                use every default pillar
  AuditRunner(pillars=[...])   restrict to a specific list

The runner executes each pillar in sequence (most tools are fast; parallelism
gives little real win and complicates the per-pillar error attribution).
Each pillar's PillarResult is collected into an AuditRecord — even
unavailable / errored pillars are kept in the record so the audit is
honest about what ran and what didn't.

The runner does NOT install missing tools. An unavailable pillar is reported
as ``status="unavailable"`` with an instructive message ("install via
pip install 'ophamin[audit]'"). Loud failure on actual runtime errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ophamin.auditing.audit_record import AuditRecord
from ophamin.auditing.base import AuditPillar, PillarResult
from ophamin.auditing.pillars import default_pillars


DEFAULT_SIGN_KEY = b"ophamin-audit-default-key"


class AuditRunner:
    """Orchestrates a list of AuditPillars against a single target path."""

    def __init__(
        self,
        pillars: Iterable[AuditPillar] | None = None,
        *,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> None:
        self.pillars: list[AuditPillar] = list(pillars) if pillars is not None else default_pillars()
        if not self.pillars:
            raise ValueError("AuditRunner requires at least one pillar")
        self.sign_key = sign_key

    def available_pillars(self) -> list[AuditPillar]:
        """Subset of configured pillars whose tool is installed."""
        return [p for p in self.pillars if p.is_available()]

    def run(self, target_path: str | Path, **pillar_kwargs: Any) -> AuditRecord:
        """Run every configured pillar against ``target_path``, return signed AuditRecord.

        ``pillar_kwargs`` are forwarded to each pillar's ``run`` (e.g.
        ``timeout_s=300``). A pillar that ignores a kwarg won't fail —
        each pillar declares ``**_kwargs`` in its run signature.
        """
        target = str(Path(target_path).resolve())
        results: list[PillarResult] = []
        for pillar in self.pillars:
            result = pillar.run(target, **pillar_kwargs)
            results.append(result)
        record = AuditRecord.build(
            target_path=target,
            results=results,
            reproduction_command=f"ophamin audit {target}",
        )
        record.sign(self.sign_key)
        return record
