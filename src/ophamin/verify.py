"""``ophamin verify`` — self-check the installation.

Reports which declared dependencies are present, which audit-pillar binaries
resolve (venv-local or PATH), which CLI subcommands are registered, and
optionally whether a passed Kimera repo path probes cleanly. Exit code is
non-zero if any required check fails — wire it into CI or a postinstall
hook to catch broken installs early.

Three severity levels:

  * **required** — Ophamin's core scenarios will not run without it
  * **optional** — feature-gated; missing means the corresponding stratum
                   isn't available but core works
  * **info**     — present-or-absent is informational
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    name: str
    severity: str           # "required" | "optional" | "info"
    status: str             # "ok" | "missing" | "error"
    detail: str
    extra_to_install: str = ""

    def is_failure(self) -> bool:
        return self.severity == "required" and self.status != "ok"


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------


# (package_name_in_pyproject, importable_module, severity, install-extra-name, description)
DEP_CHECKS: tuple[tuple[str, str, str, str, str], ...] = (
    # required (core)
    ("numpy",        "numpy",                  "required", "",          "ndarray + linalg"),
    ("scipy",        "scipy",                  "required", "",          "stats + percentile"),
    ("pyyaml",       "yaml",                   "required", "",          "config + corpus loaders"),
    ("pandas",       "pandas",                 "required", "",          "pillar dataframes"),
    ("scikit-learn", "sklearn",                "required", "",          "diagnostics pillars"),
    ("statsmodels",  "statsmodels",            "required", "",          "Wilson CI + binomial proportions"),
    ("mapie",        "mapie",                  "required", "",          "conformal-prediction pillar"),
    ("river",        "river",                  "required", "",          "online-learning pillar"),
    ("prov",         "prov",                   "required", "",          "PROV-O provenance graph"),
    ("lxml",         "lxml",                   "required", "",          "PROV-O serialisation"),
    ("rdflib",       "rdflib",                 "required", "",          "RDF graph for provenance"),
    ("omegaconf",    "omegaconf",              "required", "",          "config layering"),
    ("mlflow",       "mlflow",                 "required", "",          "lineage store + interop exporter"),
    ("dvc",          "dvc",                    "required", "",          "data-version-control"),
    ("psutil",       "psutil",                 "required", "",          "instrumenting wheel"),

    # optional (feature extras)
    ("matplotlib",   "matplotlib",             "optional", "viz",       "reporting wheel charts"),
    ("hydra-core",   "hydra",                  "optional", "hydra",     "Hydra-driven entry points"),
    ("h5py",         "h5py",                   "optional", "well",      "TheWell HDF5 corpus"),
    ("opentelemetry-api", "opentelemetry",     "optional", "telemetry", "OTel instrumentation"),
    ("opentelemetry-sdk", "opentelemetry.sdk", "optional", "telemetry", "OTel SDK"),
    ("prometheus_client", "prometheus_client", "optional", "telemetry", "PrometheusScrapeProbe consumer"),
    ("cyclonedx-python-lib", "cyclonedx",      "optional", "audit",     "CycloneDX SBOM exporter"),
    ("py-spy",       "",                       "optional", "profile",   "sampling profiler (binary tool)"),
    ("memray",       "memray",                 "optional", "profile",   "memory profiler"),
)


# (binary_name, severity, install-extra-name, description)
BINARY_CHECKS: tuple[tuple[str, str, str, str], ...] = (
    ("ruff",      "optional", "audit",   "Python linter (audit pillar)"),
    ("bandit",    "optional", "audit",   "Security linter"),
    ("mypy",      "optional", "audit",   "Static type-checker"),
    ("vulture",   "optional", "audit",   "Dead-code detector"),
    ("radon",     "optional", "audit",   "Cyclomatic complexity"),
    ("pip-audit", "optional", "audit",   "Dependency-vuln scanner"),
    ("py-spy",    "optional", "profile", "Sampling profiler"),
)


# Required CLI subcommands (must be registered in cli.main).
CLI_SUBCOMMANDS: tuple[str, ...] = (
    "demo", "run", "sweep", "probe-kimera", "lineage",
    "discover", "discover-diff", "drift-report", "watch",
    "audit", "inventory", "discover-fields", "scrape", "wiring",
    "report", "inspect", "inspect-all", "export", "verify",
)


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------


def _resolve_binary(name: str) -> str | None:
    """Look next to sys.executable first, then PATH (mirrors AuditPillar)."""
    bin_dir = os.path.dirname(sys.executable)
    candidate = os.path.join(bin_dir, name)
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return shutil.which(name)


def check_python_version() -> CheckResult:
    minor = sys.version_info.minor
    if sys.version_info.major != 3 or minor < 10:
        return CheckResult(
            name="python", severity="required", status="error",
            detail=f"Python {sys.version.split()[0]} — Ophamin requires 3.10+",
        )
    severity = "info" if minor >= 13 else "info"
    return CheckResult(
        name="python", severity=severity, status="ok",
        detail=f"Python {sys.version.split()[0]} (3.10+ required)",
    )


def check_dep(pkg: str, mod: str, severity: str, extra: str, desc: str) -> CheckResult:
    try:
        version = md.version(pkg)
    except md.PackageNotFoundError:
        return CheckResult(
            name=pkg, severity=severity, status="missing",
            detail=f"not installed — {desc}",
            extra_to_install=extra,
        )
    # Optionally also verify the import works (catches broken installs).
    if mod:
        try:
            importlib.import_module(mod)
        except Exception as e:
            return CheckResult(
                name=pkg, severity=severity, status="error",
                detail=f"installed v{version} but import failed: "
                       f"{type(e).__name__}: {e}",
                extra_to_install=extra,
            )
    return CheckResult(
        name=pkg, severity=severity, status="ok",
        detail=f"v{version} — {desc}",
    )


def check_binary(name: str, severity: str, extra: str, desc: str) -> CheckResult:
    resolved = _resolve_binary(name)
    if resolved is None:
        return CheckResult(
            name=name, severity=severity, status="missing",
            detail=f"binary not found — {desc}",
            extra_to_install=extra,
        )
    # Capture --version best-effort.
    version = ""
    try:
        result = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True, timeout=5,
        )
        version = (result.stdout + result.stderr).strip().split("\n")[0][:60]
    except (subprocess.TimeoutExpired, OSError):
        pass
    return CheckResult(
        name=name, severity=severity, status="ok",
        detail=f"{resolved}  {version}",
    )


def check_cli_subcommands() -> CheckResult:
    """Verify every documented subcommand is registered with argparse."""
    try:
        from ophamin.cli import main          # ensure import works
        # Construct the parser and inspect its subparsers.
        import argparse
        parser = argparse.ArgumentParser()
        # Re-build the parser by calling the main flow with no args triggers
        # SystemExit; we directly inspect ``cli`` module instead.
        from ophamin import cli as cli_mod
        # Quick trick: parse "--help" and capture the text.
        import io
        import contextlib
        buf = io.StringIO()
        argv_save = sys.argv[:]
        sys.argv = ["ophamin", "--help"]
        try:
            with contextlib.redirect_stdout(buf):
                with contextlib.suppress(SystemExit):
                    main(["--help"])
        finally:
            sys.argv = argv_save
        text = buf.getvalue()
        missing = [c for c in CLI_SUBCOMMANDS if c not in text]
        if missing:
            return CheckResult(
                name="cli_subcommands", severity="required", status="missing",
                detail=f"subcommands not registered: {missing}",
            )
        return CheckResult(
            name="cli_subcommands", severity="required", status="ok",
            detail=f"{len(CLI_SUBCOMMANDS)} subcommands registered",
        )
    except Exception as e:
        return CheckResult(
            name="cli_subcommands", severity="required", status="error",
            detail=f"{type(e).__name__}: {e}",
        )


def check_kimera_repo(kimera_repo: str | None) -> CheckResult | None:
    """Optional check: probe a Kimera repo if a path was passed."""
    if not kimera_repo:
        return None
    from pathlib import Path
    repo = Path(kimera_repo).expanduser().resolve()
    if not repo.is_dir():
        return CheckResult(
            name="kimera_repo", severity="info", status="missing",
            detail=f"not a directory: {repo}",
        )
    # Try a discovery probe — exercises adapter import + targets.
    try:
        from ophamin.seeing.discovery import discover_all
        inv = discover_all(repo)
        return CheckResult(
            name="kimera_repo", severity="info", status="ok",
            detail=(f"{repo}  inventory={inv.total_surfaces()} surfaces  "
                    f"commit={inv.kimera_git_commit[:8] or '(none)'}"),
        )
    except Exception as e:
        return CheckResult(
            name="kimera_repo", severity="info", status="error",
            detail=f"discover_all failed: {type(e).__name__}: {e}",
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_all_checks(*, kimera_repo: str | None = None) -> list[CheckResult]:
    out: list[CheckResult] = [check_python_version()]
    for pkg, mod, sev, extra, desc in DEP_CHECKS:
        out.append(check_dep(pkg, mod, sev, extra, desc))
    for name, sev, extra, desc in BINARY_CHECKS:
        out.append(check_binary(name, sev, extra, desc))
    out.append(check_cli_subcommands())
    if kimera_repo:
        kr = check_kimera_repo(kimera_repo)
        if kr is not None:
            out.append(kr)
    return out


def render_report(results: list[CheckResult]) -> str:
    """Markdown report — passes only required failures into the exit code."""
    lines: list[str] = []
    lines.append("# Ophamin install verification\n")
    lines.append(f"**Python**: {sys.version.split()[0]}  ")
    lines.append(f"**Interpreter**: `{sys.executable}`  ")
    lines.append("")

    by_status: dict[str, list[CheckResult]] = {"ok": [], "missing": [], "error": []}
    for r in results:
        by_status[r.status].append(r)

    lines.append(f"## Summary\n")
    lines.append(f"- ✓ ok      : {len(by_status['ok'])}")
    lines.append(f"- ⚠ missing : {len(by_status['missing'])}")
    lines.append(f"- ✗ error   : {len(by_status['error'])}\n")

    lines.append("## Per-check results\n")
    lines.append("| status | name | severity | detail | install hint |")
    lines.append("|---|---|---|---|---|")
    sev_order = {"required": 0, "optional": 1, "info": 2}
    for r in sorted(results, key=lambda x: (sev_order.get(x.severity, 3),
                                            x.status != "ok", x.name)):
        sym = {"ok": "✓", "missing": "⚠", "error": "✗"}[r.status]
        hint = f"`pip install -e '.[{r.extra_to_install}]'`" if r.extra_to_install and r.status != "ok" else ""
        lines.append(f"| {sym} | `{r.name}` | {r.severity} | {r.detail} | {hint} |")
    lines.append("")

    failures = [r for r in results if r.is_failure()]
    if failures:
        lines.append(f"## Required-check failures ({len(failures)})\n")
        for r in failures:
            lines.append(f"- **{r.name}** — {r.detail}")
            if r.extra_to_install:
                lines.append(f"  Install: `pip install -e '.[{r.extra_to_install}]'`")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_text(results: list[CheckResult]) -> str:
    """Compact terminal output."""
    lines: list[str] = []
    by_status: dict[str, list[CheckResult]] = {"ok": [], "missing": [], "error": []}
    for r in results:
        by_status[r.status].append(r)
    lines.append(f"Python: {sys.version.split()[0]} @ {sys.executable}")
    lines.append("")
    lines.append(f"{'sym':<3} {'name':<30} {'sev':<10} {'detail':<60}")
    lines.append("-" * 105)
    sev_order = {"required": 0, "optional": 1, "info": 2}
    for r in sorted(results, key=lambda x: (sev_order.get(x.severity, 3),
                                            x.status != "ok", x.name)):
        sym = {"ok": "ok ", "missing": "MISS", "error": "ERR"}[r.status]
        lines.append(f"{sym:<3} {r.name:<30} {r.severity:<10} {r.detail[:60]}")
    lines.append("")
    lines.append(f"summary: ok={len(by_status['ok'])}  "
                 f"missing={len(by_status['missing'])}  "
                 f"error={len(by_status['error'])}")
    failures = [r for r in results if r.is_failure()]
    if failures:
        lines.append("")
        lines.append(f"REQUIRED-check failures ({len(failures)}):")
        for r in failures:
            lines.append(f"  - {r.name}: {r.detail}")
            if r.extra_to_install:
                lines.append(f"    install: pip install -e '.[{r.extra_to_install}]'")
    return "\n".join(lines)


def has_required_failure(results: list[CheckResult]) -> bool:
    return any(r.is_failure() for r in results)
