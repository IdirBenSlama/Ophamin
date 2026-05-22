"""Ophamin Manage facet — substrate status / health.

The read side of managing Kimera: *is the substrate operational, and which
of its cognitive surfaces are reachable right now?* This is the Control
room's live backend, grounded in the real ``KimeraAdapter.probe()`` (which
imports each Kimera target — entity / pentecost / ouroboros / rosetta /
arachne / walker / gwf / piovra / astrolabe — in a subprocess and reports
per-target import health). Because Kimera is mid-development, some targets
may be healthy while others are broken; the status report shows exactly
that, rather than assuming.

``normalize_status`` is the deterministic core (probe report → management
status) — testable with no live substrate. ``substrate_status`` runs the
real probe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_status(probe_report: dict[str, Any]) -> dict[str, Any]:
    """Turn a ``KimeraAdapter.probe()`` report into a management status.

    Deterministic — no substrate needed. Summarises substrate identity,
    runner readiness, and per-target import health into a readiness verdict.
    """
    targets_raw = probe_report.get("targets", {}) or {}
    targets: list[dict[str, Any]] = []
    for name, info in sorted(targets_raw.items()):
        info = info or {}
        ok = bool(info.get("import_ok"))
        targets.append({
            "name": name,
            "import_ok": ok,
            "module": info.get("module", ""),
            "error": "" if ok else str(info.get("error", "")),
        })
    n_total = len(targets)
    n_healthy = sum(1 for t in targets if t["import_ok"])
    runner_ok = bool(probe_report.get("runner_ok"))
    return {
        "substrate": "kimera-swm",
        "kimera_repo": probe_report.get("kimera_repo", ""),
        "git_commit": probe_report.get("git_commit", ""),
        "python_exe": probe_report.get("python_exe", ""),
        "runner_ok": runner_ok,
        # "ready" = the runner imported AND at least one cognitive surface is
        # reachable. A substrate with 0 healthy targets is not operable.
        "ready": runner_ok and n_healthy > 0,
        "targets": targets,
        "n_targets": n_total,
        "n_healthy": n_healthy,
        "health_rate": (n_healthy / n_total) if n_total else 0.0,
        "error": probe_report.get("error", ""),
    }


def substrate_status(
    kimera_repo: str | Path,
    *,
    target: str = "entity",
    python_exe: str | Path | None = None,
) -> dict[str, Any]:
    """Probe the live substrate and return its management status.

    Constructs a :class:`KimeraAdapter` and runs its real ``probe()``. A
    missing/invalid repo or an un-runnable substrate is reported as
    ``runner_ok=False`` / ``ready=False`` with the error — never a crash, so
    the Control room can render a degraded state honestly.
    """
    from ophamin.seeing.substrate.kimera_adapter import (
        KimeraAdapter,
        KimeraAdapterError,
    )

    try:
        adapter = KimeraAdapter(
            kimera_repo, target=target, mode="batch", python_exe=python_exe,
        )
    except KimeraAdapterError as exc:
        return normalize_status({
            "kimera_repo": str(kimera_repo),
            "runner_ok": False,
            "error": str(exc),
        })
    report = adapter.probe()
    return normalize_status(report)
