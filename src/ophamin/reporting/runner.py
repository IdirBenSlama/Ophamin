"""ReportRunner — given a record path + a format, write the rendered output.

Picks the right renderer for the requested format, parses the record JSON,
classifies it as proof or audit, dispatches to ``renderer.render(kind, ...)``,
returns the output path.

Move M (2026-05-16) adds ``run_batch`` — campaign-level rendering across
a directory of proofs/audits with a master index page. Closes part of
gap E (inner-triad asymmetry) by giving the reporting wheel a
campaign-level surface.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ophamin.measuring.proof.codec import iter_proofs
from ophamin.reporting.base import RecordKind, ReportFormat, ReportRenderer, load_record
from ophamin.reporting.html_renderer import HTMLReporter
from ophamin.reporting.latex_renderer import LaTeXReporter
from ophamin.reporting.markdown_renderer import MarkdownReporter
from ophamin.reporting.pdf_renderer import PDFReporter


DEFAULT_RENDERERS: dict[ReportFormat, type[ReportRenderer]] = {
    ReportFormat.HTML: HTMLReporter,
    ReportFormat.MARKDOWN: MarkdownReporter,
    ReportFormat.LATEX: LaTeXReporter,
    # PDFReporter detects its TeX toolchain at construction. Including
    # it here means `ReportRunner.render(..., format=ReportFormat.PDF)`
    # works out of the box on machines with MacTeX / TeX Live; on
    # machines without, it raises PDFToolchainMissingError at the
    # request site (loud-fail at API boundary, not silent skip).
    ReportFormat.PDF: PDFReporter,
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

    def run_batch(
        self,
        records_dir: str | Path,
        out_dir: str | Path,
        format: ReportFormat = ReportFormat.MARKDOWN,
    ) -> dict[str, Any]:
        """Render every signed record under ``records_dir`` + emit an
        index page.

        Walks the directory recursively (same shape as :func:`iter_proofs`),
        renders each record to ``<out_dir>/<original_name>.<ext>``, and
        writes an ``INDEX.md`` master page listing every rendered output
        with its verdict / family heuristic / relative path.

        Returns a summary dict carrying per-format counts + the list of
        rendered output paths + the index path.
        """
        records_dir = Path(records_dir)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        rendered: list[tuple[Path, Path, str]] = []  # (input, output, verdict)
        skipped: list[tuple[Path, str]] = []         # (input, reason)
        ext = {"html": ".html", "markdown": ".md", "latex": ".tex"}[format.value]
        for record_path in iter_proofs(records_dir):
            try:
                kind, record = load_record(record_path)
            except Exception as exc:  # noqa: BLE001
                skipped.append((record_path, f"load failed: {exc}"))
                continue
            output = out_dir / (record_path.stem + ext)
            try:
                self.render(record_path, output, format)
            except Exception as exc:  # noqa: BLE001
                skipped.append((record_path, f"render failed: {exc}"))
                continue
            # load_record returns a plain dict payload — not the dataclass —
            # so verdict / summary access is via dict key, not attribute.
            verdict = ""
            if kind == RecordKind.PROOF:
                verdict = str(record.get("verdict", {}).get("outcome", ""))
            elif kind == RecordKind.AUDIT:
                n = record.get("summary", {}).get("total_findings", 0)
                verdict = f"audit ({n} findings)"
            rendered.append((record_path, output, verdict))

        index_path = out_dir / "INDEX.md"
        index_path.write_text(
            _build_batch_index(records_dir, rendered, skipped, ext),
            encoding="utf-8",
        )
        return {
            "format": format.value,
            "records_dir": str(records_dir),
            "out_dir": str(out_dir),
            "n_rendered": len(rendered),
            "n_skipped": len(skipped),
            "rendered_paths": [str(p) for _, p, _ in rendered],
            "skipped_paths": [(str(p), reason) for p, reason in skipped],
            "index_path": str(index_path),
        }


def _build_batch_index(
    records_dir: Path,
    rendered: list[tuple[Path, Path, str]],
    skipped: list[tuple[Path, str]],
    ext: str,
) -> str:
    """Render the master INDEX.md content for a batch run."""
    lines: list[str] = []
    lines.append(f"# Campaign report index — `{records_dir}`")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append(
        f"**{len(rendered)} record(s) rendered** "
        f"({len(skipped)} skipped)."
    )
    lines.append("")
    if rendered:
        lines.append("## Rendered records")
        lines.append("")
        lines.append("| Verdict | Source | Rendered |")
        lines.append("|---|---|---|")
        for source, output, verdict in rendered:
            try:
                source_rel = source.relative_to(records_dir)
            except ValueError:
                source_rel = source
            lines.append(f"| {verdict or '?'} | `{source_rel}` | `{output.name}` |")
        lines.append("")
    if skipped:
        lines.append("## Skipped")
        lines.append("")
        for source, reason in skipped:
            lines.append(f"- `{source}` — {reason}")
        lines.append("")
    return "\n".join(lines)
