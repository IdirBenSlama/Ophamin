"""Tests for the wiring probe — wired / wire_candidate / orphan / archived
classification of each KimeraInventory surface.

Synthetic Kimera trees with controllable import graphs + annotations.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from ophamin.seeing.discovery import discover_all
from ophamin.seeing.discovery.kimera_inventory import StratumInventory, Surface
from ophamin.seeing.wiring import (
    ANNOTATION_PATTERNS,
    CompletenessReport,
    DEFAULT_SIGN_KEY,
    StratumCompleteness,
    SurfaceCompleteness,
    WiringProbe,
    build_import_graph,
    classify_surface,
    scan_annotations,
    scan_stubs,
)
from ophamin.seeing.wiring.wiring_probe import (
    _extract_imported_dotted_names,
    _is_stub_body,
)


# --------------------------------------------------------------------------
# Annotation scanner
# --------------------------------------------------------------------------


def test_scan_annotations_detects_wire_candidate():
    text = '"""\n.. note:: WIRE_CANDIDATE (Phase 284, 2026-04-11)\n"""\n'
    assert scan_annotations(text) == "WIRE_CANDIDATE"


def test_scan_annotations_detects_wired():
    text = '"""Module docstring.\n\n.. note:: WIRED (Phase 284 annotation cleared)\n"""\n'
    assert scan_annotations(text) == "WIRED"


def test_scan_annotations_wired_takes_precedence_over_wire_candidate():
    """A module that is BOTH annotated (history) — WIRED wins."""
    text = (
        '"""\n.. note:: WIRE_CANDIDATE (Phase 284 — STALE / RETRACTED)\n'
        '.. note:: WIRED (replacement annotation)\n"""\n'
    )
    assert scan_annotations(text) == "WIRED"


def test_scan_annotations_detects_deprecated():
    text = '""".. note:: DEPRECATED — superseded by newer X"""'
    assert scan_annotations(text) == "DEPRECATED"


def test_scan_annotations_returns_empty_when_none_present():
    text = '"""Just a regular module without annotations."""\nimport sys\n'
    assert scan_annotations(text) == ""


def test_scan_annotations_handles_archived_path_marker():
    text = "# This is an archived note\n.. note:: ARCHIVED 2026-04-30\n"
    assert scan_annotations(text) == "ARCHIVED"


def test_annotation_patterns_all_compile():
    for name, pat in ANNOTATION_PATTERNS.items():
        assert pat.search(f".. note:: {name}")


# --------------------------------------------------------------------------
# Stub-body detection
# --------------------------------------------------------------------------


def _func_body_from_src(src: str) -> list[ast.stmt]:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.body
    raise AssertionError("no function in source")


def test_stub_body_pass_only():
    assert _is_stub_body(_func_body_from_src("def f(): pass\n"))


def test_stub_body_raise_notimplementederror():
    assert _is_stub_body(_func_body_from_src(
        "def f():\n    raise NotImplementedError()\n"
    ))


def test_stub_body_raise_notimplementederror_no_parens():
    assert _is_stub_body(_func_body_from_src(
        "def f():\n    raise NotImplementedError\n"
    ))


def test_stub_body_return_none():
    assert _is_stub_body(_func_body_from_src(
        "def f():\n    return None\n"
    ))


def test_stub_body_bare_return():
    assert _is_stub_body(_func_body_from_src(
        "def f():\n    return\n"
    ))


def test_stub_body_docstring_then_pass_is_still_stub():
    assert _is_stub_body(_func_body_from_src(
        'def f():\n    """docstring"""\n    pass\n'
    ))


def test_stub_body_real_implementation_is_not_stub():
    assert not _is_stub_body(_func_body_from_src(
        "def f(x):\n    y = x + 1\n    return y\n"
    ))


def test_stub_body_raise_other_error_is_not_stub():
    assert not _is_stub_body(_func_body_from_src(
        "def f():\n    raise ValueError('bad')\n"
    ))


