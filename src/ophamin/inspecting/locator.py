"""PrimitiveLocator — finds a primitive in the Kimera source tree.

Strategy: walk the Kimera ``kimera_swm/`` source tree looking for a
``class <CanonicalClass>(...)`` definition. When found, parse the file with
``ast`` to extract:

  - the docstring
  - method names (top-level ``def`` in the class body)
  - parent class names
  - the file's import statements

Then ``ripgrep`` (or pure-python fallback) the repo for textual references to
the class name to compute the caller list. Caller results are descriptive
only — they don't try to distinguish ``CanonicalClass`` (the actual class)
from coincidental text matches.

This is *static* introspection — no Kimera runtime, no Kimera imports.
Works against any commit of Kimera the user points to.
"""

from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ophamin.inspecting.primitive_profile import CallerReference


@dataclass(frozen=True)
class LocatedPrimitive:
    """Result of locating one primitive in the source tree."""

    found: bool
    source_file: str                        # repo-relative
    source_line: int
    docstring: str
    method_names: tuple[str, ...]
    parent_classes: tuple[str, ...]
    imports: tuple[str, ...]
    n_callers: int
    top_callers: tuple[CallerReference, ...]
    notes: tuple[str, ...]


#: cap on imports surfaced — we don't need the whole list, just the top-of-file feel
_MAX_IMPORTS = 30
#: cap on caller references collected
_MAX_CALLERS = 50


class PrimitiveLocator:
    """Locate a primitive by canonical_class name within a Kimera repo."""

    def __init__(self, kimera_repo: str | Path) -> None:
        self.kimera_repo = Path(kimera_repo).expanduser().resolve()
        if not self.kimera_repo.is_dir():
            raise NotADirectoryError(
                f"Kimera repo not found: {self.kimera_repo}"
            )
        # the substrate code is under kimera_swm/ in the standard layout
        self.substrate_root = self.kimera_repo / "kimera_swm"
        if not self.substrate_root.is_dir():
            raise NotADirectoryError(
                f"{self.kimera_repo} does not look like a Kimera repo "
                f"(no kimera_swm/ under it)"
            )

    # -- locating -------------------------------------------------------

    def locate(self, canonical_class: str) -> LocatedPrimitive:
        """Find ``class <canonical_class>(...)`` in the kimera_swm tree."""
        notes: list[str] = []
        class_re = re.compile(
            r"^\s*class\s+" + re.escape(canonical_class) + r"\s*[\(:]"
        )
        match_file: Path | None = None
        match_line = 0
        for py_file in self._iter_py_files(self.substrate_root):
            try:
                with py_file.open("r", encoding="utf-8") as fh:
                    for i, line in enumerate(fh, start=1):
                        if class_re.match(line):
                            match_file = py_file
                            match_line = i
                            break
            except OSError:
                continue
            if match_file is not None:
                break

        if match_file is None:
            notes.append(
                f"class {canonical_class!r} not located by class-def regex "
                f"under {self.substrate_root}"
            )
            n_callers, top_callers = self._find_callers(canonical_class)
            return LocatedPrimitive(
                found=False,
                source_file="",
                source_line=0,
                docstring="",
                method_names=(),
                parent_classes=(),
                imports=(),
                n_callers=n_callers,
                top_callers=top_callers,
                notes=tuple(notes),
            )

        # AST parse to extract the rich metadata
        docstring, methods, parents, imports, parse_notes = self._parse_file(
            match_file, canonical_class
        )
        notes.extend(parse_notes)
        n_callers, top_callers = self._find_callers(canonical_class)
        return LocatedPrimitive(
            found=True,
            source_file=str(match_file.relative_to(self.kimera_repo)),
            source_line=match_line,
            docstring=docstring,
            method_names=methods,
            parent_classes=parents,
            imports=imports,
            n_callers=n_callers,
            top_callers=top_callers,
            notes=tuple(notes),
        )

    # -- helpers --------------------------------------------------------

    def _iter_py_files(self, root: Path):
        """Yield every .py under ``root`` except __pycache__ + .venv."""
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or ".venv" in path.parts:
                continue
            yield path

    def _parse_file(
        self, path: Path, canonical_class: str
    ) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], list[str]]:
        """Extract docstring / methods / parents / imports via ast."""
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            return "", (), (), (), [f"could not read {path}: {exc}"]

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            return "", (), (), (), [f"could not parse {path}: {exc}"]

        notes: list[str] = []
        imports: list[str] = []
        target_class: ast.ClassDef | None = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)
            elif isinstance(node, ast.ClassDef) and node.name == canonical_class:
                target_class = node
        if target_class is None:
            notes.append(
                f"regex matched {path.name} but ast did not find class "
                f"{canonical_class!r} at top level (nested class?)"
            )
            return "", (), (), tuple(imports[:_MAX_IMPORTS]), notes

        # docstring + methods + parents
        docstring = ast.get_docstring(target_class) or ""
        method_names: list[str] = []
        for child in target_class.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_names.append(child.name)
        parents: list[str] = []
        for base in target_class.bases:
            try:
                parents.append(ast.unparse(base))
            except Exception:
                parents.append("<unparseable-base>")

        return (
            docstring,
            tuple(method_names),
            tuple(parents),
            tuple(imports[:_MAX_IMPORTS]),
            notes,
        )

    # -- callers --------------------------------------------------------

    def _find_callers(self, canonical_class: str) -> tuple[int, tuple[CallerReference, ...]]:
        """Count + sample callers via ripgrep, falling back to pure-python grep."""
        callers = self._ripgrep_callers(canonical_class)
        if callers is None:
            callers = self._fallback_grep_callers(canonical_class)
        n_callers = len(callers)
        return n_callers, tuple(callers[:_MAX_CALLERS])

    def _ripgrep_callers(self, canonical_class: str) -> list[CallerReference] | None:
        """Run `rg` if available; return None if not."""
        try:
            result = subprocess.run(
                ["rg", "--type=py", "-n", "-w", canonical_class, str(self.substrate_root)],
                capture_output=True, text=True, timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if result.returncode not in (0, 1):
            return None
        return self._parse_grep_output(result.stdout)

    def _fallback_grep_callers(self, canonical_class: str) -> list[CallerReference]:
        """Pure-python fallback: walk the tree, look for word-boundary matches."""
        pattern = re.compile(r"\b" + re.escape(canonical_class) + r"\b")
        callers: list[CallerReference] = []
        for py in self._iter_py_files(self.substrate_root):
            try:
                with py.open("r", encoding="utf-8") as fh:
                    for i, line in enumerate(fh, start=1):
                        if pattern.search(line):
                            rel = str(py.relative_to(self.kimera_repo))
                            callers.append(CallerReference(
                                file=rel, line=i, context=line.strip()[:160]
                            ))
                            if len(callers) >= _MAX_CALLERS:
                                return callers
            except OSError:
                continue
        return callers

    def _parse_grep_output(self, output: str) -> list[CallerReference]:
        callers: list[CallerReference] = []
        for line in output.splitlines():
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            path, line_no_str, content = parts
            try:
                line_no = int(line_no_str)
            except ValueError:
                continue
            try:
                rel = str(Path(path).relative_to(self.kimera_repo))
            except ValueError:
                rel = path
            callers.append(CallerReference(
                file=rel, line=line_no, context=content.strip()[:160]
            ))
        return callers
