"""Tool acquisition — Ophamin extends its own toolchain, safely.

When a measurement need has no tool (the resolver routes it to *wire* or
*synthesize*), Ophamin can acquire one from the open-source ecosystem. The
full pipeline:

    discover  →  evaluate  →  [OWNER GATE]  →  install  →  verify  →  register

Two stages are sensitive: **discover** (live web search/navigation for
candidate tools) and **install** (running code from the internet). This module
owns *evaluate / plan / verify / register* and treats install as an
owner-gated boundary: it produces the exact pinned install PLAN and the
verification steps, but it **never silently runs pip**. Auto-installing
arbitrary internet code is a supply-chain risk — doing it silently would make
an empirical observatory *less* trustworthy, not more. The gate plus mandatory
pre-deployment verification is the feature, not a limitation.

- :class:`ToolCandidate` — a discovered tool + its metadata.
- :func:`evaluate_candidate` — license-compatibility + maturity + fit + the
  security step → ``recommend`` / ``caution`` / ``reject`` with reasons.
- :func:`acquisition_plan` — a DRY-RUN install plan (pinned ``name==version``,
  the command, the verification steps). Executes nothing.
- :func:`verify_acquired_tool` — the post-install gate: imports it, checks the
  version, runs a smoke callable, surfaces the pip-audit step. A tool is not
  "deployed" until it passes.
- :func:`register_acquired_tool` — emits a toolkit-registry entry so the tool
  is listed for future use, closing the loop back to the resolver.

The *discover* stage (an agent making deep web searches for candidate tools)
needs a web-search tool wired into the agent loop; this module accepts the
candidates it produces, from any source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import metadata as _metadata
from typing import Any, Callable

#: The operator's gate for actually installing a tool. The plan + verify
#: stages never need it; only a real install does, and even then the operator
#: runs it — this module does not shell out to pip.
ACQUIRE_GATE_ENV = "OPHAMIN_ALLOW_TOOL_INSTALL"

# License classes, for the "safe for future business" question. Strong
# copyleft (esp. AGPL) is a real landmine for a proprietary/SaaS product.
_PERMISSIVE = frozenset({
    "mit", "bsd", "bsd-2-clause", "bsd-3-clause", "apache", "apache-2.0",
    "apache 2.0", "isc", "psf", "python-2.0", "unlicense", "0bsd", "zlib",
})
_WEAK_COPYLEFT = frozenset({"mpl", "mpl-2.0", "lgpl", "lgpl-3.0", "epl", "epl-2.0"})
_STRONG_COPYLEFT = frozenset({"gpl", "gpl-2.0", "gpl-3.0", "agpl", "agpl-3.0"})

RECOMMEND = "recommend"
CAUTION = "caution"
REJECT = "reject"

# package name: PEP 508 distribution name shape (conservative).
_PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")
_VERSION_RE = re.compile(r"^[0-9][0-9A-Za-z.\-+!]*$")


def _license_class(license_str: str) -> str:
    s = (license_str or "").strip().lower()
    if not s:
        return "unknown"
    # match on the first token / known substrings
    for strong in _STRONG_COPYLEFT:
        if strong in s:
            return "strong-copyleft"
    for weak in _WEAK_COPYLEFT:
        if weak in s:
            return "weak-copyleft"
    for perm in _PERMISSIVE:
        if perm in s:
            return "permissive"
    return "unknown"


@dataclass(frozen=True)
class ToolCandidate:
    """A tool discovered for a measurement need + the metadata to judge it."""

    name: str                       # PyPI / distribution name
    summary: str = ""               # one-line description
    version: str = ""               # latest version (from discovery)
    license: str = ""               # SPDX-ish license string
    homepage: str = ""
    source: str = ""                # e.g. "pypi", "github"
    import_name: str = ""           # module to import (default: name)
    # maturity signals (from discovery; absent → flagged as unknown)
    stars: int | None = None
    downloads_month: int | None = None
    last_release: str = ""          # ISO date of last release
    fit_note: str = ""              # why it might fit the need

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "summary": self.summary, "version": self.version,
            "license": self.license, "homepage": self.homepage,
            "source": self.source, "import_name": self.import_name or self.name,
            "stars": self.stars, "downloads_month": self.downloads_month,
            "last_release": self.last_release, "fit_note": self.fit_note,
        }


def evaluate_candidate(
    candidate: ToolCandidate,
    *,
    need: str = "",
    allow_copyleft: bool = False,
    min_stars: int = 100,
    min_downloads_month: int = 1000,
) -> dict[str, Any]:
    """Score a candidate on license / maturity / fit + the security step.

    Returns a structured evaluation with a ``verdict`` (recommend / caution /
    reject) and the reasons. License is the load-bearing axis for "safe for a
    future business": strong copyleft (esp. AGPL) is rejected unless
    ``allow_copyleft``. Security can only be fully assessed *after* install
    (pip-audit) — flagged as a required verification step, never assumed clean.
    """
    reasons: list[str] = []
    lic_class = _license_class(candidate.license)

    # license — the business-safety gate
    if lic_class == "permissive":
        reasons.append(f"license OK: {candidate.license or '?'} (permissive)")
        lic_ok = True
    elif lic_class == "weak-copyleft":
        reasons.append(f"license CAUTION: {candidate.license} (weak copyleft — file-level)")
        lic_ok = True
    elif lic_class == "strong-copyleft":
        reasons.append(
            f"license RISK: {candidate.license} (strong copyleft — "
            "viral for a proprietary product; AGPL also triggers on SaaS use)"
        )
        lic_ok = bool(allow_copyleft)
    else:
        reasons.append("license UNKNOWN — must be confirmed before any business use")
        lic_ok = False

    # maturity — signals from discovery
    maturity_unknown = candidate.stars is None and candidate.downloads_month is None
    mature = True
    if candidate.stars is not None and candidate.stars < min_stars:
        mature = False
        reasons.append(f"low maturity: {candidate.stars} stars < {min_stars}")
    if candidate.downloads_month is not None and candidate.downloads_month < min_downloads_month:
        mature = False
        reasons.append(
            f"low adoption: {candidate.downloads_month}/mo < {min_downloads_month}")
    if maturity_unknown:
        reasons.append("maturity UNKNOWN — discovery did not supply stars/downloads")

    # name shape (typosquat / injection guard)
    name_ok = bool(_PKG_RE.match(candidate.name))
    if not name_ok:
        reasons.append(f"refused: {candidate.name!r} is not a valid package name")

    # fit
    if candidate.fit_note:
        reasons.append(f"fit: {candidate.fit_note}")

    # verdict
    if not name_ok or not lic_ok:
        verdict = REJECT
    elif lic_class in ("weak-copyleft", "unknown") or not mature or maturity_unknown:
        verdict = CAUTION
    else:
        verdict = RECOMMEND

    return {
        "candidate": candidate.name,
        "verdict": verdict,
        "license_class": lic_class,
        "license_ok": lic_ok,
        "mature": mature,
        "maturity_unknown": maturity_unknown,
        "name_valid": name_ok,
        "reasons": reasons,
        "security_step": (
            "REQUIRED before deployment: run pip-audit on the pinned version + "
            "review the dependency tree. Security is not assessable pre-install."
        ),
    }


def acquisition_plan(candidate: ToolCandidate) -> dict[str, Any]:
    """A DRY-RUN install plan — pinned command + verification steps. Runs nothing.

    The actual install is owner-gated (``OPHAMIN_ALLOW_TOOL_INSTALL``) and the
    operator runs the command; this module only produces it. Raises ValueError
    on an unpinnable candidate (no valid version) — an unpinned install is a
    supply-chain footgun.
    """
    if not _PKG_RE.match(candidate.name):
        raise ValueError(f"invalid package name: {candidate.name!r}")
    if not candidate.version or not _VERSION_RE.match(candidate.version):
        raise ValueError(
            f"candidate {candidate.name!r} has no valid pinnable version "
            f"({candidate.version!r}) — refusing to plan an unpinned install"
        )
    pinned = f"{candidate.name}=={candidate.version}"
    return {
        "candidate": candidate.name,
        "pinned": pinned,
        "install_command": f"pip install '{pinned}'",
        "gate_env": ACQUIRE_GATE_ENV,
        "executes": False,
        "verification_steps": [
            f"pip-audit on {pinned} (vulnerability scan)",
            f"import {candidate.import_name or candidate.name}",
            "run a smoke check (sane output on a known input)",
            "confirm license compatibility for the deployment target",
            "register into the toolkit index (OPHAMIN_TOOLKITS) on pass",
        ],
        "note": (
            "DRY-RUN. The operator runs install_command (after setting "
            f"{ACQUIRE_GATE_ENV}=1); this tool never shells out to pip. Then "
            "verify_acquired_tool() gates deployment."
        ),
    }


def verify_acquired_tool(
    import_name: str,
    *,
    expected_version: str = "",
    smoke_fn: Callable[[Any], bool] | None = None,
) -> dict[str, Any]:
    """Post-install gate: import + version + smoke. A tool is not deployed until
    this passes. Safe — only imports an already-installed package.

    Returns ``{verified: bool, ...}``. Never raises for a failed check (a
    failed verification is a normal result); raises only on a blank name.
    """
    if not import_name or not import_name.strip():
        raise ValueError("import_name is required")
    out: dict[str, Any] = {"import_name": import_name}
    try:
        module = __import__(import_name)
    except Exception as exc:  # noqa: BLE001 — failed import is a verification result
        out.update({"verified": False, "stage": "import",
                    "error": f"{type(exc).__name__}: {exc}"})
        return out
    out["imported"] = True

    # version
    try:
        installed_version = _metadata.version(import_name)
    except _metadata.PackageNotFoundError:
        installed_version = getattr(module, "__version__", "")
    out["version"] = installed_version
    if expected_version and installed_version and installed_version != expected_version:
        out.update({"verified": False, "stage": "version",
                    "error": f"version {installed_version} != expected {expected_version}"})
        return out

    # smoke
    if smoke_fn is not None:
        try:
            ok = bool(smoke_fn(module))
        except Exception as exc:  # noqa: BLE001 — smoke failure is a result
            out.update({"verified": False, "stage": "smoke",
                        "error": f"{type(exc).__name__}: {exc}"})
            return out
        out["smoke_passed"] = ok
        if not ok:
            out.update({"verified": False, "stage": "smoke",
                        "error": "smoke check returned False"})
            return out

    out["verified"] = True
    return out


def register_acquired_tool(
    candidate: ToolCandidate,
    evaluation: dict[str, Any],
    verification: dict[str, Any],
    *,
    category: str = "acquired",
    role: str = "",
) -> dict[str, Any]:
    """Emit a toolkit-registry entry for a verified tool (the OPHAMIN_TOOLKITS
    extension shape) — listing it for future use, closing the loop.

    Refuses to register an unverified or rejected tool: only what passed the
    gate gets listed. Returns the registry entry dict (append it to the
    OPHAMIN_TOOLKITS JSON to make it permanent).
    """
    if evaluation.get("verdict") == REJECT:
        raise ValueError(
            f"refusing to register {candidate.name!r}: evaluation verdict is reject"
        )
    if not verification.get("verified"):
        raise ValueError(
            f"refusing to register {candidate.name!r}: not verified "
            f"(stage={verification.get('stage')}, error={verification.get('error')})"
        )
    return {
        "id": candidate.name,
        "category": category,
        "role": role or candidate.fit_note or candidate.summary or "acquired tool",
        "homepage": candidate.homepage or f"https://pypi.org/project/{candidate.name}/",
        "docs_url": candidate.homepage or f"https://pypi.org/project/{candidate.name}/",
        "pip_name": candidate.name,
        "native_ui": "",
        "native_ui_kind": "",
        "ophamin_module": "acquired",
        "_acquired": {
            "version": verification.get("version") or candidate.version,
            "license_class": evaluation.get("license_class"),
            "verdict": evaluation.get("verdict"),
            "verified": True,
        },
    }
