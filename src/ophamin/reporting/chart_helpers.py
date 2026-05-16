"""Matplotlib chart helpers — produces base64-PNG strings or writes PNG files.

The four chart shapes the reporting wheel needs:

  histogram(values, ...)                  per-cycle distribution (wall-time,
                                          CPU, RSS, dissonance_events_count)
  bar_chart(labels, counts, ...)          severity histograms, per-pillar
                                          findings, top hotspots
  pie_chart(labels, counts, ...)          severity-fraction, halt-mode
                                          distribution
  confidence_interval_plot(value, lo, hi,
                           threshold, ...) the load-bearing proof-record
                                          visual: observed value with Wilson
                                          CI bracket against the pre-
                                          registered threshold (forest-plot
                                          shape)

Every helper returns ``str`` (base64-PNG when ``out_path`` is None) or the
``Path`` written. ``write=True`` is implied when ``out_path`` is passed.

The chart helpers are pure data — no styling configuration leaks state
between calls. Each call constructs its own figure, draws, and closes.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")  # headless backend — no display required
import matplotlib.pyplot as plt   # noqa: E402


def _save_or_b64(fig: "matplotlib.figure.Figure", out_path: Path | None) -> str | Path:
    """Either write the figure as PNG to ``out_path`` or return a base64
    string suitable for inline HTML/Markdown embedding."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(buf.getvalue())
        return out_path
    return base64.b64encode(buf.getvalue()).decode("ascii")


def histogram(
    values: Iterable[float],
    *,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "count",
    bins: int = 20,
    out_path: Path | None = None,
    color: str = "#3b82f6",
) -> str | Path:
    """Histogram of a 1-D distribution. Empty data produces a clean "no data"
    placeholder rather than crashing."""
    vals = list(values)
    fig, ax = plt.subplots(figsize=(6.0, 3.5))
    if vals:
        ax.hist(vals, bins=bins, color=color, edgecolor="white", alpha=0.85)
    else:
        ax.text(0.5, 0.5, "(no data)", ha="center", va="center",
                transform=ax.transAxes, color="#666666")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return _save_or_b64(fig, out_path)


def bar_chart(
    labels: list[str],
    counts: list[float],
    *,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "count",
    out_path: Path | None = None,
    horizontal: bool = False,
    color: str = "#2563eb",
    max_labels: int = 20,
) -> str | Path:
    """Bar chart from parallel labels + counts. Truncates to ``max_labels``."""
    if len(labels) != len(counts):
        raise ValueError(
            f"bar_chart: labels ({len(labels)}) and counts ({len(counts)}) "
            f"must be the same length"
        )
    if max_labels and len(labels) > max_labels:
        labels = labels[:max_labels]
        counts = counts[:max_labels]
    fig, ax = plt.subplots(figsize=(7.0, max(3.0, 0.32 * max(1, len(labels)))))
    if not labels:
        ax.text(0.5, 0.5, "(no data)", ha="center", va="center",
                transform=ax.transAxes, color="#666666")
    elif horizontal:
        ax.barh(range(len(labels)), counts, color=color, alpha=0.85)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlabel(ylabel)  # axes swap when horizontal
    else:
        ax.bar(range(len(labels)), counts, color=color, alpha=0.85)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.grid(True, axis="x" if horizontal else "y", alpha=0.3)
    fig.tight_layout()
    return _save_or_b64(fig, out_path)


# Severity-aware colour palette used by audit reports
SEVERITY_COLORS = {
    "critical": "#991b1b",  # red-800
    "high":     "#dc2626",  # red-600
    "medium":   "#d97706",  # amber-600
    "low":      "#3b82f6",  # blue-500
    "info":     "#6b7280",  # gray-500
}


def pie_chart(
    labels: list[str],
    counts: list[float],
    *,
    title: str = "",
    out_path: Path | None = None,
    color_map: dict[str, str] | None = None,
) -> str | Path:
    """Pie of categorical counts. If ``color_map`` is given, label-keyed
    colours are used (falls back to matplotlib default for missing labels)."""
    if len(labels) != len(counts):
        raise ValueError(
            f"pie_chart: labels ({len(labels)}) and counts ({len(counts)}) "
            f"must be the same length"
        )
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    if not labels or sum(counts) == 0:
        ax.text(0.5, 0.5, "(no data)", ha="center", va="center",
                transform=ax.transAxes, color="#666666")
        ax.axis("off")
    else:
        colors = None
        if color_map:
            colors = [color_map.get(lbl, "#94a3b8") for lbl in labels]
        ax.pie(
            counts,
            labels=labels,
            autopct="%1.1f%%",
            colors=colors,
            startangle=90,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        ax.axis("equal")
    ax.set_title(title)
    fig.tight_layout()
    return _save_or_b64(fig, out_path)


def confidence_interval_plot(
    observed_value: float,
    ci_low: float | None,
    ci_high: float | None,
    threshold_value: float,
    *,
    threshold_comparator: str = ">=",
    title: str = "",
    xlabel: str = "value",
    out_path: Path | None = None,
) -> str | Path:
    """The load-bearing proof-record visual: observed value with CI bracket
    against the pre-registered threshold. Threshold drawn as a vertical line;
    observed value as a point with a horizontal CI line; pass/fail region
    shaded according to the comparator.
    """
    fig, ax = plt.subplots(figsize=(8.0, 1.8))

    # x-range covers both the CI and the threshold with a padding
    candidates_low: list[float] = [
        v for v in (ci_low, observed_value, threshold_value) if v is not None
    ]
    candidates_high: list[float] = [
        v for v in (ci_high, observed_value, threshold_value) if v is not None
    ]
    x_min = min(candidates_low)
    x_max = max(candidates_high)
    pad = max(0.05, (x_max - x_min) * 0.10)
    ax.set_xlim(x_min - pad, x_max + pad)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel(xlabel)
    ax.set_title(title)

    # threshold line
    ax.axvline(threshold_value, color="#dc2626", linestyle="--", linewidth=1.5,
               label=f"threshold {threshold_comparator} {threshold_value:.3f}")
    # pass region shading
    if threshold_comparator in (">=", ">"):
        ax.axvspan(threshold_value, x_max + pad, color="#10b981", alpha=0.10)
    elif threshold_comparator in ("<=", "<"):
        ax.axvspan(x_min - pad, threshold_value, color="#10b981", alpha=0.10)
    # CI bracket
    if ci_low is not None and ci_high is not None:
        ax.hlines(0.5, ci_low, ci_high, color="#1f2937", linewidth=2.5)
        ax.vlines([ci_low, ci_high], 0.42, 0.58, color="#1f2937", linewidth=2.5)
    # observed value point
    ax.plot(observed_value, 0.5, "o", markersize=10, color="#2563eb",
            label=f"observed {observed_value:.3f}")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return _save_or_b64(fig, out_path)
