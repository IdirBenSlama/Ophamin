"""The Scar-Accumulation Flow scenario — Ophamin's first mechanism-deep proof.

Where ``memory-deformation-flow`` scores on *concept recognition* (the concept
names Kimera reports — a layer above the substrate), this scenario scores on the
**physical mechanism itself**: the scar load and total deformation of the
manifold, read directly off the live substrate per cycle
(``_ymir.total_deformation()``, ``_ymir.n_scars``, ``_geoid_map[*].position_5d``,
surfaced by the entity adapter as ``raw["scar_state"]`` / ``raw["geoid_positions"]``
and extracted by ``observables.manifold_deformation`` / ``geoid_dispersion``).

It is the first **wedge exhibit** proof. The claim it tests is the substrate's
founding data principle made measurable — "we are the sum of conditional
experience; scars add, never replace; no state reset" (Kimera CLAUDE.md §4):

    □ ( for every consecutive cycle pair (i, i+1) in the trajectory:
        total_deformation_{i+1} >= total_deformation_i )

The manifold's deformation is a *cumulative physical trace*: it may only grow.
The same stimulus re-encountered later therefore sits on a strictly
more-deformed manifold than at first encounter — and the proof carries the
actual per-cycle deformation series as its evidence.

Why this is the wedge
=====================
The evidence in this proof is an artifact no LLM stack can produce: a signed,
reproducible series of the *physical* deformation a sequence of experiences left
on an owned substrate. An LLM has no persistent, inspectable, accumulating
memory to point at — it cannot show you the scar. This proof points at it, and
signs it.

Threshold — the substrate's own invariant, not invented
======================================================
``monotonic_nondecrease_fraction`` defaults to **1.0** (strict): scars are
permanent, so cumulative deformation must never decrease. ANY decrease falsifies
the no-reset principle and is a real defect (a memory leak / reset bug),
surfaced as the offending cycle pair in the evidence. Because this is the
substrate's own stated invariant (CLAUDE.md §4), the bar is anchored, not chosen
to make the proof pass. A strict invariant that holds is corroboration; one that
breaks is a critical finding — either way the deformation series is the exhibit.

Output
======
A signed ``EmpiricalProofRecord`` (scope = flow) whose evidence carries:

  * ``monotonic_nondecrease_fraction`` (primary) + the first offending pair if any
  * the full per-cycle ``total_deformation`` + ``n_scars`` + ``scar_dispersion`` +
    ``geoid_dispersion`` series — the physical trace itself
  * per-stimulus first/last/delta deformation (the cross-check: a later exposure
    must sit on a more-deformed manifold than the first — same-stimulus accumulation)
"""

from __future__ import annotations

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
from ophamin.seeing.substrate.observables import (
    geoid_dispersion,
    manifold_deformation,
)

# Kimera-vocabulary stimuli — substrate-engaging genesis concepts so the entity
# target produces a real cycle (not GWF-blocked, not trivially short). These are
# the re-exposed probes whose deformation footprint we track.
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

_EPS = 1e-9  # float-noise tolerance for the non-decrease comparison


