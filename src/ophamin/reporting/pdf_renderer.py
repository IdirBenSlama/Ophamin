"""PDFReporter — LaTeX → PDF via a real TeX toolchain.

Delegates LaTeX rendering to :class:`LaTeXReporter` (so the same
table / figure shape used for `.tex` output is used here), then shells
out to a TeX engine to produce the PDF. A Unicode-native engine
(``xelatex`` / ``lualatex``) is preferred so Greek + math glyphs in proof
statements (μ, σ, Φ, ≤, …) typeset natively; ``pdflatex`` is the last
resort. ``latexmk`` drives the chosen engine when present (multi-pass +
cleanup), otherwise the engine is invoked directly.

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


#: TeX engines we can drive, in preference order. Unicode-native engines
#: (xelatex, lualatex) come first so Greek / math glyphs in proof
#: statements (μ, σ, Φ, ≤, …) typeset natively. pdflatex is the last
#: resort — it relies on the inputenc + \newunicodechar mappings the
#: template emits and hard-fails on any Unicode char outside that set.
_ENGINES: tuple[str, ...] = ("xelatex", "lualatex", "pdflatex")

#: latexmk is the preferred *driver* (handles multi-pass + cleanup) when
#: present; this maps each engine to the latexmk flag that selects it.
_LATEXMK_FLAG: dict[str, str] = {
    "xelatex": "-xelatex",
    "lualatex": "-lualatex",
    "pdflatex": "-pdf",
}


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


def _detect_toolchain() -> tuple[str, bool]:
    """Return ``(engine, use_latexmk)`` for the best available toolchain.

    ``engine`` is the first available of :data:`_ENGINES` (Unicode-native
    engines preferred). ``use_latexmk`` is True when ``latexmk`` is on PATH
    and will be used as the driver (``latexmk -<engine>``); otherwise the
    engine is invoked directly.

    Loud-fails with :class:`PDFToolchainMissingError` if no engine is found
    — the framework's no-fallback rule forbids silent degradation to
    "just emit .tex".
    """
    engine = next((name for name in _ENGINES if shutil.which(name)), None)
    if engine is None:
        raise PDFToolchainMissingError(_ENGINES)
    return engine, shutil.which("latexmk") is not None


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
        # Detect toolchain eagerly — fail fast if missing.
        self._engine, self._use_latexmk = _detect_toolchain()
        self._keep_artifacts = bool(keep_artifacts)
        self._latex = LaTeXReporter(stand_alone=True)

    @property
    def compiler(self) -> str:
        """The selected TeX engine (``xelatex``, ``lualatex`` or ``pdflatex``).

        Unicode-native engines are preferred so Greek / math glyphs in proof
        statements typeset correctly; ``pdflatex`` is the last resort.
        """
        return self._engine

    @property
    def uses_latexmk(self) -> bool:
        """Whether ``latexmk`` drives the compile (vs. invoking the engine
        directly). ``latexmk`` is preferred for multi-pass + cleanup when
        present, but the engine still determines Unicode behaviour."""
        return self._use_latexmk

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
        # latexmk (when present) drives the chosen engine and handles
        # multi-pass + cleanup; otherwise invoke the engine directly.
        if self._use_latexmk:
            cmd = [
                "latexmk", _LATEXMK_FLAG[self._engine],
                "-interaction=nonstopmode", "-halt-on-error", "-quiet",
                tex_path.name,
            ]
            compiler_label = f"latexmk {_LATEXMK_FLAG[self._engine]}"
        else:  # invoke the engine directly — our doc has no refs/TOC to resolve
            cmd = [
                self._engine, "-interaction=nonstopmode", "-halt-on-error",
                tex_path.name,
            ]
            compiler_label = self._engine

        completed = subprocess.run(
            cmd, cwd=build_dir, capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0:
            raise PDFCompileError(
                tex_path, compiler_label, completed.returncode,
                completed.stderr + "\n--- STDOUT ---\n" + completed.stdout,
            )

        # Move PDF from build dir to the requested path
        built_pdf = build_dir / (tex_path.stem + ".pdf")
        if not built_pdf.is_file():
            raise PDFCompileError(
                tex_path, compiler_label, 0,
                f"compiler reported success but {built_pdf} was not produced",
            )
        shutil.move(str(built_pdf), str(out_path))

        if not self._keep_artifacts:
            # Keep the .tex; drop the rest. ignore_errors=False so any
            # leftover that survives surfaces as a real error (per the
            # framework's no-fallback rule). Common failure mode: the
            # build_dir contains an open file held by a hung subprocess —
            # better to know than to silently leak.
            tex_dst = out_path.parent / (out_path.stem + ".tex")
            shutil.move(str(tex_path), str(tex_dst))
            shutil.rmtree(build_dir, ignore_errors=False)
        return out_path

    @staticmethod
    def _with_pdf_extension(path: Path) -> Path:
        if path.suffix.lower() == ".pdf":
            return path
        return path.with_suffix(".pdf")
