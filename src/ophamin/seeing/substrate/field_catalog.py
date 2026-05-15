"""KIMERA_FIELD_CATALOG — declarative knowledge of OrchestratorResult fields.

Kimera-SWM's ``OrchestratorResult`` carries **665 fields per cycle** as of
2026-05-15 (CLAUDE.md §"Takwin — one orchestrator among many"; was 638 at
2026-05-04). Today's Ophamin ``discover`` sweep observed 666 top-level dict
keys (665 OrchestratorResult fields + 1 `raw` wrapper). The ``KimeraAdapter``
passes the whole dict through into ``CycleResult.raw``, so scenarios already
have access to all of them. What's missing is the *documentation* layer:
when a scenario references ``raw["walker_halt_mode"]``, there's no
machine-checkable record of what type that field is supposed to be, what
semantic family it belongs to, or which substrate component populates it. A
Kimera-side rename silently breaks downstream scenarios — the
``cycle_seconds``-dropped-on-floor bug surfaced in CI 2026-05-15 is exactly
this pattern.

This module is the **field contract** layer:

* :class:`CatalogedField` documents one known field — name, accepted types,
  semantic family, human-readable description.
* :data:`KIMERA_FIELD_CATALOG` is the curated list of ~30 fields Ophamin
  scenarios actively use, plus ~30 high-leverage fields that v0.2 scenarios
  will pull in next (per [`docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md`](
  ../../../../docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md)).
* :func:`validate_raw_against_catalog` checks one ``raw`` dict against the
  catalog and returns the violations (missing required, type-mismatch,
  extra-unknown). Loud failure on first invocation surfaces drift instead
  of hiding it.

The catalog is **descriptive, not prescriptive** — when Kimera adds new
``OrchestratorResult`` fields, Ophamin's :class:`SchemaMiner` still
discovers them empirically. The catalog says "these are the fields scenarios
rely on having well-defined semantics for." A field not in the catalog
isn't an error; it's just undocumented from Ophamin's side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Catalog families correspond to substrate components emitting these fields.
# Naming follows CLAUDE.md primitives (organ names where applicable).
CATALOG_FAMILIES = (
    "phi",               # IIT Φ + KII alias
    "walker",            # PrimeTopologyWalker outputs (halt mode, mode counters)
    "gwf",               # Gyroscopic Water Fortress (defensive layer)
    "echoform",          # Echoform grammar operators / event
    "consolidation",     # KCCL sleep cycle (NREM + REM)
    "prime",             # Arachne primes, composites, chains
    "piovra",            # Multi-arm sensory state
    "substrate_state",   # Substrate-state stamps + Atlas violations
    "internal_event",    # The 5 internal-event kinds (Ouroboros / Cronos / SPDE / thermo / quantum)
    "lateral_line",      # Substrate self-emission sensor
    "eikonal",           # Eikonal wavefront cognition (Phase 308)
    "ouroboros",         # Self-reference kernel
    "alexandria",        # Archival mass + isotopes
    "realtime_encoder",  # Tier-5 shadow encoder
    "timing",            # Per-cycle wall-time, KCCL phase count
    "manipulation",      # Manipulation detector
    "scar",              # SCAR formation events
    "thermodynamic",     # Layer 1/2/3 thermodynamic bridges
)


@dataclass(frozen=True)
class CatalogedField:
    """One documented field in Kimera's OrchestratorResult."""

    name: str                          # raw dict key
    types: tuple[str, ...]             # accepted Python type names (e.g. ("int", "float"))
    family: str                        # semantic family from CATALOG_FAMILIES
    description: str                   # 1-2 sentence description
    nullable: bool = False             # True if None is a valid value

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("CatalogedField.name cannot be empty")
        if not self.types:
            raise ValueError(f"CatalogedField {self.name!r}: types cannot be empty")
        if self.family not in CATALOG_FAMILIES:
            raise ValueError(
                f"CatalogedField {self.name!r}: family {self.family!r} not in "
                f"{sorted(CATALOG_FAMILIES)}"
            )

    def accepts_value(self, value: Any) -> bool:
        """Whether ``value`` matches one of this field's accepted types."""
        if value is None:
            return self.nullable
        type_name = type(value).__name__
        if type_name in self.types:
            return True
        # "int" accepts bool (Python bools ARE ints) only if "bool" is also declared.
        if isinstance(value, bool):
            return "bool" in self.types
        if isinstance(value, int) and "int" in self.types:
            return True
        if isinstance(value, float) and "float" in self.types:
            return True
        if isinstance(value, str) and "str" in self.types:
            return True
        if isinstance(value, list) and "list" in self.types:
            return True
        if isinstance(value, dict) and "dict" in self.types:
            return True
        if isinstance(value, tuple) and "tuple" in self.types:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "types": list(self.types),
            "family": self.family,
            "description": self.description,
            "nullable": self.nullable,
        }


