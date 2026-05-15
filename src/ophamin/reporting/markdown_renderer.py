"""MarkdownReporter — GFM with PNG charts in an adjacent ``assets/`` dir.

Renders proof + audit records to GFM Markdown with embedded matplotlib
charts. Charts are written as PNGs alongside the markdown file (in an
``assets/`` sub-directory next to the .md output) and referenced as
``![title](assets/chart.png)``. Renders cleanly in GitHub, GitLab,
Obsidian, VS Code preview, and `mdcat`.
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


def _write_chart(
    assets_dir: Path,
    name: str,
    factory,
) -> str:
    """Write a chart to ``assets_dir/name.png`` and return the relative ref."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    out = assets_dir / name
    factory(out)
    return f"assets/{out.name}"


def _render_proof_md(record: dict[str, Any], md_path: Path) -> str:
    claim = record.get("claim", {})
    threshold = claim.get("threshold", {})
    verdict = record.get("verdict", {})
    identity = record.get("identity", {})
    data = record.get("data", {})
    evidence = record.get("evidence", [])
    prereg = record.get("preregistration", {})
    assets = md_path.parent / "assets"

    lines: list[str] = []
    outcome = verdict.get("outcome", "")
    lines.append(f"# Empirical Proof Record — **{outcome}**\n")
    lines.append(f"**Proof ID:** `{record.get('proof_id', '')}`  ")
    lines.append(f"**Created:** {identity.get('created_at', '')}\n")

    lines.append("## 1. Claim\n")
    lines.append(f"> {claim.get('statement', '')}\n")
    lines.append(f"- **Operationalisation:** {claim.get('operationalization', '')}")
    if threshold:
        lines.append(
            f"- **Threshold:** `{threshold.get('metric')} "
            f"{threshold.get('comparator')} {threshold.get('value')} "
            f"{threshold.get('units', '')}`"
        )
    lines.append(f"- **H0:** {claim.get('h0', '')}")
    lines.append(f"- **H1:** {claim.get('h1', '')}\n")

    lines.append("## 2. Verdict\n")
    lines.append(f"**Outcome:** {outcome}  ")
    lines.append(f"**Observed:** `{verdict.get('observed_value', '')}`\n")
    lines.append(f"{verdict.get('reasoning', '')}\n")

    # CI chart for the primary statistic
    primary_metric = threshold.get("metric") if threshold else None
    primary_ev = next(
        (e for e in evidence if e.get("statistic_name") == primary_metric),
        None,
    )
    if primary_ev and primary_ev.get("ci_low") is not None:
        ref = _write_chart(
            assets,
            f"ci_{primary_metric}.png",
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
        lines.append(f"![{primary_metric} confidence interval]({ref})\n")

    lines.append("## 3. Pre-registration\n")
    lines.append(f"- Registered at: `{prereg.get('preregistered_at', '')}`")
    lines.append(f"- Config hash: `{prereg.get('config_hash', '')}`")
    lines.append(f"- Data hash: `{prereg.get('data_hash', '')}`\n")
    plan = prereg.get("analysis_plan", "")
    if plan:
        lines.append(f"_{plan}_\n")

    lines.append("## 4. Data\n")
    lines.append(f"- Substrate: `{data.get('substrate_name')}` @ "
                 f"`{data.get('substrate_git_commit', '')[:12]}`")
    for ds in data.get("datasets", []) or []:
        lines.append(
            f"- Dataset: `{ds.get('name')}` ({ds.get('kind')}, "
            f"{ds.get('n_records', 0)} records, "
            f"hash `{ds.get('content_hash', '')[:12]}…`)"
        )
    lines.append("")

    lines.append("## 5. Evidence\n")
    lines.append("| pillar | statistic | value | 95% CI | library |")
    lines.append("|---|---|---|---|---|")
    for ev in evidence:
        lo, hi = ev.get("ci_low"), ev.get("ci_high")
        ci = f"({lo:.4f}, {hi:.4f})" if (lo is not None and hi is not None) else "—"
        lines.append(
            f"| `{ev.get('pillar', '')}` | `{ev.get('statistic_name', '')}` | "
            f"`{ev.get('statistic_value', '')}` | {ci} | "
            f"{ev.get('library', '')} {ev.get('library_version', '')} |"
        )
    lines.append("")

    lines.append("## 6. Signature\n")
    lines.append(f"`{record.get('signature', '(unsigned)')}`")
    return "\n".join(lines) + "\n"


def _render_audit_md(record: dict[str, Any], md_path: Path) -> str:
    identity = record.get("identity", {})
    target = record.get("target", {})
    pillars = record.get("pillars", [])
    summary = record.get("summary", {})
    assets = md_path.parent / "assets"

    lines: list[str] = []
    lines.append("# Audit Record\n")
    lines.append(f"**Audit ID:** `{record.get('audit_id', '')}`  ")
    lines.append(f"**Captured:** {identity.get('captured_at', '')}  ")
    lines.append(f"**Target:** `{target.get('target_path', '')}`\n")

    lines.append("## 1. Pillars\n")
    lines.append("| pillar | tool | version | status | findings | wall-time |")
    lines.append("|---|---|---|---|---|---|")
    for p in pillars:
        lines.append(
            f"| `{p.get('pillar_name')}` | `{p.get('tool_name')}` | "
            f"{p.get('tool_version', '—')} | {p.get('status')} | "
            f"{p.get('finding_count', 0)} | {p.get('wall_time_s', 0.0):.2f}s |"
        )
    lines.append("")

    lines.append("## 2. Summary\n")
    lines.append(f"Total findings: **{summary.get('total_findings', 0)}**\n")

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
        lines.append("### Severity histogram\n")
        lines.append(f"![Severity]({ref})\n")

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
        lines.append("### Per pillar\n")
        lines.append(f"![Per pillar]({ref})\n")

    top_files = summary.get("top_files", []) or []
    if top_files:
        ref = _write_chart(
            assets, "hotspots.png",
            lambda out: bar_chart(
                [_short_path(p) for p, _ in top_files],
                [c for _, c in top_files],
                title="Top files by finding count",
                horizontal=True,
                out_path=out,
            ),
        )
        lines.append("### Top hotspots\n")
        lines.append(f"![Hotspots]({ref})\n")

    lines.append("## 3. Signature\n")
    lines.append(f"`{record.get('signature', '(unsigned)')}`")
    return "\n".join(lines) + "\n"


class MarkdownReporter(ReportRenderer):
    """GFM markdown with adjacent PNG charts in ``<md_dir>/assets/``."""

    format = ReportFormat.MARKDOWN

    def render_proof(self, record: dict[str, Any], out_path: Path) -> Path:
        out_path = self._with_extension(out_path, ".md")
        body = _render_proof_md(record, out_path)
        out_path.write_text(body, encoding="utf-8")
        return out_path

    def render_audit(self, record: dict[str, Any], out_path: Path) -> Path:
        out_path = self._with_extension(out_path, ".md")
        body = _render_audit_md(record, out_path)
        out_path.write_text(body, encoding="utf-8")
        return out_path

    @staticmethod
    def _with_extension(path: Path, ext: str) -> Path:
        if path.suffix.lower() == ext:
            return path
        return path.with_suffix(ext)
