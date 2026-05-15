"""ReportRunner — given a record path + a format, write the rendered output.

Picks the right renderer for the requested format, parses the record JSON,
classifies it as proof or audit, dispatches to ``renderer.render(kind, ...)``,
returns the output path.
"""

from __future__ import annotations

from pathlib import Path

from ophamin.reporting.base import RecordKind, ReportFormat, ReportRenderer, load_record
from ophamin.reporting.html_renderer import HTMLReporter
from ophamin.reporting.latex_renderer import LaTeXReporter
from ophamin.reporting.markdown_renderer import MarkdownReporter


DEFAULT_RENDERERS: dict[ReportFormat, type[ReportRenderer]] = {
    ReportFormat.HTML: HTMLReporter,
    ReportFormat.MARKDOWN: MarkdownReporter,
    ReportFormat.LATEX: LaTeXReporter,
}


class ReportRunner:
    """Single entry-point for rendering any record into any format."""

    def __init__(
        self,
        renderers: dict[ReportFormat, type[ReportRenderer]] | None = None,
    ) -> None:
        self.renderers = renderers if renderers is not None else dict(DEFAULT_RENDERERS)

    def render(
        self,
        record_path: str | Path,
        output_path: str | Path,
        format: ReportFormat,
    ) -> Path:
        kind, record = load_record(record_path)
        renderer_cls = self.renderers.get(format)
        if renderer_cls is None:
            raise ValueError(
                f"no renderer registered for format {format}; available: "
                f"{sorted(f.value for f in self.renderers)}"
            )
        renderer = renderer_cls()
        return renderer.render(kind, record, Path(output_path))

    def supported_formats(self) -> tuple[ReportFormat, ...]:
        return tuple(self.renderers.keys())
