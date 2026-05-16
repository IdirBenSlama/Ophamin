"""WiringProbe — per-surface classification: wired vs scaffolded vs orphan.

Walks the whole Kimera repo once, builds an import-name → file-path index,
then for each inventoried surface counts incoming imports + scans for
WIRE_CANDIDATE / WIRED / ARCHIVED annotations + counts stub function bodies.

Output: a content-addressed, HMAC-signed ``CompletenessReport`` carrying
per-surface classification AND per-stratum aggregates. The non-orphan rate
is the load-bearing metric — it's what the SubstrateCompletenessScenario
runs its falsifiable claim against.

Loud failure on a missing repo. Per-file errors (unparseable Python) are
recorded as ``parse_error`` on the surface rather than fatal — a known
WIRE_CANDIDATE-stale module is allowed to be broken; we just want to
surface it.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ophamin import __version__
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
from ophamin.seeing.discovery.kimera_inventory import (
    KimeraInventory,
    StratumInventory,
    Surface,
    _capture_kimera_commit,
)


DEFAULT_SIGN_KEY = b"ophamin-wiring-default-key"
WIRING_SCHEMA_VERSION = 1


# Annotation patterns are docstring-conventional in Kimera (CLAUDE.md
# §"Phase 1 verified deltas"). All are case-sensitive single-line markers.
ANNOTATION_PATTERNS: dict[str, re.Pattern[str]] = {
    "WIRE_CANDIDATE": re.compile(r"\.\.\s*note::\s*WIRE_CANDIDATE", re.MULTILINE),
    "WIRED":          re.compile(r"\.\.\s*note::\s*WIRED",          re.MULTILINE),
    "DEPRECATED":     re.compile(r"\.\.\s*note::\s*DEPRECATED",     re.MULTILINE),
    "ARCHIVED":       re.compile(r"\.\.\s*note::\s*ARCHIVED",       re.MULTILINE),
    "SUPERSEDED":     re.compile(r"\.\.\s*note::\s*SUPERSEDED",     re.MULTILINE),
}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SurfaceCompleteness:
    """One surface's empirical wired/scaffolded/orphan classification."""

    surface_name: str
    stratum: str
    file_path: str             # relative to Kimera repo root
    annotation: str            # "" | "WIRE_CANDIDATE" | "WIRED" | "DEPRECATED" | "ARCHIVED" | "SUPERSEDED"
    incoming_imports: int      # how many other files in the repo import this module
    classification: str        # "wired" | "wire_candidate" | "orphan" | "archived" | "parse_error"
    stub_count: int = 0        # number of stub function bodies (pass / NotImplementedError / return None alone)
    n_functions: int = 0       # total def + async def (top-level + nested in classes)
    n_classes: int = 0
    parse_error: str = ""

    @property
    def is_orphan(self) -> bool:
        return self.classification == "orphan"

    @property
    def is_wired(self) -> bool:
        return self.classification == "wired"

    @property
    def stub_density(self) -> float:
        if self.n_functions <= 0:
            return 0.0
        return self.stub_count / self.n_functions

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_name": self.surface_name,
            "stratum": self.stratum,
            "file_path": self.file_path,
            "annotation": self.annotation,
            "incoming_imports": self.incoming_imports,
            "classification": self.classification,
            "stub_count": self.stub_count,
            "n_functions": self.n_functions,
            "n_classes": self.n_classes,
            "parse_error": self.parse_error,
            "stub_density": self.stub_density,
        }


@dataclass(frozen=True)
class StratumCompleteness:
    """Per-stratum aggregate of surface classifications."""

    stratum: str
    n_total: int
    n_wired: int
    n_wire_candidate: int
    n_orphan: int
    n_archived: int
    n_parse_error: int
    n_with_stubs: int                  # ≥ 1 stub body
    sum_incoming_imports: int

    @property
    def wired_rate(self) -> float:
        return self.n_wired / self.n_total if self.n_total else 0.0

    @property
    def orphan_rate(self) -> float:
        return self.n_orphan / self.n_total if self.n_total else 0.0

    @property
    def wire_candidate_rate(self) -> float:
        return self.n_wire_candidate / self.n_total if self.n_total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stratum": self.stratum,
            "n_total": self.n_total,
            "n_wired": self.n_wired,
            "n_wire_candidate": self.n_wire_candidate,
            "n_orphan": self.n_orphan,
            "n_archived": self.n_archived,
            "n_parse_error": self.n_parse_error,
            "n_with_stubs": self.n_with_stubs,
            "sum_incoming_imports": self.sum_incoming_imports,
            "wired_rate": self.wired_rate,
            "orphan_rate": self.orphan_rate,
            "wire_candidate_rate": self.wire_candidate_rate,
        }


@dataclass(frozen=True)
class CompletenessReport:
    """A signed, content-addressed wiring report covering one Kimera commit."""

    ophamin_version: str
    ophamin_git_commit: str
    kimera_repo_path: str
    kimera_git_commit: str
    surfaces: tuple[SurfaceCompleteness, ...]
    per_stratum: tuple[StratumCompleteness, ...]
    captured_at: str = field(default_factory=_now_utc_iso)
    schema_version: int = WIRING_SCHEMA_VERSION
    signature: str = ""

    # ----- introspection -----

    def stratum(self, name: str) -> StratumCompleteness | None:
        for s in self.per_stratum:
            if s.stratum == name:
                return s
        return None

    def orphan_surfaces(self) -> tuple[SurfaceCompleteness, ...]:
        return tuple(s for s in self.surfaces if s.classification == "orphan")

    def wire_candidate_surfaces(self) -> tuple[SurfaceCompleteness, ...]:
        return tuple(s for s in self.surfaces if s.classification == "wire_candidate")

    def stub_heavy_surfaces(self, min_density: float = 0.5) -> tuple[SurfaceCompleteness, ...]:
        return tuple(
            s for s in self.surfaces
            if s.stub_density >= min_density and s.n_functions >= 2
        )

    def total_surfaces(self) -> int:
        return len(self.surfaces)

    # ----- signing -----

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ophamin_version": self.ophamin_version,
            "ophamin_git_commit": self.ophamin_git_commit,
            "kimera_repo_path": self.kimera_repo_path,
            "kimera_git_commit": self.kimera_git_commit,
            "captured_at": self.captured_at,
            "surfaces": [s.to_dict() for s in self.surfaces],
            "per_stratum": [s.to_dict() for s in self.per_stratum],
        }

    def _canonical_bytes(self) -> bytes:
        return json.dumps(self._body(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    @property
    def report_id(self) -> str:
        return hashlib.sha256(self._canonical_bytes()).hexdigest()

    def sign(self, key: bytes) -> CompletenessReport:
        sig = hmac.new(key, self._canonical_bytes(), hashlib.sha256).hexdigest()
        return CompletenessReport(
            ophamin_version=self.ophamin_version,
            ophamin_git_commit=self.ophamin_git_commit,
            kimera_repo_path=self.kimera_repo_path,
            kimera_git_commit=self.kimera_git_commit,
            surfaces=self.surfaces,
            per_stratum=self.per_stratum,
            captured_at=self.captured_at,
            schema_version=self.schema_version,
            signature=sig,
        )

    def verify(self, key: bytes) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(key, self._canonical_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, **self._body(), "signature": self.signature}

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        text = json.dumps(self.to_dict(), indent=indent, default=str)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletenessReport:
        required = {"ophamin_version", "ophamin_git_commit", "kimera_repo_path",
                    "kimera_git_commit", "surfaces", "per_stratum", "captured_at"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"CompletenessReport missing required keys: {sorted(missing)}")
        return cls(
            ophamin_version=str(data["ophamin_version"]),
            ophamin_git_commit=str(data["ophamin_git_commit"]),
            kimera_repo_path=str(data["kimera_repo_path"]),
            kimera_git_commit=str(data["kimera_git_commit"]),
            surfaces=tuple(
                SurfaceCompleteness(**{
                    k: v for k, v in s.items() if k != "stub_density"
                }) for s in data["surfaces"]
            ),
            per_stratum=tuple(
                StratumCompleteness(**{
                    k: v for k, v in s.items()
                    if k not in {"wired_rate", "orphan_rate", "wire_candidate_rate"}
                }) for s in data["per_stratum"]
            ),
            captured_at=str(data["captured_at"]),
            schema_version=int(data.get("schema_version", WIRING_SCHEMA_VERSION)),
            signature=str(data.get("signature", "")),
        )

    def to_markdown(self, target_path: str | None = None) -> str:
        """Human-readable per-stratum + per-surface action list."""
        lines: list[str] = []
        lines.append(f"# Ophamin Substrate Completeness Report\n")
        lines.append(f"**Report ID:** `{self.report_id}`  ")
        lines.append(f"**Schema:** v{self.schema_version}  ")
        lines.append(f"**Captured:** {self.captured_at}  \n")

        lines.append("## 1. Identity\n")
        lines.append(f"- Ophamin: `{self.ophamin_version}` @ "
                     f"`{self.ophamin_git_commit or '(no commit)'}`")
        lines.append(f"- Kimera repo: `{self.kimera_repo_path}`")
        lines.append(f"- Kimera commit: `{self.kimera_git_commit or '(not a git repo)'}`\n")

        lines.append("## 2. Per-stratum wiring distribution\n")
        lines.append("| stratum | total | wired | wire_candidate | orphan | "
                     "archived | parse_err | wired_rate | orphan_rate |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for s in self.per_stratum:
            lines.append(
                f"| `{s.stratum}` | {s.n_total} | {s.n_wired} | "
                f"{s.n_wire_candidate} | {s.n_orphan} | {s.n_archived} | "
                f"{s.n_parse_error} | {s.wired_rate:.1%} | {s.orphan_rate:.1%} |"
            )
        lines.append("")

        # Top orphan + WIRE_CANDIDATE surfaces — the action list.
        orphans = self.orphan_surfaces()
        if orphans:
            lines.append(f"## 3. Orphan surfaces — {len(orphans)} files defined "
                         f"with zero incoming imports\n")
            lines.append("| stratum | file_path | annotation |")
            lines.append("|---|---|---|")
            for surf in orphans[:50]:
                ann = surf.annotation or "_(none)_"
                lines.append(f"| `{surf.stratum}` | `{surf.file_path}` | {ann} |")
            if len(orphans) > 50:
                lines.append(f"| ... | _and {len(orphans) - 50} more_ | |")
            lines.append("")

        wc = self.wire_candidate_surfaces()
        if wc:
            lines.append(f"## 4. WIRE_CANDIDATE surfaces — {len(wc)} explicitly "
                         f"annotated as scaffolding\n")
            lines.append("| stratum | file_path |")
            lines.append("|---|---|")
            for surf in wc[:50]:
                lines.append(f"| `{surf.stratum}` | `{surf.file_path}` |")
            if len(wc) > 50:
                lines.append(f"| ... | _and {len(wc) - 50} more_ |")
            lines.append("")

        # Stub-heavy modules
        stub_heavy = self.stub_heavy_surfaces(min_density=0.5)
        if stub_heavy:
            lines.append(f"## 5. Stub-heavy surfaces — {len(stub_heavy)} modules "
                         f"with ≥50% stub-bodied functions\n")
            lines.append("| stratum | file_path | stubs / functions |")
            lines.append("|---|---|---|")
            for surf in stub_heavy[:30]:
                lines.append(f"| `{surf.stratum}` | `{surf.file_path}` | "
                             f"{surf.stub_count}/{surf.n_functions} |")
            lines.append("")

        lines.append(f"## 6. Signature\n- `{self.signature or '(not signed)'}`\n")

        body = "\n".join(lines) + "\n"
        if target_path:
            Path(target_path).write_text(body, encoding="utf-8")
        return body


# ---------------------------------------------------------------------------
# Annotation scanning
# ---------------------------------------------------------------------------


def scan_annotations(text: str) -> str:
    """Return the first matching annotation name, or '' if none.

    Order matters — checked in: WIRED > WIRE_CANDIDATE > DEPRECATED > ARCHIVED >
    SUPERSEDED. WIRED takes precedence because Kimera's convention is to add
    a ``WIRED`` annotation that *replaces* an earlier WIRE_CANDIDATE.
    """
    for name in ("WIRED", "WIRE_CANDIDATE", "DEPRECATED", "ARCHIVED", "SUPERSEDED"):
        if ANNOTATION_PATTERNS[name].search(text):
            return name
    return ""


# ---------------------------------------------------------------------------
# Stub-body detection
# ---------------------------------------------------------------------------


def _is_stub_body(body: list[ast.stmt]) -> bool:
    """A function body is a stub if it contains exactly one of:
      * ``pass``
      * ``raise NotImplementedError(...)``
      * ``return None`` / ``return``
    Optionally preceded by a single docstring (Expr+Constant str).
    """
    stmts = list(body)
    # Strip leading docstring.
    if stmts and isinstance(stmts[0], ast.Expr) and isinstance(stmts[0].value, ast.Constant) \
            and isinstance(stmts[0].value.value, str):
        stmts = stmts[1:]
    if len(stmts) != 1:
        return False
    only = stmts[0]
    if isinstance(only, ast.Pass):
        return True
    if isinstance(only, ast.Raise):
        # raise NotImplementedError(...) or raise NotImplementedError
        exc = only.exc
        if exc is None:
            return False
        if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
            return True
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) \
                and exc.func.id == "NotImplementedError":
            return True
        return False
    if isinstance(only, ast.Return):
        # return / return None
        if only.value is None:
            return True
        if isinstance(only.value, ast.Constant) and only.value.value is None:
            return True
        return False
    return False


def scan_stubs(tree: ast.AST) -> tuple[int, int, int]:
    """Count (stub_function_count, total_function_count, class_count) in an AST.

    Walks recursively — counts methods inside classes too, since stub methods
    are a real signal of unfinished implementation.
    """
    stubs = 0
    fns = 0
    cls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cls += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fns += 1
            if _is_stub_body(node.body):
                stubs += 1
    return stubs, fns, cls


# ---------------------------------------------------------------------------
# Import-graph construction
# ---------------------------------------------------------------------------


def _module_path_to_dotted(rel: str) -> str:
    """``kimera_swm/domain/cognitive/takwin.py`` → ``kimera_swm.domain.cognitive.takwin``."""
    if rel.endswith(".py"):
        rel = rel[:-3]
    return rel.replace("/", ".").replace("\\", ".")


def _extract_imported_dotted_names(tree: ast.AST, current_dotted: str) -> set[str]:
    """All dotted names this module imports — both absolute and resolved relative.

    For ``from .foo import Bar`` inside ``kimera_swm.domain.cognitive.takwin``,
    returns ``kimera_swm.domain.cognitive.foo`` AND
    ``kimera_swm.domain.cognitive.foo.Bar`` (because ``Bar`` may itself be a
    submodule — the Python ``from pkg import sub`` form is ambiguous between
    "name within pkg" and "submodule of pkg" and we want to count both for
    the wiring graph).
    """
    out: set[str] = set()
    current_parts = current_dotted.split(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                # ``from . import X`` — resolve the dotted base, then add
                # base.X for each name imported.
                base_parts: list[str] = (
                    current_parts[:-node.level]
                    if node.level <= len(current_parts) else []
                )
                if base_parts:
                    out.add(".".join(base_parts))
                    for alias in node.names:
                        out.add(".".join(base_parts + [alias.name]))
                continue
            if node.level == 0:
                base = node.module
            else:
                # Relative import: pop ``level`` parts from current_parts, then
                # prepend.
                parts = current_parts[:-node.level] if node.level <= len(current_parts) else []
                if not parts:
                    continue
                base = ".".join(parts + [node.module])
            out.add(base)
            # Each ``from X import Y, Z`` also implies a reference to ``X.Y``
            # and ``X.Z`` — since Y and Z may be submodules of X, this is the
            # load-bearing edge for module-level wire-counting (e.g.,
            # ``from kimera_swm.api.routers import computation_router`` should
            # count as an incoming edge for ``kimera_swm.api.routers.computation_router``,
            # not just for ``kimera_swm.api.routers``).
            for alias in node.names:
                if alias.name == "*":
                    continue
                out.add(f"{base}.{alias.name}")
    return out


def build_import_graph(kimera_repo: Path) -> dict[str, int]:
    """Walk every .py file under the Kimera repo, parse imports, count incoming
    edges per dotted-module-name.

    Returns ``{dotted_module_name: count_of_other_files_importing_it}``. A file
    that fails to parse is silently dropped from the *source* side (we still
    count it on the *target* side via its own dotted name when others import
    it).

    The cost is one pass over the tree. On Kimera-SWM (~3500 .py files) this
    takes a few seconds.
    """
    in_count: dict[str, int] = defaultdict(int)

    # Walk every .py file under kimera_swm/ (the production source tree).
    src_root = kimera_repo / "kimera_swm"
    if not src_root.is_dir():
        return dict(in_count)

    for p in src_root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        try:
            rel = p.relative_to(kimera_repo).as_posix()
        except ValueError:
            continue
        current_dotted = _module_path_to_dotted(rel)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text, filename=str(p))
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue
        for target in _extract_imported_dotted_names(tree, current_dotted):
            # Only count edges into kimera_swm.* modules — third-party imports
            # are irrelevant for "is this surface used internally."
            if not target.startswith("kimera_swm"):
                continue
            in_count[target] += 1
    return dict(in_count)


# ---------------------------------------------------------------------------
# Per-surface classifier
# ---------------------------------------------------------------------------


def classify_surface(
    kimera_repo: Path,
    surface: Surface,
    stratum: str,
    in_count: dict[str, int],
) -> SurfaceCompleteness:
    """Classify one surface as wired / wire_candidate / orphan / archived /
    parse_error. Stub count + function count come from a single AST walk.
    """
    full = kimera_repo / surface.file_path

    # Surfaces that aren't .py files (package_dirs, .yml configs, etc.) get
    # a special "config" classification — they have no imports and aren't
    # parseable as Python, so the wired/orphan dichotomy doesn't apply.
    if not full.is_file() or full.suffix != ".py":
        return SurfaceCompleteness(
            surface_name=surface.name,
            stratum=stratum,
            file_path=surface.file_path,
            annotation="",
            incoming_imports=0,
            classification="config",
            stub_count=0,
            n_functions=0,
            n_classes=0,
        )

    # Path-based archive detection — _archive/, _predecessor.py, etc.
    rel = surface.file_path
    if "_archive/" in rel or rel.endswith("_predecessor.py"):
        path_archived = True
    else:
        path_archived = False

    # Read + parse.
    annotation = ""
    stub_count = 0
    n_functions = 0
    n_classes = 0
    parse_error = ""
    try:
        text = full.read_text(encoding="utf-8", errors="replace")
        annotation = scan_annotations(text)
        try:
            tree = ast.parse(text, filename=str(full))
            stub_count, n_functions, n_classes = scan_stubs(tree)
        except SyntaxError as e:
            parse_error = f"{type(e).__name__}: {e.msg} at line {e.lineno}"
    except OSError as e:
        parse_error = f"{type(e).__name__}: {e}"

    # Look up incoming imports.
    dotted = _module_path_to_dotted(rel)
    incoming = in_count.get(dotted, 0)

    # Classification precedence:
    #   1. parse_error overrides everything (broken file — surfaced for fixing)
    #   2. archived (path or annotation)
    #   3. WIRE_CANDIDATE annotation
    #   4. WIRED annotation OR ≥1 incoming import (wired)
    #   5. zero incoming imports + no annotation = orphan
    if parse_error:
        classification = "parse_error"
    elif path_archived or annotation in {"ARCHIVED", "DEPRECATED", "SUPERSEDED"}:
        classification = "archived"
    elif annotation == "WIRE_CANDIDATE":
        classification = "wire_candidate"
    elif annotation == "WIRED" or incoming > 0:
        classification = "wired"
    else:
        classification = "orphan"

    return SurfaceCompleteness(
        surface_name=surface.name,
        stratum=stratum,
        file_path=rel,
        annotation=annotation,
        incoming_imports=incoming,
        classification=classification,
        stub_count=stub_count,
        n_functions=n_functions,
        n_classes=n_classes,
        parse_error=parse_error,
    )


# ---------------------------------------------------------------------------
# WiringProbe — orchestrates an inventory → completeness report
# ---------------------------------------------------------------------------


class WiringProbe:
    """Runs a full wiring-completeness pass over a Kimera repo + inventory.

    Two-stage: build the import graph once, then classify every inventoried
    surface against it. The classifier is pure; the import-graph step does
    the expensive walk.
    """

    def __init__(
        self,
        kimera_repo: str | Path,
        *,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> None:
        repo = Path(kimera_repo).expanduser().resolve()
        if not repo.is_dir():
            raise FileNotFoundError(f"Kimera repo not a directory: {repo}")
        self.kimera_repo = repo
        self.sign_key = sign_key

    def scan_all(self) -> CompletenessReport:
        """Classify every .py file under ``kimera_swm/`` — not just inventoried surfaces.

        The inventory probe covers the ~336 *named primitive* surfaces. The
        broader picture — what fraction of the entire substrate is wired vs
        scaffolded vs orphan — needs a scan of every Python file. Per-stratum
        aggregates are bucketed by top-level subpackage (``domain``,
        ``infrastructure``, ``interfaces``, ``api``, ``core``, ``tests``,
        ``other``) instead of the 9 KimeraInventory strata.

        The same classifier is applied: ``wired`` / ``wire_candidate`` /
        ``orphan`` / ``archived`` / ``parse_error``. Tests are bucketed
        separately because their "orphan" status is expected (tests are
        executed by pytest, not imported by production code).
        """
        in_count = build_import_graph(self.kimera_repo)

        src_root = self.kimera_repo / "kimera_swm"
        if not src_root.is_dir():
            raise FileNotFoundError(
                f"kimera_swm/ subdirectory missing in {self.kimera_repo}"
            )

        # Walk every .py file, classify each.
        surfaces_out: list[SurfaceCompleteness] = []
        per_bucket: dict[str, list[SurfaceCompleteness]] = defaultdict(list)

        for p in sorted(src_root.rglob("*.py")):
            if "__pycache__" in p.parts or p.name == "__init__.py":
                continue
            rel = p.relative_to(self.kimera_repo).as_posix()
            # Derive bucket from top-level subdirectory under kimera_swm/.
            # ``parts[0]`` is "kimera_swm"; ``parts[1]`` is the bucket name
            # (e.g. "domain", "infrastructure", "api") OR a top-level filename
            # for standalone scripts like ``kimera_swm/verify_5d_distance.py``.
            parts = rel.split("/")
            if len(parts) >= 2:
                bucket = parts[1]
                # Top-level standalone script — collapse into a single bucket
                # so 30+ one-off scripts don't each get their own per-file
                # "stratum" row in the aggregate table.
                if bucket.endswith(".py"):
                    bucket = "scripts"
            else:
                bucket = "other"
            if bucket == "tests" or "/tests/" in rel:
                bucket = "tests"
            surface = Surface(
                name=p.stem,
                kind="module",
                file_path=rel,
                line_count=0,
                metadata={"bucket": bucket},
            )
            sc = classify_surface(self.kimera_repo, surface, bucket, in_count)
            surfaces_out.append(sc)
            per_bucket[bucket].append(sc)

        # Aggregate per bucket.
        per_stratum: list[StratumCompleteness] = []
        for bucket_name in sorted(per_bucket):
            ss = per_bucket[bucket_name]
            applicable = [s for s in ss if s.classification != "config"]
            per_stratum.append(StratumCompleteness(
                stratum=bucket_name,
                n_total=len(applicable),
                n_wired=sum(1 for s in applicable if s.classification == "wired"),
                n_wire_candidate=sum(1 for s in applicable
                                     if s.classification == "wire_candidate"),
                n_orphan=sum(1 for s in applicable if s.classification == "orphan"),
                n_archived=sum(1 for s in applicable if s.classification == "archived"),
                n_parse_error=sum(1 for s in applicable
                                  if s.classification == "parse_error"),
                n_with_stubs=sum(1 for s in applicable if s.stub_count > 0),
                sum_incoming_imports=sum(s.incoming_imports for s in applicable),
            ))

        report = CompletenessReport(
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()) or "",
            kimera_repo_path=str(self.kimera_repo),
            kimera_git_commit=_capture_kimera_commit(self.kimera_repo),
            surfaces=tuple(surfaces_out),
            per_stratum=tuple(per_stratum),
        )
        return report.sign(self.sign_key)

    def probe(self, inventory: KimeraInventory) -> CompletenessReport:
        """Classify every surface in ``inventory`` against the repo's import graph."""
        in_count = build_import_graph(self.kimera_repo)

        surfaces_out: list[SurfaceCompleteness] = []
        per_stratum_data: dict[str, list[SurfaceCompleteness]] = defaultdict(list)
        for stratum in inventory.strata:
            for surface in stratum.surfaces:
                sc = classify_surface(self.kimera_repo, surface, stratum.stratum, in_count)
                surfaces_out.append(sc)
                per_stratum_data[stratum.stratum].append(sc)

        per_stratum: list[StratumCompleteness] = []
        for stratum_name in (s.stratum for s in inventory.strata):
            ss = per_stratum_data.get(stratum_name, [])
            # Exclude "config" classifications from the wired/orphan counts —
            # they're non-Python surfaces and not subject to the wiring contract.
            applicable = [s for s in ss if s.classification != "config"]
            per_stratum.append(StratumCompleteness(
                stratum=stratum_name,
                n_total=len(applicable),
                n_wired=sum(1 for s in applicable if s.classification == "wired"),
                n_wire_candidate=sum(1 for s in applicable
                                     if s.classification == "wire_candidate"),
                n_orphan=sum(1 for s in applicable if s.classification == "orphan"),
                n_archived=sum(1 for s in applicable if s.classification == "archived"),
                n_parse_error=sum(1 for s in applicable
                                  if s.classification == "parse_error"),
                n_with_stubs=sum(1 for s in applicable if s.stub_count > 0),
                sum_incoming_imports=sum(s.incoming_imports for s in applicable),
            ))

        report = CompletenessReport(
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()) or "",
            kimera_repo_path=str(self.kimera_repo),
            kimera_git_commit=_capture_kimera_commit(self.kimera_repo),
            surfaces=tuple(surfaces_out),
            per_stratum=tuple(per_stratum),
        )
        return report.sign(self.sign_key)