def test_scan_stubs_counts_correctly():
    src = (
        "def real(x): return x + 1\n"
        "def stub_pass(): pass\n"
        "async def stub_raise(): raise NotImplementedError()\n"
        "class C:\n"
        "    def m(self): return 42\n"
        "    def stub_m(self): pass\n"
    )
    tree = ast.parse(src)
    stubs, fns, cls = scan_stubs(tree)
    assert stubs == 3   # stub_pass, stub_raise, stub_m
    assert fns == 5     # real, stub_pass, stub_raise, m, stub_m
    assert cls == 1


# --------------------------------------------------------------------------
# Import-graph extraction
# --------------------------------------------------------------------------


def test_extract_imports_absolute():
    tree = ast.parse(
        "import foo\nimport bar.baz\nfrom qux import quux\n"
    )
    out = _extract_imported_dotted_names(tree, "kimera_swm.x")
    assert "foo" in out
    assert "bar.baz" in out
    assert "qux" in out
    assert "qux.quux" in out      # from-import implies a reference to submodule


def test_extract_imports_relative():
    tree = ast.parse("from .foo import Bar\n")
    out = _extract_imported_dotted_names(tree, "kimera_swm.domain.cognitive.takwin")
    # Resolve relative: parent package = kimera_swm.domain.cognitive
    assert "kimera_swm.domain.cognitive.foo" in out
    assert "kimera_swm.domain.cognitive.foo.Bar" in out


def test_extract_imports_dot_only_relative():
    """``from . import X`` — no module, just the parent."""
    tree = ast.parse("from . import sibling\n")
    out = _extract_imported_dotted_names(tree, "kimera_swm.pkg.module")
    assert "kimera_swm.pkg" in out
    assert "kimera_swm.pkg.sibling" in out


def test_extract_imports_star_does_not_emit_starred_target():
    tree = ast.parse("from foo import *\n")
    out = _extract_imported_dotted_names(tree, "kimera_swm.x")
    assert "foo" in out
    # The literal "*" must NOT be in the output.
    assert "foo.*" not in out


def test_build_import_graph_counts_incoming_edges(tmp_path):
    """A 3-file synthetic tree where module C is imported by both A and B."""
    src = tmp_path / "kimera_swm"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("from kimera_swm import c\nc.foo()\n")
    (src / "b.py").write_text("from kimera_swm.c import foo\n")
    (src / "c.py").write_text("def foo(): return 1\n")

    graph = build_import_graph(tmp_path)
    # ``c`` is referenced via two patterns: a.py imports ``kimera_swm.c`` and
    # b.py imports ``kimera_swm.c.foo`` (also counts as a reference to ``kimera_swm.c``).
    assert graph.get("kimera_swm.c", 0) >= 2


def test_build_import_graph_ignores_third_party():
    """Only ``kimera_swm.*`` targets are counted."""
    src = tmp_path = Path("/tmp") / "ophamin_test_external"
    if tmp_path.exists():
        import shutil
        shutil.rmtree(tmp_path)
    src = tmp_path / "kimera_swm"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "a.py").write_text("import requests\nimport sys\n")
    graph = build_import_graph(tmp_path)
    assert "requests" not in graph
    assert "sys" not in graph


def test_build_import_graph_handles_unparseable_files(tmp_path):
    src = tmp_path / "kimera_swm"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "broken.py").write_text("def f(:\n    pass\n")   # syntax error
    (src / "good.py").write_text("from kimera_swm import broken\n")
    # Should not raise; broken is still countable as a target.
    graph = build_import_graph(tmp_path)
    assert "kimera_swm.broken" in graph


# --------------------------------------------------------------------------
# Per-surface classification
# --------------------------------------------------------------------------


def _build_minimal_kimera(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


def test_classify_surface_wired(tmp_path):
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/x.py": "def foo(): pass\n",
        "kimera_swm/y.py": "from kimera_swm import x\nx.foo()\n",
    })
    surf = Surface(name="x", kind="module", file_path="kimera_swm/x.py",
                   line_count=1, metadata={})
    in_count = build_import_graph(repo)
    sc = classify_surface(repo, surf, "test", in_count)
    assert sc.classification == "wired"
    assert sc.incoming_imports >= 1


def test_classify_surface_orphan(tmp_path):
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/orphan.py": "def f(): pass\n",
    })
    surf = Surface(name="orphan", kind="module",
                   file_path="kimera_swm/orphan.py", line_count=1, metadata={})
    sc = classify_surface(repo, surf, "test", build_import_graph(repo))
    assert sc.classification == "orphan"
    assert sc.incoming_imports == 0


