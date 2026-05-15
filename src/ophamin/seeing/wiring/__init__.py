"""seeing/wiring/ — empirical feedback on what's wired vs scaffolding.

Kimera-SWM is incomplete by design — many primitives are scaffolded
(``WIRE_CANDIDATE``) before they're wired into production paths. Ophamin's
value-add at this stratum is to surface the *empirical* wired-vs-scaffolded
distribution, per stratum, so the operator has an action list:

    wired           — has ≥ 1 incoming import from another file in the repo,
                      AND is not annotated WIRE_CANDIDATE
    wire_candidate  — explicitly annotated ``.. note:: WIRE_CANDIDATE``
                      (per CLAUDE.md, 322 such annotations in the tree)
    orphan          — 0 incoming imports AND no annotation
    archived        — annotated ``ARCHIVED`` / ``DEPRECATED`` / under
                      ``_archive/`` / ``_predecessor.py`` path

Stub bodies (``pass`` only, ``raise NotImplementedError``, ``return None``
single-statement) are counted separately — they're surface that exists but
isn't *implemented* even if imported.

This is the empirical layer underneath the SubstrateCompletenessScenario.
"""

from ophamin.seeing.wiring.wiring_probe import (
    ANNOTATION_PATTERNS,
    CompletenessReport,
    DEFAULT_SIGN_KEY,
    StratumCompleteness,
    SurfaceCompleteness,
    WiringProbe,
    build_import_graph,
    classify_surface,
    scan_annotations,
    scan_stubs,
)

__all__ = [
    "ANNOTATION_PATTERNS",
    "CompletenessReport",
    "DEFAULT_SIGN_KEY",
    "StratumCompleteness",
    "SurfaceCompleteness",
    "WiringProbe",
    "build_import_graph",
    "classify_surface",
    "scan_annotations",
    "scan_stubs",
]
