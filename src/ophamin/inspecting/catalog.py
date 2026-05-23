"""PrimitiveCatalog — curated list of known Kimera primitives.

Per CLAUDE.md, Kimera has 60+ named primitives across 15 biological families.
The full inventory lives in Kimera's
``Docs_v2/02_architecture/thermodynamic/primitive_inventory.md`` and is
considered authoritative. This catalog is the *Ophamin-side* working
subset — every primitive Ophamin currently has a probe shape for (whether
as a Kimera adapter target, a scenario, or just static introspection).

Family tags follow CLAUDE.md's biological-role organisation:
  brain          — orchestration (Takwin, Walker, CIP, KCCL, …)
  nervous_system — prime apparatus (Arachne, Rosetta, ZetaBridge)
  sensory        — Piovra, Empathy, Lateral Line
  body           — substrate (Geoid, Vault, SCAR, Manifold)
  physics        — partition / TFD / SPDE / PDE Fields
  time           — Cronos
  memory         — Hopfield / Mycelium / Physarum / Dopamine
  defence        — GWF / Zetetic / Danger Theory / Colony
  coordination   — Kuramoto / Siphonophore / Maxwell's Demon / CIP
  self_model     — Ouroboros / Attention Schema / Mirror Neuron
  form_algebra   — Echoform / Ecoform
  expression     — BrocaCortex
  governance     — Alexandria / Provenance / Event Encoding
  language       — Pentecost (1+3+1 perception)
  topology       — TopologicalComplexityAnalyzer / Walker

Tags are descriptive, not exclusive — a primitive can carry multiple. The
catalog is *additive*: new primitives can be registered programmatically by
``PrimitiveCatalog.register``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator


@dataclass(frozen=True)
class PrimitiveEntry:
    """One known primitive's catalog entry.

    ``canonical_class`` is the Python class name; ``canonical_module`` is the
    fully-qualified module path within the Kimera repository (without the
    ``kimera_swm.`` prefix — added when the locator resolves). ``adapter_target``
    is the KimeraAdapter target name if this primitive has a direct probe.
    """

    name: str                          # display name, e.g. "Walker"
    canonical_class: str               # Python class name, e.g. "PrimeTopologyWalker"
    canonical_module: str              # e.g. "domain.cognitive.prime_topology_walker"
    family_tags: tuple[str, ...]
    adapter_target: str | None = None  # KIMERA_TARGETS key if probable
    description: str = ""

    @property
    def fully_qualified_module(self) -> str:
        return f"kimera_swm.{self.canonical_module}"


#: The initial Ophamin-side catalog — every primitive surfaced by our four
#: existing scenarios + a handful of CLAUDE.md's most-mentioned named subsystems.
#: Add to this list as new probes get wired.
KNOWN_PRIMITIVES: tuple[PrimitiveEntry, ...] = (
    # brain
    PrimitiveEntry(
        name="Takwin",
        canonical_class="Takwin",
        canonical_module="domain.cognitive.takwin",
        family_tags=("brain", "orchestration"),
        adapter_target="entity",
        description="7-step cognitive cycle; orchestrator of the named primitives",
    ),
    PrimitiveEntry(
        name="Walker",
        canonical_class="PrimeTopologyWalker",
        canonical_module="domain.cognitive.prime_topology_walker",
        family_tags=("brain", "topology", "coordination"),
        adapter_target="walker",
        description="Physics-driven manifold traversal; 4 modes (M1-M4)",
    ),
    PrimitiveEntry(
        name="CognitiveInterpreter",
        canonical_class="CognitiveInterpreter",
        canonical_module="domain.cognitive.cognitive_interpreter",
        family_tags=("brain", "expression"),
        description="Physics → interpretation → language spine (Phase 236)",
    ),

    # nervous_system
    PrimitiveEntry(
        name="Arachne",
        canonical_class="ArachneProtocol",
        canonical_module="domain.prime.arachne_protocol",
        family_tags=("nervous_system",),
        adapter_target="arachne",
        description="Prime nervous system / registry / bidirectional weave",
    ),
    PrimitiveEntry(
        name="Rosetta",
        canonical_class="RosettaStele",
        canonical_module="domain.semantic.rosetta_stele",
        family_tags=("nervous_system", "language"),
        adapter_target="rosetta",
        description="Universal semantic-address translator",
    ),
    PrimitiveEntry(
        name="ZetaBridge",
        canonical_class="ZetaBridge",
        canonical_module="domain.prime.zeta_bridge",
        family_tags=("nervous_system", "physics"),
        description="Zero-parameter ζ-prime emergence bridge",
    ),

    # sensory
    PrimitiveEntry(
        name="Piovra",
        canonical_class="ArmGanglion",
        canonical_module="domain.piovra.arm_ganglion",
        family_tags=("sensory",),
        adapter_target="piovra",
        description="Distributed multi-arm sensory architecture",
    ),

    # body
    PrimitiveEntry(
        name="Geoid",
        canonical_class="Atlas",
        canonical_module="domain.geoid.geoid_1_3_1_enforcement",
        family_tags=("body",),
        description="1+3+1 skeleton of every Geoid (renamed from Geoid1_3_1_Enforcer to Atlas)",
    ),
    PrimitiveEntry(
        name="Astrolabe",
        canonical_class="Astrolabe",
        canonical_module="domain.geoid.spherical_5d_geometry",
        family_tags=("body", "topology"),
        adapter_target="astrolabe",
        description="5D spherical-geometry engine (S⁴ ⊂ ℝ⁵)",
    ),

    # physics
    PrimitiveEntry(
        name="PrimeWaveQuantumEngine",
        canonical_class="PrimeWaveQuantumEngine",
        canonical_module="domain.quantum.prime_wave_quantum_engine",
        family_tags=("physics", "nervous_system"),
        description="Quantum-style state composition (ω_p = exp(2πi/p))",
    ),
    PrimitiveEntry(
        name="SPDE",
        canonical_class="SPDEEngine",
        canonical_module="domain.cognitive.spde_engine",
        family_tags=("physics",),
        description="Semantic Pressure Diffusion Engine (4 pressure types)",
    ),

    # time
    PrimitiveEntry(
        name="Cronos",
        canonical_class="CronosSync",
        canonical_module="infrastructure.temporal.cronos.cronos_sync",
        family_tags=("time",),
        description="6-layer atomic clock + sync; 51.4μs/tick",
    ),

    # defence
    PrimitiveEntry(
        name="GWF",
        canonical_class="GWFProtocol",
        canonical_module="domain.security.gyroscopic_water_fortress.gwf_protocol",
        family_tags=("defence",),
        adapter_target="gwf",
        description="Gyroscopic Water Fortress immune membrane",
    ),

    # self_model
    PrimitiveEntry(
        name="Ouroboros",
        canonical_class="OuroborosKernel",
        canonical_module="domain.mathematical.ouroboros_kernel",
        family_tags=("self_model",),
        adapter_target="ouroboros",
        description="Self-reference / closed-loop kernel",
    ),

    # form_algebra
    PrimitiveEntry(
        name="Echoform",
        canonical_class="EchoformOperatorSystem",
        canonical_module="domain.ecosystem_form.echoform_operator_system",
        family_tags=("form_algebra",),
        description="Substrate's grammar engine; ΔS≥0 enforcement",
    ),

    # governance
    PrimitiveEntry(
        name="Alexandria",
        canonical_class="AlexandriaInterface",
        canonical_module="domain.mathematical.alexandria_protocol",
        family_tags=("governance", "memory"),
        description="Library/archival protocol; REM-sleep micro-dreams",
    ),

    # language
    PrimitiveEntry(
        name="Pentecost",
        canonical_class="Pentecost",
        canonical_module="domain.linguistic.one_plus_three_plus_one_enforcer",
        family_tags=("language",),
        adapter_target="pentecost",
        description="Multi-language 1+3+1 perception organ",
    ),
)


class PrimitiveCatalog:
    """Indexed view over the catalogued primitives + a place to register new ones."""

    def __init__(self, entries: Iterable[PrimitiveEntry] | None = None) -> None:
        self._entries: list[PrimitiveEntry] = list(entries if entries is not None else KNOWN_PRIMITIVES)
        self._by_name: dict[str, PrimitiveEntry] = {e.name.lower(): e for e in self._entries}
        # also index by class name for lookup-by-class (common when probing
        # from inside Kimera-aware code)
        for entry in self._entries:
            self._by_name.setdefault(entry.canonical_class.lower(), entry)

    def __iter__(self) -> "Iterator[PrimitiveEntry]":
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def all_entries(self) -> tuple[PrimitiveEntry, ...]:
        return tuple(self._entries)

    def by_name(self, name: str) -> PrimitiveEntry | None:
        return self._by_name.get(name.strip().lower())

    def by_family(self, family_tag: str) -> list[PrimitiveEntry]:
        return [e for e in self._entries if family_tag in e.family_tags]

    def register(self, entry: PrimitiveEntry) -> None:
        """Add a new primitive to the catalog. Refuses to clobber an
        existing entry with the same name."""
        key = entry.name.strip().lower()
        if key in self._by_name:
            raise ValueError(
                f"primitive {entry.name!r} is already registered "
                f"(class {self._by_name[key].canonical_class})"
            )
        self._entries.append(entry)
        self._by_name[key] = entry
        self._by_name.setdefault(entry.canonical_class.lower(), entry)
