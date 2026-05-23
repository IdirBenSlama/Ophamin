"""Tests for the reporting wheel (HTML / Markdown / LaTeX).

The renderers are tested on synthetic proof + audit record dicts; charts go
to a tmp_path. Live end-to-end against the four shipped proof records is
covered by the example runner.
"""

from __future__ import annotations

import base64
import json

import pytest

from ophamin.reporting import (
    HTMLReporter,
    LaTeXReporter,
    MarkdownReporter,
    RecordKind,
    ReportFormat,
    ReportRunner,
    bar_chart,
    confidence_interval_plot,
    histogram,
    pie_chart,
)
from ophamin.reporting.base import load_record


# --------------------------------------------------------------------------
# Synthetic record builders
# --------------------------------------------------------------------------


def _proof_record(*, outcome: str = "VALIDATED") -> dict:
    """Build a proof-record dict in the shape EmpiricalProofRecord.to_dict() emits."""
    return {
        "proof_id": "deadbeef" * 8,
        "schema_version": "proof/1.0",
        "identity": {
            "ophamin_version": "0.1.0",
            "ophamin_git_commit": "abcdef1234567890",
            "created_at": "2026-05-15T12:00:00+00:00",
        },
        "claim": {
            "statement": "On X, Kimera does Y in ≥ 90% of cycles.",
            "operationalization": "fraction of X for which Y",
            "threshold": {
                "metric": "x_rate", "comparator": ">=",
                "value": 0.90, "units": "fraction",
            },
            "h0": "P(Y | X) < 0.90",
            "h1": "P(Y | X) >= 0.90",
        },
        "preregistration": {
            "config_hash": "c" * 32, "data_hash": "d" * 32,
            "analysis_plan": "stream X through Y",
            "preregistered_at": "2026-05-15T11:00:00+00:00",
            "sweep_grid": {},
        },
        "data": {
            "substrate_name": "kimera-swm",
            "substrate_git_commit": "8" * 40,
            "datasets": [
                {"name": "enron-email-corpus", "kind": "email_corpus",
                 "n_records": 100000, "content_hash": "f" * 64,
                 "source": "cmu.edu"},
            ],
        },
        "evidence": [
            {
                "pillar": "O.x.rate", "statistic_name": "x_rate",
                "statistic_value": 0.974, "library": "statsmodels",
                "library_version": "0.14",
                "ci_low": 0.962, "ci_high": 0.983,
                "p_value": None, "effect_size": None,
                "cross_check": "n/a",
                "detail": {
                    "distribution": {
                        "n": 100, "min": 0.5, "max": 1.0,
                        "median": 0.97, "mean": 0.96,
                        "p10": 0.88, "p90": 1.0,
                    },
                },
            },
        ],
        "verdict": {
            "outcome": outcome, "observed_value": 0.974,
            "threshold": {
                "metric": "x_rate", "comparator": ">=",
                "value": 0.90, "units": "fraction",
            },
            "reasoning": "rate 0.974 satisfies the threshold",
        },
        "reproduction": {"command": "ophamin scenario x", "environment": {}, "lineage_chain": []},
        "provenance": {},
        "signature": "1" * 64,
    }


def _audit_record() -> dict:
    return {
        "audit_id": "f" * 64,
        "schema_version": "audit/1.0",
        "identity": {
            "ophamin_version": "0.1.0",
            "ophamin_git_commit": "abcdef1234567890",
            "captured_at": "2026-05-15T13:00:00+00:00",
        },
        "target": {
            "target_path": "/tmp/foo",
            "target_content_hash": "a" * 64,
        },
        "pillars": [
            {
                "pillar_name": "ruff", "tool_name": "ruff",
                "tool_version": "ruff 0.x", "status": "ok",
                "target_path": "/tmp/foo", "finding_count": 13,
                "findings": [], "severity_histogram": {"high": 13},
                "per_file_top10": [["/tmp/foo/x.py", 13]],
                "per_rule_top10": [["E501", 13]],
                "raw_stdout_bytes": 1000, "raw_stderr_bytes": 0,
                "exit_code": 0, "wall_time_s": 0.02, "error_message": "",
            },
            {
                "pillar_name": "vulture", "tool_name": "vulture",
                "tool_version": "", "status": "unavailable",
                "target_path": "/tmp/foo", "finding_count": 0,
                "findings": [], "severity_histogram": {},
                "per_file_top10": [], "per_rule_top10": [],
                "raw_stdout_bytes": 0, "raw_stderr_bytes": 0,
                "exit_code": None, "wall_time_s": 0.0,
                "error_message": "vulture not installed",
            },
        ],
        "summary": {
            "total_findings": 13,
            "severity_histogram": {"high": 13},
            "findings_per_pillar": {"ruff": 13, "vulture": 0},
            "top_files": [["/tmp/foo/long/nested/path/x.py", 13]],
            "pillars_run": ["ruff"],
            "pillars_unavailable": ["vulture"],
            "pillars_errored": [],
        },
        "reproduction": {"command": "ophamin audit /tmp/foo"},
        "signature": "5" * 64,
    }


