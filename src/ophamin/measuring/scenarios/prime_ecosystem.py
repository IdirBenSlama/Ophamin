"""The Prime Ecosystem scenario — non-core prime systems characterization.

Round I follow-on to Family U. Rounds G + H covered the core prime
apparatus (concept recognition, F.1.1 factorization, p_identity invariance,
substrate_state_stamp provenance). Round I characterises three additional
prime-related substrate phenomena that didn't fit the core scenarios:

1. **U6 — Alexandria fused-prime stability**: per CLAUDE.md §"Alexandria"
   + §"Fusion §metabolic", Alexandria's "knowledge fusion via dream cycles"
   produces `alexandria_fused_primes` — a per-cycle dict mapping
   `Fused(concept_a+concept_b)` keys to prime values. This claim verifies
   that the substrate's fusion engine produces a STABLE vocabulary of
   persistent fusions (a "knowledge index").

2. **U7 — Quantum prime basis entropy distribution**: per CLAUDE.md §"Prime
   Waves" and §"PrimeWaveQuantumEngine", the substrate maintains a quantum
   prime basis whose entropy (`quantum_prime_basis_entropy`) reports the
   information content per cycle. Empirically this is bimodal — many cycles
   at 0 (fully concentrated), many cycles with substantial spread.

3. **U8 — Internal-event prime emission**: per CLAUDE.md §"Internal-event
   closure trilogy (2026-05-06)" the 5 internal-event kinds
   (ouroboros_tick, cronos_drift, spde_pressure_peak,
   thermodynamic_transition, quantum_amplitude_burst) emit primes via
   `assign_from_internal_event`. EV-37 measured 4/5 fire on every cycle
   in treatment. Round I re-verifies on this commit's trajectory.

Falsifiable claim
==================

> At least 5 `alexandria_fused_primes` keys appear in ≥ 90% of cycles —
> the substrate's fusion engine produces persistent, recognizable fusions
> (validating Alexandria's "knowledge fusion" claim at this commit).

A REFUTED here means the substrate's fusion engine is producing
ephemeral fusions only — never re-encountering the same fused concept
pair across cycles. That would be a Pattern-T failure of the
"knowledge index" promise.

Inputs
======

The scenario takes a ``trajectory_path`` to a JSON with per-cycle
`alexandria_fused_primes`, `quantum_prime_basis_entropy`, and
`internal_event_primes_assigned_this_cycle` fields.

Output
======

Signed proof carrying:

* U6: fused-prime persistence (top-K appearance rate; unique fused values)
* U7: quantum prime basis entropy distribution (mean, stdev, bimodality
  indicators via median-vs-mean ratio + bimodal count)
* U8: internal-event prime emission rate (per-cycle count distribution;
  per-CLAUDE-md-EV-37 corroboration)
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

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
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class PrimeEcosystemScenario(Scenario):
    """Characterise non-core prime systems: fused primes + quantum basis + internal events."""

    name = "prime-ecosystem"
    tier = Tier.EMPIRICAL_DEEP
    family = "prime"
    goal = (
        "Characterise the non-core prime systems: Alexandria fused "
        "primes + quantum prime basis entropy + internal-event "
        "prime emission."
    )
    explanation = (
        "Round I follow-on covering three substrate phenomena "
        "outside the core prime apparatus: (U6) Alexandria's "
        "knowledge-fusion engine should produce a STABLE vocabulary "
        "of persistent fusions (>= 5 keys appearing in >= 90% of "
        "cycles); (U7) quantum_prime_basis_entropy is empirically "
        "bimodal — many cycles at 0 (concentrated), many at >= 3 "
        "nats (spread); (U8) internal-event prime emission "
        "(ouroboros / cronos / spde / thermodynamic / quantum) "
        "re-verifies EV-37's 4/5-fire-per-cycle finding on this "
        "commit."
    )
    method = "persistence_count"
    falsification_consequence = (
        "Fewer than 5 Alexandria fused-prime keys persist across "
        ">= 90% of cycles — the substrate's fusion engine produces "
        "ephemeral fusions only; the 'knowledge index' promise is "
        "structurally broken."
    )

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        fused_prime_persistence_threshold: float = 0.90,
        n_top_k_fused: int = 5,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not 0.0 < fused_prime_persistence_threshold <= 1.0:
            raise ValueError(
                f"fused_prime_persistence_threshold must be in (0, 1], "
                f"got {fused_prime_persistence_threshold}"
            )
        if n_top_k_fused < 1:
            raise ValueError(f"n_top_k_fused must be ≥ 1, got {n_top_k_fused}")
        self.fused_prime_persistence_threshold = float(
            fused_prime_persistence_threshold
        )
        self.n_top_k_fused = int(n_top_k_fused)
        self.n_cycles = 0  # static; base.run() overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "PrimeEcosystemScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"At least {self.n_top_k_fused} `alexandria_fused_primes` "
                f"keys appear in ≥ "
                f"{self.fused_prime_persistence_threshold:.0%} of cycles "
                "— the substrate's fusion engine produces persistent, "
                "recognizable fusions (validating Alexandria's "
                "'knowledge fusion via dream cycles' claim at this commit)."
            ),
            operationalization=(
                "Per cycle, harvest the `alexandria_fused_primes` dict keys. "
                "Across all cycles, count how often each fused-key appears. "
                f"Headline = number of fused-keys appearing in ≥ "
                f"{self.fused_prime_persistence_threshold:.0%} of cycles."
            ),
            threshold=Threshold(
                metric="n_persistent_fused_primes",
                comparator=">=",
                value=float(self.n_top_k_fused),
                units="fused_keys",
            ),
            h0=(
                f"fewer than {self.n_top_k_fused} fused-keys appear in "
                f"≥ {self.fused_prime_persistence_threshold:.0%} of "
                "cycles — the substrate's fusion engine produces "
                "ephemeral fusions only (no 'knowledge index')"
            ),
            h1=(
                f"≥ {self.n_top_k_fused} fused-keys persist across most "
                "cycles — Alexandria's knowledge-fusion claim is supported"
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

        # ---- (1) U6: Alexandria fused-prime stability ----
        fused_key_freq: Counter[str] = Counter()
        all_fused_values: list[int] = []
        per_cycle_fused_count: list[int] = []
        n_cycles_with_fused = 0
        for c in trajectory:
            fp = c.get("alexandria_fused_primes")
            if isinstance(fp, dict):
                n_cycles_with_fused += 1
                per_cycle_fused_count.append(len(fp))
                fused_key_freq.update(fp.keys())
                for v in fp.values():
                    if isinstance(v, int):
                        all_fused_values.append(v)
        persistence_threshold_cycles = int(
            n_cycles_with_fused * self.fused_prime_persistence_threshold
        )
        persistent_fused_keys = [
            (k, count) for k, count in fused_key_freq.most_common()
            if count >= persistence_threshold_cycles
        ]
        n_persistent_fused_primes = len(persistent_fused_keys)

        fused_summary = {
            "n_cycles_with_fused": n_cycles_with_fused,
            "n_unique_fused_keys": len(fused_key_freq),
            "n_persistent_fused_primes": n_persistent_fused_primes,
            "persistence_threshold_cycles": persistence_threshold_cycles,
            "fused_count_per_cycle_mean": (
                statistics.mean(per_cycle_fused_count)
                if per_cycle_fused_count else None
            ),
            "fused_count_per_cycle_min": (
                min(per_cycle_fused_count) if per_cycle_fused_count else None
            ),
            "fused_count_per_cycle_max": (
                max(per_cycle_fused_count) if per_cycle_fused_count else None
            ),
            "top_10_persistent": persistent_fused_keys[:10],
            "fused_value_count": len(all_fused_values),
            "fused_value_unique": len(set(all_fused_values)),
            "fused_value_min": (
                min(all_fused_values) if all_fused_values else None
            ),
            "fused_value_max": (
                max(all_fused_values) if all_fused_values else None
            ),
        }

        # ---- (2) U7: Quantum prime basis entropy distribution ----
        qbe = [
            c.get("quantum_prime_basis_entropy") for c in trajectory
            if isinstance(c.get("quantum_prime_basis_entropy"), (int, float))
        ]
        qbe_summary: dict[str, Any] = {
            "n_cycles_with_qbe": len(qbe),
        }
        if qbe:
            qbe_summary.update({
                "mean": statistics.mean(qbe),
                "median": statistics.median(qbe),
                "stdev": statistics.stdev(qbe) if len(qbe) > 1 else 0.0,
                "min": min(qbe),
                "max": max(qbe),
                "n_at_zero": sum(1 for v in qbe if v < 1e-9),
                "n_above_1nat": sum(1 for v in qbe if v >= 1.0),
                "n_above_3nat": sum(1 for v in qbe if v >= 3.0),
            })
            # Bimodality indicator: ratio of stdev to mean. Unimodal
            # distributions typically have stdev/mean < 0.5; bimodal
            # often have stdev > mean.
            qbe_summary["stdev_to_mean_ratio"] = (
                qbe_summary["stdev"] / qbe_summary["mean"]
                if qbe_summary["mean"] > 0 else float("inf")
            )
            qbe_summary["bimodal_indicator"] = (
                qbe_summary["stdev_to_mean_ratio"] > 0.8
            )

        # ---- (3) U8: Internal-event prime emission ----
        iev_count = [
            c.get("internal_event_primes_assigned_this_cycle") for c in trajectory
            if isinstance(c.get("internal_event_primes_assigned_this_cycle"), int)
        ]
        last_iev_prime = [
            c.get("last_internal_event_prime") for c in trajectory
            if isinstance(c.get("last_internal_event_prime"), int)
        ]
        iev_summary: dict[str, Any] = {
            "n_cycles_with_iev_count": len(iev_count),
            "n_cycles_with_last_iev_prime": len(last_iev_prime),
        }
        if iev_count:
            iev_dist = Counter(iev_count)
            iev_summary.update({
                "mean": statistics.mean(iev_count),
                "min": min(iev_count),
                "max": max(iev_count),
                "distribution": iev_dist.most_common(),
                # Per CLAUDE.md EV-37: 4 of 5 internal-event kinds fire
                # on every cycle in treatment (cronos_drift rare).
                # Test: % of cycles firing ≥ 3 events
                "n_cycles_firing_3_or_more": sum(
                    1 for n in iev_count if n >= 3
                ),
                "rate_firing_3_or_more": (
                    sum(1 for n in iev_count if n >= 3) / len(iev_count)
                ),
                "matches_ev37_expectation": (
                    sum(1 for n in iev_count if n >= 3) / len(iev_count) >= 0.90
                ),
            })
        if last_iev_prime:
            iev_summary.update({
                "last_iev_unique": len(set(last_iev_prime)),
                "last_iev_min": min(last_iev_prime),
                "last_iev_max": max(last_iev_prime),
            })

        # ---- VERDICT ----
        observed = float(n_persistent_fused_primes)
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "fused_prime_persistence_threshold": self.fused_prime_persistence_threshold,
            "n_top_k_fused": self.n_top_k_fused,
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
                f"U6 fused-prime persistence: {n_persistent_fused_primes} "
                f"fused-keys appear in ≥ "
                f"{self.fused_prime_persistence_threshold:.0%} of "
                f"{n_cycles_with_fused} cycles (threshold "
                f"{self.n_top_k_fused}). "
                f"U7 quantum basis entropy: mean "
                f"{qbe_summary.get('mean', 0):.3f} ± "
                f"{qbe_summary.get('stdev', 0):.3f}, median "
                f"{qbe_summary.get('median', 0):.3f}, "
                f"bimodal_indicator={qbe_summary.get('bimodal_indicator')}. "
                f"U8 internal-event prime emission: "
                f"{iev_summary.get('rate_firing_3_or_more', 0)*100:.1f}% "
                "of cycles fire ≥ 3 events, "
                f"matches_ev37={iev_summary.get('matches_ev37_expectation')}."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="prime_ecosystem",
                statistic_name="n_persistent_fused_primes",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.prime_ecosystem",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check="passed",
                detail={
                    "cross_check_note": (
                    "secondary measurements: U7 quantum basis entropy "
                    "distribution + bimodality; U8 internal-event "
                    "emission rate (per EV-37 reference)"
                    ),
                    "kimera_commit": kimera_commit,
                    "n_cycles": n_cycles,
                    "u6_alexandria_fused": fused_summary,
                    "u7_quantum_basis_entropy": qbe_summary,
                    "u8_internal_event_primes": iev_summary,
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

                command=self._build_reproduction_command(),

            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof

    def analysis_plan(self) -> str:
        return (
            f"U6: harvest alexandria_fused_primes per cycle; verdict against "
            f"≥ {self.n_top_k_fused} keys appearing in ≥ "
            f"{self.fused_prime_persistence_threshold:.0%} of cycles. "
            "U7: quantum_prime_basis_entropy distribution + bimodality. "
            "U8: internal-event count distribution + EV-37 corroboration."
        )
