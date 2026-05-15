"""LaTeXReporter — paper-ready table + figure fragments.

Renders proof + audit records as a LaTeX document that's suitable either
as a stand-alone compilation (the ``\\documentclass{article}`` header is
emitted) or as a fragment (``\\input{}`` from a parent paper). Tables use
``booktabs`` for clean publication style; figures use ``\\includegraphics{}``
referencing PNGs in an adjacent ``assets/`` directory.

The renderer escapes LaTeX-special characters in cell values (``_``, ``&``,
``$``, ``%``, ``#``, etc.) so a stray underscore in a metric name doesn't
crash compilation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ophamin.reporting.base import ReportFormat, ReportRenderer
from ophamin.reporting.chart_helpers import (
    SEVERITY_COLORS,
    bar_chart,
    confidence_interval_plot,
    pie_chart,
)
from ophamin.reporting.html_renderer import _short_path


_LATEX_ESCAPE = str.maketrans({
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
})


def _esc(value: Any) -> str:
    return str(value).translate(_LATEX_ESCAPE)


def _write_chart(assets_dir: Path, name: str, factory) -> str:
    """Write a chart PNG to assets_dir/name; return the LaTeX-include filename
    (without extension, since ``\\includegraphics`` handles the extension)."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    out = assets_dir / name
    factory(out)
    # use forward slashes — LaTeX accepts those on every platform
    return f"assets/{out.stem}"


_DOC_PREAMBLE = (
    "\\documentclass{article}\n"
    "\\usepackage[utf8]{inputenc}\n"
    "\\usepackage[T1]{fontenc}\n"
    "\\usepackage{booktabs}\n"
    "\\usepackage{graphicx}\n"
    "\\usepackage{hyperref}\n"
    "\\usepackage{xcolor}\n"
    "\\definecolor{validated}{HTML}{047857}\n"
    "\\definecolor{refuted}{HTML}{B91C1C}\n"
    "\\definecolor{inconclusive}{HTML}{9A3412}\n"
    "\\title{%(title)s}\n"
    "\\date{%(date)s}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
)


def _wrap_document(title: str, date: str, body: str, *, stand_alone: bool = True) -> str:
    if not stand_alone:
        return body
    return (
        _DOC_PREAMBLE % {"title": _esc(title), "date": _esc(date)}
        + body
        + "\n\\end{document}\n"
    )


