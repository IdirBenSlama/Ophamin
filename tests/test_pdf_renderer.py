"""Tests for PDFReporter — LaTeX → PDF via the real TeX toolchain.

Most tests require `latexmk` or `pdflatex` on PATH (MacTeX / TeX Live).
When the toolchain is absent, the PDFReporter is loud-fail-at-construct
— a separate test pins that error path.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ophamin.reporting import (
    PDFCompileError,
    PDFReporter,
    PDFToolchainMissingError,
)
from ophamin.reporting.base import ReportFormat
from ophamin.reporting.runner import DEFAULT_RENDERERS


def _toolchain_present() -> bool:
    # A PDF can be produced as long as SOME engine is available; latexmk
    # is only the optional driver.
    return any(shutil.which(c) for c in ("xelatex", "lualatex", "pdflatex"))


pdf_only = pytest.mark.skipif(
    not _toolchain_present(),
    reason="LaTeX toolchain (latexmk / pdflatex) not on PATH",
)


# --------------------------------------------------------------------------
# Fixtures — minimal proof + audit dicts for fast tests
# --------------------------------------------------------------------------


@pytest.fixture
def minimal_proof() -> dict:
    """A schema-valid-ish proof record minimal enough to render but
    rich enough that the LaTeX template hits its main code paths
    (verdict block + threshold + at least one PillarEvidence)."""
    return {
        "proof_id": "abc123" * 11,
        "schema_version": "1.0",
        "identity": {
            "ophamin_version": "0.59.0",
            "ophamin_git_commit": "deadbeef" * 5,
            "created_at": "2026-05-19T12:00:00+00:00",
        },
        "claim": {
            "statement": "Test claim with LaTeX-special chars: $50 & 100% under_score.",
            "operationalization": "noop",
            "threshold": {
                "metric": "x_metric",
                "comparator": ">=",
                "value": 1.0,
                "units": "boolean",
            },
            "h0": "H0 text",
            "h1": "H1 text",
        },
        "preregistration": {
            "config_hash": "0" * 64,
            "data_hash": "1" * 64,
            "analysis_plan": "Plan with underscores_and_$dollar.",
            "sweep_grid": {},
            "preregistered_at": "2026-05-19T11:59:00+00:00",
        },
        "data": {
            "substrate_name": "kimera-swm",
            "substrate_git_commit": "cafef00d" * 5,
            "datasets": [
                {
                    "name": "ds",
                    "content_hash": "2" * 64,
                    "n_records": 1,
                    "source": "synthetic",
                    "kind": "test",
                }
            ],
        },
        "evidence": [
            {
                "pillar": "test",
                "statistic_name": "x",
                "statistic_value": 1.0,
                "library": "stdlib",
                "library_version": "1.0",
                "effect_size": None,
                "ci_low": None,
                "ci_high": None,
                "p_value": None,
                "cross_check": "n/a",
                "detail": {"note": "100% pass with $signs."},
            },
        ],
        "verdict": {
            "outcome": "VALIDATED",
            "observed": 1.0,
            "reasoning": "Threshold met.",
            "decided_at": "2026-05-19T12:00:00+00:00",
        },
        "reproduction": {"command": "echo run"},
        "provenance": {},
        "signature": "deadbeef" * 8,
    }


# --------------------------------------------------------------------------
# Construction / toolchain detection
# --------------------------------------------------------------------------


@pdf_only
def test_pdfreporter_constructs_when_toolchain_present():
    reporter = PDFReporter()
    # Unicode-native engines are preferred; pdflatex is the last resort.
    assert reporter.compiler in ("xelatex", "lualatex", "pdflatex")
    assert isinstance(reporter.uses_latexmk, bool)


def test_pdfreporter_raises_when_toolchain_missing(monkeypatch):
    """When neither latexmk nor pdflatex is on PATH, construction
    raises a typed error (loud failure at API boundary)."""
    import ophamin.reporting.pdf_renderer as mod
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    with pytest.raises(PDFToolchainMissingError) as exc_info:
        PDFReporter()
    assert "latexmk" in str(exc_info.value) or "pdflatex" in str(exc_info.value)
    assert "MacTeX" in str(exc_info.value) or "TeX Live" in str(exc_info.value)


def test_pdfreporter_format_attribute_is_pdf():
    """The renderer's class-level format attribute must be PDF so the
    ReportRunner dispatches correctly."""
    assert PDFReporter.format is ReportFormat.PDF


def test_pdfreporter_registered_in_default_renderers():
    """The DEFAULT_RENDERERS map must wire ReportFormat.PDF → PDFReporter
    so `ophamin report ... --format pdf` works out of the box."""
    assert DEFAULT_RENDERERS.get(ReportFormat.PDF) is PDFReporter


# --------------------------------------------------------------------------
# Live render — produces a real PDF
# --------------------------------------------------------------------------


@pdf_only
def test_render_proof_produces_valid_pdf(tmp_path, minimal_proof):
    out = tmp_path / "proof.pdf"
    reporter = PDFReporter()
    result = reporter.render_proof(minimal_proof, out)
    assert result == out
    assert out.is_file()
    # PDF files begin with %PDF- magic bytes.
    head = out.read_bytes()[:4]
    assert head == b"%PDF", f"output is not a PDF (head={head!r})"
    # Non-trivial size — a real LaTeX document compiles to ≥ 10KB.
    assert out.stat().st_size > 10_000


@pdf_only
def test_render_proof_keeps_tex_sidecar(tmp_path, minimal_proof):
    """The .tex source must stay alongside the .pdf so the operator can
    re-compile or inspect — the .pdf alone leaves no audit trail of
    what produced it."""
    out = tmp_path / "proof.pdf"
    reporter = PDFReporter()
    reporter.render_proof(minimal_proof, out)
    tex = tmp_path / "proof.tex"
    assert tex.is_file(), "PDFReporter must keep the .tex sidecar"
    # The .tex content should mention the verdict somewhere
    body = tex.read_text()
    assert "VALIDATED" in body


@pdf_only
def test_render_proof_cleans_up_build_dir_by_default(tmp_path, minimal_proof):
    """Transient .aux / .log / .out artefacts must NOT pollute the
    bundle dir unless keep_artifacts=True."""
    out = tmp_path / "proof.pdf"
    reporter = PDFReporter()
    reporter.render_proof(minimal_proof, out)
    build_dir = tmp_path / ".pdfbuild"
    assert not build_dir.exists(), (
        f"build dir {build_dir} should be cleaned up by default"
    )


@pdf_only
def test_render_proof_keeps_build_dir_when_requested(tmp_path, minimal_proof):
    out = tmp_path / "proof.pdf"
    reporter = PDFReporter(keep_artifacts=True)
    reporter.render_proof(minimal_proof, out)
    build_dir = tmp_path / ".pdfbuild"
    assert build_dir.is_dir()
    # Should contain at least the .log
    contents = list(build_dir.iterdir())
    assert any(p.suffix == ".log" for p in contents)


@pdf_only
def test_render_proof_handles_latex_special_chars(tmp_path, minimal_proof):
    """Underscores / dollars / ampersands / percents in proof fields
    must be escaped by the LaTeX renderer so the compile succeeds."""
    # minimal_proof already carries `$50 & 100% under_score.` in its
    # claim — if escaping is broken the compile will hard-fail.
    out = tmp_path / "proof.pdf"
    PDFReporter().render_proof(minimal_proof, out)
    assert out.is_file()


@pdf_only
def test_render_via_report_runner_dispatch(tmp_path, minimal_proof):
    """Calling ReportRunner.render(..., format=PDF) on a proof file
    must produce a PDF (proves the dispatch wiring works)."""
    from ophamin.reporting.runner import ReportRunner

    proof_json = tmp_path / "input.json"
    proof_json.write_text(json.dumps(minimal_proof))
    out = tmp_path / "out.pdf"
    runner = ReportRunner()
    result = runner.render(proof_json, out, ReportFormat.PDF)
    assert result.suffix == ".pdf"
    assert result.is_file()
    assert result.read_bytes()[:4] == b"%PDF"


# --------------------------------------------------------------------------
# Compile-failure path
# --------------------------------------------------------------------------


@pdf_only
def test_compile_error_surfaces_typed_exception(tmp_path, minimal_proof, monkeypatch):
    """If the TeX compiler returns non-zero, the .tex stays in the
    build dir for debugging and PDFCompileError is raised with stderr."""
    import ophamin.reporting.pdf_renderer as mod

    real_run = subprocess.run

    def failing_run(cmd, **kwargs):
        # Return a fake CompletedProcess with non-zero rc.
        class _CP:
            returncode = 1
            stdout = "fake stdout"
            stderr = "! Undefined control sequence.\n! \\bogus"
        return _CP()

    monkeypatch.setattr(mod.subprocess, "run", failing_run)

    out = tmp_path / "proof.pdf"
    reporter = PDFReporter()
    with pytest.raises(PDFCompileError) as exc_info:
        reporter.render_proof(minimal_proof, out)
    assert exc_info.value.returncode == 1
    assert "Undefined control sequence" in exc_info.value.stderr


def test_with_pdf_extension_idempotent():
    """Calling render with a path that already ends in .pdf should not
    double-extension the output."""
    p = Path("/tmp/foo.pdf")
    assert PDFReporter._with_pdf_extension(p) == p


def test_with_pdf_extension_swaps_suffix():
    p = Path("/tmp/foo.tex")
    assert PDFReporter._with_pdf_extension(p) == Path("/tmp/foo.pdf")


# --------------------------------------------------------------------------
# Unicode / Greek-math compile (0.62.0 contract)
#
# Statistics scenarios emit raw Greek + math notation ("Normal(μ_g, σ²)",
# "Φ ≥ 0.62", "Δ ∈ [−1, 1]"). Before the Unicode-engine fix these
# hard-failed every PDF compile with:
#   ! LaTeX Error: Unicode character μ (U+03BC) not set up for use with LaTeX.
# These tests pin the fix so that regression is caught.
# --------------------------------------------------------------------------


@pytest.fixture
def greek_proof(minimal_proof) -> dict:
    """A proof carrying Greek + math Unicode in statement / operationalisation
    / reasoning — the exact shape that hard-failed pdflatex pre-fix."""
    proof = dict(minimal_proof)
    proof["claim"] = {
        **minimal_proof["claim"],
        "statement": (
            "Posterior mean μ_g of Normal(μ, σ²) with Φ ≥ 0.62; "
            "Δ ∈ [−1, 1], ρ ≈ 0.8, α-level 0.05."
        ),
        "operationalization": "estimate μ ± σ via NUTS; report Φ fixed-point.",
    }
    proof["verdict"] = {
        **minimal_proof["verdict"],
        "reasoning": "μ=0.62, σ=0.03 → Φ ≥ threshold; ρ ∈ ℝ, √n scaling.",
    }
    return proof


@pdf_only
def test_render_proof_with_unicode_greek_math(tmp_path, greek_proof):
    """A proof containing μ / σ / Φ (and ≤ ∈ Δ ρ √ …) must compile to a
    valid PDF. This is the 0.62.0 self-test contract."""
    out = tmp_path / "greek.pdf"
    result = PDFReporter().render_proof(greek_proof, out)
    assert result == out
    assert out.is_file()
    assert out.read_bytes()[:4] == b"%PDF", "output is not a valid PDF"
    assert out.stat().st_size > 10_000
    # The raw Greek must survive into the .tex sidecar (escaped text, not
    # stripped) — the preamble's \newunicodechar maps it at typeset time.
    tex = (tmp_path / "greek.tex").read_text(encoding="utf-8")
    for ch in ("μ", "σ", "Φ", "Δ", "ρ"):
        assert ch in tex, f"Greek glyph {ch!r} missing from rendered .tex"


@pdf_only
def test_unicode_glyphs_not_silently_dropped(tmp_path, greek_proof):
    """Beyond 'it compiles': assert ZERO 'Missing character' warnings in the
    TeX log — every Greek/math glyph must actually render, not blank. A
    silently-dropped glyph would violate the no-silent-degradation rule
    (the PDF would be 'valid' but its content corrupted)."""
    out = tmp_path / "greek.pdf"
    PDFReporter(keep_artifacts=True).render_proof(greek_proof, out)
    logs = list((tmp_path / ".pdfbuild").glob("*.log"))
    assert logs, "expected a TeX .log in the kept build dir"
    log_text = logs[0].read_text(errors="replace")
    missing = [ln for ln in log_text.splitlines() if "Missing character" in ln]
    assert not missing, f"glyphs silently dropped (font lacks them): {missing[:5]}"


def test_latex_preamble_is_unicode_engine_aware():
    """The standalone .tex preamble must branch on engine (iftex) and load
    the \\newunicodechar mappings so Greek/math compiles under xelatex
    (native) and degrades gracefully under pdflatex. No toolchain needed."""
    from ophamin.reporting.latex_renderer import _wrap_document

    doc = _wrap_document("Title", "2026-05-20", "body", stand_alone=True)
    assert "\\documentclass{article}" in doc
    assert "\\usepackage{iftex}" in doc
    assert "\\ifPDFTeX" in doc
    assert "\\usepackage{fontspec}" in doc          # xelatex/lualatex branch
    assert "\\usepackage{newunicodechar}" in doc
    # The exact codepoints from the failing report must be mapped.
    for ch in ("μ", "σ", "Φ"):
        assert f"\\newunicodechar{{{ch}}}" in doc, f"{ch!r} not mapped"
    # Fragment mode stays preamble-free (unchanged contract).
    assert "\\documentclass" not in _wrap_document("T", "D", "b", stand_alone=False)


def test_engine_detection_prefers_unicode_native(monkeypatch):
    """Toolchain detection must prefer a Unicode-native engine
    (xelatex > lualatex > pdflatex) so Greek typesets natively, and report
    latexmk as the driver when present. No toolchain needed."""
    import ophamin.reporting.pdf_renderer as mod

    # All present → xelatex wins, latexmk drives.
    monkeypatch.setattr(mod.shutil, "which", lambda n: f"/bin/{n}")
    r = PDFReporter()
    assert r.compiler == "xelatex"
    assert r.uses_latexmk is True

    # xelatex absent → lualatex.
    present = {"lualatex", "pdflatex", "latexmk"}
    monkeypatch.setattr(mod.shutil, "which",
                        lambda n: f"/bin/{n}" if n in present else None)
    assert PDFReporter().compiler == "lualatex"

    # Only pdflatex, no latexmk → pdflatex, direct invocation.
    monkeypatch.setattr(mod.shutil, "which",
                        lambda n: f"/bin/{n}" if n == "pdflatex" else None)
    r = PDFReporter()
    assert r.compiler == "pdflatex"
    assert r.uses_latexmk is False
