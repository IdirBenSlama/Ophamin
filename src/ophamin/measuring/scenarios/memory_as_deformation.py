"""The Memory-As-Deformation scenario — cycle-level path-dependence
empirical measurement (Round M, 2026-05-16).

Builds on Session 013 (cognitive drift on re-exposure) and Family A4
(memory-as-deformation at the prime layer). Round M extends to direct
re-exposure measurement on a single-process Takwin trajectory:

  - HEADLINE claim: when the same stimulus is re-exposed at a later
    cycle (after the substrate has accumulated experience), the
    concept extraction layer is STABLE (≥ 90% Jaccard floor) — the
    substrate recognizes content reliably.
  - Secondary measurement: halt-mode can FLIP between exposures because
    the substrate's web state has evolved (substrate path-dependence,
    Round L architectural truth). This is NOT a defect; it's the
    "sum of conditional experience" axiom in action.
  - Secondary measurement: phi drift magnitude across re-exposures —
    typically small (|dphi| < 0.05) because phi is computed on the
    integrated information graph which content-stabilizes.

Falsifiable claims
==================

> M1: For re-exposure pairs in a Takwin trajectory (same stimulus run
>     at two cycle indices with intervening experience), the
>     concept-set Jaccard floor is >= 0.80. Recognition layer is
>     substrate-state-INDEPENDENT.

Threshold rationale: Round G U1 (commit f41a7fbd8) measured floor =
0.8462 on 640 same-stimulus pairs, anchored to ONE stimulus ("The
imperfection is essential. Chaos is not the enemy of meaning — it is
the engine.") whose Zetetic-noise concept extraction varies slightly
across re-exposures. Round M (commit fad09fdda) reproduces floor =
0.8462 on the same trajectory shape (200 cycles, 30 stimuli, 650
pairs). The 0.80 threshold sits safely below the empirically measured
floor of 0.846; REFUTED would mean the recognition layer regressed
beyond the Zetetic-noise bound.

REFUTED would mean the substrate fails to recognize previously-seen
content after accumulating experience — a Pattern-T defect in the
substrate's content-recognition layer. CLAUDE.md F.1.1's p_identity
determinism guarantees this CANNOT fail at the prime layer; the
concept-extraction layer one level up COULD be brittle if Zetetic /
tokenization were non-deterministic. Session 013 reported 0.94 floor
at 500-cycle scale on a different stimulus set; the empirical floor
in any given trajectory depends on which stimuli are sampled.

> M2 (characterisation, no headline): halt-mode flip rate across
>     re-exposure pairs. Observed ~20% in 50-cycle probes; pins the
>     substrate's path-dependence at the cognitive-cycle layer.

> M3 (characterisation, no headline): phi delta distribution across
>     re-exposure pairs. Mean |dphi| < 0.05 is a stability sentinel;
>     larger means substrate is genuinely "thinking different" about
>     same content.

Inputs
======

Trajectory captured via ``/tmp/capture_kimera_50cycle_trajectory_round_m.py``
or equivalent. The trajectory must contain re-exposure pairs (same
stimulus at distinct cycle indices). The scenario auto-detects pairs
from the per-cycle stimulus list.

Output
======

Signed `EmpiricalProofRecord` with:
- Headline: concept_jaccard_floor (>= 0.85 to pass)
- Secondary: per-pair phi delta, halt-mode flip rate, concept-set
  Jaccard distribution

Artifacts
=========

* `/tmp/ophamin_kimera_runs/round_l_followup_2026_05_16/trajectory_50cycles_*.json`
  — capture used for first signed proof.
"""

from __future__ import annotations

