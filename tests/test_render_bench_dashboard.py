"""Hardening pins for scripts/render_bench_dashboard.py.

The script converts pytest-benchmark JSON output into a self-
contained HTML dashboard that ``.github/workflows/docs.yml``
publishes under ``https://idirbenslama.github.io/Ophamin/bench/``.

These tests validate:
- Pure-stdlib import surface (the script must run in slim CI envs)
- Round-trip from pytest-benchmark JSON to renderable HTML
- HTML well-formedness (matched tags, embedded raw JSON)
- Format helpers (time + ops with adaptive units)
- Multiple JSON-file handling (latest-by-mtime wins)
- CLI surface: directory input + file input + bad input rejection
"""

from __future__ import annotations

import html.parser
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Path to the script under test
SCRIPT = Path(__file__).parent.parent / "scripts" / "render_bench_dashboard.py"


# --------------------------------------------------------------------------
# Sample pytest-benchmark JSON (minimal shape — captures everything the
# renderer actually reads)
# --------------------------------------------------------------------------

SAMPLE_BENCH_JSON = {
    "machine_info": {
        "node": "test-runner-1",
        "processor": "x86_64",
        "machine": "x86_64",
        "python_implementation": "CPython",
        "python_version": "3.12.7",
        "release": "5.15.0",
        "system": "Linux",
        "cpu": {
            "brand_raw": "Intel(R) Xeon(R) Platinum 8370C",
            "count": 4,
            "arch_string_raw": "x86_64",
        },
    },
    "commit_info": {
        "id": "abc123def456789012345678901234567890abcd",
        "time": "2026-05-19T01:23:45+00:00",
        "branch": "main",
        "project": "Ophamin",
        "dirty": False,
    },
    "benchmarks": [
        {
            "name": "test_bench_proof_verify",
            "fullname": "tests/bench/test_bench_codec.py::test_bench_proof_verify",
            "stats": {
                "min": 0.00012,
                "max": 0.00018,
                "mean": 0.00014,
                "median": 0.00013,
                "stddev": 1e-5,
                "rounds": 1000,
                "ops": 7142.0,
            },
        },
        {
            "name": "test_bench_proof_canonical_bytes",
            "fullname": "tests/bench/test_bench_codec.py::test_bench_proof_canonical_bytes",
            "stats": {
                "min": 0.0000095,  # 9.5 μs
                "max": 0.000020,
                "mean": 0.000012,
                "median": 0.000011,
                "stddev": 2e-6,
                "rounds": 10000,
                "ops": 83333.0,
            },
        },
    ],
}


# --------------------------------------------------------------------------
# HTML well-formedness
# --------------------------------------------------------------------------


class _TagDepthChecker(html.parser.HTMLParser):
    """Tracks tag-depth + collects mismatched-close errors."""

    VOID_TAGS = frozenset({
        "meta", "br", "hr", "img", "input", "link", "area", "base",
        "col", "embed", "param", "source", "track", "wbr",
    })

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag not in self.VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(
                f"mismatched close <{tag}>; expected </{self.stack[-1] if self.stack else 'none'}>"
            )


def render_to_string(data: dict) -> str:
    """Helper: import the render module and produce HTML from data."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "render_bench_dashboard", SCRIPT
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.render_html(data)
    finally:
        sys.path.pop(0)


# --------------------------------------------------------------------------
# Script-level invariants
# --------------------------------------------------------------------------


def test_script_file_exists():
    assert SCRIPT.is_file(), f"render script missing at {SCRIPT}"


def test_script_is_pure_stdlib_imports():
    """The script MUST be runnable in a slim CI environment, so it
    can't depend on numpy / matplotlib / pandas / etc."""
    content = SCRIPT.read_text()
    # Get all import lines (stripping comments)
    imports = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("import ") or line.startswith("from "):
            imports.append(line)
    # Allowed: stdlib modules
    stdlib = {
        "argparse", "datetime", "html", "json", "sys", "pathlib",
        "typing", "os", "re", "io", "collections", "itertools",
        "functools", "tempfile", "shutil",
    }
    allowed_prefix = {"from __future__ "}
    for imp in imports:
        if any(imp.startswith(p) for p in allowed_prefix):
            continue
        if imp.startswith("import "):
            mod = imp.split()[1].split(".")[0].rstrip(",")
        else:  # from X import Y
            mod = imp.split()[1].split(".")[0]
        assert mod in stdlib, (
            f"Non-stdlib import in render script: {imp!r} "
            f"(module {mod!r}). The script must be pure stdlib so it "
            f"runs in slim CI environments."
        )


def test_script_has_main_function():
    """Standard CLI shape — `main(argv=None) -> int` entry point."""
    content = SCRIPT.read_text()
    assert "def main(" in content


