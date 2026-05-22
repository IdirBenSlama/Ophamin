"""The Memory-as-Deformation Flow scenario — Ophamin's first FLOW-scope proof.

Every other scenario in Ophamin is a POINT proof: it measures one property
at one substrate state. This one is different. It measures a property of a
*trajectory* — a temporal-logic invariant that must hold across a whole run
of cycles, not at a single point. That is the L5 "Flow" scope of the
Ophamin Protocol, and it is the thing the vision-holder has said is the real
frontier:

  > Kimera is all about flow and dynamics, like biology. I've been testing
  > individually but [that misses] flow.  — owner

The property under test is **memory-as-deformation**, the substrate's
load-bearing claim (Kimera CLAUDE.md / Session 013): experience carves the
manifold, and subsequent recall *follows the reshaped curvature*. The
testable, dynamics-level signature is **recognition stability under
re-exposure**: when the same stimulus is shown again later in the
trajectory — after intervening cycles have deformed the manifold — the
substrate must still recognise it, i.e. extract substantially the same
concept set.

Temporal-logic invariant (LTL safety form)
==========================================

    □ ( for every same-stimulus re-exposure pair (i, j) in the trajectory:
        Jaccard( concepts_i , concepts_j ) ≥ θ )

"□" is ALWAYS — the invariant must hold at *every* re-exposure across the
whole run. The scenario reports the **floor** (the worst re-exposure pair)
as the primary statistic; a single violation anywhere falsifies the
invariant, which is exactly the safety-property semantics.

Threshold θ — anchored, not invented
====================================

θ defaults to **0.80**, anchored to Kimera's own documented empirical
record (the academic/industrial cross-check the owner requires):

  * Session 013 measured the recognition floor at **≥ 0.94** across
    re-exposures.
  * Round G U1 measured a worst-case floor of **0.8462** on a deliberately
    chaotic stimulus (chaos-axiom Zetetic noise); 28 of 30 stimuli held a
    perfect 1.000 floor.
  * Round M V1's calibrated hardening threshold is **0.80**.

θ = 0.80 is therefore the substrate's own documented worst-case bound, not
a number chosen to make the proof pass. A REFUTED verdict here means
recognition is collapsing under manifold deformation — a real dynamics
defect, surfaced as the per-pair series in the evidence.

Output
======

A signed ``EmpiricalProofRecord`` (scope = flow) whose evidence carries:

  * the recognition-Jaccard floor (primary) + mean across all pairs
  * the full per-re-exposure-pair series (which stimulus, which exposures,
    the Jaccard, the two concept-set sizes)
  * per-stimulus floors (which concept is least stable under re-exposure)
  * the trajectory schedule (so the run is fully reproducible)
"""

from __future__ import annotations

