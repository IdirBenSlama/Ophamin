"""The Phi-Stability Flow scenario — Ophamin's second FLOW-scope proof.

Where ``memory-deformation-flow`` tests *what* the substrate recalls across
a trajectory, this tests whether the substrate stays *cognitively alive*
across one. Φ (phi) is Kimera's integrated-information signal — the IIT
measure the cycle reports as ``phi``. A healthy cognitive substrate should
keep Φ in a coherent operating band under sustained load; if Φ collapses to
zero somewhere in the run, the substrate went cognitively dark on that
cycle.

Temporal-logic invariant (LTL safety form)
==========================================

    □ ( for every cycle in the sustained-load trajectory:  Φ ≥ φ_floor )

"□" is ALWAYS — the substrate must keep integrated information above the
collapse floor at *every* cycle of the run, not just on average. A single
collapse falsifies the invariant; the worst cycle is the counterexample.

Threshold φ_floor — anchored, not invented
==========================================

φ_floor defaults to **0.05**, a conservative non-collapse bar anchored to
Kimera's own Φ record:

  * Round M V1 measured Φ essentially stable across re-exposures
    (|ΔΦ| ≈ 0.002).
  * Round E/F measured Φ ≈ 0.33 (mixed pool) and 0.48–0.62 (genesis
    axioms) for substantive stimuli; Family L measured Φ across the corpus.

Substantive stimuli cluster Φ in roughly [0.2, 0.8]; 0.05 is therefore well
below the observed operating range — it is the "is the substrate alive at
all" bar, not a performance target. A REFUTED verdict means Φ collapsed
below 0.05 somewhere in the run — a real dynamics defect, surfaced as the
worst cycle.

The descriptive evidence (band: min/max/mean/stdev, per-pass mean to expose
degradation across passes, the full per-cycle Φ series) is reported but not
pre-registered.

Output — generic flow shape
===========================

This proof emits the *generic* flow-evidence keys (``flow_metric_label``,
``flow_unit_label``, ``flow_mean``, ``per_stimulus_floor``, ``worst_unit``)
so the Console Flow screen renders it with no scenario-specific code — the
Flow scope is extensible: subsequent flow proofs follow the same shape.
"""

from __future__ import annotations