def test_classify_surface_wire_candidate(tmp_path):
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/scaffold.py": (
            '"""\n.. note:: WIRE_CANDIDATE (Phase 284, 2026-04-11)\n"""\n'
            "def f(): pass\n"
        ),
        "kimera_swm/uses.py": "from kimera_swm import scaffold\nscaffold.f()\n",
    })
    surf = Surface(name="scaffold", kind="module",
                   file_path="kimera_swm/scaffold.py", line_count=4, metadata={})
    sc = classify_surface(repo, surf, "test", build_import_graph(repo))
    # WIRE_CANDIDATE annotation wins even when imported.
    assert sc.classification == "wire_candidate"
    assert sc.annotation == "WIRE_CANDIDATE"


def test_classify_surface_wired_annotation_overrides_zero_imports(tmp_path):
    """A file annotated WIRED but nothing imports it is still 'wired' — the
    annotation is the declarative truth (per CLAUDE.md's Phase 284 cleanup pattern).
    """
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/declared.py": (
            '"""\n.. note:: WIRED (Phase 284 annotation cleared)\n"""\n'
            "def f(): pass\n"
        ),
    })
    surf = Surface(name="declared", kind="module",
                   file_path="kimera_swm/declared.py", line_count=4, metadata={})
    sc = classify_surface(repo, surf, "test", build_import_graph(repo))
    assert sc.classification == "wired"
    assert sc.annotation == "WIRED"


def test_classify_surface_archived_by_path(tmp_path):
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/_archive/old.py": "def f(): pass\n",
    })
    surf = Surface(name="old", kind="module",
                   file_path="kimera_swm/_archive/old.py", line_count=1, metadata={})
    sc = classify_surface(repo, surf, "test", build_import_graph(repo))
    assert sc.classification == "archived"


def test_classify_surface_archived_by_predecessor_suffix(tmp_path):
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/foo_predecessor.py": "def f(): pass\n",
    })
    surf = Surface(name="foo_predecessor", kind="module",
                   file_path="kimera_swm/foo_predecessor.py", line_count=1,
                   metadata={})
    sc = classify_surface(repo, surf, "test", build_import_graph(repo))
    assert sc.classification == "archived"


def test_classify_surface_parse_error(tmp_path):
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/broken.py": "def f(:\n    pass\n",   # syntax error
    })
    surf = Surface(name="broken", kind="module",
                   file_path="kimera_swm/broken.py", line_count=2, metadata={})
    sc = classify_surface(repo, surf, "test", build_import_graph(repo))
    assert sc.classification == "parse_error"
    assert "SyntaxError" in sc.parse_error


def test_classify_surface_config_for_non_python(tmp_path):
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/config.yml": "key: value\n",
    })
    surf = Surface(name="config", kind="config_file",
                   file_path="kimera_swm/config.yml", line_count=1, metadata={})
    sc = classify_surface(repo, surf, "test", build_import_graph(repo))
    assert sc.classification == "config"


def test_classify_surface_counts_stubs(tmp_path):
    repo = _build_minimal_kimera(tmp_path, {
        "kimera_swm/__init__.py": "",
        "kimera_swm/stubby.py": (
            "def f(): pass\n"
            "def g(): raise NotImplementedError\n"
            "def h(): return 7\n"
        ),
    })
    surf = Surface(name="stubby", kind="module",
                   file_path="kimera_swm/stubby.py", line_count=3, metadata={})
    sc = classify_surface(repo, surf, "test", build_import_graph(repo))
    assert sc.stub_count == 2
    assert sc.n_functions == 3
    assert sc.stub_density == pytest.approx(2 / 3)


# --------------------------------------------------------------------------
# WiringProbe — end-to-end
# --------------------------------------------------------------------------


