"""PDFReporter — LaTeX → PDF via a real TeX toolchain.

Delegates LaTeX rendering to :class:`LaTeXReporter` (so the same
table / figure shape used for `.tex` output is used here), then shells
out to ``latexmk -pdf`` or ``pdflatex`` to produce the PDF.

Failure mode (per the framework's no-fallback rule):

- If the toolchain is missing on PATH, construction raises
  :class:`PDFToolchainMissingError`. No silent degradation to "just
  emit .tex" — the caller asked for a PDF; missing toolchain is a
  loud failure at boundary.
- If the TeX compile fails (a real LaTeX error in the rendered
  document — escape bug, missing package, etc.), the .tex file is
  kept so the operator can debug. The render call raises
  :class:`PDFCompileError` carrying the compiler's stderr.

The compile is run inside a temp directory next to the output (a
``.pdfbuild/`` sibling) so transient .aux / .log / .out files don't
pollute the proof bundle. The final PDF is moved into place; the
build dir is removed unless ``keep_artifacts=True``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from ophamin.reporting.base import ReportFormat, ReportRenderer
from ophamin.reporting.latex_renderer import LaTeXReporter


#: Preferred compiler chain — latexmk first (handles multi-pass), pdflatex fallback.
_COMPILERS: tuple[str, ...] = ("latexmk", "pdflatex")


class PDFToolchainMissingError(RuntimeError):
    """Raised when neither ``latexmk`` nor ``pdflatex`` is on PATH.

    PDFReporter cannot degrade silently to "just emit .tex" — the
    caller explicitly asked for a PDF artefact. Missing toolchain is
    a configuration error surfaced at boundary; the operator's fix
    is to install MacTeX / TeX Live / MiKTeX.
    """

    def __init__(self, tried: tuple[str, ...]) -> None:
        self.tried = tried
        super().__init__(
            "no LaTeX toolchain found on PATH (tried: "
            + ", ".join(tried)
            + "). Install MacTeX (https://tug.org/mactex/) or TeX Live to "
            "enable PDF rendering."
        )


class PDFCompileError(RuntimeError):
    """Raised when the TeX compiler returns non-zero.

    The .tex file is preserved so the operator can debug; the compiler
    log is kept too when ``keep_artifacts=True`` is set on the
    PDFReporter (default off). The exception carries the truncated
    stderr for fast triage.
    """

    def __init__(self, tex_path: Path, compiler: str, returncode: int, stderr: str) -> None:
        self.tex_path = tex_path
        self.compiler = compiler
        self.returncode = returncode
        self.stderr = stderr
        snippet = stderr[-1200:] if len(stderr) > 1200 else stderr
        super().__init__(
            f"PDF compilation failed: {compiler} returned {returncode} on "
            f"{tex_path}. Last 1200 chars of stderr:\n{snippet}"
        )


def _detect_compiler() -> str:
    """Return the name of the first available compiler in :data:`_COMPILERS`.

    Loud-fails with :class:`PDFToolchainMissingError` if none are found.
    """
    for name in _COMPILERS:
        if shutil.which(name):
            return name
    raise PDFToolchainMissingError(_COMPILERS)


class PDFReporter(ReportRenderer):
    """LaTeX → PDF renderer.

    Internally constructs a :class:`LaTeXReporter` (in stand-alone
    mode, so the document carries its own ``\\documentclass``), writes
    the .tex into a per-render build directory, runs the compiler,
    and moves the .pdf into place at the requested path.

    The toolchain is detected at construction time so a missing tool
    surfaces at scenario-build time (when the caller can choose to
    drop PDF from the format list) rather than at render time (when
    half the proof bundle may already be written).
    """

    format = ReportFormat.PDF

    def __init__(self, *, keep_artifacts: bool = False) -> None:
        # Detect compiler eagerly — fail fast if missing.
        self._compiler = _detect_compiler()
        self._keep_artifacts = bool(keep_artifacts)
        self._latex = LaTeXReporter(stand_alone=True)

    @property
    def compiler(self) -> str:
        """The selected TeX compiler (``latexmk`` or ``pdflatex``)."""
        return self._compiler

    def render_proof(self, record: dict[str, Any], out_path: Path) -> Path:
        return self._render(record, out_path, kind="proof")

    def render_audit(self, record: dict[str, Any], out_path: Path) -> Path:
        return self._render(record, out_path, kind="audit")

    # -- internal --------------------------------------------------------

    def _render(self, record: dict[str, Any], out_path: Path, *, kind: str) -> Path:
        out_path = self._with_pdf_extension(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Build dir sits next to the final PDF; transient .aux/.log/.out
        # land there and get removed on success unless keep_artifacts is set.
        build_dir = out_path.parent / ".pdfbuild"
        build_dir.mkdir(parents=True, exist_ok=True)
        tex_path = build_dir / (out_path.stem + ".tex")

        if kind == "proof":
            self._latex.render_proof(record, tex_path)
        elif kind == "audit":
            self._latex.render_audit(record, tex_path)
        else:
            raise ValueError(f"unknown record kind: {kind!r}")

        # Run the compiler in the build dir so its working dir is right.
        if self._compiler == "latexmk":
            cmd = [
                "latexmk", "-pdf", "-interaction=nonstopmode",
                "-halt-on-error", "-quiet", tex_path.name,
            ]
        else:  # pdflatex — run twice for refs / TOC, though our doc has none today
            cmd = [
                "pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                tex_path.name,
            ]

        completed = subprocess.run(
            cmd, cwd=build_dir, capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0:
            raise PDFCompileError(
                tex_path, self._compiler, completed.returncode,
                completed.stderr + "\n--- STDOUT ---\n" + completed.stdout,
            )

        # Move PDF from build dir to the requested path
        built_pdf = build_dir / (tex_path.stem + ".pdf")
        if not built_pdf.is_file():
            raise PDFCompileError(
                tex_path, self._compiler, 0,
                f"compiler reported success but {built_pdf} was not produced",
            )
        shutil.move(str(built_pdf), str(out_path))

        if not self._keep_artifacts:
            # Keep the .tex; drop the rest.
            tex_dst = out_path.parent / (out_path.stem + ".tex")
            shutil.move(str(tex_path), str(tex_dst))
            shutil.rmtree(build_dir, ignore_errors=True)
        return out_path

    @staticmethod
    def _with_pdf_extension(path: Path) -> Path:
        if path.suffix.lower() == ".pdf":
            return path
        return path.with_suffix(".pdf")