# --------------------------------------------------------------------------
# Chart helpers
# --------------------------------------------------------------------------


def test_histogram_produces_base64_when_no_out_path():
    b64 = histogram([1, 2, 3, 4, 5], title="t", xlabel="x")
    assert isinstance(b64, str)
    # PNG signature: \x89PNG\r\n\x1a\n -> base64 starts with "iVBOR"
    assert b64.startswith("iVBOR")
    base64.b64decode(b64)  # round-trips


def test_histogram_writes_png_when_path_given(tmp_path):
    p = tmp_path / "h.png"
    out = histogram([1, 2, 3], out_path=p)
    assert out == p
    assert p.exists()
    assert p.read_bytes()[:4] == b"\x89PNG"


def test_histogram_handles_empty_values():
    b64 = histogram([], title="empty")
    assert isinstance(b64, str) and len(b64) > 0


def test_bar_chart_truncates_to_max_labels():
    # 30 bars with max_labels=5 -> only 5 visible
    labels = [f"L{i}" for i in range(30)]
    counts = list(range(30))
    b64 = bar_chart(labels, counts, max_labels=5, title="t")
    assert isinstance(b64, str)


def test_bar_chart_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="must be the same length"):
        bar_chart(["a", "b"], [1, 2, 3])


def test_pie_chart_uses_color_map():
    b64 = pie_chart(
        ["high", "low"], [10, 5],
        color_map={"high": "#dc2626", "low": "#3b82f6"},
        title="severity",
    )
    assert isinstance(b64, str)


def test_pie_chart_handles_zero_total():
    b64 = pie_chart(["a", "b"], [0, 0])
    assert isinstance(b64, str)


def test_pie_chart_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="must be the same length"):
        pie_chart(["a"], [1, 2])


def test_confidence_interval_plot_basic():
    b64 = confidence_interval_plot(
        observed_value=0.5, ci_low=0.4, ci_high=0.6,
        threshold_value=0.45, threshold_comparator=">=",
        title="ci",
    )
    assert isinstance(b64, str)


def test_confidence_interval_plot_handles_missing_ci():
    """Missing CI should still produce a chart (just no bracket)."""
    b64 = confidence_interval_plot(
        observed_value=0.5, ci_low=None, ci_high=None,
        threshold_value=0.45,
    )
    assert isinstance(b64, str)


# --------------------------------------------------------------------------
# load_record classification
# --------------------------------------------------------------------------


def test_load_record_classifies_proof(tmp_path):
    p = tmp_path / "proof.json"
    p.write_text(json.dumps(_proof_record()))
    kind, payload = load_record(p)
    assert kind == RecordKind.PROOF
    assert payload["claim"]["statement"]


def test_load_record_classifies_audit(tmp_path):
    p = tmp_path / "audit.json"
    p.write_text(json.dumps(_audit_record()))
    kind, payload = load_record(p)
    assert kind == RecordKind.AUDIT
    assert payload["summary"]["total_findings"] == 13


def test_load_record_rejects_unrecognised_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"hello": "world"}))
    with pytest.raises(ValueError, match="not recognisable"):
        load_record(p)


def test_load_record_rejects_non_dict(tmp_path):
    p = tmp_path / "list.json"
    p.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(ValueError, match="not a JSON object"):
        load_record(p)


# --------------------------------------------------------------------------
# HTMLReporter
# --------------------------------------------------------------------------


def test_html_reporter_renders_proof(tmp_path):
    out = HTMLReporter().render_proof(_proof_record(), tmp_path / "report")
    assert out == tmp_path / "report.html"
    body = out.read_text()
    assert "Empirical Proof Record" in body
    assert "VALIDATED" in body
    assert "x_rate" in body
    # CI chart inlined as base64
    assert "data:image/png;base64," in body


def test_html_reporter_renders_audit(tmp_path):
    out = HTMLReporter().render_audit(_audit_record(), tmp_path / "audit")
    assert out == tmp_path / "audit.html"
    body = out.read_text()
    assert "Audit Record" in body
    assert "ruff" in body
    # severity pie should be inlined
    assert "data:image/png;base64," in body


def test_html_reporter_respects_existing_extension(tmp_path):
    out = HTMLReporter().render_proof(_proof_record(), tmp_path / "report.html")
    assert out == tmp_path / "report.html"
    assert out.exists()


