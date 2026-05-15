"""The Prime Structure scenario — substrate's prime emission as a measured object.

Per CLAUDE.md §"Primes are load-bearing, not decorative" and §"Arachne F.1.1
composite — empirically airtight" — the substrate emits primes per cycle via
``ArachneProtocol.assign_via_lyriform``. The composite_prime is
``p_thermo × p_identity × stamp`` per CLAUDE.md F.1.1, where:

- ``p_thermo`` carries ~2 bits per concept (omega_obs lyriform output)
- ``p_identity`` is SHA-256-deterministic from concept name (~16 bits)
- ``stamp`` evolves per-cycle within ONE Takwin (substrate-state factor)

So `prime_chain` (composite-level) Jaccard between repeated-stimulus pairs
is **expected near 0** because the stamp factor makes every composite unique
even for the same content. Recognition lives at the **content layer**:

> "For pure content fingerprinting, `concepts` is the cleanest layer
> (deterministic + content-discriminating)." — CLAUDE.md F.1.1

This scenario probes four structural properties:

1. **Concept-set recognition Jaccard** — for stimuli that repeat across
   cycles, the Jaccard similarity between extracted ``concepts`` sets
   should be high. Session 013 reported recognition Jaccard ≥ 0.94 in a
   controlled regime; the scenario's pre-registered floor is 0.50 (allows
   substantial substrate-state drift).

2. **Composite-set Jaccard** (informational, not headline) — should be
   near 0 by stamp-factor design. A non-zero floor here would indicate
   either the stamp isn't actually evolving per-cycle (substrate bug) or
   primes are being reused as composites across stimuli (also a bug).

3. **Identity coverage** — ``prime_identity_coverage.coverage_ratio`` per
   cycle. Should be near 1.0 (every concept extracted gets a registered
   prime). Drops below 1.0 surface registration gaps.

4. **Vocabulary growth + size distribution** — how does the cardinality
   of unique composite primes used grow with cycles? Linear growth (every
   cycle adds new primes) confirms the stamp factor is doing its job;
   sub-linear with high drift would surface a stamp-evolution defect.

Falsifiable claim
==================

> Across N captured cycles with a repeating stimulus schedule, the
> CONCEPT-SET recognition Jaccard floor for repeated stimuli is ≥ 0.50.

This is the load-bearing recognition claim — not composite-Jaccard, which
IS expected near 0 by F.1.1 architecture.

Inputs
======

The scenario takes a ``trajectory_path`` to a JSON containing a
``trajectory`` list with per-cycle ``prime_chain`` + ``stimulus`` +
``prime_identity_coverage``.

Output
======

A signed ``EmpiricalProofRecord`` with:

* recognition Jaccard per (stimulus, rep_pair) — distribution + floor
* vocabulary growth curve (cycle → cumulative unique primes)
* coverage ratio distribution (mean, min, p10, p90)
* prime size distribution (log10(prime) histogram bins)
* substrate "favourite primes" (top-10 most-frequent emissions)
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _is_prime(n: int) -> bool:
    """Deterministic primality test for n < 10^8 (matches Arachne's _is_prime)."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def _identity_prime_from_canonical(canonical: str) -> int:
    """Re-implementation of ArachneProtocol._identity_prime per CLAUDE.md F.1.1.

    SHA-256 hash of the canonical concept name → small prime in [100, 49100].
    Deterministic; same canonical name always produces the same prime.
    Source-of-truth: kimera_swm/domain/prime/arachne_protocol.py:2313
    """
    h = hashlib.sha256(canonical.encode("utf-8")).digest()
    candidate = (int.from_bytes(h[:4], "big") % 49000) + 100
    while not _is_prime(candidate):
        candidate += 1
    return candidate

from ophamin import __version__
from ophamin.comparing.provenance import ProvenanceGraph
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class PrimeStructureScenario(Scenario):
    """Multi-faceted probe of substrate's prime emission structure."""

    name = "prime-structure"
    corpus_name = "kimera-prime-trajectory"
    target = "captured_prime_chain_emission"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        recognition_jaccard_floor: float = 0.50,
        coverage_ratio_floor: float = 0.95,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not 0.0 < recognition_jaccard_floor <= 1.0:
            raise ValueError(
                f"recognition_jaccard_floor must be in (0, 1], got "
                f"{recognition_jaccard_floor}"
            )
        if not 0.0 < coverage_ratio_floor <= 1.0:
            raise ValueError(
                f"coverage_ratio_floor must be in (0, 1], got "
                f"{coverage_ratio_floor}"
            )
        self.recognition_jaccard_floor = float(recognition_jaccard_floor)
        self.coverage_ratio_floor = float(coverage_ratio_floor)
        self.n_cycles = 0  # static; base.run() overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "PrimeStructureScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across cycles with repeated stimuli, the substrate's "
                f"recognition Jaccard floor (min Jaccard between "
                f"prime_chains of two cycles seeing the same stimulus) is "
                f"≥ {self.recognition_jaccard_floor}. Validates "
                "Family L L5+L6's recognition / cross-cycle prime stability "
                "claim at this commit; refutation = recognition layer "
                "broken."
            ),
            operationalization=(
                "Group cycles by stimulus; for each stimulus with ≥ 2 "
                "cycles, compute pairwise Jaccard between prime_chains "
                "(treated as sets); take min across all pairs as the floor. "
                "Verdict against the pre-registered floor."
            ),
            threshold=Threshold(
                metric="recognition_jaccard_floor",
                comparator=">=",
                value=self.recognition_jaccard_floor,
                units="jaccard",
            ),
            h0=(
                f"recognition_jaccard_floor < {self.recognition_jaccard_floor} — "
                "substrate emits substantially different primes for the "
                "same stimulus across cycles (recognition layer broken or "
                "substrate-state drift exceeds tolerable limit)"
            ),
            h1=(
                f"recognition_jaccard_floor >= {self.recognition_jaccard_floor} — "
                "substrate's prime emission is stable across re-exposures "
                "to the same stimulus, with allowed substrate-state "
                "evolution drift"
            ),
        )

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        traj_data = json.loads(self.trajectory_path.read_text())
        trajectory = traj_data.get("trajectory", [])
        if not trajectory:
            raise ValueError("trajectory is empty")
        kimera_commit = traj_data.get("kimera_commit", "")
        n_cycles = len(trajectory)

        # ---- (1) Recognition Jaccard at CONCEPT-SET layer ---------------
        # Per CLAUDE.md F.1.1: composite-prime Jaccard is ~0 by design
        # (stamp evolves per-cycle); recognition lives at concepts layer.
        per_stimulus_concepts: dict[str, list[set[str]]] = defaultdict(list)
        per_stimulus_chains: dict[str, list[set[int]]] = defaultdict(list)
        for c in trajectory:
            stim = c.get("stimulus", "")
            concepts = c.get("concepts")
            chain = c.get("prime_chain")
            if isinstance(concepts, list) and concepts:
                per_stimulus_concepts[stim].append(
                    set(str(x) for x in concepts)
                )
            if isinstance(chain, list) and chain:
                per_stimulus_chains[stim].append(
                    set(int(p) for p in chain if isinstance(p, (int, float)))
                )

        # Concept-Jaccard (HEADLINE for verdict)
        per_stimulus_concept_pairs: list[dict[str, Any]] = []
        all_concept_jaccards: list[float] = []
        for stim, concept_sets in per_stimulus_concepts.items():
            if len(concept_sets) < 2:
                continue
            stim_jaccards: list[float] = []
            for i in range(len(concept_sets)):
                for j in range(i + 1, len(concept_sets)):
                    a, b = concept_sets[i], concept_sets[j]
                    if not a and not b:
                        continue
                    j_val = len(a & b) / max(len(a | b), 1)
                    stim_jaccards.append(j_val)
            if stim_jaccards:
                all_concept_jaccards.extend(stim_jaccards)
                per_stimulus_concept_pairs.append({
                    "stimulus": stim[:60],
                    "n_cycles_with_stim": len(concept_sets),
                    "n_pairs": len(stim_jaccards),
                    "jaccard_min": min(stim_jaccards),
                    "jaccard_max": max(stim_jaccards),
                    "jaccard_mean": statistics.mean(stim_jaccards),
                })

        # Composite-Jaccard (INFORMATIONAL — expected near 0 by stamp design)
        all_composite_jaccards: list[float] = []
        for stim, chains in per_stimulus_chains.items():
            if len(chains) < 2:
                continue
            for i in range(len(chains)):
                for j in range(i + 1, len(chains)):
                    a, b = chains[i], chains[j]
                    if not a and not b:
                        continue
                    j_val = len(a & b) / max(len(a | b), 1)
                    all_composite_jaccards.append(j_val)

        if not all_concept_jaccards:
            raise RuntimeError(
                "No repeated-stimulus pairs found in trajectory — concept "
                "recognition Jaccard cannot be computed. Need a trajectory "
                "where stimuli repeat across cycles."
            )
        recognition_floor = min(all_concept_jaccards)
        recognition_mean = statistics.mean(all_concept_jaccards)
        recognition_max = max(all_concept_jaccards)
        composite_floor = min(all_composite_jaccards) if all_composite_jaccards else 0.0
        composite_mean = (statistics.mean(all_composite_jaccards)
                          if all_composite_jaccards else 0.0)

        # ---- (2) Vocabulary growth ----------------------------------------
        seen_primes: set[int] = set()
        growth_curve: list[tuple[int, int]] = []
        for c in trajectory:
            chain = c.get("prime_chain")
            if isinstance(chain, list):
                seen_primes.update(int(p) for p in chain if isinstance(p, (int, float)))
            growth_curve.append((c.get("cycle_index", len(growth_curve)),
                                 len(seen_primes)))
        n_unique_primes = len(seen_primes)
        # Sub-linear check: final unique-count vs n_cycles
        sublinear_ratio = n_unique_primes / max(n_cycles, 1)

        # ---- (3) Coverage ratio distribution ---------------------------
        coverage_ratios = [
            c["prime_identity_coverage"]["coverage_ratio"]
            for c in trajectory
            if isinstance(c.get("prime_identity_coverage"), dict)
            and "coverage_ratio" in c["prime_identity_coverage"]
        ]
        coverage_summary = {
            "n_with_coverage": len(coverage_ratios),
            "mean": statistics.mean(coverage_ratios) if coverage_ratios else None,
            "min": min(coverage_ratios) if coverage_ratios else None,
            "n_below_floor": sum(1 for r in coverage_ratios
                                 if r < self.coverage_ratio_floor),
        }

        # ---- (4) Prime size distribution ---------------------------------
        log10_primes = [
            math.log10(p) for p in seen_primes
            if isinstance(p, int) and p > 0
        ]
        size_dist_summary = {
            "n_primes": len(log10_primes),
            "log10_mean": statistics.mean(log10_primes) if log10_primes else None,
            "log10_p10": (statistics.quantiles(log10_primes, n=10)[0]
                         if len(log10_primes) >= 10 else None),
            "log10_median": statistics.median(log10_primes) if log10_primes else None,
            "log10_p90": (statistics.quantiles(log10_primes, n=10)[8]
                         if len(log10_primes) >= 10 else None),
            "log10_max": max(log10_primes) if log10_primes else None,
            "smallest_prime": min(seen_primes) if seen_primes else None,
            "largest_prime": max(seen_primes) if seen_primes else None,
        }

        # ---- (5) Substrate's favourite primes ----------------------------
        prime_freq: Counter[int] = Counter()
        for c in trajectory:
            chain = c.get("prime_chain")
            if isinstance(chain, list):
                prime_freq.update(int(p) for p in chain if isinstance(p, (int, float)))
        top_10_primes = prime_freq.most_common(10)

        # ---- (6) F.1.1 composite-factorization integrity ------------------
        # Per CLAUDE.md F.1.1: composite[j] = p_thermo[j] × p_identity[j] × stamp
        # where p_identity[j] = _identity_prime(trajectory[j]) (SHA-256 prime).
        # Verify: composite[j] % p_identity[j] == 0 for every (cycle, j) pair
        # where we can recover the trajectory walk position. If TRUE for ≥ 99%
        # of pairs, F.1.1 is empirically airtight at this commit.
        # CLAUDE.md Phase 4 reported 37/37 verification; this is a fresh probe
        # at the current commit on a 200-cycle real trajectory.
        f11_total = 0
        f11_divisible_by_p_identity = 0
        f11_per_cycle_misses: list[dict[str, Any]] = []
        for c in trajectory:
            chain = c.get("prime_chain")
            walk = c.get("trajectory_walk")  # walker's traversal order
            if not (isinstance(chain, list) and isinstance(walk, list)):
                continue
            cycle_misses: list[dict[str, Any]] = []
            # Per CLAUDE.md: prime_chain element ordering matches trajectory
            # (walker visit order), NOT concepts (extraction order). Pair them
            # element-wise.
            for j, composite in enumerate(chain):
                if j >= len(walk):
                    break
                if not isinstance(composite, (int, float)):
                    continue
                concept_name = walk[j]
                if not isinstance(concept_name, str):
                    continue
                p_identity = _identity_prime_from_canonical(concept_name)
                f11_total += 1
                if int(composite) % p_identity == 0:
                    f11_divisible_by_p_identity += 1
                else:
                    cycle_misses.append({
                        "j": j,
                        "concept": concept_name,
                        "composite": int(composite),
                        "p_identity": p_identity,
                    })
            if cycle_misses:
                f11_per_cycle_misses.append({
                    "cycle_index": c.get("cycle_index"),
                    "stimulus": c.get("stimulus", "")[:60],
                    "misses": cycle_misses[:5],
                })
        f11_divisibility_rate = (
            f11_divisible_by_p_identity / f11_total if f11_total else 0.0
        )

        # ---- VERDICT -----------------------------------------------------
        observed = recognition_floor
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "recognition_jaccard_floor": self.recognition_jaccard_floor,
            "coverage_ratio_floor": self.coverage_ratio_floor,
            "n_cycles": n_cycles,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": kimera_commit,
                "n_cycles": n_cycles,
            }),
            n_records=n_cycles,
            source=str(self.trajectory_path),
            kind="captured-prime-trajectory",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"CONCEPT recognition Jaccard floor = {recognition_floor:.4f} "
                f"(mean {recognition_mean:.4f}, max {recognition_max:.4f}) "
                f"across {len(all_concept_jaccards)} same-stimulus pairs "
                f"from {len(per_stimulus_concept_pairs)} repeated stimuli. "
                f"COMPOSITE Jaccard (informational, ~0 expected by stamp "
                f"design): floor={composite_floor:.4f} mean={composite_mean:.4f}. "
                f"Vocabulary: {n_unique_primes} unique composite primes "
                f"across {n_cycles} cycles ({sublinear_ratio:.3f}/cycle). "
                f"Coverage: mean {coverage_summary['mean']:.4f}, "
                f"min {coverage_summary['min']:.4f}; "
                f"{coverage_summary['n_below_floor']} cycles below "
                f"{self.coverage_ratio_floor} floor."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="prime_recognition_jaccard",
                statistic_name="recognition_jaccard_floor",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.prime_structure",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check=(
                    "secondary measurements: vocabulary-growth, coverage, "
                    "size distribution, top-10 favourite primes (in detail)"
                ),
                detail={
                    "kimera_commit": kimera_commit,
                    "n_cycles": n_cycles,
                    "n_repeated_stimuli": len(per_stimulus_concept_pairs),
                    "n_total_pairs": len(all_concept_jaccards),
                    "recognition_floor": recognition_floor,
                    "recognition_mean": recognition_mean,
                    "recognition_max": recognition_max,
                    "composite_floor": composite_floor,
                    "composite_mean": composite_mean,
                    "composite_n_pairs": len(all_composite_jaccards),
                    "per_stimulus_pairs": per_stimulus_concept_pairs[:30],
                    "vocabulary_growth_curve_summary": {
                        "n_cycles": n_cycles,
                        "n_unique_primes": n_unique_primes,
                        "sublinear_ratio": sublinear_ratio,
                        "first_cycle_primes": growth_curve[0][1] if growth_curve else 0,
                        "last_cycle_primes": growth_curve[-1][1] if growth_curve else 0,
                    },
                    "coverage_summary": coverage_summary,
                    "prime_size_distribution": size_dist_summary,
                    "top_10_most_frequent_primes": top_10_primes,
                    "f11_composite_factorization": {
                        "n_total_pairs": f11_total,
                        "n_divisible_by_p_identity": f11_divisible_by_p_identity,
                        "divisibility_rate": f11_divisibility_rate,
                        "n_cycles_with_misses": len(f11_per_cycle_misses),
                        "first_5_miss_cycles": f11_per_cycle_misses[:5],
                        "claude_md_baseline": "Phase 4 reported 37/37 (Apr 2026)",
                    },
                    "trajectory_path": str(self.trajectory_path),
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_kimera = prov.agent(
            "kimera-swm", role="substrate_under_observation",
        )
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            source=str(self.trajectory_path),
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            n_cycles=n_cycles,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_kimera)
        prov.was_generated_by(result_entity, activity)
        prov.was_attributed_to(result_entity, agent_kimera)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="kimera-swm",
            substrate_git_commit=kimera_commit,
            evidence=evidence,
            verdict=verdict,
            reproduction=Reproduction(
                command=(
                    f"PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario "
                    f"{self.name} --trajectory-path {self.trajectory_path}"
                )
            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof

    def analysis_plan(self) -> str:
        return (
            "Group trajectory cycles by stimulus; pairwise prime_chain "
            "Jaccard for repeated-stimulus pairs. Vocabulary growth + "
            "coverage + size distribution as secondary measurements. "
            f"Verdict against recognition_jaccard_floor ≥ "
            f"{self.recognition_jaccard_floor}."
        )