def _render_proof_latex(record: dict[str, Any], tex_path: Path) -> str:
    claim = record.get("claim", {})
    threshold = claim.get("threshold", {})
    verdict = record.get("verdict", {})
    identity = record.get("identity", {})
    data = record.get("data", {})
    evidence = record.get("evidence", [])
    prereg = record.get("preregistration", {})
    assets = tex_path.parent / "assets"

    outcome = verdict.get("outcome", "")
    outcome_color = {
        "VALIDATED": "validated",
        "REFUTED": "refuted",
        "INCONCLUSIVE": "inconclusive",
    }.get(outcome, "black")

    parts: list[str] = []
    parts.append(f"\\section*{{Empirical Proof Record --- \\textcolor{{{outcome_color}}}"
                 f"{{\\textbf{{{_esc(outcome)}}}}}}}")
    parts.append(f"\\textbf{{Proof ID:}} \\texttt{{{_esc(record.get('proof_id', '')[:32])}\\dots}}\\\\")
    parts.append(f"\\textbf{{Created:}} {_esc(identity.get('created_at', ''))}")

    parts.append("\\subsection*{1. Claim}")
    parts.append(f"\\begin{{quote}}{_esc(claim.get('statement', ''))}\\end{{quote}}")
    parts.append("\\begin{itemize}")
    parts.append(f"\\item \\textbf{{Operationalisation:}} {_esc(claim.get('operationalization', ''))}")
    if threshold:
        parts.append(
            f"\\item \\textbf{{Threshold:}} \\texttt{{"
            f"{_esc(threshold.get('metric'))} {_esc(threshold.get('comparator'))} "
            f"{_esc(threshold.get('value'))} {_esc(threshold.get('units', ''))}}}"
        )
    parts.append(f"\\item \\textbf{{H0:}} {_esc(claim.get('h0', ''))}")
    parts.append(f"\\item \\textbf{{H1:}} {_esc(claim.get('h1', ''))}")
    parts.append("\\end{itemize}")

    parts.append("\\subsection*{2. Verdict}")
    parts.append(f"\\textcolor{{{outcome_color}}}{{\\textbf{{{_esc(outcome)}}}}} --- "
                 f"observed \\texttt{{{_esc(verdict.get('observed_value'))}}}\\\\")
    parts.append(_esc(verdict.get("reasoning", "")))

    # CI figure
    primary_metric = threshold.get("metric") if threshold else None
    primary_ev = next(
        (e for e in evidence if e.get("statistic_name") == primary_metric),
        None,
    )
    if primary_ev and primary_ev.get("ci_low") is not None:
        ref = _write_chart(
            assets, f"ci_{_safe_filename(primary_metric)}.png",
            lambda out: confidence_interval_plot(
                observed_value=float(primary_ev["statistic_value"]),
                ci_low=primary_ev["ci_low"],
                ci_high=primary_ev["ci_high"],
                threshold_value=float(threshold["value"]),
                threshold_comparator=threshold.get("comparator", ">="),
                title=f"{primary_metric}: observed value vs pre-registered threshold",
                xlabel=primary_metric,
                out_path=out,
            ),
        )
        parts.append("\\begin{figure}[h!]\\centering")
        parts.append(f"\\includegraphics[width=0.8\\linewidth]{{{ref}}}")
        parts.append(f"\\caption{{{_esc(primary_metric)} -- observed value with Wilson 95\\% CI.}}")
        parts.append("\\end{figure}")

    parts.append("\\subsection*{3. Evidence}")
    parts.append("\\begin{tabular}{llrrl}\\toprule")
    parts.append("\\textbf{Pillar} & \\textbf{Statistic} & \\textbf{Value} & "
                 "\\textbf{95\\% CI} & \\textbf{Library} \\\\\\midrule")
    for ev in evidence:
        lo, hi = ev.get("ci_low"), ev.get("ci_high")
        ci = f"({lo:.4f}, {hi:.4f})" if (lo is not None and hi is not None) else "---"
        parts.append(
            f"\\texttt{{{_esc(ev.get('pillar', ''))}}} & "
            f"\\texttt{{{_esc(ev.get('statistic_name', ''))}}} & "
            f"\\texttt{{{_esc(ev.get('statistic_value', ''))}}} & "
            f"{_esc(ci)} & "
            f"{_esc(ev.get('library', ''))} {_esc(ev.get('library_version', ''))} \\\\"
        )
    parts.append("\\bottomrule\\end{tabular}")

    parts.append("\\subsection*{4. Pre-registration}")
    parts.append("\\begin{itemize}")
    parts.append(f"\\item Registered at: \\texttt{{{_esc(prereg.get('preregistered_at', ''))}}}")
    parts.append(f"\\item Config hash: \\texttt{{{_esc(prereg.get('config_hash', '')[:32])}\\dots}}")
    parts.append(f"\\item Data hash: \\texttt{{{_esc(prereg.get('data_hash', '')[:32])}\\dots}}")
    parts.append("\\end{itemize}")

    parts.append("\\subsection*{5. Signature}")
    parts.append(f"\\texttt{{{_esc(record.get('signature', '(unsigned)')[:64])}}}\\\\")
    return "\n".join(parts) + "\n"


