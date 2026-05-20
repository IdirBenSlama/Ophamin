"""Bundle-aware enumeration + path-safe file serving for the proofs/ tree.

The 0.59.0 layout writes each signed proof into

    <proofs_root>/<tier>/<scenario>/<YYYY-MM-DD>_<verdict>_<short-hash>/
    ├── proof.json
    ├── proof.md
    ├── proof.html
    ├── proof.tex
    └── proof.pdf

This module exposes that structure to the HTTP layer:

- :func:`bundle_tree` walks the layout once and returns the nested
  ``tier → scenario → list[bundle]`` shape the SPA renders as a tree.
- :func:`safe_bundle_file_path` resolves a user-supplied
  ``<tier>/<scenario>/<bundle>/<filename>`` request into an
  on-disk path, refusing every form of traversal AND restricting
  the filename to the canonical five (``proof.{json,md,html,tex,pdf}``).
  Loud-failure on any deviation — the GUI is read-only and local-dev,
  but the file-serve surface must still refuse ``../`` even there.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


#: Filenames the bundle-file-serve endpoint will return. Anything else
#: gets refused at the boundary — the GUI doesn't need anything else,
#: and arbitrary file-reads inside a proofs/ tree (which could carry
#: a .pdfbuild/ leftover or a user-stashed file) would be a footgun.
ALLOWED_BUNDLE_FILES: frozenset[str] = frozenset({
    "proof.json", "proof.md", "proof.html", "proof.tex", "proof.pdf",
})

#: Bundle assets live in `<bundle>/assets/<name>.<ext>` (matplotlib
#: charts referenced by proof.md's relative `![](assets/...)` links;
#: proof.html embeds them as data-URIs so it's self-contained, but the
#: MD view needs them served). Only image extensions, only a single
#: `assets/` segment, only a safe basename charset. The `.resolve()` +
#: containment check in safe_bundle_file_path is the second line of
#: defense; this regex is the first.
_ASSET_FILE_RE = re.compile(
    r"^assets/[A-Za-z0-9][A-Za-z0-9._-]*\.(png|jpg|jpeg|svg|webp|gif)$"
)

#: A bundle dir's name is `<YYYY-MM-DD>_<verdict>_<short-hash>`.
#: Match strictly so a stray sibling dir doesn't get picked up as a bundle.
_BUNDLE_DIR_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(validated|refuted|inconclusive)_([0-9a-f]{8,16})$"
)

#: Tier + scenario dir names: lowercase letters, digits, dashes, underscores.
_PATH_COMPONENT_RE = re.compile(r"^[a-z0-9_-]+$")


class BundlePathError(ValueError):
    """Raised when a bundle-file-serve request has an invalid component.

    Loud-failure at the API boundary so the GUI sees a 400, not a
    silent 200 with empty body or a 500 with a path-traversal error.
    """


def _parse_bundle_dir(d: Path) -> dict[str, str] | None:
    """Parse a bundle dir's name; return None if it doesn't match."""
    m = _BUNDLE_DIR_RE.match(d.name)
    if not m:
        return None
    return {
        "date": m.group(1),
        "verdict": m.group(2),
        "short_hash": m.group(3),
    }


def _list_bundle_files(bundle_dir: Path) -> list[str]:
    """Return the subset of :data:`ALLOWED_BUNDLE_FILES` that actually
    exist in this bundle dir. Order is the canonical write order so
    the GUI's tab order is stable across bundles."""
    ordered = ("proof.json", "proof.md", "proof.html", "proof.tex", "proof.pdf")
    return [name for name in ordered if (bundle_dir / name).is_file()]