# ---------------------------------------------------------------------------
# Curated catalog — ~30 high-signal fields scenarios actively use or are about
# to use. Update as new scenarios land. Order: roughly family-then-name.
# ---------------------------------------------------------------------------


KIMERA_FIELD_CATALOG: tuple[CatalogedField, ...] = (
    # --- timing ---------------------------------------------------------
    CatalogedField(
        "cycle_seconds", ("float", "int"), "timing",
        "Per-cycle wall-time in seconds. Surfaced from the subprocess "
        "runner's top-level emit into raw; the InstrumentedSubstrate fallback "
        "is an even split across the batch.",
    ),

    # --- phi ------------------------------------------------------------
    CatalogedField(
        "phi_value", ("float", "int"), "phi",
        "Φ — IIT-derived integrated-information measure per cycle. Family L "
        "EV-71 reported mean 0.621 ± 0.065 across 200 cycles on engineered "
        "axioms; Family P measured ~0.209 on Linux kernel commits.",
        nullable=True,
    ),
    CatalogedField(
        "kii_value", ("float", "int"), "phi",
        "Alias for phi_value. Kept available for Pattern-P phi/KII rename "
        "(owner-territory per CLAUDE.md §Family L).",
        nullable=True,
    ),

    # --- walker ---------------------------------------------------------
    CatalogedField(
        "walker_halt_mode", ("str",), "walker",
        "PrimeTopologyWalker halt mode for this cycle. One of: 'exhausted' "
        "(sustained traversal), 'selective' (partial halt), 'amplitude_death' "
        "(silent collapse), 'commit' (M1), 'rollback' (M3), 'lateral_leap' "
        "(M4). Plus 'exception' on substrate crash.",
        nullable=True,
    ),
    CatalogedField(
        "walker_m1_commit_count", ("int",), "walker",
        "Number of M1 COMMIT events the walker fired this cycle.",
        nullable=True,
    ),
    CatalogedField(
        "walker_m2_amplitude_death_count", ("int",), "walker",
        "Number of M2 amplitude_death events this cycle.",
        nullable=True,
    ),
    CatalogedField(
        "walker_m3_rollback_count", ("int",), "walker",
        "Number of M3 ROLLBACK events this cycle.",
        nullable=True,
    ),
    CatalogedField(
        "walker_m4_lateral_leap_count", ("int",), "walker",
        "Number of M4 LATERAL LEAP events this cycle. Family E4 measured "
        "1.67% ± 1.53% firing rate across 3 replicates post-PR #180.",
        nullable=True,
    ),

    # --- gwf ------------------------------------------------------------
    CatalogedField(
        "gwf_blocked", ("bool",), "gwf",
        "True if the Gyroscopic Water Fortress defensive layer blocked this "
        "stimulus. Family M reported 3.2% FP rate on labelled-benign prompts; "
        "Family P reported 33.9% on Linux kernel commit messages.",
        nullable=True,
    ),
    CatalogedField(
        "gwf_block_reason", ("str",), "gwf",
        "Human-readable reason when gwf_blocked=True (e.g. anchor that "
        "matched).",
        nullable=True,
    ),

    # --- manipulation ---------------------------------------------------
    CatalogedField(
        "manipulation_detected", ("bool",), "manipulation",
        "True if the manipulation_detector layer (downstream of GWF) flagged "
        "this stimulus. Family O reported 0.3% rate on Enron — ~30× more "
        "conservative than GWF on the same corpus.",
        nullable=True,
    ),

    # --- prime ----------------------------------------------------------
    CatalogedField(
        "concepts_count", ("int",), "prime",
        "Number of extracted concepts that produced the prime_chain this "
        "cycle. Family P median ~9; saturated content sees substantially more.",
        nullable=True,
    ),
    CatalogedField(
        "prime_chain", ("list",), "prime",
        "Per-cycle list of composite primes (Walker visit order). Composite = "
        "p_thermo × p_identity × stamp per the F.1.1 architecture verified "
        "37/37 in Phase 4 (CLAUDE.md §Arachne F.1.1 composite).",
        nullable=True,
    ),
    CatalogedField(
        "composite_prime", ("int",), "prime",
        "Cycle-level composite_prime exposed after the Layer-5 fix (J2). "
        "AAPL×XOM Layer-5 Jaccard went 0.647 → 0.000 after this surfaced.",
        nullable=True,
    ),

    # --- substrate_state ------------------------------------------------
    CatalogedField(
        "substrate_state_stamp", ("int", "str"), "substrate_state",
        "Per-cycle stamp that evolves with substrate experience. F.1.2 "
        "stamp dropped scars_stored as a contributor (Edit 15, 2026-04-26).",
        nullable=True,
    ),
    CatalogedField(
        "atlas_violations_count", ("int",), "substrate_state",
        "Atlas (Geoid 1+3+1 enforcer, post-Q4 organ rename) violation count. "
        "Atlas catches 7 violation types.",
        nullable=True,
    ),
    CatalogedField(
        "arachne_web_kuramoto_order", ("float",), "substrate_state",
        "Arachne web Kuramoto order parameter. Empirically saturates at "
        "~0.81 across 300+ cycles (CLAUDE.md §Phase 1 verified deltas).",
        nullable=True,
    ),
    CatalogedField(
        "arachne_web_order_parameter", ("float",), "substrate_state",
        "Arachne web order parameter (raw, before Kuramoto normalization). "
        "2026-05-15 discover sweep observed monotonic growth 0.295→0.741 "
        "across cycles 1-10 — the 'memory-as-deformation' signature visible "
        "at the Arachne layer.",
        nullable=True,
    ),
    CatalogedField(
        "arachne_web_coupling_frobenius", ("float",), "substrate_state",
        "Frobenius norm of the Arachne web coupling matrix. 2026-05-15 "
        "discover sweep observed monotonic growth 1.27→2.64 across cycles "
        "1-10 (memory-as-deformation, energy interpretation).",
        nullable=True,
    ),
    CatalogedField(
        "arachne_web_coupling_top_eigenvalue", ("float",), "substrate_state",
        "Top eigenvalue of the Arachne web coupling matrix. 2026-05-15 "
        "discover sweep observed 1.18→2.24 across cycles 1-10 (dominant "
        "mode amplification).",
        nullable=True,
    ),
    CatalogedField(
        "alexandria_knowledge_mass_cumulative", ("float", "int"), "alexandria",
        "Cumulative Alexandria knowledge mass. 2026-05-15 discover sweep "
        "observed linear ~4.5 mass-units/cycle accumulation (8.8→45.4 over "
        "10 cycles); CLAUDE.md §Phase 1 verified deltas reports ~17 "
        "mass-units/cycle on different stimuli (rate is content-dependent).",
        nullable=True,
    ),

    # --- consolidation --------------------------------------------------
    CatalogedField(
        "consolidation_pulse_fired", ("bool",), "consolidation",
        "True when the KCCL sleep cycle fired this cycle (every "
        "_consolidation_interval, default 5).",
        nullable=True,
    ),
    CatalogedField(
        "nrem_scars_replayed", ("int",), "consolidation",
        "Number of SCARs replayed during the NREM phase of consolidation "
        "(Session 010 calibrated default 0.40).",
        nullable=True,
    ),
    CatalogedField(
        "rem_edges_pruned", ("int",), "consolidation",
        "Number of weak Physarum edges pruned during the REM phase "
        "(Session 010 calibrated default 0.15).",
        nullable=True,
    ),

    # --- echoform -------------------------------------------------------
    CatalogedField(
        "echoform_event", ("dict",), "echoform",
        "Per-cycle Echoform event with the 6 genesis White Paper §V fields: "
        "actor/action/object/target/time+context/outcome/causal_links. "
        "Landed in Gap 5 closure 2026-05-12.",
        nullable=True,
    ),
    CatalogedField(
        "dissonance_events_count", ("int",), "echoform",
        "Per-cycle dissonance event count. Family O reported median 21 on "
        "Enron, median 28 on Linux kernel commits; range [0, 57].",
        nullable=True,
    ),

    # --- piovra ---------------------------------------------------------
    CatalogedField(
        "piovra_arms_active", ("list", "int"), "piovra",
        "Active Piovra arms this cycle. text_arm_0 fires always; "
        "reasoning_arm_0 after concept-count threshold; visual + audio fire "
        "via Phase 262.3 prosodic + text-concept-landscape fallbacks unless "
        "real encoders provide non-empty input.",
        nullable=True,
    ),
    CatalogedField(
        "piovra_visual_source", ("str",), "piovra",
        "Source of visual_arm_0's input this cycle: 'ImageGeoidEncoder' (real) "
        "vs 'text_concept_landscape' (fallback). Distinguishing this matters "
        "for cross-modal experiments.",
        nullable=True,
    ),

    # --- internal_event (the 5 kinds, closed 2026-05-06) ---------------
    CatalogedField(
        "ouroboros_tick_fired", ("bool",), "internal_event",
        "Roots-inward internal-event kind: Ouroboros self-output tick. EV-37 "
        "found this fires every cycle in treatment (universal state-emitter).",
        nullable=True,
    ),
    CatalogedField(
        "cronos_drift_event", ("bool",), "internal_event",
        "Roots-inward internal-event kind: Cronos L4 drift / amplitude-death "
        "detector. Boolean rare-event detector — fires on hallucinating OR "
        "amplitude_death (EV-38 Branch 4 classification).",
        nullable=True,
    ),
    CatalogedField(
        "spde_pressure_peak_event", ("bool",), "internal_event",
        "Roots-inward internal-event kind: SPDE void-suction pressure peak. "
        "EV-38 measured 100% → 0% under 10× threshold tightening.",
        nullable=True,
    ),
    CatalogedField(
        "thermodynamic_transition_event", ("bool",), "internal_event",
        "Roots-inward internal-event kind: Echoform-operator ΔS transition. "
        "EV-38 found this fires every cycle under both threshold conditions.",
        nullable=True,
    ),
    CatalogedField(
        "quantum_amplitude_burst_event", ("bool",), "internal_event",
        "Roots-inward internal-event kind: PrimeWaveQuantumEngine entanglement "
        "burst. EV-38 F-3 found it responds to *distributed* semantic "
        "activation, not concentrated.",
        nullable=True,
    ),

    # --- lateral_line ---------------------------------------------------
    CatalogedField(
        "lateral_line_pressure", ("float",), "lateral_line",
        "Substrate self-emission pressure (rate × magnitude). EV-39g "
        "production midpoint ~3e-7 mag/ns.",
        nullable=True,
    ),
    CatalogedField(
        "lateral_line_rhythm", ("float",), "lateral_line",
        "Autocorrelation-peak rhythm of the substrate's self-emission stream.",
        nullable=True,
    ),
    CatalogedField(
        "lateral_line_drift", ("float",), "lateral_line",
        "First-derivative drift of the substrate's self-emission stream.",
        nullable=True,
    ),

    # --- eikonal --------------------------------------------------------
    CatalogedField(
        "eikonal_active", ("bool",), "eikonal",
        "True when Phase 308 Eikonal wavefront cognition fired this cycle "
        "(conditional on SPDE engine availability).",
        nullable=True,
    ),
    CatalogedField(
        "eikonal_mean_arrival_time", ("float",), "eikonal",
        "Mean wavefront arrival time across nodes Eikonal reached this cycle.",
        nullable=True,
    ),
    CatalogedField(
        "eikonal_nodes_reached", ("int",), "eikonal",
        "Number of manifold nodes the Eikonal wavefront reached this cycle.",
        nullable=True,
    ),

    # --- alexandria -----------------------------------------------------
    CatalogedField(
        "alexandria_mass", ("float", "int"), "alexandria",
        "Cumulative Alexandria archival mass after this cycle. Phase 1 probe "
        "measured ~17 mass-units/cycle linear growth.",
        nullable=True,
    ),

    # --- realtime_encoder ----------------------------------------------
    CatalogedField(
        "realtime_encoder_attached", ("bool",), "realtime_encoder",
        "True when Tier-5 realtime encoder shadow-training hook is wired "
        "this cycle (default-True since 2026-04-29).",
        nullable=True,
    ),
    CatalogedField(
        "realtime_encoder_health", ("dict",), "realtime_encoder",
        "Per-cycle shadow-encoder health report (fires per consolidation "
        "interval, default 5 cycles).",
        nullable=True,
    ),

    # --- scar -----------------------------------------------------------
    CatalogedField(
        "scars_written", ("int",), "scar",
        "Number of SCARs written to the vault this cycle.",
        nullable=True,
    ),
)


