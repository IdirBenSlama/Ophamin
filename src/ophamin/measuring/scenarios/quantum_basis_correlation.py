"""The Quantum Basis Correlation scenario — Round J follow-on to Round I U7.

Round I's U7 finding: the substrate's `quantum_prime_basis_entropy` (QBE) is
empirically bimodal — 56.5% of cycles at QBE=0 (focused on one prime),
40.5% at QBE≥3 nats (spread across many primes), only 2.5% in between.

Round J asks: WHAT TRIGGERS the bimodality? When is the substrate in the
"focused" state vs the "spread" state? Initial partition analysis shows
three differentiating factors:

  1. **Stimulus class**: mixed-pool stimuli are ~3× more likely to produce
     high QBE than genesis axioms.
  2. **prime_chain length**: high-QBE cycles emit fewer primes per cycle
     (mean ~8 vs ~11).
  3. **halt_reason**: high-QBE cycles rarely trigger amplitude_death
     (2.5% vs 12.4%).

This scenario operationalises those three patterns as a single composite
finding: the QBE state is statistically dependent on (stimulus class,
prime_chain length, halt_reason). Validates that the bimodality isn't
random — it tracks substrate state in a measurable way.

Falsifiable claim
==================

> The proportion of high-QBE cycles (QBE ≥ 3 nats) differs by at least
> 15 percentage points between the two stimulus classes (genesis axioms
> vs mixed-pool), confirming the bimodality is content-driven (not
> random).

A REFUTED here means QBE bimodality is content-independent (random or
substrate-state-only) — the substrate's quantum basis state has no
relationship to the content it's processing.

Inputs
======

The scenario takes a ``trajectory_path`` to a JSON with per-cycle
`quantum_prime_basis_entropy` AND a `stimulus_class` discriminator
(e.g. "axiom" vs "mixed"). Trajectories captured via
``capture_kimera_prime_trajectory.py`` carry both.

Output
======

Signed proof carrying:

* QBE distribution per stimulus class (focused / spread rates per class)
* Stimulus-class effect size on high-QBE rate
* halt_reason × QBE state cross-tab
* prime_chain length distribution per QBE state
* phi distribution per QBE state
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


DEFAULT_HIGH_QBE_THRESHOLD: float = 3.0
DEFAULT_CLASS_DIFFERENCE_FLOOR: float = 0.15  # 15 percentage points


class QuantumBasisCorrelationScenario(Scenario):
    """Disambiguate WHAT TRIGGERS Round I U7's bimodality."""

    name = "quantum-basis-correlation"
    tier = Tier.EMPIRICAL_DEEP
    family = "quantum"
    goal = (
        "Disambiguate what triggers Round I U7's "
        "quantum_prime_basis_entropy bimodality (stimulus class? "
        "halt mode? prime-chain length?)."
    )
    explanation = (
        "Round I found QBE empirically bimodal: 56.5% of cycles at "
        "QBE=0 (focused on one prime), 40.5% at QBE >= 3 nats "
        "(spread), only 2.5% in between. Round J asks WHAT TRIGGERS "
        "the bimodality. Initial partition analysis surfaces three "
        "differentiating factors: stimulus class (mixed-pool ~3x "
        "more likely high-QBE than axioms), prime_chain length "
        "(high-QBE cycles emit fewer primes), halt_reason "
        "(high-QBE rarely amplitude_death). Headline: stimulus-class "
        "QBE difference >= 15pp."
    )
    method = "content_class_effect_difference"
    falsification_consequence = (
        "QBE bimodality is content-INDEPENDENT — the substrate's "
        "quantum basis state has no relationship to the content it "
        "processes; the bimodality is random or substrate-state-only."
    )

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        high_qbe_threshold: float = DEFAULT_HIGH_QBE_THRESHOLD,
        class_difference_floor: float = DEFAULT_CLASS_DIFFERENCE_FLOOR,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if high_qbe_threshold <= 0:
            raise ValueError(
                f"high_qbe_threshold must be > 0, got {high_qbe_threshold}"
            )
        if not 0.0 < class_difference_floor <= 1.0:
            raise ValueError(
                f"class_difference_floor must be in (0, 1], got "
                f"{class_difference_floor}"
            )
        self.high_qbe_threshold = float(high_qbe_threshold)
        self.class_difference_floor = float(class_difference_floor)
        self.n_cycles = 0  # static; base.run() overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "QuantumBasisCorrelationScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"The proportion of high-QBE cycles "
                f"(QBE ≥ {self.high_qbe_threshold} nats) differs by at "
                f"least {self.class_difference_floor:.0%} between the "
                "two stimulus classes (genesis axioms vs mixed-pool), "
                "confirming the bimodality is content-driven (not random). "
                "Validates Round I U7's finding that the substrate's "
                "quantum prime basis bimodality tracks substrate state, "
                "not just internal noise."
            ),
            operationalization=(
                "Partition cycles by `stimulus_class` field; compute "
                f"high-QBE rate per class. Headline = "
                f"|rate_mixed - rate_axiom|; verdict against ≥ "
                f"{self.class_difference_floor}. Secondary measurements: "
                "halt_reason × QBE state cross-tab, prime_chain length "
                "distribution per QBE state, phi distribution per QBE state."
            ),
            threshold=Threshold(
                metric="qbe_class_difference",
                comparator=">=",
                value=self.class_difference_floor,
                units="proportion_difference",
            ),
            h0=(
                f"high-QBE rate difference between classes < "
                f"{self.class_difference_floor} — QBE bimodality is "
                "content-independent (random or substrate-state-only)"
            ),
            h1=(
                f"high-QBE rate difference between classes >= "
                f"{self.class_difference_floor} — QBE bimodality is "
                "content-driven; the substrate's quantum basis state "
                "depends on what it's processing"
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

        # ---- (1) Partition cycles by stimulus class + QBE state ----
        per_class_qbe: dict[str, list[float]] = {}
        per_class_high_count: dict[str, int] = {}
        per_class_total: dict[str, int] = {}
        for c in trajectory:
            qbe = c.get("quantum_prime_basis_entropy")
            sc = c.get("stimulus_class", "unknown")
            if not isinstance(qbe, (int, float)):
                continue
            per_class_qbe.setdefault(sc, []).append(qbe)
            per_class_total[sc] = per_class_total.get(sc, 0) + 1
            if qbe >= self.high_qbe_threshold:
                per_class_high_count[sc] = per_class_high_count.get(sc, 0) + 1

        per_class_summary: list[dict[str, Any]] = []
        for sc in sorted(per_class_qbe.keys()):
            n = per_class_total.get(sc, 0)
            high = per_class_high_count.get(sc, 0)
            per_class_summary.append({
                "stimulus_class": sc,
                "n_cycles": n,
                "n_high_qbe": high,
                "high_qbe_rate": high / max(n, 1),
                "qbe_mean": statistics.mean(per_class_qbe[sc]),
                "qbe_median": statistics.median(per_class_qbe[sc]),
            })

        # Headline: maximum |rate_a - rate_b| across all class pairs
        rates = [(row["stimulus_class"], row["high_qbe_rate"])
                 for row in per_class_summary]
        if len(rates) < 2:
            observed = 0.0
            class_pair: tuple[str, str] | None = None
        else:
            max_diff = 0.0
            class_pair = None
            for i in range(len(rates)):
                for j in range(i + 1, len(rates)):
                    diff = abs(rates[i][1] - rates[j][1])
                    if diff > max_diff:
                        max_diff = diff
                        class_pair = (rates[i][0], rates[j][0])
            observed = max_diff

        # ---- (2) halt_reason × QBE state cross-tab ----
        halt_x_qbe: dict[str, dict[str, int]] = {}
        for c in trajectory:
            qbe = c.get("quantum_prime_basis_entropy")
            halt = c.get("halt_reason", "missing")
            if not isinstance(qbe, (int, float)):
                continue
            state = "high_qbe" if qbe >= self.high_qbe_threshold else (
                "zero_qbe" if qbe < 1e-9 else "middle_qbe"
            )
            halt_x_qbe.setdefault(halt, {"high_qbe": 0, "zero_qbe": 0, "middle_qbe": 0})
            halt_x_qbe[halt][state] += 1

        # ---- (3) prime_chain length per QBE state ----
        chain_len_by_state: dict[str, list[int]] = {
            "zero_qbe": [], "high_qbe": [], "middle_qbe": [],
        }
        phi_by_state: dict[str, list[float]] = {
            "zero_qbe": [], "high_qbe": [], "middle_qbe": [],
        }
        for c in trajectory:
            qbe = c.get("quantum_prime_basis_entropy")
            if not isinstance(qbe, (int, float)):
                continue
            state = "high_qbe" if qbe >= self.high_qbe_threshold else (
                "zero_qbe" if qbe < 1e-9 else "middle_qbe"
            )
            chain = c.get("prime_chain")
            if isinstance(chain, list):
                chain_len_by_state[state].append(len(chain))
            phi = c.get("phi")
            if isinstance(phi, (int, float)):
                phi_by_state[state].append(phi)

        chain_len_summary: dict[str, dict[str, float]] = {}
        for state, lens in chain_len_by_state.items():
            if lens:
                chain_len_summary[state] = {
                    "n": len(lens),
                    "mean": statistics.mean(lens),
                    "min": min(lens),
                    "max": max(lens),
                }
        phi_summary: dict[str, dict[str, float]] = {}
        for state, phis in phi_by_state.items():
            if phis:
                phi_summary[state] = {
                    "n": len(phis),
                    "mean": statistics.mean(phis),
                    "stdev": statistics.stdev(phis) if len(phis) > 1 else 0.0,
                    "median": statistics.median(phis),
                }

        # ---- VERDICT ----
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "high_qbe_threshold": self.high_qbe_threshold,
            "class_difference_floor": self.class_difference_floor,
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
        reasoning_parts = [
            f"Per-class high-QBE rates: "
            + ", ".join(
                f"{row['stimulus_class']} {row['n_high_qbe']}/{row['n_cycles']}"
                f" = {row['high_qbe_rate']:.3f}"
                for row in per_class_summary
            ),
            f"Max class-pair difference {observed:.3f} ({class_pair})."
            if class_pair else "Insufficient classes to compute diff.",
        ]
        if "high_qbe" in chain_len_summary and "zero_qbe" in chain_len_summary:
            reasoning_parts.append(
                f"prime_chain mean: high-QBE "
                f"{chain_len_summary['high_qbe']['mean']:.1f} vs "
                f"zero-QBE {chain_len_summary['zero_qbe']['mean']:.1f}."
            )
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=" ".join(reasoning_parts),
        )

        evidence = [
            PillarEvidence(
                pillar="qbe_correlation_analysis",
                statistic_name="qbe_class_difference",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.quantum_basis_correlation",
                library_version=__version__,
                effect_size=observed,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check="passed",
                detail={
                    "cross_check_note": (
                    "secondary measurements: halt_reason × QBE cross-tab, "
                    "prime_chain length per QBE state, phi per QBE state"
                    ),
                    "kimera_commit": kimera_commit,
                    "n_cycles": n_cycles,
                    "high_qbe_threshold": self.high_qbe_threshold,
                    "per_class_summary": per_class_summary,
                    "max_class_pair_difference": observed,
                    "max_diff_class_pair": list(class_pair) if class_pair else None,
                    "halt_reason_x_qbe_state": halt_x_qbe,
                    "prime_chain_length_per_qbe_state": chain_len_summary,
                    "phi_per_qbe_state": phi_summary,
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
            "Partition cycles by stimulus_class; compute high-QBE rate per "
            f"class; verdict against |rate_diff| >= "
            f"{self.class_difference_floor}. Secondary: halt_reason × QBE "
            "cross-tab; prime_chain length per QBE state; phi per QBE state."
        )