def bundle_tree(proofs_root: str | Path) -> dict[str, Any]:
    """Walk ``proofs_root`` and return the SPA-shaped tree.

    Shape::

        {
            "tiers": [
                {
                    "tier": "scientific",
                    "scenarios": [
                        {
                            "scenario": "concentrated-immune-siege",
                            "bundles": [
                                {
                                    "date": "2026-05-14",
                                    "verdict": "validated",
                                    "short_hash": "0a0575db92c0",
                                    "path": "scientific/.../2026-05-14_validated_...",
                                    "files": ["proof.json", "proof.md", ...]
                                }, ...
                            ]
                        }, ...
                    ]
                }, ...
            ],
            "totals": {
                "tiers": 4,
                "scenarios": 11,
                "bundles": 33,
                "verdicts": {"validated": 15, "refuted": 9, "inconclusive": 2}
            }
        }

    Returns ``{"tiers": [], "totals": {...zeros}}`` when the root
    doesn't exist or is empty — no exceptions for the empty case.

    Idempotent + side-effect-free: the function only reads.
    """
    root = Path(proofs_root)
    if not root.is_dir():
        return {
            "tiers": [],
            "totals": {"tiers": 0, "scenarios": 0, "bundles": 0, "verdicts": {}},
        }

    tiers_out: list[dict[str, Any]] = []
    verdict_counts: dict[str, int] = {}
    total_bundles = 0
    total_scenarios = 0

    for tier_dir in sorted(root.iterdir()):
        if not tier_dir.is_dir():
            continue
        if not _PATH_COMPONENT_RE.match(tier_dir.name):
            continue
        scenarios_out: list[dict[str, Any]] = []
        for scenario_dir in sorted(tier_dir.iterdir()):
            if not scenario_dir.is_dir():
                continue
            if not _PATH_COMPONENT_RE.match(scenario_dir.name):
                continue
            bundles_out: list[dict[str, Any]] = []
            for bundle_dir in sorted(scenario_dir.iterdir()):
                if not bundle_dir.is_dir():
                    continue
                parsed = _parse_bundle_dir(bundle_dir)
                if parsed is None:
                    continue
                files = _list_bundle_files(bundle_dir)
                rel = bundle_dir.relative_to(root)
                bundles_out.append({
                    **parsed,
                    "path": str(rel),
                    "files": files,
                })
                total_bundles += 1
                verdict_counts[parsed["verdict"]] = (
                    verdict_counts.get(parsed["verdict"], 0) + 1
                )
            if bundles_out:
                scenarios_out.append({
                    "scenario": scenario_dir.name,
                    "bundles": bundles_out,
                })
                total_scenarios += 1
        if scenarios_out:
            tiers_out.append({
                "tier": tier_dir.name,
                "scenarios": scenarios_out,
            })

    return {
        "tiers": tiers_out,
        "totals": {
            "tiers": len(tiers_out),
            "scenarios": total_scenarios,
            "bundles": total_bundles,
            "verdicts": verdict_counts,
        },
    }


def safe_bundle_file_path(
    proofs_root: str | Path,
    tier: str,
    scenario: str,
    bundle: str,
    filename: str,
) -> Path:
    """Resolve a bundle-file request into a safe on-disk path.

    Refuses every form of attack at the boundary:

    1. Each path component must match the regex for its component
       kind. ``tier`` + ``scenario`` are lowercase identifiers;
       ``bundle`` matches the canonical date_verdict_hash pattern;
       ``filename`` must be one of :data:`ALLOWED_BUNDLE_FILES`.
    2. After joining + resolving, the result must remain *inside*
       ``proofs_root`` — defends against symlinks that would
       otherwise escape the tree.
    3. The resolved path must exist + be a file (not a dir / symlink).

    Returns the resolved absolute Path on success; raises
    :class:`BundlePathError` on any boundary violation +
    :class:`FileNotFoundError` when the file simply isn't there.
    """
    if not _PATH_COMPONENT_RE.match(tier):
        raise BundlePathError(f"invalid tier name: {tier!r}")
    if not _PATH_COMPONENT_RE.match(scenario):
        raise BundlePathError(f"invalid scenario name: {scenario!r}")
    if not _BUNDLE_DIR_RE.match(bundle):
        raise BundlePathError(f"invalid bundle dir name: {bundle!r}")
    # filename is either one of the canonical five proof.* files OR a
    # bundle asset (assets/<name>.<img-ext>). ".." is refused outright
    # even though the containment check below would also catch it —
    # belt and suspenders for the one path that accepts a slash.
    is_proof_file = filename in ALLOWED_BUNDLE_FILES
    is_asset = bool(_ASSET_FILE_RE.match(filename)) and ".." not in filename
    if not (is_proof_file or is_asset):
        raise BundlePathError(
            f"refusing to serve {filename!r}; allowed: "
            f"{sorted(ALLOWED_BUNDLE_FILES)} or assets/<name>.<png|jpg|jpeg|svg|webp|gif>"
        )

    root = Path(proofs_root).resolve()
    candidate = (root / tier / scenario / bundle / filename).resolve()

    # Strict containment check — defeats both ``../`` and symlink
    # escapes. Uses Path.is_relative_to which is exact (no string ops).
    try:
        candidate.relative_to(root)
    except ValueError:
        raise BundlePathError(
            f"path escapes proofs root: {candidate} not under {root}"
        )

    if not candidate.is_file():
        raise FileNotFoundError(
            f"bundle file not found: {tier}/{scenario}/{bundle}/{filename}"
        )
    return candidate