def test_script_is_executable_via_python_dash_m():
    """The script must run via ``python scripts/render_bench_dashboard.py``."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "Render an Ophamin benchmark dashboard" in result.stdout


# --------------------------------------------------------------------------
# render_html() — output shape
# --------------------------------------------------------------------------


def test_render_html_is_well_formed():
    """Every opening tag has a matching close — load-bearing for
    consumers (mkdocs, browsers, accessibility tools)."""
    out = render_to_string(SAMPLE_BENCH_JSON)
    checker = _TagDepthChecker()
    checker.feed(out)
    assert checker.errors == [], f"HTML structure errors: {checker.errors}"
    assert checker.stack == [], f"Unclosed tags: {checker.stack}"


def test_render_html_starts_with_doctype():
    """A real browser-friendly page declares its DOCTYPE."""
    out = render_to_string(SAMPLE_BENCH_JSON)
    assert out.startswith("<!DOCTYPE html>")


def test_render_html_has_title():
    out = render_to_string(SAMPLE_BENCH_JSON)
    assert "<title>Ophamin benchmark dashboard</title>" in out


def test_render_html_has_table_with_correct_row_count():
    """Two benchmarks in input → two body rows in the table (plus one header row)."""
    out = render_to_string(SAMPLE_BENCH_JSON)
    # Each <tr> appears once for thead + once per bench in tbody
    # so 2 benchmarks → 3 <tr>s total
    assert out.count("<tr>") == 3, "expected 3 <tr> (1 thead + 2 benchmarks)"


def test_render_html_includes_machine_info():
    out = render_to_string(SAMPLE_BENCH_JSON)
    assert "Intel(R) Xeon(R) Platinum 8370C" in out
    assert "Linux" in out
    assert "CPython" in out
    assert "3.12.7" in out


def test_render_html_includes_commit_info():
    out = render_to_string(SAMPLE_BENCH_JSON)
    # First 12 chars of commit id
    assert "abc123def456" in out
    assert "main" in out
    # Commit time
    assert "2026-05-19" in out


def test_render_html_includes_benchmark_names():
    out = render_to_string(SAMPLE_BENCH_JSON)
    assert "test_bench_proof_verify" in out
    assert "test_bench_proof_canonical_bytes" in out


def test_render_html_orders_benchmarks_by_mean_ascending():
    """Fastest (smallest mean) first by default. The canonical_bytes
    bench (12 μs) sorts before the verify bench (140 μs)."""
    out = render_to_string(SAMPLE_BENCH_JSON)
    idx_canonical = out.find("test_bench_proof_canonical_bytes")
    idx_verify = out.find("test_bench_proof_verify")
    assert idx_canonical < idx_verify, (
        "canonical_bytes (faster) must appear before verify (slower)"
    )


def test_render_html_escapes_dangerous_chars_in_names():
    """If a benchmark name contains <script> or " characters, the
    HTML output must escape them. Otherwise rendering becomes an XSS
    vector for anyone who can inject benchmark names."""
    data = json.loads(json.dumps(SAMPLE_BENCH_JSON))  # deep copy
    data["benchmarks"][0]["name"] = "test_<script>alert(1)</script>"
    out = render_to_string(data)
    # Raw script tag must NOT appear in the visible HTML body
    # (the embedded raw_json escapes it via html.escape too)
    body_start = out.find("<tbody>")
    body_end = out.find("</tbody>")
    body = out[body_start:body_end]
    assert "<script>alert(1)</script>" not in body, (
        "benchmark name should be html-escaped in the rendered table"
    )
    assert "test_&lt;script&gt;" in body


def test_render_html_includes_embedded_raw_json():
    """The page is self-contained — anyone right-clicking + saving the
    HTML still has the raw bench data."""
    out = render_to_string(SAMPLE_BENCH_JSON)
    assert 'id="bench-json"' in out
    # And the structure is preserved (escaped) inside it
    assert "test_bench_proof_verify" in out


def test_render_html_has_sort_javascript():
    """Headers are click-to-sort — the JS section must be present."""
    out = render_to_string(SAMPLE_BENCH_JSON)
    assert "addEventListener('click'" in out
    assert "tbody.appendChild" in out


def test_render_html_includes_dark_mode_styles():
    """Operators on dark-mode systems should see the dashboard
    natively styled — accessibility / quality-of-life."""
    out = render_to_string(SAMPLE_BENCH_JSON)
    assert "prefers-color-scheme: dark" in out


def test_render_html_links_to_data_json():
    """The 'raw data' link points to the sidecar data.json file."""
    out = render_to_string(SAMPLE_BENCH_JSON)
    assert 'href="data.json"' in out


def test_render_html_handles_empty_benchmarks():
    """A bench run with zero benchmarks shouldn't crash — produces
    a valid (but empty) table."""
    data = {
        "machine_info": SAMPLE_BENCH_JSON["machine_info"],
        "commit_info": SAMPLE_BENCH_JSON["commit_info"],
        "benchmarks": [],
    }
    out = render_to_string(data)
    assert "<tbody>" in out  # table renders, even empty
    assert "</tbody>" in out
    # No bench rows in tbody
    body_start = out.find("<tbody>")
    body_end = out.find("</tbody>")
    body = out[body_start:body_end]
    assert "<tr>" not in body


# --------------------------------------------------------------------------
# format_seconds() + format_ops() — unit-adaptive
# --------------------------------------------------------------------------


def test_format_seconds_picks_unit():
    """Sanity-check the unit selection (the format helper is in the
    render script; we import it through the same path)."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "render_bench_dashboard", SCRIPT
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.format_seconds(1.5).endswith(" s")
        assert mod.format_seconds(0.005).endswith(" ms")
        assert mod.format_seconds(0.0000095).endswith(" μs")
        assert mod.format_seconds(9.5e-9).endswith(" ns")
    finally:
        sys.path.pop(0)