@pytest.fixture
def fake_kimera_for_wiring(tmp_path):
    """A small Kimera with controllable wired/orphan distribution."""
    # 2 cognitive (wired via internal cross-refs)
    files = {
        "kimera_swm/__init__.py": "",
        "kimera_swm/domain/__init__.py": "",
        "kimera_swm/domain/cognitive/__init__.py": "",
        "kimera_swm/domain/cognitive/takwin.py": "def run(): return 1\n",
        "kimera_swm/domain/cognitive/walker.py": (
            "from kimera_swm.domain.cognitive import takwin\nclass Walker: pass\n"
        ),
        # Interface — 2 routers, one orphan
        "kimera_swm/api/__init__.py": "",
        "kimera_swm/api/routers/__init__.py": "",
        "kimera_swm/api/routers/wired_router.py": "def get(): pass\n",
        "kimera_swm/api/routers/orphan_router.py": "def get(): pass\n",
        # Transport — 1 wired
        "kimera_swm/domain/piovra/__init__.py": "",
        "kimera_swm/domain/piovra/transports/__init__.py": "",
        "kimera_swm/domain/piovra/transports/tcp.py": "def connect(): pass\n",
        # Use the wired_router + tcp
        "kimera_swm/main.py": (
            "from kimera_swm.api.routers import wired_router\n"
            "from kimera_swm.domain.piovra.transports import tcp\n"
        ),
    }
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


def test_wiring_probe_against_synthetic_kimera(fake_kimera_for_wiring):
    inv = discover_all(fake_kimera_for_wiring)
    report = WiringProbe(fake_kimera_for_wiring).probe(inv)
    assert isinstance(report, CompletenessReport)
    assert report.signature
    assert report.verify(DEFAULT_SIGN_KEY)

    iface = report.stratum("interface")
    assert iface is not None
    assert iface.n_total == 2
    assert iface.n_wired == 1          # wired_router
    assert iface.n_orphan == 1         # orphan_router


def test_wiring_probe_lists_orphan_files(fake_kimera_for_wiring):
    inv = discover_all(fake_kimera_for_wiring)
    report = WiringProbe(fake_kimera_for_wiring).probe(inv)
    orphans = report.orphan_surfaces()
    orphan_paths = {s.file_path for s in orphans}
    assert "kimera_swm/api/routers/orphan_router.py" in orphan_paths


def test_wiring_probe_signs_and_round_trips(fake_kimera_for_wiring):
    inv = discover_all(fake_kimera_for_wiring)
    report = WiringProbe(fake_kimera_for_wiring).probe(inv)
    text = report.to_json()
    rebuilt = CompletenessReport.from_dict(json.loads(text))
    assert rebuilt.report_id == report.report_id
    assert rebuilt.total_surfaces() == report.total_surfaces()
    assert rebuilt.verify(DEFAULT_SIGN_KEY)


def test_wiring_probe_tampering_breaks_signature(fake_kimera_for_wiring):
    inv = discover_all(fake_kimera_for_wiring)
    report = WiringProbe(fake_kimera_for_wiring).probe(inv)
    tampered = CompletenessReport(
        ophamin_version=report.ophamin_version,
        ophamin_git_commit=report.ophamin_git_commit,
        kimera_repo_path=report.kimera_repo_path,
        kimera_git_commit=report.kimera_git_commit,
        surfaces=report.surfaces[1:],     # drop one
        per_stratum=report.per_stratum,
        captured_at=report.captured_at,
        schema_version=report.schema_version,
        signature=report.signature,       # keep old
    )
    assert not tampered.verify(DEFAULT_SIGN_KEY)


def test_wiring_probe_loud_failure_on_missing_repo(tmp_path):
    nonexistent = tmp_path / "no_such_kimera"
    with pytest.raises(FileNotFoundError):
        WiringProbe(nonexistent)


def test_wiring_probe_markdown_renders_action_list(fake_kimera_for_wiring):
    inv = discover_all(fake_kimera_for_wiring)
    report = WiringProbe(fake_kimera_for_wiring).probe(inv)
    md = report.to_markdown()
    assert "# Ophamin Substrate Completeness Report" in md
    assert "## 2. Per-stratum wiring distribution" in md
    assert "orphan_router" in md


def test_surface_completeness_to_dict_round_trip(fake_kimera_for_wiring):
    inv = discover_all(fake_kimera_for_wiring)
    report = WiringProbe(fake_kimera_for_wiring).probe(inv)
    for s in report.surfaces:
        d = s.to_dict()
        assert d["surface_name"] == s.surface_name
        assert d["classification"] == s.classification


