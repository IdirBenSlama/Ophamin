"""Toolkit registry — Ophamin as a unified index that routes to native UIs.

Ophamin is the garage; the mature open-source projects it wraps are the tools
on the wall, each with its own parameters, docs, and (sometimes) its own GUI.
This registry is the index: for every external toolkit Ophamin builds on, it
records the toolkit's role in Ophamin, the installed version, and a direct link
to its **native** interface (docs, and a live UI where one exists — MLflow,
DVC, Prometheus). The Console renders both surfaces side by side: Ophamin's
view AND the tool's own, so nothing is hidden behind Ophamin's abstraction.

It is **extensible** — the whole point is to plug in *whatever* you want to
measure or experiment with. Point ``OPHAMIN_TOOLKITS`` at a JSON file (a list
of toolkit objects) and those entries are merged in. So a user's own SDK or a
new dataset toolkit appears in the same unified index, routed the same way.

Honesty: versions are resolved from the actually-installed distributions
(``importlib.metadata``); a toolkit Ophamin can use but that isn't installed is
reported ``installed=false`` — never silently assumed present.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib import metadata as _metadata
from pathlib import Path
from typing import Any

# native_ui_kind values
_DOC = "doc"                # documentation site only
_LOCAL_SERVER = "local-server"  # spins up a local web UI (e.g. `mlflow ui`)
_WEB_APP = "web-app"        # hosted/desktop app


@dataclass(frozen=True)
class Toolkit:
    """One external tool Ophamin wraps, with a route to its native interface."""

    id: str
    category: str            # statistical / provenance / audit / viz / ...
    role: str                # what it does FOR Ophamin (one line)
    homepage: str            # canonical project homepage
    docs_url: str            # canonical documentation
    pip_name: str = ""       # distribution name for version resolution (default id)
    native_ui: str = ""      # how to reach the tool's own UI (URL or command)
    native_ui_kind: str = "" # _DOC | _LOCAL_SERVER | _WEB_APP | ""
    ophamin_module: str = "" # where in Ophamin it's used (optional hint)

    def resolved(self) -> dict[str, Any]:
        dist = self.pip_name or self.id
        try:
            version = _metadata.version(dist)
            installed = True
        except _metadata.PackageNotFoundError:
            version, installed = None, False
        return {
            "id": self.id,
            "category": self.category,
            "role": self.role,
            "homepage": self.homepage,
            "docs_url": self.docs_url,
            "native_ui": self.native_ui,
            "native_ui_kind": self.native_ui_kind,
            "ophamin_module": self.ophamin_module,
            "pip_name": dist,
            "version": version,
            "installed": installed,
        }


#: The curated core — the load-bearing tools Ophamin builds on, with canonical
#: links. The ones with a *live* native UI (MLflow / DVC / Prometheus) are the
#: ones where "both interfaces" matters most, so they carry a launch route.
_CORE_TOOLKITS: tuple[Toolkit, ...] = (
    # --- statistical / measuring ---
    Toolkit("scipy", "statistical", "significance tests + Wilson/eigendecomp",
            "https://scipy.org", "https://docs.scipy.org/doc/scipy/",
            ophamin_module="measuring"),
    Toolkit("statsmodels", "statistical", "MixedLM, ANOVA, meta-analysis, Wilson CI",
            "https://www.statsmodels.org/", "https://www.statsmodels.org/stable/",
            ophamin_module="measuring.pillars"),
    Toolkit("scikit-learn", "statistical", "cross-validation splitters (N pillar)",
            "https://scikit-learn.org/", "https://scikit-learn.org/stable/",
            pip_name="scikit-learn", ophamin_module="measuring.pillars"),
    Toolkit("river", "statistical", "streaming drift detectors (O pillar)",
            "https://riverml.xyz/", "https://riverml.xyz/latest/api/overview/",
            ophamin_module="observability"),
    Toolkit("mapie", "statistical", "split-conformal prediction intervals",
            "https://mapie.readthedocs.io/", "https://mapie.readthedocs.io/en/stable/",
            ophamin_module="measuring.pillars.diagnostics"),
    Toolkit("pingouin", "statistical", "effect sizes + multi-comparison correction",
            "https://pingouin-stats.org/", "https://pingouin-stats.org/build/html/api.html",
            ophamin_module="measuring"),
    Toolkit("pymc", "bayesian", "Bayesian PPL — Φ posterior modeling",
            "https://www.pymc.io/", "https://www.pymc.io/projects/docs/en/stable/",
            ophamin_module="measuring"),
    Toolkit("arviz", "bayesian", "posterior diagnostics + HDI",
            "https://www.arviz.org/", "https://python.arviz.org/en/stable/",
            ophamin_module="measuring"),
    Toolkit("tigramite", "causal", "PCMCI causal discovery on time series",
            "https://github.com/jakobrunge/tigramite",
            "https://jakobrunge.github.io/tigramite/",
            ophamin_module="measuring"),
    Toolkit("dowhy", "causal", "PyWhy causal-inference orchestrator",
            "https://www.pywhy.org/dowhy/", "https://www.pywhy.org/dowhy/stable/",
            ophamin_module="measuring"),
    # --- provenance (F pillar) — these have LIVE native UIs ---
    Toolkit("mlflow", "provenance", "experiment tracking + model registry",
            "https://mlflow.org/", "https://mlflow.org/docs/latest/",
            native_ui="mlflow ui  →  http://localhost:5000",
            native_ui_kind=_LOCAL_SERVER, ophamin_module="comparing.provenance"),
    Toolkit("dvc", "provenance", "data + pipeline versioning",
            "https://dvc.org/", "https://dvc.org/doc",
            native_ui="dvc studio / `dvc dag`  →  https://studio.datachain.ai",
            native_ui_kind=_WEB_APP, ophamin_module="comparing.provenance"),
    Toolkit("prov", "provenance", "W3C PROV-O graph construction (PROV-JSON)",
            "https://prov.readthedocs.io/", "https://prov.readthedocs.io/en/latest/",
            ophamin_module="comparing.provenance"),
    # --- config ---
    Toolkit("omegaconf", "config", "config composition / merge / dotted access",
            "https://omegaconf.readthedocs.io/",
            "https://omegaconf.readthedocs.io/en/latest/", ophamin_module="config"),
    # --- instrumenting — Prometheus has a LIVE native UI ---
    Toolkit("psutil", "instrumenting", "per-cycle CPU / RSS / page-fault sampling",
            "https://github.com/giampaolo/psutil", "https://psutil.readthedocs.io/",
            ophamin_module="instrumenting"),
    Toolkit("prometheus-client", "instrumenting", "scrape Kimera /metrics",
            "https://github.com/prometheus/client_python",
            "https://prometheus.github.io/client_python/",
            native_ui="prometheus server  →  http://localhost:9090",
            native_ui_kind=_LOCAL_SERVER, ophamin_module="instrumenting"),
    Toolkit("opentelemetry-sdk", "instrumenting", "spans + metrics export",
            "https://opentelemetry.io/", "https://opentelemetry.io/docs/languages/python/",
            ophamin_module="instrumenting"),
    Toolkit("memray", "instrumenting", "memory profiler (flamegraphs)",
            "https://github.com/bloomberg/memray", "https://bloomberg.github.io/memray/",
            native_ui="memray flamegraph  →  local HTML report",
            native_ui_kind=_DOC, ophamin_module="instrumenting"),
    # --- auditing (static analysis) ---
    Toolkit("ruff", "audit", "fast linter (replaces flake8/pylint/isort)",
            "https://docs.astral.sh/ruff/", "https://docs.astral.sh/ruff/",
            ophamin_module="auditing"),
    Toolkit("bandit", "audit", "security linter",
            "https://bandit.readthedocs.io/", "https://bandit.readthedocs.io/en/latest/",
            ophamin_module="auditing"),
    Toolkit("mypy", "audit", "static type checker",
            "https://www.mypy-lang.org/", "https://mypy.readthedocs.io/en/stable/",
            ophamin_module="auditing"),
    Toolkit("radon", "audit", "cyclomatic complexity + maintainability",
            "https://radon.readthedocs.io/", "https://radon.readthedocs.io/en/latest/",
            ophamin_module="auditing"),
    Toolkit("pip-audit", "audit", "dependency-vulnerability scanner",
            "https://pypi.org/project/pip-audit/",
            "https://pypi.org/project/pip-audit/", ophamin_module="auditing"),
    # --- reporting / viz ---
    Toolkit("matplotlib", "viz", "charts in the reporting wheel",
            "https://matplotlib.org/", "https://matplotlib.org/stable/",
            ophamin_module="reporting"),
    Toolkit("umap-learn", "viz", "2-D dimensionality reduction for reports",
            "https://umap-learn.readthedocs.io/",
            "https://umap-learn.readthedocs.io/en/latest/", ophamin_module="reporting"),
    # --- validation / property ---
    Toolkit("hypothesis", "validation", "property-based testing",
            "https://hypothesis.works/", "https://hypothesis.readthedocs.io/en/latest/",
            ophamin_module="auditing"),
    Toolkit("jsonschema", "validation", "proof-record JSON-Schema validation",
            "https://github.com/python-jsonschema/jsonschema",
            "https://python-jsonschema.readthedocs.io/en/stable/",
            ophamin_module="measuring.proof"),
    # --- security ---
    Toolkit("cryptography", "security", "ed25519 per-author attestation (CR2)",
            "https://cryptography.io/", "https://cryptography.io/en/latest/",
            ophamin_module="measuring.proof.attestation"),
    # --- interop ---
    Toolkit("cyclonedx-python-lib", "interop", "CycloneDX SBOM export",
            "https://cyclonedx.org/", "https://cyclonedx.org/docs/",
            ophamin_module="interop.cyclonedx"),
)


class ToolkitConfigError(RuntimeError):
    """A user-supplied OPHAMIN_TOOLKITS entry is missing or malformed."""


_REQUIRED_EXTRA_KEYS = ("id", "category", "role", "homepage", "docs_url")


def _load_extra_toolkits(path: str | Path) -> list[Toolkit]:
    """Load user-defined toolkits from a JSON file (a list of objects).

    Loud-failure: a missing file or a malformed entry raises — a plugged-in
    toolkit that can't be parsed is a real configuration error, not a silent
    skip.
    """
    p = Path(path)
    if not p.exists():
        raise ToolkitConfigError(f"OPHAMIN_TOOLKITS file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ToolkitConfigError(f"unreadable OPHAMIN_TOOLKITS {p}: {exc}") from exc
    if not isinstance(data, list):
        raise ToolkitConfigError("OPHAMIN_TOOLKITS must be a JSON list")
    out: list[Toolkit] = []
    for i, obj in enumerate(data):
        if not isinstance(obj, dict) or any(k not in obj for k in _REQUIRED_EXTRA_KEYS):
            raise ToolkitConfigError(
                f"OPHAMIN_TOOLKITS[{i}] needs keys {_REQUIRED_EXTRA_KEYS}")
        out.append(Toolkit(
            id=str(obj["id"]), category=str(obj["category"]), role=str(obj["role"]),
            homepage=str(obj["homepage"]), docs_url=str(obj["docs_url"]),
            pip_name=str(obj.get("pip_name", "")),
            native_ui=str(obj.get("native_ui", "")),
            native_ui_kind=str(obj.get("native_ui_kind", "")),
            ophamin_module=str(obj.get("ophamin_module", "")),
        ))
    return out


def toolkit_registry(extra_path: str | Path | None = None) -> dict[str, Any]:
    """The unified toolkit index — core tools + any plugged-in extras.

    Resolves each toolkit's installed version, merges user extras (from
    ``extra_path`` or ``OPHAMIN_TOOLKITS``), and groups by category. This is
    the surface that lets the Console route to every tool's native interface
    alongside Ophamin's own.
    """
    toolkits = list(_CORE_TOOLKITS)
    extra = extra_path or os.environ.get("OPHAMIN_TOOLKITS", "")
    n_extra = 0
    if extra:
        loaded = _load_extra_toolkits(extra)
        toolkits.extend(loaded)
        n_extra = len(loaded)

    resolved = [t.resolved() for t in toolkits]
    categories: dict[str, int] = {}
    n_installed = 0
    n_with_ui = 0
    for r in resolved:
        categories[r["category"]] = categories.get(r["category"], 0) + 1
        if r["installed"]:
            n_installed += 1
        if r["native_ui"]:
            n_with_ui += 1
    return {
        "toolkits": resolved,
        "n_toolkits": len(resolved),
        "n_core": len(_CORE_TOOLKITS),
        "n_extra": n_extra,
        "n_installed": n_installed,
        "n_with_native_ui": n_with_ui,
        "categories": dict(sorted(categories.items())),
        "extensible_via": "OPHAMIN_TOOLKITS=<path-to-json-list>",
        "boundary": (
            "Ophamin routes to each tool's NATIVE interface (docs, and a live "
            "UI where one exists) — it does not hide them behind its own. "
            "Tooling layer only; never in the substrate measurement path."
        ),
    }