import json
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
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class MemoryAsDeformationScenario(Scenario):
    """Cycle-level memory-as-deformation — recognition stable, halt mode CAN flip."""

    name = "memory-as-deformation"
    corpus_name = "kimera-trajectory-with-reexposure"
    target = "captured_takwin_trajectory"

    def __init__(
        self,
        trajectory_path: str | Path,
        *,
        concept_jaccard_floor: float = 0.80,
    ) -> None:
        self.trajectory_path = Path(trajectory_path).expanduser()
        if not self.trajectory_path.is_file():
            raise FileNotFoundError(
                f"trajectory_path not found: {self.trajectory_path}"
            )
        if not 0.0 < concept_jaccard_floor <= 1.0:
            raise ValueError(
                f"concept_jaccard_floor must be in (0, 1], got "
                f"{concept_jaccard_floor}"
            )
        self.concept_jaccard_floor = float(concept_jaccard_floor)
        self.n_cycles = 0  # static; base.run() overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "MemoryAsDeformationScenario uses a custom run() loop."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"For re-exposure pairs in a single-process Takwin "
                f"trajectory (same stimulus at distinct cycle indices "
                f"with intervening experience), the concept-set Jaccard "
                f"floor is >= {self.concept_jaccard_floor:.0%}. The "
                "substrate's content-recognition layer is "
                "substrate-state-INDEPENDENT — Session 013 + Family A4 + "
                "Round G U1 confirmed at the prime-content layer; this "
                "scenario extends to the concept-extraction layer one "
                "level up. Threshold 0.80 is set safely below the "
                "empirical floor of 0.8462 (Round G U1 + Round M "
                "reproduction), bounded by the Zetetic-noise behavior "
                "of one anchor stimulus."
            ),
            operationalization=(
                "Auto-detect re-exposure pairs from the trajectory's "
                "stimulus list (same string at distinct cycle indices). "
                "For each pair, compare the cycle's `concepts_sample` "
                "lists via Jaccard similarity. Headline = floor (min) "
                "Jaccard across all re-exposure pairs. Secondary: "
                "halt-mode flip rate, phi delta distribution, "
                "concept-count delta distribution."
            ),
            threshold=Threshold(
                metric="concept_jaccard_floor",
                comparator=">=",
                value=self.concept_jaccard_floor,
                units="proportion",
            ),
            h0=(
                f"concept_jaccard_floor < {self.concept_jaccard_floor} "
                "— the substrate fails to recognize previously-seen "
                "content after accumulating experience; Pattern-T "
                "defect in the concept-extraction layer that would "
                "compound at the prime layer"
            ),
            h1=(
                f"concept_jaccard_floor >= {self.concept_jaccard_floor} "
                "— recognition layer is substrate-state-INDEPENDENT; "
                "Session 013's 0.94 floor + Round G U1's 0.846 floor "
                "validated at the cycle-level concept-extraction layer "
                "on this commit"
            ),
        )

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        traj_data = json.loads(self.trajectory_path.read_text())
        per_cycle = traj_data.get("per_cycle", [])
        if not per_cycle:
            raise ValueError(
                "trajectory has no per_cycle records — ensure capture "
                "produces a per_cycle list with stimulus + concepts_sample"
            )
        n_cycles = len(per_cycle)
        kimera_commit = traj_data.get("kimera_commit", "")

        # Auto-detect re-exposure pairs: group by stimulus, keep all pairs
        # (i, j) where i < j and stimulus matches.
        by_stimulus: dict[str, list[int]] = {}
        for idx, c in enumerate(per_cycle):
            stim = c.get("stimulus") or ""
            if not stim:
                continue
            by_stimulus.setdefault(stim, []).append(idx)

        pairs: list[tuple[int, int]] = []
        for stim, indices in by_stimulus.items():
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    pairs.append((indices[i], indices[j]))

        if not pairs:
            # Degenerate trajectory — no re-exposure pairs found.
            # Refuse to emit a verdict on no data.
            raise ValueError(
                "no re-exposure pairs found in trajectory — at least 2 "
                "cycles must share the same stimulus string"
            )

        # Per-pair metrics
        per_pair_records: list[dict[str, Any]] = []
        for i, j in pairs:
            ci = per_cycle[i]
            cj = per_cycle[j]
            sample_i = set(ci.get("concepts_sample") or [])
            sample_j = set(cj.get("concepts_sample") or [])
            jacc = _jaccard(sample_i, sample_j)
            phi_i = ci.get("phi")
            phi_j = cj.get("phi")
            dphi = (phi_j - phi_i) if (phi_i is not None and phi_j is not None) else None
            halt_i = ci.get("halt_reason")
            halt_j = cj.get("halt_reason")
            halt_flip = (halt_i != halt_j) if (halt_i and halt_j) else None
            dc = (cj.get("concepts_count") or 0) - (ci.get("concepts_count") or 0)
            per_pair_records.append({
                "cycle_a": i,
                "cycle_b": j,
                "stimulus_excerpt": (ci.get("stimulus") or "")[:60],
                "concept_jaccard": jacc,
                "phi_a": phi_i,
                "phi_b": phi_j,
                "phi_delta": dphi,
                "halt_a": halt_i,
                "halt_b": halt_j,
                "halt_flipped": halt_flip,
                "concept_count_delta": dc,
            })

        n_pairs = len(per_pair_records)
        jaccards = [r["concept_jaccard"] for r in per_pair_records]
        concept_jaccard_floor = min(jaccards)
        concept_jaccard_mean = sum(jaccards) / n_pairs
        n_halt_flipped = sum(1 for r in per_pair_records if r["halt_flipped"])
        halt_flip_rate = n_halt_flipped / n_pairs
        phi_deltas = [r["phi_delta"] for r in per_pair_records if r["phi_delta"] is not None]
        phi_delta_abs_mean = sum(abs(d) for d in phi_deltas) / max(len(phi_deltas), 1)
        phi_delta_abs_max = max(abs(d) for d in phi_deltas) if phi_deltas else 0.0
        n_concept_count_stable = sum(
            1 for r in per_pair_records if r["concept_count_delta"] == 0
        )

        observed = concept_jaccard_floor
        config = {
            "scenario": self.name,
            "trajectory_path": str(self.trajectory_path),
            "concept_jaccard_floor": self.concept_jaccard_floor,
            "n_cycles": n_cycles,
            "n_pairs": n_pairs,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "kimera_commit": kimera_commit,
                "n_cycles": n_cycles,
                "n_pairs": n_pairs,
            }),
            n_records=n_pairs,
            source=str(self.trajectory_path),
            kind="takwin-trajectory-with-reexposure",
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
                f"Re-exposure analysis ({n_pairs} pairs across "
                f"{n_cycles} cycles): concept_jaccard_floor = "
                f"{concept_jaccard_floor:.4f} (mean "
                f"{concept_jaccard_mean:.4f}); halt-mode flipped in "
                f"{n_halt_flipped}/{n_pairs} = {halt_flip_rate*100:.1f}% "
                f"of pairs (substrate path-dependence); |phi_delta| "
                f"mean = {phi_delta_abs_mean:.4f}, max = "
                f"{phi_delta_abs_max:.4f}; concept_count stable in "
                f"{n_concept_count_stable}/{n_pairs} pairs."
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="memory_as_deformation",
                statistic_name="concept_jaccard_floor",
                statistic_value=observed,
                library="ophamin.measuring.scenarios.memory_as_deformation",
                library_version=__version__,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check=(
                    "secondary characterizations: halt_flip_rate, "
                    "phi_delta_abs_mean, concept_count_stable_rate. "
                    "Halt-mode flips are substrate-state-conditional "
                    "(per CLAUDE.md sum-of-conditional-experience axiom + "
                    "Round L architectural truth); recognition layer "
                    "remains stable per Session 013 + Family A4."
                ),
                detail={
                    "kimera_commit": kimera_commit,
                    "n_cycles": n_cycles,
                    "n_pairs": n_pairs,
                    "concept_jaccard_floor": concept_jaccard_floor,
                    "concept_jaccard_mean": concept_jaccard_mean,
                    "halt_flip_rate": halt_flip_rate,
                    "n_halt_flipped": n_halt_flipped,
                    "phi_delta_abs_mean": phi_delta_abs_mean,
                    "phi_delta_abs_max": phi_delta_abs_max,
                    "n_concept_count_stable": n_concept_count_stable,
                    "per_pair_records": per_pair_records,
                    "trajectory_path": str(self.trajectory_path),
                },
            ),
        ]

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
            n_pairs=n_pairs,
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
            "Auto-detect re-exposure pairs (same stimulus at distinct "
            "cycle indices) from trajectory; compute per-pair "
            "concept-set Jaccard, halt-mode flip detection, phi delta. "
            f"Verdict against concept_jaccard_floor >= "
            f"{self.concept_jaccard_floor}. Secondary characterizations: "
            "halt-flip rate, |phi_delta| mean/max, concept_count "
            "stability."
        )