class ScarAccumulationFlowScenario(Scenario):
    """Cumulative scar deformation never decreases across a Kimera trajectory.

    Construct with the run shape (how many unique stimuli, how many
    re-exposures each, the monotonic floor θ); call ``run(adapter)`` with a
    live :class:`KimeraAdapter` to get a signed ``EmpiricalProofRecord`` whose
    evidence is the physical deformation series. ``run()`` is fully overridden
    — this is a trajectory scenario reading mechanism state, not a
    corpus-stream scenario, so ``score()`` is unreachable.
    """

    name = "scar-accumulation-flow"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "flow"
    runner_path = "examples/run_scar_accumulation_flow.py"
    target = "entity"
    goal = (
        "Measure memory-as-deformation at the PHYSICAL mechanism: across a "
        "trajectory, the manifold's cumulative scar deformation only ever "
        "accumulates (never resets), so a re-encountered stimulus sits on a "
        "strictly more-deformed manifold than before."
    )
    explanation = (
        "Ophamin's first mechanism-deep proof — the wedge exhibit. Where "
        "memory-deformation-flow scores on concept recognition (what Kimera "
        "reports), this reads the substrate's PHYSICAL state: the live "
        "total_deformation and scar count of the manifold, per cycle. It tests "
        "the substrate's founding invariant as a flow property: "
        "ALWAYS(total_deformation_{i+1} >= total_deformation_i) — scars add, "
        "never reset (CLAUDE.md §4). The same stimulus seen again later must "
        "therefore sit on a strictly more-deformed manifold. The proof's "
        "evidence is the deformation series itself: a signed, reproducible "
        "physical trace of accumulated experience — the artifact no LLM stack "
        "can produce, because a rented model has no scar to point at."
    )
    method = "monotonic_nondecrease_of_total_deformation_over_trajectory"
    falsification_consequence = (
        "Total manifold deformation decreased at some cycle — a scar was lost "
        "or the manifold was reset, violating the substrate's permanence "
        "invariant. The offending cycle pair is named in the evidence."
    )

    def __init__(
        self,
        *,
        stimuli: tuple[str, ...] = _DEFAULT_STIMULI,
        n_exposures: int = 3,
        monotonic_floor: float = 1.0,
        min_pairs: int = 6,
        corpus_label: str = "kimera-genesis",
    ) -> None:
        if n_exposures < 2:
            raise ValueError(f"n_exposures must be >= 2, got {n_exposures}")
        if not 0.0 < monotonic_floor <= 1.0:
            raise ValueError(
                f"monotonic_floor must be in (0, 1], got {monotonic_floor}"
            )
        if not stimuli:
            raise ValueError("stimuli must be non-empty")
        self.stimuli = tuple(stimuli)
        self.n_exposures = int(n_exposures)
        self.monotonic_floor = float(monotonic_floor)
        self.min_pairs = int(min_pairs)
        self.corpus_label = str(corpus_label)
        # Static-trajectory scenario — base.run() is overridden.
        self.n_cycles = len(self.stimuli) * self.n_exposures

    # ------------------------------------------------------------- schedule --

    def build_schedule(self) -> list[tuple[int, str]]:
        """Interleaved re-exposure schedule: each stimulus appears
        ``n_exposures`` times, spaced by ``len(stimuli)`` cycles so a
        re-exposure always lands *after* intervening cycles have deformed the
        manifold (the dynamics condition). Returns ``(stimulus_index, text)``
        in cycle order.
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
                "Across a trajectory of spaced re-exposures, the manifold's "
                "cumulative scar deformation never decreases: □ (for every "
                "consecutive cycle pair (i, i+1), total_deformation_{i+1} >= "
                f"total_deformation_i). The reported metric is the fraction of "
                "consecutive pairs that hold; the invariant requires "
                f"{self.monotonic_floor:.2f}."
            ),
            operationalization=(
                "Run a schedule of len(stimuli) unique stimuli each repeated "
                f"{self.n_exposures}x and interleaved (gap = len(stimuli)) "
                "through Kimera's entity target (Takwin). Read the live "
                "manifold deformation per cycle via observables."
                "manifold_deformation (raw['scar_state'].total_deformation). "
                "monotonic_nondecrease_fraction = (# consecutive pairs with "
                "total_deformation non-decreasing) / (# pairs); the invariant "
                "holds iff fraction >= theta."
            ),
            threshold=Threshold(
                metric="monotonic_nondecrease_fraction",
                comparator=">=",
                value=self.monotonic_floor,
                units="fraction",
            ),
            h0=(
                f"H0: fraction < {self.monotonic_floor:.2f} — cumulative "
                "deformation decreased somewhere (a scar was lost / a reset "
                "occurred), violating permanence"
            ),
            h1=(
                f"H1: fraction >= {self.monotonic_floor:.2f} — deformation is "
                "monotonically non-decreasing across the whole trajectory "
                "(scars accumulate, never reset)"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Build an interleaved re-exposure schedule "
            f"({len(self.stimuli)} stimuli x {self.n_exposures} exposures, "
            f"gap = {len(self.stimuli)}); stream it through Kimera's entity "
            f"target. Per cycle, read live total_deformation + n_scars via "
            f"observables.manifold_deformation. Decide the LTL invariant: "
            f"fraction of consecutive pairs with non-decreasing "
            f"total_deformation >= {self.monotonic_floor:.2f} (eps={_EPS}). "
            f"INCONCLUSIVE if fewer than {self.min_pairs} pairs emitted a "
            f"deformation value. Cross-check (independent): each stimulus's "
            f"last-exposure deformation must exceed its first-exposure "
            f"deformation (same-stimulus accumulation). The per-cycle series, "
            f"the first violation, and the per-stimulus deltas are the action "
            f"evidence; none post-hoc-claimable."
        )

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[Any],
    ) -> ScenarioScore:
        """Never called — base.run() is overridden for trajectory control."""
        raise NotImplementedError(
            "ScarAccumulationFlowScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: object = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        """Run the re-exposure trajectory and emit a signed flow proof whose
        evidence is the physical deformation series.

        ``substrate`` must be a live adapter (e.g. ``KimeraAdapter``) — a flow
        proof has nothing to measure without a real trajectory, so a missing
        substrate is a loud failure, not a silent skip.
        """
        if substrate is None:
            raise ValueError(
                "ScarAccumulationFlowScenario.run needs a live substrate "
                "adapter (a flow proof measures a real trajectory)."
            )

        schedule = self.build_schedule()
        stimuli_text = [text for _, text in schedule]
        cycle_results = substrate.run_batch(stimuli_text)

        # --- read the physical deformation per cycle (gaps recorded, not faked) -
        series: list[dict[str, Any]] = []
        n_gap = 0
        for (idx, _text), result in zip(schedule, cycle_results):
            md = manifold_deformation(result)  # {n_scars,total_deformation,scar_dispersion} | None
            gd = geoid_dispersion(result)
            td = md.get("total_deformation") if isinstance(md, dict) else None
            if td is None:
                n_gap += 1
            series.append({
                "cycle": result.cycle_index,
                "stimulus_index": idx,
                "total_deformation": (float(td) if td is not None else None),
                "n_scars": (md.get("n_scars") if isinstance(md, dict) else None),
                "scar_dispersion": (md.get("scar_dispersion") if isinstance(md, dict) else None),
                "geoid_dispersion": gd,
            })

        # --- primary: monotonic non-decrease over cycles that emitted a value --
        td_seq = [
            (s["cycle"], s["total_deformation"])
            for s in series if s["total_deformation"] is not None
        ]
        pairs = list(zip(td_seq, td_seq[1:]))
        n_pairs = len(pairs)
        n_nondec = sum(1 for (_, a), (_, b) in pairs if b >= a - _EPS)
        frac = (n_nondec / n_pairs) if n_pairs else 0.0
        first_violation = next(
            (
                {"cycle_a": ca, "cycle_b": cb, "td_a": round(a, 6), "td_b": round(b, 6)}
                for (ca, a), (cb, b) in pairs if b < a - _EPS
            ),
            None,
        )

        # --- cross-check: same-stimulus accumulation (later >= earlier) --------
        by_stim: dict[int, list[tuple[int, float]]] = {}
        for s in series:
            if s["total_deformation"] is not None:
                by_stim.setdefault(s["stimulus_index"], []).append(
                    (s["cycle"], s["total_deformation"])
                )
        per_stimulus: list[dict[str, Any]] = []
        n_counted = 0
        n_positive = 0
        for idx, lst in by_stim.items():
            lst.sort()
            if len(lst) >= 2:
                first_td, last_td = lst[0][1], lst[-1][1]
                delta = last_td - first_td
                per_stimulus.append({
                    "stimulus_index": idx,
                    "stimulus": self.stimuli[idx][:60],
                    "first_td": round(first_td, 6),
                    "last_td": round(last_td, 6),
                    "delta": round(delta, 6),
                })
                n_counted += 1
                if delta > _EPS:
                    n_positive += 1
        cross_frac = (n_positive / n_counted) if n_counted else 0.0
        if not n_counted:
            cross_status = "skipped"
        elif n_positive == n_counted:
            cross_status = "passed"
        else:
            cross_status = "failed"

        # n_scars growth (independent corroboration of accumulation)
        n_scars_seq = [s["n_scars"] for s in series if isinstance(s["n_scars"], int)]
        n_scars_first = n_scars_seq[0] if n_scars_seq else None
        n_scars_last = n_scars_seq[-1] if n_scars_seq else None

        inconclusive = n_pairs < self.min_pairs

        # --- verdict -----------------------------------------------------------
        claim = self.build_claim()
        reasoning = (
            f"monotonic non-decrease fraction {frac:.4f} over {n_pairs} "
            f"consecutive cycle pairs ({len(self.stimuli)} stimuli x "
            f"{self.n_exposures} exposures); {n_gap} cycles emitted no "
            f"deformation value (recorded gaps)"
        )
        if first_violation is not None:
            reasoning += (
                f"; FIRST VIOLATION at cycles "
                f"{first_violation['cycle_a']}->{first_violation['cycle_b']}: "
                f"{first_violation['td_a']} -> {first_violation['td_b']} "
                "(deformation decreased — permanence broken)"
            )
        if n_scars_first is not None and n_scars_last is not None:
            reasoning += f"; n_scars {n_scars_first} -> {n_scars_last}"
        if n_counted:
            reasoning += (
                f"; cross-check: {n_positive}/{n_counted} stimuli sit on a "
                f"more-deformed manifold at last exposure than first "
                f"(same-stimulus accumulation {cross_status})"
            )
        if inconclusive:
            reasoning += (
                f"; too few pairs (<{self.min_pairs}) emitted a deformation "
                "value to decide the invariant"
            )
        verdict = Verdict.decide(
            observed=frac,
            threshold=claim.threshold,
            inconclusive=inconclusive,
            reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.flow.scar_accumulation",
                statistic_name="monotonic_nondecrease_fraction",
                statistic_value=frac,
                library="ophamin",
                library_version=__version__,
                cross_check=cross_status,
                p_value=None,
                detail={
                    "scope": "flow",
                    "flow_metric_label": "total manifold deformation",
                    "flow_unit_label": "cycle",
                    "ltl_invariant": (
                        "ALWAYS(total_deformation_{i+1} >= total_deformation_i) "
                        "over consecutive cycles"
                    ),
                    "monotonic_nondecrease_fraction": frac,
                    "n_pairs": n_pairs,
                    "n_gap_cycles": n_gap,
                    "first_violation": first_violation,
                    "n_scars_first": n_scars_first,
                    "n_scars_last": n_scars_last,
                    "same_stimulus_accumulation": {
                        "fraction_positive": round(cross_frac, 4),
                        "n_positive": n_positive,
                        "n_counted": n_counted,
                        "status": cross_status,
                        "per_stimulus": per_stimulus,
                    },
                    # The physical trace itself — the wedge artifact.
                    "deformation_series": series,
                    "threshold_anchor": (
                        "monotonic_floor=1.0 anchored to Kimera CLAUDE.md §4: "
                        "scars add, never replace; no state reset — a "
                        "permanence invariant, not an invented bar"
                    ),
                },
            ),
        ]

        # --- pre-registration --------------------------------------------------
        config = {
            "scenario": self.name,
            "scope": self.scope,
            "n_stimuli": len(self.stimuli),
            "n_exposures": self.n_exposures,
            "monotonic_floor": self.monotonic_floor,
            "schedule_len": len(schedule),
        }
        dataset = DatasetRef(
            name="kimera-scar-accumulation-trajectory",
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

        # --- provenance --------------------------------------------------------
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_kimera = prov.agent("kimera-swm", role="substrate_under_flow_test")
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            kind=dataset.kind,
        )
        activity = prov.activity(
            f"scenario:{self.name}", target=self.target, n_cycles=len(schedule)
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
