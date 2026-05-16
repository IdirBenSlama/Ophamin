"""PrimitiveInspector — orchestrator producing a PrimitiveProfile.

The inspector composes existing wheels:

  static introspection    — PrimitiveLocator (in this module)
  schema discovery        — seeing.discovery.SchemaMiner (only when an
                            adapter target is wired and ``with_discovery=True``)
  audit findings          — auditing.AuditRunner (only when ``with_audit=True``)
  resource profile        — instrumenting (deferred until a per-primitive
                            instrumentation contract exists; not in Phase 1)

By default (``inspect(name)``), only static introspection runs — fast,
no Kimera process spawned, no subprocess overhead. The richer modes
(``with_discovery=True``, ``with_audit=True``) opt in to the per-wheel work
explicitly.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ophamin.inspecting.catalog import KNOWN_PRIMITIVES, PrimitiveCatalog, PrimitiveEntry
from ophamin.inspecting.locator import PrimitiveLocator
from ophamin.inspecting.primitive_profile import CallerReference, PrimitiveProfile


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _kimera_git_commit(repo: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


class PrimitiveInspector:
    """Produces PrimitiveProfile for one or many primitives."""

    def __init__(
        self,
        kimera_repo: str | Path,
        *,
        catalog: PrimitiveCatalog | None = None,
    ) -> None:
        self.kimera_repo = Path(kimera_repo).expanduser().resolve()
        self.locator = PrimitiveLocator(self.kimera_repo)
        self.catalog = catalog if catalog is not None else PrimitiveCatalog()
        self.kimera_commit = _kimera_git_commit(self.kimera_repo)

    # -- single-primitive inspection ------------------------------------

    def inspect(
        self,
        name: str,
        *,
        with_discovery: bool = False,
        with_audit: bool = False,
        with_comparing: bool = False,
        with_instrumenting: bool = False,
    ) -> PrimitiveProfile:
        """Produce a PrimitiveProfile for one named primitive.

        ``name`` matches either the catalog display name or the canonical
        class name. Unknown names produce a profile with the static-only
        introspection of the *literal class name* — no catalog metadata.
        """
        entry = self.catalog.by_name(name)
        if entry is None:
            # treat ``name`` as the class name directly; build a minimal entry
            entry = PrimitiveEntry(
                name=name,
                canonical_class=name,
                canonical_module="",
                family_tags=(),
                description="(not in catalog)",
            )

        located = self.locator.locate(entry.canonical_class)

        profile = PrimitiveProfile(
            name=entry.name,
            canonical_class=entry.canonical_class,
            family_tags=entry.family_tags,
            source_file=located.source_file,
            source_line=located.source_line,
            docstring=located.docstring,
            method_names=located.method_names,
            parent_classes=located.parent_classes,
            imports=located.imports,
            n_callers=located.n_callers,
            top_callers=located.top_callers,
            notes=located.notes,
            adapter_target=entry.adapter_target,
            adapter_is_available=False,  # filled when discovery runs
            kimera_repo=str(self.kimera_repo),
            kimera_git_commit=self.kimera_commit,
            captured_at=_now_utc_iso(),
        )

        if with_discovery and entry.adapter_target:
            self._fill_discovery(profile, entry)
        if with_audit and profile.source_file:
            self._fill_audit(profile)
        if with_comparing and entry.adapter_target:
            self._fill_comparing(profile, entry)
        if with_instrumenting and entry.adapter_target:
            self._fill_instrumenting(profile, entry)

        return profile

    # -- catalog-wide survey --------------------------------------------

    def inspect_all(
        self,
        *,
        with_discovery: bool = False,
        with_audit: bool = False,
        with_comparing: bool = False,
        with_instrumenting: bool = False,
        family_filter: str | None = None,
    ) -> list[PrimitiveProfile]:
        """Inspect every catalogued primitive (optionally filtered by family)."""
        entries = list(self.catalog)
        if family_filter:
            entries = [e for e in entries if family_filter in e.family_tags]
        return [
            self.inspect(
                e.name,
                with_discovery=with_discovery,
                with_audit=with_audit,
                with_comparing=with_comparing,
                with_instrumenting=with_instrumenting,
            )
            for e in entries
        ]

    # -- dynamic-wheel integrations (best-effort, fail-soft) ------------

    def _fill_discovery(self, profile: PrimitiveProfile, entry: PrimitiveEntry) -> None:
        assert entry.adapter_target is not None, "caller must gate on adapter_target"
        """Run a small Layer A schema-mining probe for this primitive's target.

        Spawns a Kimera subprocess (via KimeraAdapter). If the construction
        fails, the failure is surfaced as a note rather than crashing the
        whole inspection — the static read is still useful.
        """
        try:
            from ophamin.seeing.discovery import SchemaMiner
            from ophamin.seeing.substrate import KimeraAdapter
        except ImportError as exc:
            profile.notes = profile.notes + (
                f"discovery skipped — import failed: {exc}",
            )
            return

        try:
            adapter = KimeraAdapter(
                self.kimera_repo,
                target=entry.adapter_target,
                mode="batch",
                batch_timeout=300.0,
            )
        except Exception as exc:  # noqa: BLE001 — adapter construction can fail loudly
            profile.notes = profile.notes + (
                f"discovery skipped — KimeraAdapter ctor failed for "
                f"target={entry.adapter_target!r}: {type(exc).__name__}: {exc}",
            )
            return
        profile.adapter_is_available = True

        # ~3 stimuli is enough to discover the field shape without spending
        # several seconds of substrate time per primitive
        stimuli = [
            "the quarterly earnings report shows steady revenue growth.",
            "memory is the deformation of the manifold by accumulated experience.",
            "Reminder: the Tuesday status meeting will be at 3pm.",
        ]
        try:
            miner = SchemaMiner(adapter)
            doc = miner.mine(targets=[entry.adapter_target], stimuli=stimuli)
        except Exception as exc:  # noqa: BLE001
            profile.notes = profile.notes + (
                f"discovery skipped — schema mining failed: "
                f"{type(exc).__name__}: {exc}",
            )
            return

        target_schema = doc.target(entry.adapter_target)
        if target_schema is None:
            profile.notes = profile.notes + (
                f"discovery returned no schema for target {entry.adapter_target!r}",
            )
            return
        profile.discovery_field_count = len(target_schema.fields)
        # first ~8 field paths as a sample for the report
        profile.discovery_field_sample = tuple(
            f.path for f in target_schema.fields[:8]
        )

    def _fill_comparing(self, profile: PrimitiveProfile, entry: PrimitiveEntry) -> None:
        """Run a small drift-detection probe against this primitive's adapter target.

        Assumes caller has verified ``entry.adapter_target`` is set.

        Streams a fixed N stimuli through the primitive, extracts the phi
        stream (or per-cycle wall-time when phi isn't present), feeds it
        through River ADWIN, and reports the detected drift-event count.
        Best-effort: if the adapter / River / extraction fails, the failure
        is captured as a note rather than crashing the inspection.
        """
        assert entry.adapter_target is not None, "caller must gate on adapter_target"
        try:
            from ophamin.comparing.drift_detection import (
                StreamDriftDetector,
                extract_phi_stream,
            )
            from ophamin.seeing.substrate import KimeraAdapter
        except ImportError as exc:
            profile.notes = profile.notes + (
                f"comparing skipped — import failed: {exc}",
            )
            return
        try:
            adapter = KimeraAdapter(
                self.kimera_repo,
                target=entry.adapter_target,
                mode="batch",
                batch_timeout=300.0,
            )
        except Exception as exc:  # noqa: BLE001
            profile.notes = profile.notes + (
                f"comparing skipped — KimeraAdapter ctor failed: "
                f"{type(exc).__name__}: {exc}",
            )
            return
        profile.adapter_is_available = True

        stimuli = [
            "the quarterly earnings report shows steady revenue growth.",
            "memory is the deformation of the manifold by accumulated experience.",
            "Reminder: the Tuesday status meeting will be at 3pm.",
            "the substrate accumulates semantic mass like Earth's geoid.",
            "an immune membrane screens inputs against intent anchors.",
        ]
        try:
            results = adapter.run_batch(stimuli)
            phi_stream = extract_phi_stream(results)
            if not phi_stream:
                profile.notes = profile.notes + (
                    "comparing skipped — no phi_value stream extractable from cycles",
                )
                return
            detector = StreamDriftDetector(
                detector_name="adwin",
                stream_name="phi_value",
            )
            scan = detector.scan(phi_stream)
            profile.comparing_n_drift_events = scan.n_events
            profile.comparing_detector_name = "adwin"
            profile.comparing_stream_name = "phi_value"
        except Exception as exc:  # noqa: BLE001
            profile.notes = profile.notes + (
                f"comparing skipped — drift detection failed: "
                f"{type(exc).__name__}: {exc}",
            )

    def _fill_instrumenting(self, profile: PrimitiveProfile, entry: PrimitiveEntry) -> None:
        """Run a small instrumented batch + harvest the resource profile.

        Wraps the KimeraAdapter in an InstrumentedSubstrate and runs N
        stimuli. Best-effort — failures captured as notes.

        Assumes caller has verified ``entry.adapter_target`` is set.
        """
        assert entry.adapter_target is not None, "caller must gate on adapter_target"
        try:
            from ophamin.instrumenting import InstrumentedSubstrate
            from ophamin.seeing.substrate import KimeraAdapter
        except ImportError as exc:
            profile.notes = profile.notes + (
                f"instrumenting skipped — import failed: {exc}",
            )
            return
        try:
            adapter = KimeraAdapter(
                self.kimera_repo,
                target=entry.adapter_target,
                mode="batch",
                batch_timeout=300.0,
            )
        except Exception as exc:  # noqa: BLE001
            profile.notes = profile.notes + (
                f"instrumenting skipped — KimeraAdapter ctor failed: "
                f"{type(exc).__name__}: {exc}",
            )
            return
        profile.adapter_is_available = True

        stimuli = [f"stimulus_{i}" for i in range(5)]
        try:
            wrapped = InstrumentedSubstrate(adapter)
            results = wrapped.run_batch(stimuli)
            last = wrapped.last_profile()
            prof: dict[str, Any] = last.to_dict() if last is not None else {}
        except Exception as exc:  # noqa: BLE001
            profile.notes = profile.notes + (
                f"instrumenting skipped — batch failed: "
                f"{type(exc).__name__}: {exc}",
            )
            return
        # InstrumentedSubstrate exposes batch_wall_time_s / batch_cpu_total_s /
        # rss_peak / process_count_max — derive a p50 from the cycle count.
        n = len(results) or 1
        wall = float(prof.get("batch_wall_time_s", 0.0))
        cpu = float(prof.get("batch_cpu_total_s", 0.0))
        profile.instrumenting_wall_time_p50_s = wall / n
        profile.instrumenting_cpu_time_p50_s = cpu / n
        profile.instrumenting_n_cycles_observed = n
        rss_peak = prof.get("rss_peak")
        if isinstance(rss_peak, (int, float)):
            profile.instrumenting_rss_peak_bytes = int(rss_peak)

    def _fill_audit(self, profile: PrimitiveProfile) -> None:
        """Run an audit (static analysis) against the primitive's source file.

        Scopes to the single .py file containing the class definition — that's
        enough to surface debt local to the primitive; cross-file audits live
        at the repo level via ``ophamin audit``.
        """
        try:
            from ophamin.auditing import AuditRunner
        except ImportError as exc:
            profile.notes = profile.notes + (
                f"audit skipped — import failed: {exc}",
            )
            return
        source_path = self.kimera_repo / profile.source_file
        if not source_path.is_file():
            profile.notes = profile.notes + (
                f"audit skipped — source file not on disk: {source_path}",
            )
            return
        try:
            runner = AuditRunner()
            record = runner.run(source_path, timeout_s=120.0)
        except Exception as exc:  # noqa: BLE001
            profile.notes = profile.notes + (
                f"audit skipped — AuditRunner failed: "
                f"{type(exc).__name__}: {exc}",
            )
            return
        profile.audit_finding_count = record.summary.total_findings
        profile.audit_severity_histogram = dict(record.summary.severity_histogram)