# Indexed lookup for cheap by-name access
CATALOG_BY_NAME: dict[str, CatalogedField] = {f.name: f for f in KIMERA_FIELD_CATALOG}


def cataloged(name: str) -> CatalogedField | None:
    """Look up a CatalogedField by name. ``None`` if not in catalog."""
    return CATALOG_BY_NAME.get(name)


def catalog_by_family(family: str) -> tuple[CatalogedField, ...]:
    """All cataloged fields belonging to one semantic family."""
    return tuple(f for f in KIMERA_FIELD_CATALOG if f.family == family)


# ---------------------------------------------------------------------------
# Scenario field-contract — what one scenario depends on
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldContract:
    """A scenario's stated dependency on one OrchestratorResult field.

    ``required=True`` means: missing this field on a probe is a hard failure
    (scenario cannot run). ``required=False`` means: missing is logged but
    not fatal (scenario degrades).

    The contract is *informational* if the field isn't in the catalog —
    catalog membership lets us check types; without it, only presence is
    validated.
    """

    field_name: str
    required: bool = True
    expected_family: str = ""   # if set, must match catalog entry's family

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "required": self.required,
            "expected_family": self.expected_family,
        }


@dataclass(frozen=True)
class ScenarioFieldContract:
    """The complete field-dependency contract for one scenario."""

    scenario_name: str
    contracts: tuple[FieldContract, ...]

    def field_names(self) -> tuple[str, ...]:
        return tuple(c.field_name for c in self.contracts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "contracts": [c.to_dict() for c in self.contracts],
        }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractViolation:
    """One way a probe cycle's raw dict failed to satisfy a contract."""

    field_name: str
    kind: str          # "missing_required" | "type_mismatch" | "family_mismatch" | "uncataloged_required"
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"field_name": self.field_name, "kind": self.kind, "detail": self.detail}