from itertools import combinations
from statistics import mean, median
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
from ophamin.measuring.scenarios.base import (
    DEFAULT_SIGN_KEY,
    Scenario,
    ScenarioScore,
    Tier,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest
from ophamin.seeing.substrate.observables import concept_set, jaccard

# Kimera-vocabulary stimuli — substrate-engaging genesis concepts so the
# entity target produces a real concept set per cycle (not GWF-blocked,
# not trivially short). These are the re-exposed probes.
_DEFAULT_STIMULI: tuple[str, ...] = (
    "Memory is the deformation of the spherical manifold by experience.",
    "A scar is a permanent topological deformation; it cannot be reset.",
    "The geoid accumulates semantic mass the way Earth accumulates gravity.",
    "Primes are the atoms of the substrate; meaning is indexed by a prime.",
    "The walker traverses the manifold and resolves contradiction by moving.",
    "Retrieval follows the geodesics of the reshaped manifold, not a key.",
    "The vault stores scars; recall is conditional on the manifold's shape.",
    "Resonance binds concepts whose primes share multiplicative structure.",
)


class MemoryDeformationFlowScenario(Scenario):
    """Recognition stability under re-exposure across a Kimera trajectory.

    Construct with the run shape (how many unique stimuli, how many
    re-exposures each, the recognition floor θ); call ``run(adapter)``
    with a live :class:`KimeraAdapter` to get a signed
    ``EmpiricalProofRecord``. ``run()`` is fully overridden — this is a
    trajectory scenario with a custom stimulus schedule, not a
    corpus-stream scenario, so ``score()`` is unreachable.
    """

    name = "memory-deformation-flow"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "flow"
    runner_path = "examples/run_memory_deformation_flow.py"
    target = "entity"
    goal = (
        "Test the substrate's memory-as-deformation claim as a FLOW "
        "invariant: across a trajectory with spaced re-exposures, "
        "recognition stays stable even as the manifold deforms."
    )
    explanation = (
        "Ophamin's first Flow-scope proof. Where point scenarios measure "
        "one state, this measures a temporal-logic invariant over a whole "
        "trajectory: □ (for every same-stimulus re-exposure pair, the "
        "concept-set Jaccard ≥ θ). The same stimuli are shown again after "
        "intervening cycles have deformed the manifold; if recognition "
        "holds, memory-as-deformation is working as a dynamics property, "
        "not just at a single point. θ defaults to 0.80, anchored to "
        "Kimera's documented empirical floor (Session 013 ≥0.94; Round G "
        "0.8462 worst-case; Round M V1 threshold 0.80) — not an invented "
        "bar. The floor (worst re-exposure pair) is the primary statistic; "
        "the per-pair series is the action signal."
    )
    method = "recognition_jaccard_floor_over_trajectory"
    falsification_consequence = (
        "Recognition collapses under manifold deformation — the substrate "
        "stops recognising a stimulus it saw earlier in the same run. The "
        "per-pair series names which concept destabilised and when."
    )

    def __init__(
        self,
        *,
        stimuli: tuple[str, ...] = _DEFAULT_STIMULI,
        n_exposures: int = 3,
        recognition_floor: float = 0.80,
        min_pairs: int = 6,
        corpus_label: str = "kimera-genesis",
    ) -> None:
        if n_exposures < 2:
            raise ValueError(f"n_exposures must be >= 2, got {n_exposures}")
        if not 0.0 < recognition_floor <= 1.0:
            raise ValueError(
                f"recognition_floor must be in (0, 1], got {recognition_floor}"
            )
        if not stimuli:
            raise ValueError("stimuli must be non-empty")
        self.stimuli = tuple(stimuli)
        self.n_exposures = int(n_exposures)
        self.recognition_floor = float(recognition_floor)
        self.min_pairs = int(min_pairs)
        # Where the stimuli came from — lets the Flow surface distinguish a
        # run on curated Kimera vocabulary from one on a real corpus.
        self.corpus_label = str(corpus_label)
        # Static-trajectory scenario — base.run() is overridden.
        self.n_cycles = len(self.stimuli) * self.n_exposures

    # ------------------------------------------------------------- schedule --

    def build_schedule(self) -> list[tuple[int, str]]:
        """Interleaved re-exposure schedule: each stimulus appears
        ``n_exposures`` times, spaced by ``len(stimuli)`` cycles so a
        re-exposure always lands *after* intervening cycles have deformed
        the manifold (the dynamics condition).

        Returns a list of ``(stimulus_index, text)`` in cycle order.
        """
        schedule: list[tuple[int, str]] = []
        for _ in range(self.n_exposures):
            for idx, text in enumerate(self.stimuli):
                schedule.append((idx, text))
        return schedule

    # ---------------------------------------------------------------- claim --

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "Across a trajectory with spaced re-exposures, the substrate "
                "keeps recognising every re-exposed stimulus: □ (for every "
                "same-stimulus re-exposure pair (i, j) in the trajectory, "
                "Jaccard(concepts_i, concepts_j) ≥ "
                f"{self.recognition_floor:.2f}). The reported floor is the "
                "worst pair across the whole run."
            ),
            operationalization=(
                "Run a schedule of len(stimuli) unique stimuli each repeated "
                f"{self.n_exposures}× and interleaved (gap = len(stimuli)) "
                "through Kimera's entity target (Takwin). For each stimulus, "
                "take the per-cycle ``concepts`` set at each exposure and "
                "compute Jaccard over all exposure pairs. "
                "recognition_jaccard_floor = min over all pairs across all "
                "stimuli; the LTL □ invariant holds iff floor ≥ θ."
            ),
            threshold=Threshold(
                metric="recognition_jaccard_floor",
                comparator=">=",
                value=self.recognition_floor,
                units="jaccard",
            ),
            h0=(
                f"H0: floor < {self.recognition_floor:.2f} — recognition "
                "collapses under manifold deformation somewhere in the run"
            ),
            h1=(
                f"H1: floor ≥ {self.recognition_floor:.2f} — recognition is "
                "stable across the whole trajectory (memory-as-deformation "
                "holds as a flow property)"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Build an interleaved re-exposure schedule "
            f"({len(self.stimuli)} stimuli × {self.n_exposures} exposures, "
            f"gap = {len(self.stimuli)}); stream it through Kimera's entity "
            f"target. Per stimulus, compute Jaccard of the per-cycle concept "
            f"set across all exposure pairs. Decide the LTL □ invariant: "
            f"floor (min Jaccard over all pairs) ≥ {self.recognition_floor:.2f}. "
            f"INCONCLUSIVE if fewer than {self.min_pairs} valid pairs were "
            f"measured. Per-pair series + per-stimulus floors are the "
            f"action evidence; none post-hoc-claimable."
        )

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[Any],
    ) -> ScenarioScore:
        """Never called — base.run() is overridden for trajectory control."""
        raise NotImplementedError(
            "MemoryDeformationFlowScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    # ----------------------------------------------------------- extraction --
    # Canonical extractors live in ophamin.seeing.substrate.observables; these
    # staticmethods delegate so the importers (memory-cued-recall-flow,
    # memory-permanence-flow) all share the single implementation.
    _concept_set = staticmethod(concept_set)
    _jaccard = staticmethod(jaccard)

    @classmethod
    def _control_crosscheck(
        cls,
        by_stimulus: dict[int, list[tuple[int, "frozenset[str] | None"]]],
        same_jaccards: list[float],
    ) -> dict[str, Any]:
        """Negative control: same-stimulus vs cross-stimulus Jaccard.

        Builds the cross-stimulus Jaccard distribution (pairs of concept sets
        from DIFFERENT stimuli) and tests, with scipy's Mann-Whitney U
        (one-sided, same > cross), whether recognition is a real signal or
        just generic similarity. Returns the control stats + a pass/fail.
        """
        from itertools import combinations as _comb

        # All valid (stimulus_idx, concept_set), then cross-stimulus pairs.
        items: list[tuple[int, frozenset[str]]] = []
        for idx, exposures in by_stimulus.items():
            for _ci, cs in exposures:
                if cs is not None:
                    items.append((idx, cs))
        cross: list[float] = [
            cls._jaccard(a, b)
            for (ia, a), (ib, b) in _comb(items, 2) if ia != ib
        ]

        out: dict[str, Any] = {
            "control": "same_stimulus_vs_cross_stimulus_jaccard",
            "n_same": len(same_jaccards),
            "n_cross": len(cross),
            "same_median": round(median(same_jaccards), 6) if same_jaccards else 0.0,
            "cross_median": round(median(cross), 6) if cross else 0.0,
        }
        if len(same_jaccards) < 3 or len(cross) < 3:
            out.update({"status": "skipped", "reason": "too few pairs for a test",
                        "p_value": None, "mannwhitney_u": None,
                        "cl_effect_size": None, "recognition_significant": False})
            return out
        try:
            from scipy.stats import mannwhitneyu
            u, p = mannwhitneyu(same_jaccards, cross, alternative="greater")
            cl = float(u) / (len(same_jaccards) * len(cross))  # P(same > cross)
            significant = (p < 0.05) and (out["same_median"] > out["cross_median"])
            out.update({
                "status": "passed" if significant else "failed",
                "mannwhitney_u": float(u),
                "p_value": float(p),
                "cl_effect_size": round(cl, 4),   # common-language: P(same>cross)
                "recognition_significant": bool(significant),
                "library": "scipy",
            })
        except Exception as exc:  # noqa: BLE001 — control is best-effort
            out.update({"status": "skipped", "reason": f"scipy: {exc}",
                        "p_value": None, "mannwhitney_u": None,
                        "cl_effect_size": None, "recognition_significant": False})
        return out

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        """Run the re-exposure trajectory and emit a signed flow proof.

        ``substrate`` must be a live adapter (e.g. ``KimeraAdapter``) — a
        flow proof has nothing to measure without a real trajectory, so a
        missing substrate is a loud failure, not a silent skip.
        """
        if substrate is None:
            raise ValueError(
                "MemoryDeformationFlowScenario.run needs a live substrate "
                "adapter (a flow proof measures a real trajectory)."
            )

        schedule = self.build_schedule()
        stimuli_text = [text for _, text in schedule]
        cycle_results = substrate.run_batch(stimuli_text)

        # Group concept sets by stimulus index, preserving exposure order.
        by_stimulus: dict[int, list[tuple[int, frozenset[str] | None]]] = {
            i: [] for i in range(len(self.stimuli))
        }
        n_failed = 0
        for (idx, _text), result in zip(schedule, cycle_results):
            cs = self._concept_set(result)
            if cs is None:
                n_failed += 1
            by_stimulus[idx].append((result.cycle_index, cs))

        # Compute Jaccard over all exposure pairs per stimulus.
        pair_series: list[dict[str, Any]] = []
        per_stimulus_floor: dict[int, float] = {}
        all_jaccards: list[float] = []
        for idx, exposures in by_stimulus.items():
            valid = [(ci, cs) for ci, cs in exposures if cs is not None]
            stim_jaccards: list[float] = []
            for (ci_a, cs_a), (ci_b, cs_b) in combinations(valid, 2):
                j = self._jaccard(cs_a, cs_b)
                stim_jaccards.append(j)
                all_jaccards.append(j)
                pair_series.append({
                    "stimulus_index": idx,
                    "stimulus": self.stimuli[idx][:60],
                    "cycle_a": ci_a,
                    "cycle_b": ci_b,
                    "jaccard": round(j, 6),
                    "n_concepts_a": len(cs_a),
                    "n_concepts_b": len(cs_b),
                })
            if stim_jaccards:
                per_stimulus_floor[idx] = min(stim_jaccards)

        n_pairs = len(all_jaccards)
        floor = min(all_jaccards) if all_jaccards else 0.0
        mean_j = mean(all_jaccards) if all_jaccards else 0.0
        inconclusive = n_pairs < self.min_pairs

        # Identify the worst pair (the LTL counterexample, if any).
        worst = min(
            pair_series, key=lambda p: p["jaccard"], default=None
        ) if pair_series else None

        # --- NEGATIVE CONTROL + significance (the cross-check) -------------
        # Recognition is only "real" if same-stimulus re-exposure similarity
        # is significantly HIGHER than the similarity between DIFFERENT
        # stimuli. Otherwise a high Jaccard could just mean "all text looks
        # alike" (the lexical-overlap confound). We compute the cross-stimulus
        # Jaccard distribution and test same > cross with Mann-Whitney U
        # (scipy — an independent, standard library), with a common-language
        # effect size. This is what makes the verdict trustworthy.
        control = self._control_crosscheck(by_stimulus, all_jaccards)

        # PRE-REGISTRATION
        config = {
            "scenario": self.name,
            "scope": self.scope,
            "n_stimuli": len(self.stimuli),
            "n_exposures": self.n_exposures,
            "recognition_floor": self.recognition_floor,
            "schedule_len": len(schedule),
        }
        dataset = DatasetRef(
            name="kimera-memory-deformation-trajectory",
            content_hash=content_hash({"schedule": stimuli_text}),
            n_records=len(schedule),
            source=getattr(substrate, "name", "kimera-swm"),
            kind="substrate-trajectory+reexposure",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        reasoning = (
            f"recognition floor {floor:.4f} over {n_pairs} re-exposure pairs "
            f"({len(self.stimuli)} stimuli × {self.n_exposures} exposures); "
            f"mean Jaccard {mean_j:.4f}; {n_failed} exposures produced no "
            f"concept set"
        )
        if worst is not None:
            reasoning += (
                f"; worst pair: stimulus {worst['stimulus_index']} "
                f"cycles {worst['cycle_a']}↔{worst['cycle_b']} = "
                f"{worst['jaccard']:.4f}"
            )
        if control.get("p_value") is not None:
            reasoning += (
                f"; control: same-stimulus median {control['same_median']:.3f} vs "
                f"cross-stimulus median {control['cross_median']:.3f}, "
                f"Mann-Whitney p={control['p_value']:.2g} "
                f"(recognition {'IS' if control['recognition_significant'] else 'NOT'} "
                f"significantly above the cross-stimulus baseline)"
            )
        if inconclusive:
            reasoning += (
                f"; too few valid pairs (<{self.min_pairs}) to decide the "
                "invariant"
            )
        verdict = Verdict.decide(
            observed=floor,
            threshold=claim.threshold,
            inconclusive=inconclusive,
            reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.flow.recognition_stability",
                statistic_name="recognition_jaccard_floor",
                statistic_value=floor,
                library="ophamin",
                library_version=__version__,
                # The cross-check is the negative control: did same-stimulus
                # recognition test SIGNIFICANTLY above the cross-stimulus
                # baseline? passed / failed / skipped (too few pairs).
                cross_check=control.get("status", "skipped"),
                p_value=control.get("p_value"),
                detail={
                    "scope": "flow",
                    "flow_metric_label": "recognition Jaccard",
                    "flow_unit_label": "stimulus",
                    "flow_corpus_label": self.corpus_label,
                    "ltl_invariant": (
                        "ALWAYS(jaccard(concepts_i, concepts_j) >= theta) "
                        "over same-stimulus re-exposure pairs"
                    ),
                    "control": control,
                    "recognition_jaccard_mean": mean_j,
                    "n_pairs": n_pairs,
                    "n_stimuli": len(self.stimuli),
                    "n_exposures": self.n_exposures,
                    "n_failed_exposures": n_failed,
                    "schedule_len": len(schedule),
                    "per_stimulus_floor": {
                        str(k): v for k, v in per_stimulus_floor.items()
                    },
                    "worst_pair": worst,
                    "pair_series": pair_series,
                    "threshold_anchor": (
                        "theta=0.80 anchored to Kimera empirical record: "
                        "Session 013 floor >=0.94; Round G U1 worst 0.8462; "
                        "Round M V1 threshold 0.80"
                    ),
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_kimera = prov.agent(
            "kimera-swm", role="substrate_under_flow_test",
        )
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            kind=dataset.kind,
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            n_cycles=len(schedule),
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_kimera)
        prov.was_generated_by(result_entity, activity)
        prov.was_attributed_to(result_entity, agent_kimera)
        prov.was_derived_from(result_entity, data_entity)

        substrate_commit = ""
        getter = getattr(substrate, "git_commit", None)
        if callable(getter):
            try:
                substrate_commit = str(getter() or "")[:12]
            except Exception:  # noqa: BLE001 — provenance is best-effort
                substrate_commit = ""

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name=getattr(substrate, "name", "kimera-swm"),
            substrate_git_commit=substrate_commit,
            evidence=evidence,
            verdict=verdict,
            reproduction=Reproduction(command=self._build_reproduction_command()),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof
