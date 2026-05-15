"""HTMLReporter — single-file HTML report with inline base64 charts.

Renders both proof records and audit records into a self-contained HTML
file. Charts are embedded as inline base64 PNGs so the report is e-mailable
and survives passing through systems that strip relative paths. Styling is
inline CSS (Tailwind-inspired greys + indigos) — no external CSS deps.

Designed for *academic review*: clean tables, full provenance section,
embedded charts that render at print-resolution.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from ophamin.reporting.base import ReportFormat, ReportRenderer
from ophamin.reporting.chart_helpers import (
    SEVERITY_COLORS,
    bar_chart,
    confidence_interval_plot,
    histogram,
    pie_chart,
)

_INLINE_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       max-width: 1100px; margin: 2em auto; padding: 0 1.5em; color: #1f2937; line-height: 1.55; }
h1 { font-size: 1.7em; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.3em; }
h2 { font-size: 1.25em; margin-top: 2em; color: #1f2937;
     border-bottom: 1px solid #e5e7eb; padding-bottom: 0.2em; }
h3 { font-size: 1.05em; margin-top: 1.4em; color: #374151; }
code, pre { font-family: "SFMono-Regular", Menlo, Consolas, monospace;
            background: #f3f4f6; padding: 0.1em 0.35em; border-radius: 3px; }
pre { padding: 0.75em; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 0.5em 0 1em; font-size: 0.93em; }
th, td { border: 1px solid #e5e7eb; padding: 0.4em 0.7em; text-align: left;
         vertical-align: top; }
th { background: #f9fafb; font-weight: 600; }
.verdict-VALIDATED { color: #047857; font-weight: 700; }
.verdict-REFUTED   { color: #b91c1c; font-weight: 700; }
.verdict-INCONCLUSIVE { color: #9a3412; font-weight: 700; }
.tag { display: inline-block; padding: 0.15em 0.55em; border-radius: 4px;
       font-size: 0.85em; font-family: monospace; background: #e5e7eb;
       color: #1f2937; margin-right: 0.3em; }
.tag-critical { background: #fee2e2; color: #991b1b; }
.tag-high     { background: #fef2f2; color: #dc2626; }
.tag-medium   { background: #fef3c7; color: #92400e; }
.tag-low      { background: #dbeafe; color: #1e3a8a; }
.tag-info     { background: #e5e7eb; color: #1f2937; }
.chart img { max-width: 100%; height: auto; display: block; margin: 0.5em 0; }
footer { margin-top: 3em; padding-top: 1em; border-top: 1px solid #e5e7eb;
         color: #6b7280; font-size: 0.85em; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _img(b64: str, alt: str = "") -> str:
    return (
        f'<div class="chart">'
        f'<img alt="{_esc(alt)}" src="data:image/png;base64,{b64}" />'
        f"</div>"
    )


def _wrap_html(title: str, body: str) -> str:
    return (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title>"
        f"<style>{_INLINE_CSS}</style></head><body>"
        f"{body}"
        "</body></html>"
    )


# --------------------------------------------------------------------------
# Proof record rendering
# --------------------------------------------------------------------------


def _render_proof_body(record: dict[str, Any]) -> str:
    claim = record.get("claim", {})
    threshold = claim.get("threshold", {})
    verdict = record.get("verdict", {})
    identity = record.get("identity", {})
    data = record.get("data", {})
    evidence_list = record.get("evidence", [])
    prereg = record.get("preregistration", {})

    outcome = str(verdict.get("outcome", ""))
    parts: list[str] = []
    parts.append(f"<h1>Empirical Proof Record — "
                 f"<span class='verdict-{_esc(outcome)}'>{_esc(outcome)}</span></h1>")
    parts.append(f"<p><strong>Proof ID:</strong> <code>{_esc(record.get('proof_id', ''))}</code><br>"
                 f"<strong>Created:</strong> {_esc(identity.get('created_at', ''))}</p>")

    parts.append("<h2>1. Claim</h2>")
    parts.append(f"<blockquote><p>{_esc(claim.get('statement', ''))}</p></blockquote>")
    parts.append("<ul>")
    parts.append(f"<li><strong>Operationalisation:</strong> {_esc(claim.get('operationalization', ''))}</li>")
    if threshold:
        parts.append(
            f"<li><strong>Threshold:</strong> <code>"
            f"{_esc(threshold.get('metric'))} {_esc(threshold.get('comparator'))} "
            f"{_esc(threshold.get('value'))} {_esc(threshold.get('units', ''))}</code></li>"
        )
    parts.append(f"<li><strong>H0:</strong> {_esc(claim.get('h0', ''))}</li>")
    parts.append(f"<li><strong>H1:</strong> {_esc(claim.get('h1', ''))}</li>")
    parts.append("</ul>")

    parts.append("<h2>2. Verdict</h2>")
    parts.append(
        f"<p>Outcome: <span class='verdict-{_esc(outcome)}'>{_esc(outcome)}</span>"
        f" — observed <code>{_esc(verdict.get('observed_value'))}</code></p>"
    )
    parts.append(f"<p>{_esc(verdict.get('reasoning', ''))}</p>")

    # Confidence-interval chart for the primary statistic, if present in evidence
    primary_metric = threshold.get("metric")
    primary_ev = next(
        (e for e in evidence_list if e.get("statistic_name") == primary_metric),
        None,
    )
    if primary_ev and primary_ev.get("ci_low") is not None:
        chart = confidence_interval_plot(
            observed_value=float(primary_ev["statistic_value"]),
            ci_low=primary_ev["ci_low"],
            ci_high=primary_ev["ci_high"],
            threshold_value=float(threshold["value"]),
            threshold_comparator=threshold.get("comparator", ">="),
            title=f"{primary_metric}: observed value vs pre-registered threshold",
            xlabel=primary_metric,
        )
        parts.append(_img(chart, alt=primary_metric))

    parts.append("<h2>3. Pre-registration</h2>")
    parts.append("<ul>")
    parts.append(f"<li>Registered at: <code>{_esc(prereg.get('preregistered_at', ''))}</code></li>")
    parts.append(f"<li>Config hash: <code>{_esc(prereg.get('config_hash', ''))}</code></li>")
    parts.append(f"<li>Data hash: <code>{_esc(prereg.get('data_hash', ''))}</code></li>")
    parts.append("</ul>")
    plan = prereg.get("analysis_plan", "")
    if plan:
        parts.append(f"<p><em>Plan:</em> {_esc(plan)}</p>")

    parts.append("<h2>4. Data</h2>")
    parts.append("<ul>")
    parts.append(f"<li>Substrate: <code>{_esc(data.get('substrate_name', ''))}</code> "
                 f"@ <code>{_esc(data.get('substrate_git_commit', '')[:12])}</code></li>")
    for ds in data.get("datasets", []) or []:
        parts.append(
            f"<li>Dataset: <code>{_esc(ds.get('name'))}</code> "
            f"({_esc(ds.get('kind'))}, {ds.get('n_records', 0)} records, "
            f"hash <code>{_esc(ds.get('content_hash', '')[:12])}…</code>)</li>"
        )
    parts.append("</ul>")

    parts.append("<h2>5. Evidence</h2>")
    parts.append("<table><thead><tr>"
                 "<th>Pillar</th><th>Statistic</th><th>Value</th><th>95% CI</th>"
                 "<th>Library</th></tr></thead><tbody>")
    for ev in evidence_list:
        lo = ev.get("ci_low")
        hi = ev.get("ci_high")
        ci_cell = (
            f"({lo:.4f}, {hi:.4f})" if (lo is not None and hi is not None) else "—"
        )
        parts.append(
            f"<tr><td><code>{_esc(ev.get('pillar', ''))}</code></td>"
            f"<td><code>{_esc(ev.get('statistic_name', ''))}</code></td>"
            f"<td><code>{_esc(ev.get('statistic_value'))}</code></td>"
            f"<td>{_esc(ci_cell)}</td>"
            f"<td>{_esc(ev.get('library', ''))} {_esc(ev.get('library_version', ''))}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")

    # Distribution histograms for any evidence pillar carrying a per-cycle
    # distribution in detail
    for ev in evidence_list:
        detail = ev.get("detail") or {}
        dist = detail.get("distribution")
        if isinstance(dist, dict) and dist.get("n", 0) > 0:
            stat_name = ev.get("statistic_name", "")
            # synthesize a sample histogram-like chart from the summary stats
            # (we can't reconstruct the full distribution from summary stats,
            # but we can show min/p10/median/mean/p90/max as a horizontal bar)
            labels = ["min", "p10", "median", "mean", "p90", "max"]
            values = [dist.get(k, 0.0) for k in labels]
            chart = bar_chart(
                labels, values,
                title=f"{stat_name} distribution summary (n={dist.get('n')})",
                ylabel="value",
                horizontal=True,
            )
            parts.append(_img(chart, alt=stat_name))

    parts.append("<h2>6. Signature</h2>")
    parts.append(f"<p><code>{_esc(record.get('signature', '(unsigned)'))}</code></p>")

    parts.append(
        f"<footer>Rendered by Ophamin reporting wheel · "
        f"schema {_esc(record.get('schema_version', ''))} · "
        f"ophamin {_esc(identity.get('ophamin_version', ''))} "
        f"@ <code>{_esc(identity.get('ophamin_git_commit', '')[:12])}</code></footer>"
    )
    return "".join(parts)


# --------------------------------------------------------------------------
# Audit record rendering
# --------------------------------------------------------------------------


def _render_audit_body(record: dict[str, Any]) -> str:
    identity = record.get("identity", {})
    target = record.get("target", {})
    pillars = record.get("pillars", [])
    summary = record.get("summary", {})
    parts: list[str] = []

    parts.append("<h1>Audit Record</h1>")
    parts.append(f"<p><strong>Audit ID:</strong> <code>{_esc(record.get('audit_id', ''))}</code><br>"
                 f"<strong>Captured:</strong> {_esc(identity.get('captured_at', ''))}<br>"
                 f"<strong>Target:</strong> <code>{_esc(target.get('target_path', ''))}</code></p>")

    parts.append("<h2>1. Pillars</h2>")
    parts.append("<table><thead><tr>"
                 "<th>Pillar</th><th>Tool</th><th>Version</th><th>Status</th>"
                 "<th>Findings</th><th>Wall-time</th></tr></thead><tbody>")
    for p in pillars:
        parts.append(
            f"<tr><td><code>{_esc(p.get('pillar_name'))}</code></td>"
            f"<td><code>{_esc(p.get('tool_name'))}</code></td>"
            f"<td>{_esc(p.get('tool_version', '—'))}</td>"
            f"<td>{_esc(p.get('status'))}</td>"
            f"<td>{_esc(p.get('finding_count', 0))}</td>"
            f"<td>{p.get('wall_time_s', 0.0):.2f}s</td></tr>"
        )
    parts.append("</tbody></table>")

    parts.append("<h2>2. Summary</h2>")
    parts.append(f"<p>Total findings: <strong>{_esc(summary.get('total_findings', 0))}</strong></p>")

    # Severity pie
    sev_hist: dict[str, int] = summary.get("severity_histogram", {}) or {}
    if sev_hist:
        labels = list(sev_hist.keys())
        counts = [sev_hist[k] for k in labels]
        parts.append("<h3>Severity histogram</h3>")
        parts.append(_img(
            pie_chart(labels, counts, title="Findings by severity", color_map=SEVERITY_COLORS),
            alt="severity-pie",
        ))

    # Per-pillar bar
    per_pillar: dict[str, int] = summary.get("findings_per_pillar", {}) or {}
    if per_pillar:
        labels = list(per_pillar.keys())
        counts = [per_pillar[k] for k in labels]
        parts.append("<h3>Findings per pillar</h3>")
        parts.append(_img(
            bar_chart(labels, counts, title="Findings per pillar"),
            alt="per-pillar",
        ))

    # Top hotspot files
    top_files = summary.get("top_files", []) or []
    if top_files:
        parts.append("<h3>Top hotspot files</h3>")
        labels = [_short_path(p) for p, _ in top_files]
        counts = [c for _, c in top_files]
        parts.append(_img(
            bar_chart(labels, counts, title="Top files by finding count", horizontal=True),
            alt="hotspots",
        ))

    parts.append("<h2>3. Signature</h2>")
    parts.append(f"<p><code>{_esc(record.get('signature', '(unsigned)'))}</code></p>")
    parts.append(
        f"<footer>Rendered by Ophamin reporting wheel · "
        f"schema {_esc(record.get('schema_version', ''))} · "
        f"ophamin {_esc(identity.get('ophamin_version', ''))} "
        f"@ <code>{_esc(identity.get('ophamin_git_commit', '')[:12])}</code></footer>"
    )
    return "".join(parts)


def _short_path(p: str, max_len: int = 60) -> str:
    """Trim a long file path to ``…/last_two_components`` if needed."""
    if len(p) <= max_len:
        return p
    parts = p.replace("\\", "/").split("/")
    if len(parts) >= 2:
        return ".../" + "/".join(parts[-2:])
    return p


# --------------------------------------------------------------------------
# HTMLReporter
# --------------------------------------------------------------------------


class HTMLReporter(ReportRenderer):
    """Single-file self-contained HTML with inline base64 charts."""

    format = ReportFormat.HTML

    def render_proof(self, record: dict[str, Any], out_path: Path) -> Path:
        out_path = self._with_extension(out_path, ".html")
        body = _render_proof_body(record)
        title = f"Proof Record — {record.get('verdict', {}).get('outcome', '')}"
        out_path.write_text(_wrap_html(title, body), encoding="utf-8")
        return out_path

    def render_audit(self, record: dict[str, Any], out_path: Path) -> Path:
        out_path = self._with_extension(out_path, ".html")
        body = _render_audit_body(record)
        out_path.write_text(_wrap_html("Audit Record", body), encoding="utf-8")
        return out_path

    @staticmethod
    def _with_extension(path: Path, ext: str) -> Path:
        if path.suffix.lower() == ext:
            return path
        return path.with_suffix(ext)
