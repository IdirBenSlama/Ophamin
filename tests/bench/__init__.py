"""Performance micro-benches — Phase S3 of the elevation roadmap.

Run via:

    .venv/bin/python -m pytest tests/bench/ -q --benchmark-only \\
        --benchmark-storage=file:./bench_storage \\
        --benchmark-save=baseline

Compare a later run against the saved baseline via:

    .venv/bin/python -m pytest tests/bench/ -q --benchmark-only \\
        --benchmark-storage=file:./bench_storage \\
        --benchmark-compare=baseline --benchmark-compare-fail=mean:20%

Per-bench guidance lives in ``docs/BENCHMARKS_AND_COVERAGE.md``.
"""