def test_stratum_completeness_rates_correct(fake_kimera_for_wiring):
    inv = discover_all(fake_kimera_for_wiring)
    report = WiringProbe(fake_kimera_for_wiring).probe(inv)
    iface = report.stratum("interface")
    assert iface is not None
    # 1 wired, 1 orphan out of 2 → 50/50
    assert iface.wired_rate == pytest.approx(0.5)
    assert iface.orphan_rate == pytest.approx(0.5)


# --------------------------------------------------------------------------
# WiringProbe.scan_all — every .py file, bucketed by top-level subdir
# --------------------------------------------------------------------------


def test_scan_all_classifies_every_python_file(fake_kimera_for_wiring):
    report = WiringProbe(fake_kimera_for_wiring).scan_all()
    # Fixture has ≥ 5 non-__init__ modules: takwin, walker, wired_router,
    # orphan_router, tcp, main. __init__.py files are excluded by design.
    assert report.total_surfaces() >= 5
    valid = {"wired", "wire_candidate", "orphan", "archived", "parse_error", "config"}
    for s in report.surfaces:
        assert s.classification in valid


def test_scan_all_buckets_by_top_level_subdir(fake_kimera_for_wiring):
    report = WiringProbe(fake_kimera_for_wiring).scan_all()
    buckets = {s.stratum for s in report.per_stratum}
    # The fixture has modules under domain/, api/, etc.
    assert "domain" in buckets or "api" in buckets


def test_scan_all_collapses_top_level_scripts_into_one_bucket(tmp_path):
    """Top-level standalone scripts should all bucket as 'scripts'."""
    (tmp_path / "kimera_swm").mkdir()
    (tmp_path / "kimera_swm/__init__.py").write_text("")
    for name in ("verify_x.py", "benchmark_y.py", "debug_z.py"):
        (tmp_path / "kimera_swm" / name).write_text("def f(): pass\n")
    report = WiringProbe(tmp_path).scan_all()
    scripts = report.stratum("scripts")
    assert scripts is not None
    assert scripts.n_total == 3
    # Make sure no bucket is named after one of these files.
    bad = {b for b in (s.stratum for s in report.per_stratum) if b.endswith(".py")}
    assert bad == set(), f"per-file buckets leaked: {bad}"


def test_scan_all_buckets_tests_separately(tmp_path):
    (tmp_path / "kimera_swm").mkdir()
    (tmp_path / "kimera_swm/__init__.py").write_text("")
    (tmp_path / "kimera_swm/tests").mkdir()
    (tmp_path / "kimera_swm/tests/test_a.py").write_text("def test_x(): pass\n")
    (tmp_path / "kimera_swm/tests/test_b.py").write_text("def test_y(): pass\n")
    report = WiringProbe(tmp_path).scan_all()
    tests = report.stratum("tests")
    assert tests is not None
    assert tests.n_total == 2


def test_scan_all_loud_failure_when_kimera_swm_subdir_missing(tmp_path):
    (tmp_path / "not_kimera_swm").mkdir()
    with pytest.raises(FileNotFoundError, match="kimera_swm/ subdirectory missing"):
        WiringProbe(tmp_path).scan_all()


def test_scan_all_skips_init_and_pycache(tmp_path):
    """__init__.py + __pycache__ excluded from the scan."""
    (tmp_path / "kimera_swm").mkdir()
    (tmp_path / "kimera_swm/__init__.py").write_text("")
    (tmp_path / "kimera_swm/__pycache__").mkdir()
    (tmp_path / "kimera_swm/__pycache__/cached.cpython-312.pyc").write_text("")
    (tmp_path / "kimera_swm/real.py").write_text("def f(): pass\n")
    report = WiringProbe(tmp_path).scan_all()
    file_paths = {s.file_path for s in report.surfaces}
    assert "kimera_swm/real.py" in file_paths
    assert not any("__init__.py" in p for p in file_paths)
    assert not any("__pycache__" in p for p in file_paths)


def test_scan_all_is_signed(fake_kimera_for_wiring):
    report = WiringProbe(fake_kimera_for_wiring).scan_all()
    assert report.signature
    assert report.verify(DEFAULT_SIGN_KEY)
