"""PrimitiveProfile — unified per-primitive view across every Ophamin wheel.

A profile is the *static + dynamic* read of one primitive: where its code
lives, what its public surface is (methods, docstring), who calls it inside
the Kimera repo, and (optionally) what the dynamic wheels have observed —
schema mining (seeing.discovery), audit findings (auditing), runtime
resource use (instrumenting).

The profile is JSON-serialisable so it round-trips through the reporting
wheel into HTML / Markdown / LaTeX academic-review output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CallerReference:
    """One file that mentions this primitive's class/module."""

    file: str            # path relative to the Kimera repo root
    line: int            # first line where the name appears
    context: str         # ~80 chars of context around that line

    def to_dict(self) -> dict[str, Any]:
        return {"file": self.file, "line": self.line, "context": self.context}


@dataclass
class PrimitiveProfile:
    """Unified per-primitive profile — every wheel's read aggregated."""

    name: str
    canonical_class: str
    family_tags: tuple[str, ...] = ()

    # --- static introspection -----------------------------------------
    source_file: str = ""              # path relative to the Kimera repo root
    source_line: int = 0
    docstring: str = ""
    method_names: tuple[str, ...] = ()
    parent_classes: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    n_callers: int = 0
    top_callers: tuple[CallerReference, ...] = ()
    notes: tuple[str, ...] = ()        # diagnostics ("could not locate class def", etc.)

    # --- adapter linkage ----------------------------------------------
    adapter_target: str | None = None  # KIMERA_TARGETS key if probable
    adapter_is_available: bool = False

    # --- dynamic wheels' contributions (optional, fill when run) ------
    discovery_field_count: int | None = None
    discovery_field_sample: tuple[str, ...] = ()
    audit_finding_count: int | None = None
    audit_severity_histogram: dict[str, int] = field(default_factory=dict)
    instrumenting_wall_time_p50_s: float | None = None
    instrumenting_cpu_time_p50_s: float | None = None
    instrumenting_n_cycles_observed: int | None = None
    instrumenting_rss_peak_bytes: int | None = None
    comparing_n_drift_events: int | None = None
    comparing_detector_name: str = ""
    comparing_stream_name: str = ""

    # --- provenance ----------------------------------------------------
    kimera_repo: str = ""              # absolute path
    kimera_git_commit: str = ""
    captured_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "canonical_class": self.canonical_class,
            "family_tags": list(self.family_tags),
            "static": {
                "source_file": self.source_file,
                "source_line": self.source_line,
                "docstring": self.docstring,
                "method_names": list(self.method_names),
                "parent_classes": list(self.parent_classes),
                "imports": list(self.imports),
                "n_callers": self.n_callers,
                "top_callers": [c.to_dict() for c in self.top_callers],
                "notes": list(self.notes),
            },
            "adapter": {
                "target": self.adapter_target,
                "is_available": self.adapter_is_available,
            },
            "dynamic": {
                "discovery_field_count": self.discovery_field_count,
                "discovery_field_sample": list(self.discovery_field_sample),
                "audit_finding_count": self.audit_finding_count,
                "audit_severity_histogram": dict(self.audit_severity_histogram),
                "instrumenting_wall_time_p50_s": self.instrumenting_wall_time_p50_s,
                "instrumenting_cpu_time_p50_s": self.instrumenting_cpu_time_p50_s,
                "instrumenting_n_cycles_observed": self.instrumenting_n_cycles_observed,
                "instrumenting_rss_peak_bytes": self.instrumenting_rss_peak_bytes,
                "comparing_n_drift_events": self.comparing_n_drift_events,
                "comparing_detector_name": self.comparing_detector_name,
                "comparing_stream_name": self.comparing_stream_name,
            },
            "provenance": {
                "kimera_repo": self.kimera_repo,
                "kimera_git_commit": self.kimera_git_commit,
                "captured_at": self.captured_at,
            },
        }

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        text = json.dumps(self.to_dict(), indent=indent, default=str)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    def to_markdown(self, path: str | None = None) -> str:
        """Render the profile as a Markdown report. Charts not included here —
        the reporting wheel handles richer output via the ReportRunner."""
        lines: list[str] = []
        lines.append(f"# Primitive Profile — `{self.name}`\n")
        lines.append(f"**Canonical class:** `{self.canonical_class}`  ")
        lines.append(f"**Family:** {', '.join(self.family_tags) or '(unclassified)'}  ")
        if self.kimera_git_commit:
            lines.append(f"**Kimera commit:** `{self.kimera_git_commit[:12]}`  ")
        lines.append(f"**Captured at:** {self.captured_at}\n")

        lines.append("## Location\n")
        if self.source_file:
            lines.append(f"- File: `{self.source_file}`")
            if self.source_line:
                lines.append(f"- Line: {self.source_line}")
        else:
            lines.append("- _class definition not located in the Kimera tree_")
        if self.notes:
            lines.append("\n_Notes:_")
            for n in self.notes:
                lines.append(f"- {n}")
        lines.append("")

        if self.docstring:
            lines.append("## Docstring\n")
            lines.append("```")
            lines.append(self.docstring.strip()[:2000])
            lines.append("```\n")

        if self.parent_classes:
            lines.append("## Parent classes\n")
            for cls in self.parent_classes:
                lines.append(f"- `{cls}`")
            lines.append("")

        if self.method_names:
            lines.append("## Methods\n")
            for m in self.method_names:
                lines.append(f"- `{m}`")
            lines.append("")

        lines.append("## Adapter wiring\n")
        if self.adapter_target:
            lines.append(f"- Target: `{self.adapter_target}` "
                         f"({'available' if self.adapter_is_available else 'unavailable'})")
        else:
            lines.append("- _no Kimera adapter target wired for this primitive yet_")
        lines.append("")

        lines.append("## Callers\n")
        lines.append(f"- Total mentions in the repo: {self.n_callers}")
        if self.top_callers:
            lines.append("- Top references:")
            for c in self.top_callers[:10]:
                lines.append(f"  - `{c.file}:{c.line}` — `{c.context.strip()[:80]}`")
        lines.append("")

        if any([
            self.discovery_field_count is not None,
            self.audit_finding_count is not None,
            self.instrumenting_wall_time_p50_s is not None,
            self.comparing_n_drift_events is not None,
        ]):
            lines.append("## Dynamic readings\n")
            if self.discovery_field_count is not None:
                lines.append(f"- Discovery: {self.discovery_field_count} field path(s) "
                             f"in `CycleResult.raw` (Layer A)")
                if self.discovery_field_sample:
                    sample = ", ".join(f"`{s}`" for s in self.discovery_field_sample[:8])
                    lines.append(f"  - sample: {sample}")
            if self.audit_finding_count is not None:
                lines.append(f"- Auditing: {self.audit_finding_count} static-analysis finding(s)")
                if self.audit_severity_histogram:
                    parts = ", ".join(f"{k}={v}" for k, v in
                                       sorted(self.audit_severity_histogram.items(),
                                              key=lambda kv: -kv[1]))
                    lines.append(f"  - severity: {parts}")
            if self.instrumenting_wall_time_p50_s is not None:
                lines.append(
                    f"- Instrumenting: p50 cycle wall-time "
                    f"{self.instrumenting_wall_time_p50_s:.3f}s"
                    + (f", p50 CPU {self.instrumenting_cpu_time_p50_s:.3f}s"
                       if self.instrumenting_cpu_time_p50_s is not None else "")
                    + (f", over {self.instrumenting_n_cycles_observed} cycle(s)"
                       if self.instrumenting_n_cycles_observed else "")
                    + (f", RSS peak {self.instrumenting_rss_peak_bytes // (1024*1024)} MB"
                       if self.instrumenting_rss_peak_bytes else "")
                )
            if self.comparing_n_drift_events is not None:
                lines.append(
                    f"- Comparing (drift): {self.comparing_n_drift_events} drift "
                    f"event(s) detected by `{self.comparing_detector_name or '?'}` on "
                    f"stream `{self.comparing_stream_name or '?'}`"
                )
            lines.append("")

        body = "\n".join(lines) + "\n"
        if path:
            Path(path).write_text(body, encoding="utf-8")
        return body