def _render_audit_latex(record: dict[str, Any], tex_path: Path) -> str:
    identity = record.get("identity", {})
    target = record.get("target", {})
    pillars = record.get("pillars", [])
    summary = record.get("summary", {})
    assets = tex_path.parent / "assets"

    parts: list[str] = []
    parts.append("\\section*{Audit Record}")
    parts.append(f"\\textbf{{Audit ID:}} \\texttt{{{_esc(record.get('audit_id', '')[:32])}\\dots}}\\\\")
    parts.append(f"\\textbf{{Captured:}} {_esc(identity.get('captured_at', ''))}\\\\")
    parts.append(f"\\textbf{{Target:}} \\texttt{{{_esc(target.get('target_path', ''))}}}")

    parts.append("\\subsection*{1. Pillars}")
    parts.append("\\begin{tabular}{llllrr}\\toprule")
    parts.append("\\textbf{Pillar} & \\textbf{Tool} & \\textbf{Version} & "
                 "\\textbf{Status} & \\textbf{Findings} & \\textbf{Wall-time (s)} \\\\\\midrule")
    for p in pillars:
        parts.append(
            f"\\texttt{{{_esc(p.get('pillar_name'))}}} & "
            f"\\texttt{{{_esc(p.get('tool_name'))}}} & "
            f"{_esc(p.get('tool_version', '---'))} & "
            f"{_esc(p.get('status'))} & "
            f"{p.get('finding_count', 0)} & "
            f"{p.get('wall_time_s', 0.0):.2f} \\\\"
        )
    parts.append("\\bottomrule\\end{tabular}")

    parts.append("\\subsection*{2. Summary}")
    parts.append(f"Total findings: \\textbf{{{summary.get('total_findings', 0)}}}\\\\")

    sev_hist = summary.get("severity_histogram", {}) or {}
    if sev_hist:
        ref = _write_chart(
            assets, "severity.png",
            lambda out: pie_chart(
                list(sev_hist.keys()), [sev_hist[k] for k in sev_hist],
                title="Findings by severity",
                color_map=SEVERITY_COLORS,
                out_path=out,
            ),
        )
        parts.append("\\begin{figure}[h!]\\centering")
        parts.append(f"\\includegraphics[width=0.55\\linewidth]{{{ref}}}")
        parts.append("\\caption{Findings by severity.}\\end{figure}")

    per_pillar = summary.get("findings_per_pillar", {}) or {}
    if per_pillar:
        ref = _write_chart(
            assets, "per_pillar.png",
            lambda out: bar_chart(
                list(per_pillar.keys()),
                [per_pillar[k] for k in per_pillar],
                title="Findings per pillar",
                out_path=out,
            ),
        )
        parts.append("\\begin{figure}[h!]\\centering")
        parts.append(f"\\includegraphics[width=0.7\\linewidth]{{{ref}}}")
        parts.append("\\caption{Findings per pillar.}\\end{figure}")

    top_files = summary.get("top_files", []) or []
    if top_files:
        ref = _write_chart(
            assets, "hotspots.png",
            lambda out: bar_chart(
                [_short_path(p) for p, _ in top_files],
                [c for _, c in top_files],
                title="Top hotspot files",
                horizontal=True,
                out_path=out,
            ),
        )
        parts.append("\\begin{figure}[h!]\\centering")
        parts.append(f"\\includegraphics[width=0.85\\linewidth]{{{ref}}}")
        parts.append("\\caption{Top hotspot files by finding count.}\\end{figure}")

    parts.append("\\subsection*{3. Signature}")
    parts.append(f"\\texttt{{{_esc(record.get('signature', '(unsigned)')[:64])}}}\\\\")
    return "\n".join(parts) + "\n"


def _safe_filename(s: str) -> str:
    """Strip characters that aren't safe in filenames."""
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in (s or "chart"))


class LaTeXReporter(ReportRenderer):
    """LaTeX renderer — emits a stand-alone .tex document by default; pass
    ``stand_alone=False`` at construction for fragment-only output suitable
    for ``\\input{}`` in a parent paper."""

    format = ReportFormat.LATEX

    def __init__(self, *, stand_alone: bool = True) -> None:
        self.stand_alone = bool(stand_alone)

    def render_proof(self, record: dict[str, Any], out_path: Path) -> Path:
        out_path = self._with_extension(out_path, ".tex")
        body = _render_proof_latex(record, out_path)
        title = (
            f"Empirical Proof Record: "
            f"{record.get('verdict', {}).get('outcome', '')}"
        )
        date = record.get("identity", {}).get("created_at", "")
        out_path.write_text(
            _wrap_document(title, date, body, stand_alone=self.stand_alone),
            encoding="utf-8",
        )
        return out_path

    def render_audit(self, record: dict[str, Any], out_path: Path) -> Path:
        out_path = self._with_extension(out_path, ".tex")
        body = _render_audit_latex(record, out_path)
        date = record.get("identity", {}).get("captured_at", "")
        out_path.write_text(
            _wrap_document("Audit Record", date, body, stand_alone=self.stand_alone),
            encoding="utf-8",
        )
        return out_path

    @staticmethod
    def _with_extension(path: Path, ext: str) -> Path:
        if path.suffix.lower() == ext:
            return path
        return path.with_suffix(ext)