def test_format_ops_picks_unit():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "render_bench_dashboard", SCRIPT
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert "G ops/s" in mod.format_ops(2.5e9)
        assert "M ops/s" in mod.format_ops(2.5e6)
        assert "K ops/s" in mod.format_ops(2500)
        assert "ops/s" in mod.format_ops(500)  # bare ops, no K prefix
    finally:
        sys.path.pop(0)


# --------------------------------------------------------------------------
# CLI: file + directory + missing-path
# --------------------------------------------------------------------------


def test_cli_runs_against_directory(tmp_path):
    """Pointed at a directory containing pytest-benchmark JSON, emits
    index.html + data.json under the output directory."""
    bench_dir = tmp_path / "bench_storage" / "Linux-CPython-3.12-64bit"
    bench_dir.mkdir(parents=True)
    json_path = bench_dir / "0001_demo.json"
    json_path.write_text(json.dumps(SAMPLE_BENCH_JSON))

    out_dir = tmp_path / "dashboard"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "bench_storage"), str(out_dir)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (out_dir / "index.html").is_file()
    assert (out_dir / "data.json").is_file()


def test_cli_runs_against_single_json_file(tmp_path):
    """Pointed at a specific .json file, also works."""
    json_path = tmp_path / "0001_demo.json"
    json_path.write_text(json.dumps(SAMPLE_BENCH_JSON))

    out_dir = tmp_path / "dashboard"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(json_path), str(out_dir)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (out_dir / "index.html").is_file()


def test_cli_picks_most_recently_modified_json(tmp_path):
    """When multiple JSON files exist, the latest-by-mtime wins."""
    import time
    bench_dir = tmp_path / "bench_storage" / "Linux-CPython-3.12-64bit"
    bench_dir.mkdir(parents=True)
    # Older JSON
    older = bench_dir / "0001_old.json"
    older.write_text(json.dumps(SAMPLE_BENCH_JSON))
    time.sleep(0.05)  # ensure mtime difference
    # Newer JSON with a different benchmark name to distinguish
    newer_data = json.loads(json.dumps(SAMPLE_BENCH_JSON))
    newer_data["benchmarks"][0]["name"] = "test_distinctive_marker_for_newer"
    newer = bench_dir / "0002_new.json"
    newer.write_text(json.dumps(newer_data))

    out_dir = tmp_path / "dashboard"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "bench_storage"), str(out_dir)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    html_out = (out_dir / "index.html").read_text()
    assert "test_distinctive_marker_for_newer" in html_out


def test_cli_fails_loud_on_missing_input(tmp_path):
    out_dir = tmp_path / "dashboard"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "nonexistent"), str(out_dir)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0


def test_cli_fails_loud_on_empty_directory(tmp_path):
    """An empty bench storage directory → loud error, not silent
    success that produces an empty dashboard."""
    empty = tmp_path / "empty_storage"
    empty.mkdir()
    out_dir = tmp_path / "dashboard"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(empty), str(out_dir)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
    assert "no pytest-benchmark JSON found" in result.stderr.lower() or \
        "no pytest-benchmark json found" in result.stderr.lower()


def test_cli_data_json_is_valid_json(tmp_path):
    """The sidecar data.json must be parseable as JSON."""
    json_path = tmp_path / "0001_demo.json"
    json_path.write_text(json.dumps(SAMPLE_BENCH_JSON))

    out_dir = tmp_path / "dashboard"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(json_path), str(out_dir)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    # data.json should parse + contain the benchmarks key
    parsed = json.loads((out_dir / "data.json").read_text())
    assert "benchmarks" in parsed
    assert len(parsed["benchmarks"]) == len(SAMPLE_BENCH_JSON["benchmarks"])
    # The render script adds a "datetime" field
    assert "datetime" in parsed


def test_cli_creates_output_dir_recursively(tmp_path):
    """Output dir + any missing parents are created."""
    json_path = tmp_path / "0001_demo.json"
    json_path.write_text(json.dumps(SAMPLE_BENCH_JSON))

    deep_out = tmp_path / "a" / "b" / "c" / "dashboard"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(json_path), str(deep_out)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert (deep_out / "index.html").is_file()
