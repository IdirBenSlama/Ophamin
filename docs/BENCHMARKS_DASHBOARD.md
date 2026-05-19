# Benchmarks dashboard

> Live, browser-renderable dashboard of the latest `bench` workflow
> run's pytest-benchmark results. Updated automatically on every
> push to main + on tag pushes.

## Open the dashboard

**[Open the live dashboard →](https://idirbenslama.github.io/Ophamin/bench/){target="_blank"}**

The dashboard is a self-contained HTML page rendered by
[`scripts/render_bench_dashboard.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/scripts/render_bench_dashboard.py)
from the most recent successful run of the
[`bench` workflow](https://github.com/IdirBenSlama/Ophamin/actions/workflows/bench.yml).

What's there:

- Machine + commit metadata (CPU, Python version, branch, commit SHA + time)
- Sortable table of every benchmark with min / median / mean / max / stddev / ops-per-second / rounds
- Relative-time bar chart (visualises each benchmark's mean as a fraction of the slowest)
- Light / dark mode (follows the browser's `prefers-color-scheme`)
- Sidecar [`data.json`](https://idirbenslama.github.io/Ophamin/bench/data.json){target="_blank"} for machine
  consumers — the raw pytest-benchmark JSON the dashboard was rendered from

## How it works

```text
   ┌─────────────────────────────┐
   │  bench workflow (push/PR)   │
   │  pytest-benchmark           │
   │   ↓                         │
   │  bench_storage/*.json       │
   │   ↓                         │
   │  render_bench_dashboard.py  │
   │   ↓                         │
   │  index.html + data.json     │
   │   ↓                         │
   │  upload-artifact "bench-    │
   │   dashboard" (90d retention)│
   └─────────────────────────────┘
                  │
                  ↓ (cross-workflow fetch)
   ┌─────────────────────────────┐
   │  docs workflow (push to     │
   │  main)                      │
   │   ↓                         │
   │  gh run download bench-     │
   │   dashboard → site/bench/   │
   │   ↓                         │
   │  mkdocs build → site/       │
   │   ↓                         │
   │  deploy to GitHub Pages     │
   └─────────────────────────────┘
                  │
                  ↓
   https://idirbenslama.github.io/Ophamin/bench/
```

The render script is **pure Python stdlib** — no matplotlib, no
pandas, no JS framework. The dashboard renders without any
external dependency (CSS + JS embedded inline).

## What the dashboard does NOT show

- **Cross-commit comparison** — the dashboard reflects the latest
  run only. The pinned baseline (in
  [`BENCHMARKS_AND_COVERAGE.md`](BENCHMARKS_AND_COVERAGE.md)) is
  the cross-run reference; the workflow's `>25% regression`
  gate fires against that file, not the dashboard.
- **Historical trends** — bench artifacts have 90-day retention.
  For longer-term tracking, the workflow's GitHub Actions run
  history is the source of truth.
- **Per-PR previews** — pull requests build the docs (preview
  only) but don't deploy. The dashboard reflects main-branch
  state only.

## Hardware noise caveat

GitHub-hosted runners have variable load; absolute numbers don't
cross-machine-compare. The dashboard is for **shape inspection**
(which bench is the slowest, which has the highest stddev, is the
ordering stable across runs) — not for comparing to your local
laptop's numbers.

## Reproducing the dashboard locally

```bash
# 1. Run the benches against your local checkout
PYTHONPATH=src python -m pytest tests/bench/ -q \
    --benchmark-only \
    --benchmark-storage=./bench_storage \
    --benchmark-save=local

# 2. Render the dashboard
python scripts/render_bench_dashboard.py \
    bench_storage \
    /tmp/ophamin_bench_dashboard

# 3. Open it
open /tmp/ophamin_bench_dashboard/index.html   # macOS
# xdg-open /tmp/ophamin_bench_dashboard/index.html   # Linux
```

The locally-generated dashboard is byte-identical to the CI one
when run against the same JSON input — the script is deterministic
modulo the embedded render timestamp.

## See also

- [BENCHMARKS_AND_COVERAGE.md](BENCHMARKS_AND_COVERAGE.md) — the
  pinned baseline + regression gate semantics
- [`scripts/render_bench_dashboard.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/scripts/render_bench_dashboard.py) — the renderer source
- [`.github/workflows/bench.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/.github/workflows/bench.yml) — the bench workflow
- [`.github/workflows/docs.yml`](https://github.com/IdirBenSlama/Ophamin/blob/main/.github/workflows/docs.yml) — the docs workflow that publishes the dashboard
