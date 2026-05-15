"""Wheel 6 — Reporting.

The outer wheel of Ophamin's inner triad: multi-format academic output for
every signed record the observatory produces. Where the other wheels
*generate* records (proof records from scenarios, audit records from static
analysis, schema documents from discovery, drift reports from comparing),
``reporting/`` *renders* them — into formats that academic reviewers,
engineering audits, and operational dashboards expect.

Five output formats:

  HTML            single-file HTML with embedded matplotlib SVGs/PNGs as
                  base64; self-contained, e-mailable
  Markdown        GFM with PNG charts in an adjacent ``assets/`` dir;
                  renders in GitHub / GitLab / Obsidian / VS Code preview
  LaTeX           table + figure fragments suitable for ``\\input{}`` in a
                  paper. Charts as ``\\includegraphics{}``
  PDF             via WeasyPrint (HTML → PDF) — preserves the same charts +
                  styling as the HTML output
  Jupyter         (deferred) notebook output for interactive review

Two record kinds (Phase 1):

  proof           Empirical Proof Record (scenarios)
  audit           Audit Record (static analysis)

Renderers are *pure data* — they take a Record + a destination path and
write a file. No network, no side-effects beyond the destination path.
Chart helpers in ``chart_helpers.py`` are matplotlib-only and produce
base64-PNG strings or write PNG files; renderers compose them.

CLI:

  ophamin report <record.json> --format html|markdown|latex|pdf
"""

from __future__ import annotations

from ophamin.reporting.base import RecordKind, ReportFormat, ReportRenderer
from ophamin.reporting.chart_helpers import (
    bar_chart,
    confidence_interval_plot,
    histogram,
    pie_chart,
)
from ophamin.reporting.html_renderer import HTMLReporter
from ophamin.reporting.latex_renderer import LaTeXReporter
from ophamin.reporting.markdown_renderer import MarkdownReporter
from ophamin.reporting.runner import ReportRunner

__all__ = [
    "HTMLReporter",
    "LaTeXReporter",
    "MarkdownReporter",
    "RecordKind",
    "ReportFormat",
    "ReportRenderer",
    "ReportRunner",
    "bar_chart",
    "confidence_interval_plot",
    "histogram",
    "pie_chart",
]
