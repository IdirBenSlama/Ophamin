#!/usr/bin/env python3
"""Render a self-contained HTML dashboard from pytest-benchmark JSON output.

Reads the most recent pytest-benchmark JSON file from a storage
directory (the layout produced by ``pytest --benchmark-storage=...``
with ``--benchmark-save=<name>``) and emits a static HTML page +
JSON sidecar at the output directory.

Used by ``.github/workflows/bench.yml`` to produce the bench
dashboard that ``docs.yml`` publishes under
``https://idirbenslama.github.io/Ophamin/bench/``.

Pure Python stdlib — no external dependencies — so the script
runs cleanly in a slim CI environment.

Usage::

    python scripts/render_bench_dashboard.py \\
        bench_storage/Linux-CPython-3.12-64bit \\
        /tmp/bench_dashboard

The dashboard is one self-contained ``index.html`` (data
embedded inline; no XHR / no external CSS) + a sidecar
``data.json`` for machine consumers.

The HTML page renders a sortable table, per-benchmark
ASCII-ish bar charts, machine metadata, and the commit info
that produced the run.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
import sys
from pathlib import Path
from typing import Any


def find_latest_json(storage_dir: Path) -> Path:
    """Return the most-recently-modified ``*.json`` under ``storage_dir``.

    pytest-benchmark stores results under
    ``<storage_dir>/<machine-tag>/NNNN_<save-name>.json``. We pick
    the freshest file regardless of nesting depth.
    """
    candidates = sorted(
        storage_dir.rglob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"no pytest-benchmark JSON found under {storage_dir}"
        )
    return candidates[0]


def format_seconds(s: float) -> str:
    """Human-friendly time format with adaptive units."""
    if s >= 1.0:
        return f"{s:.3f} s"
    if s >= 1e-3:
        return f"{s * 1e3:.3f} ms"
    if s >= 1e-6:
        return f"{s * 1e6:.2f} μs"
    return f"{s * 1e9:.0f} ns"


def format_ops(ops: float) -> str:
    """Operations-per-second with K/M/G suffix."""
    if ops >= 1e9:
        return f"{ops / 1e9:.2f} G ops/s"
    if ops >= 1e6:
        return f"{ops / 1e6:.2f} M ops/s"
    if ops >= 1e3:
        return f"{ops / 1e3:.2f} K ops/s"
    return f"{ops:.1f} ops/s"


def render_html(data: dict[str, Any]) -> str:
    """Produce a self-contained HTML page for the benchmark data."""
    machine = data.get("machine_info", {})
    commit = data.get("commit_info", {})
    benchmarks = data.get("benchmarks", [])
    datetime_str = data.get("datetime", "")

    # Sort by mean (fastest first) by default — operators usually look
    # for the slowest at the top, but the JS table handles re-sort.
    benchmarks_sorted = sorted(
        benchmarks,
        key=lambda b: b.get("stats", {}).get("mean", 0),
    )

    # Find the slowest mean to scale the bar chart
    max_mean = max(
        (b.get("stats", {}).get("mean", 0) for b in benchmarks_sorted),
        default=0,
    )

    rows = []
    for idx, bench in enumerate(benchmarks_sorted):
        name = bench.get("name", "?")
        stats = bench.get("stats", {})
        mean = stats.get("mean", 0)
        median = stats.get("median", 0)
        min_t = stats.get("min", 0)
        max_t = stats.get("max", 0)
        stddev = stats.get("stddev", 0)
        ops = stats.get("ops", 0)
        rounds = stats.get("rounds", 0)
        bar_pct = (mean / max_mean * 100) if max_mean else 0

        rows.append(
            "<tr>"
            f"<td class='idx'>{idx + 1}</td>"
            f"<td class='name'>{html.escape(name)}</td>"
            f"<td class='num'>{html.escape(format_seconds(min_t))}</td>"
            f"<td class='num'>{html.escape(format_seconds(median))}</td>"
            f"<td class='num emph'>{html.escape(format_seconds(mean))}</td>"
            f"<td class='num'>{html.escape(format_seconds(max_t))}</td>"
            f"<td class='num'>{html.escape(format_seconds(stddev))}</td>"
            f"<td class='num'>{html.escape(format_ops(ops))}</td>"
            f"<td class='num'>{rounds}</td>"
            f"<td class='bar'><div class='bar-inner' style='width:{bar_pct:.1f}%'></div></td>"
            "</tr>"
        )

    cpu_info = machine.get("cpu", {})
    cpu_brand = cpu_info.get("brand_raw") or cpu_info.get("arch_string_raw") or "?"
    cpu_count = cpu_info.get("count", "?")

    commit_id = commit.get("id", "")
    commit_short = commit_id[:12] if commit_id else "?"
    commit_branch = commit.get("branch", "?")
    commit_time = commit.get("time", "?")

    # Embed the raw JSON so the page is self-contained — anyone
    # right-clicking + saving the HTML keeps the data with it.
    raw_json = json.dumps(data, sort_keys=True)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ophamin benchmark dashboard</title>
<style>
:root {{
  --fg: #1e1e1e;
  --fg-muted: #5b5b5b;
  --bg: #fdfdfd;
  --border: #d0d0d0;
  --bar: #5a8dee;
  --emph: #d97706;
  --code-bg: #f4f4f4;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --fg: #e8e8e8;
    --fg-muted: #a0a0a0;
    --bg: #1a1a1a;
    --border: #333;
    --bar: #6ea2f5;
    --emph: #f59e0b;
    --code-bg: #232323;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  font-size: 14px;
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.45;
}}
header {{
  padding: 1.5rem 2rem 1rem 2rem;
  border-bottom: 1px solid var(--border);
}}
h1 {{ margin: 0 0 0.5rem 0; font-size: 1.5rem; font-weight: 600; }}
.subtitle {{ color: var(--fg-muted); margin-top: 0.25rem; }}
.meta {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin: 1rem 2rem;
  padding: 1rem;
  background: var(--code-bg);
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}}
.meta dt {{ font-weight: 600; margin-top: 0.25rem; color: var(--fg-muted); }}
.meta dd {{ margin: 0.1rem 0 0 0; padding: 0; }}
.meta-block {{ min-width: 0; }}
table {{
  width: calc(100% - 4rem);
  margin: 1rem 2rem 3rem 2rem;
  border-collapse: collapse;
  font-size: 13px;
}}
thead th {{
  background: var(--code-bg);
  border-bottom: 2px solid var(--border);
  text-align: left;
  padding: 0.5rem 0.6rem;
  font-weight: 600;
  position: sticky;
  top: 0;
  user-select: none;
  cursor: pointer;
}}
thead th.num, thead th.bar {{ text-align: right; }}
thead th.bar {{ text-align: left; }}
thead th::after {{ content: ' ↕'; opacity: 0.4; font-size: 0.8em; }}
tbody td {{
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border);
}}
tbody tr:hover {{ background: var(--code-bg); }}
tbody td.idx {{ color: var(--fg-muted); width: 2.5rem; text-align: right; font-family: ui-monospace, monospace; }}
tbody td.name {{
  font-family: ui-monospace, monospace;
  font-size: 12px;
  word-break: break-all;
  min-width: 18rem;
}}
tbody td.num {{ font-family: ui-monospace, monospace; text-align: right; white-space: nowrap; }}
tbody td.num.emph {{ color: var(--emph); font-weight: 600; }}
tbody td.bar {{ width: 18rem; padding-right: 1rem; }}
.bar-inner {{
  height: 8px;
  background: var(--bar);
  border-radius: 2px;
  min-width: 1px;
}}
footer {{
  border-top: 1px solid var(--border);
  padding: 1rem 2rem;
  color: var(--fg-muted);
  font-size: 12px;
}}
a {{ color: var(--bar); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
code {{
  background: var(--code-bg);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-size: 0.92em;
}}
</style>
</head>
<body>
<header>
  <h1>Ophamin benchmark dashboard</h1>
  <div class="subtitle">
    pytest-benchmark results published via the
    <a href="https://github.com/IdirBenSlama/Ophamin/blob/main/.github/workflows/bench.yml"><code>bench</code></a>
    workflow.
    See <a href="https://github.com/IdirBenSlama/Ophamin/blob/main/docs/BENCHMARKS_AND_COVERAGE.md">BENCHMARKS_AND_COVERAGE.md</a>
    for the pinned baseline + regression gate (>25% slowdown fails CI).
  </div>
</header>
<dl class="meta">
  <div class="meta-block">
    <dt>Machine</dt>
    <dd>{html.escape(machine.get("system", "?"))} {html.escape(machine.get("release", ""))} ({html.escape(machine.get("machine", "?"))})</dd>
    <dt>CPU</dt>
    <dd>{html.escape(str(cpu_brand))} × {html.escape(str(cpu_count))} core</dd>
    <dt>Python</dt>
    <dd>{html.escape(machine.get("python_implementation", "?"))} {html.escape(machine.get("python_version", "?"))}</dd>
  </div>
  <div class="meta-block">
    <dt>Commit</dt>
    <dd><a href="https://github.com/IdirBenSlama/Ophamin/commit/{html.escape(commit_id)}"><code>{html.escape(commit_short)}</code></a></dd>
    <dt>Branch</dt>
    <dd>{html.escape(str(commit_branch))}</dd>
    <dt>Run time</dt>
    <dd>{html.escape(str(commit_time))}</dd>
  </div>
  <div class="meta-block">
    <dt>Benchmarks measured</dt>
    <dd>{len(benchmarks_sorted)}</dd>
    <dt>Dashboard generated</dt>
    <dd>{html.escape(datetime_str)}</dd>
    <dt>Raw data</dt>
    <dd><a href="data.json">data.json</a> (download)</dd>
  </div>
</dl>
<table id="bench-table">
<thead>
<tr>
<th data-col="idx">#</th>
<th data-col="name">Benchmark</th>
<th class="num" data-col="min">min</th>
<th class="num" data-col="median">median</th>
<th class="num" data-col="mean">mean</th>
<th class="num" data-col="max">max</th>
<th class="num" data-col="stddev">stddev</th>
<th class="num" data-col="ops">ops/s</th>
<th class="num" data-col="rounds">rounds</th>
<th class="bar" data-col="bar">relative</th>
</tr>
</thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
<footer>
  Ophamin benchmark dashboard — generated by <code>scripts/render_bench_dashboard.py</code>.
  Hardware noise: GitHub-hosted runners have variable load; absolute numbers don't
  cross-machine-compare. The shape is what matters.
  Click any column header to sort by that column.
</footer>
<script>
// Click-to-sort table (numeric for `num`/`bar` columns, lexical for the rest).
(function() {{
  const table = document.getElementById('bench-table');
  const tbody = table.querySelector('tbody');
  table.querySelectorAll('thead th').forEach((th, colIdx) => {{
    let ascending = true;
    th.addEventListener('click', () => {{
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const isNumeric = th.classList.contains('num') || th.classList.contains('bar');
      rows.sort((a, b) => {{
        const va = a.cells[colIdx].textContent.trim();
        const vb = b.cells[colIdx].textContent.trim();
        if (isNumeric) {{
          // Parse first leading numeric (handles "12.3 ms", "1.2 K ops/s", etc.)
          const pa = parseFloat(va.replace(/[^0-9.\\-eE]+.*$/, ''));
          const pb = parseFloat(vb.replace(/[^0-9.\\-eE]+.*$/, ''));
          // Unit suffix matters for time columns — multiply by unit factor
          const factor = (s) => {{
            if (s.includes(' s')) return 1;
            if (s.includes(' ms')) return 1e-3;
            if (s.includes(' μs') || s.includes(' us')) return 1e-6;
            if (s.includes(' ns')) return 1e-9;
            if (s.includes(' G')) return 1e9;
            if (s.includes(' M')) return 1e6;
            if (s.includes(' K')) return 1e3;
            return 1;
          }};
          const sa = (pa || 0) * factor(va);
          const sb = (pb || 0) * factor(vb);
          return ascending ? sa - sb : sb - sa;
        }}
        return ascending ? va.localeCompare(vb) : vb.localeCompare(va);
      }});
      ascending = !ascending;
      rows.forEach(r => tbody.appendChild(r));
    }});
  }});
}})();
</script>
<!-- Raw pytest-benchmark JSON for archival / machine consumption. -->
<script id="bench-json" type="application/json">{html.escape(raw_json)}</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render an Ophamin benchmark dashboard."
    )
    parser.add_argument(
        "storage",
        type=Path,
        help="pytest-benchmark storage directory (or a specific JSON file)",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output directory for index.html + data.json",
    )
    args = parser.parse_args(argv)

    src: Path = args.storage
    out_dir: Path = args.output

    if src.is_dir():
        json_path = find_latest_json(src)
    elif src.is_file() and src.suffix == ".json":
        json_path = src
    else:
        print(f"ERROR: {src} is neither a directory nor a .json file", file=sys.stderr)
        return 1

    print(f"Reading benchmarks from {json_path}", file=sys.stderr)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    # Stamp the dashboard with the render timestamp so consumers can
    # tell how fresh it is independent of the bench run time.
    data["datetime"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data.json").write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    html_text = render_html(data)
    (out_dir / "index.html").write_text(html_text, encoding="utf-8")

    print(
        f"Wrote {out_dir / 'index.html'} "
        f"({len(html_text):,} bytes; {len(data.get('benchmarks', []))} benchmarks)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