def validate_contract_against_raw(
    contract: ScenarioFieldContract,
    raw: dict[str, Any],
) -> tuple[ContractViolation, ...]:
    """Check one ``raw`` dict against a scenario's field contract.

    Returns a tuple of violations. Empty tuple = contract satisfied.

    Catalog-aware: if the contract names a field that's in the catalog AND
    the field is present in raw, the value's type is checked against the
    catalog entry's accepted types.

    A contract on an uncataloged field surfaces ``uncataloged_required`` —
    NOT a violation per se, but a hint to add the field to the catalog (so
    type checking can apply on future runs).
    """
    violations: list[ContractViolation] = []
    for c in contract.contracts:
        cataloged_entry = CATALOG_BY_NAME.get(c.field_name)
        present = c.field_name in raw
        if not present:
            if c.required:
                violations.append(ContractViolation(
                    field_name=c.field_name,
                    kind="missing_required",
                    detail=f"scenario {contract.scenario_name!r} declares "
                           f"{c.field_name!r} as required but raw lacks it",
                ))
            continue
        # field is present
        value = raw[c.field_name]
        if cataloged_entry is None:
            if c.required:
                violations.append(ContractViolation(
                    field_name=c.field_name,
                    kind="uncataloged_required",
                    detail=f"scenario {contract.scenario_name!r} requires "
                           f"{c.field_name!r} but it's not in KIMERA_FIELD_CATALOG; "
                           f"add a CatalogedField entry to enable type checking",
                ))
            continue
        if not cataloged_entry.accepts_value(value):
            violations.append(ContractViolation(
                field_name=c.field_name,
                kind="type_mismatch",
                detail=f"raw[{c.field_name!r}] has type {type(value).__name__!r}, "
                       f"catalog accepts {sorted(cataloged_entry.types)}"
                       f"{' or None' if cataloged_entry.nullable else ''}",
            ))
            continue
        if c.expected_family and cataloged_entry.family != c.expected_family:
            violations.append(ContractViolation(
                field_name=c.field_name,
                kind="family_mismatch",
                detail=f"scenario expected family {c.expected_family!r}, "
                       f"catalog has {cataloged_entry.family!r}",
            ))
    return tuple(violations)


def catalog_coverage(raw: dict[str, Any]) -> dict[str, Any]:
    """Compute coverage statistics for a probe cycle's raw dict.

    Returns ``{"in_catalog": N, "uncataloged": M, "missing_from_raw": K,
    "in_catalog_names": [...], "uncataloged_names": [...],
    "missing_from_raw_names": [...]}``.

    Use this to drive a ``discover-fields`` command that diffs the catalog
    against an actual probe cycle and surfaces undocumented fields.
    """
    cat_names = set(CATALOG_BY_NAME)
    raw_names = set(raw)
    in_catalog = sorted(raw_names & cat_names)
    uncataloged = sorted(raw_names - cat_names)
    missing_from_raw = sorted(cat_names - raw_names)
    return {
        "in_catalog": len(in_catalog),
        "uncataloged": len(uncataloged),
        "missing_from_raw": len(missing_from_raw),
        "in_catalog_names": in_catalog,
        "uncataloged_names": uncataloged,
        "missing_from_raw_names": missing_from_raw,
        "catalog_size": len(KIMERA_FIELD_CATALOG),
        "raw_size": len(raw),
    }