def test_html_render_via_dispatch(tmp_path):
    """ReportRenderer.render dispatches on kind."""
    out = HTMLReporter().render(RecordKind.PROOF, _proof_record(), tmp_path / "p")
    assert out == tmp_path / "p.html"


# --------------------------------------------------------------------------
# MarkdownReporter
# --------------------------------------------------------------------------


def test_markdown_reporter_writes_md_and_assets(tmp_path):
    out = MarkdownReporter().render_proof(_proof_record(), tmp_path / "report")
    assert out == tmp_path / "report.md"
    body = out.read_text()
    assert "# Empirical Proof Record" in body
    # markdown references PNGs from assets/ dir
    assert "![" in body
    assets = tmp_path / "assets"
    assert assets.exists()
    pngs = list(assets.glob("*.png"))
    assert len(pngs) >= 1  # at least the CI chart


def test_markdown_audit_charts(tmp_path):
    out = MarkdownReporter().render_audit(_audit_record(), tmp_path / "audit")
    assert out == tmp_path / "audit.md"
    body = out.read_text()
    assert "# Audit Record" in body
    assert "## 2. Summary" in body
    # severity pie + per_pillar bar should be present
    assets = tmp_path / "assets"
    assert (assets / "severity.png").exists()
    assert (assets / "per_pillar.png").exists()


# --------------------------------------------------------------------------
# LaTeXReporter
# --------------------------------------------------------------------------


def test_latex_reporter_proof_compiles_to_text(tmp_path):
    out = LaTeXReporter().render_proof(_proof_record(), tmp_path / "report")
    assert out == tmp_path / "report.tex"
    body = out.read_text()
    assert "\\documentclass{article}" in body
    assert "\\begin{document}" in body
    assert "\\end{document}" in body
    # underscores in the metric name MUST be escaped
    assert "\\_" in body or "_" not in "x_rate"  # if x_rate appears, _ must be escaped
    # CI figure included
    assets = tmp_path / "assets"
    assert any(assets.glob("ci_*.png"))


def test_latex_reporter_audit_stand_alone(tmp_path):
    out = LaTeXReporter().render_audit(_audit_record(), tmp_path / "audit")
    body = out.read_text()
    assert "\\documentclass" in body
    assert "\\begin{tabular}" in body


def test_latex_reporter_fragment_mode_omits_preamble(tmp_path):
    out = LaTeXReporter(stand_alone=False).render_proof(_proof_record(), tmp_path / "frag")
    body = out.read_text()
    assert "\\documentclass" not in body
    assert "\\begin{document}" not in body
    assert "\\section*" in body  # body content still present


def test_latex_reporter_escapes_special_chars(tmp_path):
    record = _proof_record()
    record["claim"]["statement"] = "100% of cases & $variables_with_underscores"
    out = LaTeXReporter().render_proof(record, tmp_path / "esc")
    body = out.read_text()
    assert "100\\%" in body
    assert "\\&" in body
    assert "\\$" in body
    assert "\\_" in body


# --------------------------------------------------------------------------
# ReportRunner
# --------------------------------------------------------------------------


def test_report_runner_dispatches_html(tmp_path):
    record_path = tmp_path / "proof.json"
    record_path.write_text(json.dumps(_proof_record()))
    runner = ReportRunner()
    out = runner.render(record_path, tmp_path / "report", ReportFormat.HTML)
    assert out.suffix == ".html"
    assert out.exists()


def test_report_runner_dispatches_markdown(tmp_path):
    record_path = tmp_path / "audit.json"
    record_path.write_text(json.dumps(_audit_record()))
    runner = ReportRunner()
    out = runner.render(record_path, tmp_path / "audit", ReportFormat.MARKDOWN)
    assert out.suffix == ".md"
    assert out.exists()


def test_report_runner_dispatches_latex(tmp_path):
    record_path = tmp_path / "proof.json"
    record_path.write_text(json.dumps(_proof_record()))
    runner = ReportRunner()
    out = runner.render(record_path, tmp_path / "report", ReportFormat.LATEX)
    assert out.suffix == ".tex"
    assert out.exists()


def test_report_runner_rejects_unknown_format(tmp_path):
    record_path = tmp_path / "proof.json"
    record_path.write_text(json.dumps(_proof_record()))
    runner = ReportRunner(renderers={ReportFormat.HTML: HTMLReporter})
    with pytest.raises(ValueError, match="no renderer registered"):
        runner.render(record_path, tmp_path / "x", ReportFormat.LATEX)


def test_report_runner_reports_supported_formats():
    runner = ReportRunner()
    assert ReportFormat.HTML in runner.supported_formats()
    assert ReportFormat.MARKDOWN in runner.supported_formats()
    assert ReportFormat.LATEX in runner.supported_formats()