from pathlib import Path
from statistics import mean, pstdev
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
from ophamin.measuring.scenarios.memory_deformation_flow import _DEFAULT_STIMULI
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class PhiStabilityFlowScenario(Scenario):
    """Φ-non-collapse under sustained load across a Kimera trajectory.

    Construct with the run shape (stimuli, how many passes, the Φ floor);
    call ``run(adapter)`` with a live :class:`KimeraAdapter` to get a signed
    ``EmpiricalProofRecord``. ``run()`` is fully overridden — trajectory
    scenario — so ``score()`` is unreachable.
    """

    name = "phi-stability-flow"
    tier = Tier.SCIENTIFIC
    family = "phi"
    scope = "flow"
    runner_path = "examples/run_phi_stability_flow.py"
    target = "entity"
    goal = (
        "Test whether the substrate stays cognitively alive under sustained "
        "load: Φ (integrated information) never collapses below a floor "
        "across the whole trajectory."
    )
    explanation = (
        "Ophamin's second Flow-scope proof. memory-deformation-flow tests "
        "WHAT the substrate recalls; this tests whether it stays "
        "cognitively alive. Φ is Kimera's IIT integrated-information signal. "
        "The LTL invariant is □ (Φ ≥ φ_floor) over the sustained-load run, "
        "measured on REAL-INPUT cycles only: a cycle that produced no "
        "concept set has nothing to integrate, so Φ=0 there is correct, not "
        "a defect — those cycles are excluded from the floor and their rate "
        "reported as empty_input_rate (with phi_floor_strict, the "
        "over-all-cycles floor, kept as a canary). This refinement followed "
        "the linux/cyber refutations, where Φ=0 collapses correlated exactly "
        "with concept-extraction gaps. φ_floor defaults to 0.05, anchored to "
        "Kimera's record (substantive stimuli cluster Φ in ~[0.2, 0.8]; "
        "Round M Φ essentially stable) — the 'alive at all' bar, not a "
        "performance target. The worst real cycle is the counterexample."
    )
    method = "phi_floor_over_trajectory"
    falsification_consequence = (
        "Φ collapsed below the floor somewhere in the run — the substrate "
        "went cognitively dark on at least one cycle under sustained load."
    )

    def __init__(
        self,
        *,
        stimuli: tuple[str, ...] = _DEFAULT_STIMULI,
        n_passes: int = 3,
        phi_floor: float = 0.05,
        min_cycles: int = 6,
        corpus_label: str = "kimera-genesis",
    ) -> None:
        if n_passes < 1:
            raise ValueError(f"n_passes must be >= 1, got {n_passes}")
        if not 0.0 < phi_floor <= 1.0:
            raise ValueError(f"phi_floor must be in (0, 1], got {phi_floor}")
        if not stimuli:
            raise ValueError("stimuli must be non-empty")
        self.stimuli = tuple(stimuli)
        self.n_passes = int(n_passes)
        self.phi_floor = float(phi_floor)
        self.min_cycles = int(min_cycles)
        self.corpus_label = str(corpus_label)
        self.n_cycles = len(self.stimuli) * self.n_passes

    # ------------------------------------------------------------- schedule --

    def build_schedule(self) -> list[tuple[int, str]]:
        """Sustained-load schedule: ``n_passes`` passes over the stimuli."""
        schedule: list[tuple[int, str]] = []
        for _ in range(self.n_passes):
            for idx, text in enumerate(self.stimuli):
                schedule.append((idx, text))
        return schedule

    # ---------------------------------------------------------------- claim --

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "Under sustained load, the substrate stays cognitively alive "
                "on real input: □ (for every cycle that produced a concept "
                f"set, Φ ≥ {self.phi_floor:.2f}). Empty-concept cycles are "
                "excluded — with nothing to integrate, Φ=0 is correct, not a "
                "defect; their rate is reported separately. The floor is the "
                "lowest-Φ real-input cycle across the run."
            ),
            operationalization=(
                f"Stream {self.n_passes} passes over {len(self.stimuli)} "
                "substantive stimuli through Kimera's entity target (Takwin); "
                "read the per-cycle ``phi`` and ``concepts``. Partition cycles "
                "into real-input (concepts non-empty) and empty-input. "
                "phi_floor = min Φ over real-input cycles; the LTL □ invariant "
                "holds iff that floor ≥ φ_floor. empty_input_rate and the "
                "over-all-cycles phi_floor_strict are reported alongside."
            ),
            threshold=Threshold(
                metric="phi_floor",
                comparator=">=",
                value=self.phi_floor,
                units="phi",
            ),
            h0=(
                f"H0: min Φ < {self.phi_floor:.2f} on real-input cycles — Φ "
                "collapses below the floor despite the input producing concepts"
            ),
            h1=(
                f"H1: min Φ ≥ {self.phi_floor:.2f} on real-input cycles — the "
                "substrate stays cognitively alive whenever it has something "
                "to integrate"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Build a sustained-load schedule ({self.n_passes} passes over "
            f"{len(self.stimuli)} stimuli = {self.n_cycles} cycles); stream "
            f"it through Kimera's entity target. Read per-cycle Φ + concepts; "
            f"partition into real-input vs empty-input cycles. Decide the LTL "
            f"□ invariant on real-input cycles: min Φ ≥ {self.phi_floor:.2f}. "
            f"Report empty_input_rate + phi_floor_strict (over all cycles) "
            f"alongside. INCONCLUSIVE if fewer than {self.min_cycles} "
            f"real-input cycles. The Φ band, per-pass means, and per-cycle Φ "
            f"series are descriptive; none post-hoc-claimable."
        )

    def score(
        self, cycle_results: list[CycleResult], records: list[Any],
    ) -> ScenarioScore:
        """Never called — base.run() is overridden for trajectory control."""
        raise NotImplementedError(
            "PhiStabilityFlowScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    # ----------------------------------------------------------- extraction --

    @staticmethod
    def _phi(result: CycleResult) -> float | None:
        """Per-cycle Φ, or None when the cycle failed / exposed no Φ."""
        if not result.success:
            return None
        raw = result.raw or {}
        v = raw.get("phi")
        if not isinstance(v, (int, float)):
            return None
        return float(v)

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        if substrate is None:
            raise ValueError(
                "PhiStabilityFlowScenario.run needs a live substrate adapter "
                "(a flow proof measures a real trajectory)."
            )

        schedule = self.build_schedule()
        stimuli_text = [text for _, text in schedule]
        cycle_results = substrate.run_batch(stimuli_text)

        # Collect Φ per cycle, grouped by stimulus + by pass.
        #
        # Refined invariant (since the linux/cyber refutations): a cycle that
        # produced NO concept set has nothing to integrate, so Φ=0 is correct
        # behaviour, not a substrate defect. We therefore measure the floor
        # over *real-input* cycles (concepts non-empty) and report the
        # empty-input rate separately. ``phi_floor_strict`` keeps the old
        # over-all-cycles floor as a canary in the evidence.
        phi_real: list[float] = []      # Φ on cycles that produced concepts
        phi_all: list[float] = []       # Φ on every cycle that returned a Φ
        n_failed = 0                    # cycle failed entirely (no Φ)
        n_empty_input = 0               # cycle ran but produced no concepts
        per_stimulus: dict[int, list[float]] = {
            i: [] for i in range(len(self.stimuli))
        }
        phi_series: list[dict[str, Any]] = []
        worst_unit: dict[str, Any] | None = None
        for pos, ((idx, _text), result) in enumerate(zip(schedule, cycle_results)):
            phi = self._phi(result)
            if phi is None:
                n_failed += 1
                continue
            phi_all.append(phi)
            raw = result.raw or {}
            concepts = raw.get("concepts")
            has_concepts = isinstance(concepts, list) and len(concepts) > 0
            pass_i = pos // len(self.stimuli)
            phi_series.append({
                "cycle": result.cycle_index,
                "pass": pass_i,
                "stimulus_index": idx,
                "phi": round(phi, 6),
                "empty_input": not has_concepts,
            })
            if not has_concepts:
                n_empty_input += 1
                continue
            phi_real.append(phi)
            per_stimulus[idx].append(phi)
            if worst_unit is None or phi < worst_unit["value"]:
                worst_unit = {
                    "stimulus_index": idx,
                    "cycle": result.cycle_index,
                    "pass": pass_i,
                    "value": round(phi, 6),
                }

        n_measured = len(phi_real)
        n_returned = len(phi_all)
        floor = min(phi_real) if phi_real else 0.0
        phi_mean = mean(phi_real) if phi_real else 0.0
        phi_max = max(phi_real) if phi_real else 0.0
        phi_std = pstdev(phi_real) if len(phi_real) > 1 else 0.0
        phi_floor_strict = min(phi_all) if phi_all else 0.0
        non_collapse_rate = (
            sum(1 for v in phi_real if v >= self.phi_floor) / n_measured
            if n_measured else 0.0
        )
        empty_input_rate = (n_empty_input / n_returned) if n_returned else 0.0
        per_stimulus_floor = {
            str(i): min(vals) for i, vals in per_stimulus.items() if vals
        }
        # per-pass mean Φ over real-input cycles — exposes degradation under
        # sustained load.
        per_pass: dict[int, list[float]] = {}
        for pt in phi_series:
            if pt.get("empty_input"):
                continue
            per_pass.setdefault(pt["pass"], []).append(pt["phi"])
        per_pass_mean = {
            str(p): round(mean(v), 6) for p, v in sorted(per_pass.items())
        }
        inconclusive = n_measured < self.min_cycles

        # PRE-REGISTRATION
        config = {
            "scenario": self.name,
            "scope": self.scope,
            "n_stimuli": len(self.stimuli),
            "n_passes": self.n_passes,
            "phi_floor": self.phi_floor,
            "schedule_len": len(schedule),
        }
        dataset = DatasetRef(
            name="kimera-phi-stability-trajectory",
            content_hash=content_hash({"schedule": stimuli_text}),
            n_records=len(schedule),
            source=getattr(substrate, "name", "kimera-swm"),
            kind="substrate-trajectory+sustained-load",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        reasoning = (
            f"Φ floor {floor:.4f} over {n_measured} real-input cycles "
            f"({self.n_passes} passes × {len(self.stimuli)} stimuli); "
            f"mean Φ {phi_mean:.4f}, band [{floor:.4f}, {phi_max:.4f}], "
            f"stdev {phi_std:.4f}; non-collapse rate {non_collapse_rate:.1%}; "
            f"{n_empty_input} empty-input cycles excluded "
            f"({empty_input_rate:.1%}; strict floor over all cycles "
            f"{phi_floor_strict:.4f}); {n_failed} cycles produced no Φ"
        )
        if worst_unit is not None:
            reasoning += (
                f"; worst real cycle: stimulus {worst_unit['stimulus_index']} "
                f"@ cycle {worst_unit['cycle']} = {worst_unit['value']:.4f}"
            )
        if inconclusive:
            reasoning += (
                f"; too few real-input cycles (<{self.min_cycles}) to decide"
            )
        verdict = Verdict.decide(
            observed=floor,
            threshold=claim.threshold,
            inconclusive=inconclusive,
            reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.flow.phi_stability",
                statistic_name="phi_floor",
                statistic_value=floor,
                library="ophamin",
                library_version=__version__,
                cross_check="n/a",
                detail={
                    "scope": "flow",
                    "flow_metric_label": "Φ (integrated information)",
                    "flow_unit_label": "stimulus",
                    "flow_corpus_label": self.corpus_label,
                    "flow_mean": phi_mean,
                    "ltl_invariant": (
                        "ALWAYS(phi >= phi_floor) over real-input cycles "
                        "(empty-concept cycles excluded — Φ=0 there is "
                        "correct, not a defect)"
                    ),
                    "phi_min": floor,
                    "phi_max": phi_max,
                    "phi_stdev": phi_std,
                    "phi_floor_strict": phi_floor_strict,
                    "non_collapse_rate": non_collapse_rate,
                    "empty_input_cycles": n_empty_input,
                    "empty_input_rate": empty_input_rate,
                    "n_measured": n_measured,
                    "n_returned": n_returned,
                    "n_passes": self.n_passes,
                    "n_stimuli": len(self.stimuli),
                    "n_failed_cycles": n_failed,
                    "schedule_len": len(schedule),
                    "per_stimulus_floor": per_stimulus_floor,
                    "per_pass_mean": per_pass_mean,
                    "worst_unit": worst_unit,
                    "phi_series": phi_series,
                    "threshold_anchor": (
                        "phi_floor=0.05 anchored to Kimera record: "
                        "substantive stimuli cluster Φ in ~[0.2, 0.8]; "
                        "Round M Φ essentially stable; Family L Φ corpus"
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
