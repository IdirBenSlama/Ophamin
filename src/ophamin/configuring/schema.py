"""Introspect Kimera-SWM's configuration surface — statically, from source.

Ophamin's Configure facet manages Kimera's config without importing or
running Kimera (which keeps the substrate isolated and works even when
Kimera's runtime is mid-development / broken). Kimera's config is
**env-var-driven** — ``os.getenv("KIMERA_…", default)`` across
``core/configuration_predecessor.py`` (the app-level Database / API / System
config) and the ``core/configuration/`` domain package (geoid / scar /
thermodynamic / ecoform / operator / event-matching knobs).

``extract_config_schema(kimera_repo)`` AST-parses those files for every
``os.getenv`` / ``os.environ.get`` call and returns the live knob contract:
each knob's env var, default, inferred type, config group, source file, and
whether it's a secret. This is the real surface — parsed from Kimera's own
source — so it stays in sync with Kimera rather than being a hand-kept list.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Files that hold Kimera's config knobs, relative to the repo root.
_APP_CONFIG = "kimera_swm/core/configuration_predecessor.py"
_DOMAIN_PKG = "kimera_swm/core/configuration"

_SECRET_TOKENS = ("PASSWORD", "SECRET", "KEY", "TOKEN", "CREDENTIAL")


@dataclass(frozen=True)
class ConfigKnob:
    """One configurable env-var knob in Kimera."""

    env_var: str
    default: str            # the literal default ("" if none)
    value_type: str         # "int" | "float" | "bool" | "str"
    group: str              # database / api / system / test / <domain> / other
    source_file: str        # repo-relative path it was parsed from
    secret: bool            # name implies a secret → value must be redacted

    def to_dict(self) -> dict[str, Any]:
        return {
            "env_var": self.env_var,
            "default": self.default,
            "value_type": self.value_type,
            "group": self.group,
            "source_file": self.source_file,
            "secret": self.secret,
        }


def _infer_type(default: str) -> str:
    if default == "":
        return "str"
    if default.lower() in ("true", "false"):
        return "bool"
    try:
        int(default)
        return "int"
    except ValueError:
        pass
    try:
        float(default)
        return "float"
    except ValueError:
        pass
    return "str"


def _group_for(env_var: str, source_file: str) -> str:
    # Domain configs are named by their file (geoid_config.py → geoid).
    stem = Path(source_file).stem
    if stem.endswith("_config") and stem != "config_loader":
        return stem[: -len("_config")]
    if env_var.startswith("KIMERA_TEST_DB"):
        return "test_database"
    if env_var.startswith("KIMERA_DB"):
        return "database"
    if env_var.startswith(("KIMERA_API", "KIMERA_SERVER", "CORS")):
        return "api"
    if env_var.startswith(("KIMERA_ENVIRONMENT", "KIMERA_DEBUG",
                           "KIMERA_LOG", "KIMERA_PROJECT")):
        return "system"
    return "other"


def _is_secret(env_var: str) -> bool:
    up = env_var.upper()
    return any(tok in up for tok in _SECRET_TOKENS)


def _find_env_prefix(tree: ast.AST) -> str:
    """Find an ``ENV_PREFIX = "..."`` (or annotated) assignment in the module.

    The domain configs name their vars ``f"{cls.ENV_PREFIX}SUFFIX"``; the
    prefix is a class/module constant like ``ENV_PREFIX: ClassVar[str] =
    "GEOID_"``. Returns '' if none found.
    """
    for node in ast.walk(tree):
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if (isinstance(target, ast.Name) and target.id == "ENV_PREFIX"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)):
            return value.value
    return ""


def _resolve_arg0(arg: ast.expr, env_prefix: str) -> str | None:
    """Reconstruct an env-var name from a getenv first arg.

    Handles a plain string literal AND an f-string of the form
    ``f"{cls.ENV_PREFIX}SUFFIX"`` (the domain-config pattern). Returns None
    if it can't be fully resolved (e.g. a dynamic prefix we don't know).
    """
    if isinstance(arg, ast.Constant):
        return arg.value if isinstance(arg.value, str) else None
    if isinstance(arg, ast.JoinedStr):
        parts: list[str] = []
        for piece in arg.values:
            if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                parts.append(piece.value)
            elif isinstance(piece, ast.FormattedValue):
                v = piece.value
                refs_prefix = (
                    (isinstance(v, ast.Attribute) and v.attr == "ENV_PREFIX")
                    or (isinstance(v, ast.Name) and v.id == "ENV_PREFIX")
                )
                if refs_prefix and env_prefix:
                    parts.append(env_prefix)
                else:
                    return None  # unresolvable interpolation
            else:
                return None
        return "".join(parts)
    return None


def _getenv_calls(tree: ast.AST, env_prefix: str = "") -> list[tuple[str, str]]:
    """Return (env_var, default) for every os.getenv / os.environ.get call
    whose first arg resolves to a name (literal or ENV_PREFIX f-string).
    Default is '' when absent."""
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_getenv = (
            isinstance(func, ast.Attribute) and func.attr == "getenv"
            and isinstance(func.value, ast.Name) and func.value.id == "os"
        )
        is_environ_get = (
            isinstance(func, ast.Attribute) and func.attr == "get"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "environ"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "os"
        )
        if not (is_getenv or is_environ_get):
            continue
        if not node.args:
            continue
        var = _resolve_arg0(node.args[0], env_prefix)
        if not var:
            continue
        default = ""
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            dv = node.args[1].value
            default = dv if isinstance(dv, str) else str(dv)
        found.append((var, default))
    return found


def extract_config_schema(kimera_repo: str | Path) -> list[ConfigKnob]:
    """Parse Kimera's config sources → the live env-var knob contract.

    Static AST parse — no import, no run. De-duplicates by env var (first
    occurrence wins). Raises FileNotFoundError if the repo path is wrong;
    skips individual source files that don't exist (config layout drifts).
    """
    repo = Path(kimera_repo).expanduser().resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"Kimera repo not a directory: {repo}")

    sources: list[Path] = []
    app = repo / _APP_CONFIG
    if app.is_file():
        sources.append(app)
    domain = repo / _DOMAIN_PKG
    if domain.is_dir():
        for p in sorted(domain.glob("*.py")):
            if p.name.startswith("test_") or p.name == "__init__.py":
                continue
            sources.append(p)

    seen: set[str] = set()
    knobs: list[ConfigKnob] = []
    for src in sources:
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"), filename=str(src))
        except (OSError, SyntaxError):
            continue
        rel = str(src.relative_to(repo))
        env_prefix = _find_env_prefix(tree)
        for var, default in _getenv_calls(tree, env_prefix):
            if var in seen:
                continue
            seen.add(var)
            knobs.append(ConfigKnob(
                env_var=var,
                default=default,
                value_type=_infer_type(default),
                group=_group_for(var, rel),
                source_file=rel,
                secret=_is_secret(var),
            ))
    knobs.sort(key=lambda k: (k.group, k.env_var))
    return knobs
