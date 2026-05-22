"""The Memory-Permanence Flow scenario — measure the MEMORY ITSELF, not recognition.

Owner correction (2026-05-22): *"Kimera SWM is the Memory itself, the scars,
the S4 manifold is the memory."* Every prior memory scenario in Ophamin
(``memory-deformation-flow``, ``memory-as-deformation``,
``memory-cued-recall-flow``, ``memory-horizon-flow``) leads with the
**concept-set layer** — same stimulus in, do the same concepts come out. But
that layer is *recognition*, and recognition is content-deterministic **by
design** (Session 013: "Recognition is preserved... Cognition drifts").
Measuring it answers "does the substrate recognise text it has seen", which a
1M-token LLM also passes. It does **not** measure memory.

The memory is the **scars and the S⁴ manifold deformation** — the permanent,
accumulating, path-shaping substrate. This scenario measures that directly, by
reading Kimera's own memory accumulators off ``OrchestratorResult`` (verified
field names, 2026-05-22 live probe):

  * ``vault_stats.total_scars_stored`` — the canonical permanent scar count
    (= ``vault_a.scar_count + vault_b.scar_count``; append-only by the
    SphericalMemoryVault ``monotonic_violations`` invariant: *a scar cannot be
    reset*).
  * ``arachne_web_coupling_frobenius`` — the manifold's coupling deformation.
  * ``alexandria_knowledge_mass_cumulative`` — cumulative semantic mass.
  * ``hypertree_total_nodes`` — structural growth of the memory graph.

The decisive memory-vs-re-derivation discriminator
==================================================

A stateless re-deriver re-exposed to byte-identical, perfectly-recognised
input is in an **identical** state every time. Kimera re-exposed to the same
input is in a **strictly deeper** state every time — more permanent scars, a
more-deformed manifold — *while still recognising the input perfectly*. That
**dissociation** (recognition held constant; substrate permanently deeper) is
the textbook signature of path-dependent memory, and it is impossible for a
stateless recompute.

The live probe that motivated this design (P re-exposed at cycles 0, 2, 4):
``phi`` was rigid (0.7023 → 0.7023 → 0.7023) and recognition Jaccard was
1.0000 — yet ``total_scars_stored`` went 1 → 3 → 5 and
``arachne_web_coupling_frobenius`` went 1.29 → 1.56 → 1.96. The memory is in
the scars and the manifold, NOT in a Φ drift. A Φ-drift proof would have
returned INCONCLUSIVE on this content; this one returns VALIDATED on exactly
the layer the owner named.

Pre-registered headline metric
==============================

    memory_path_dependence
      = ( # same-stimulus re-exposure transitions that are RECOGNISED
          AND land on a strictly-deeper manifold (Δ permanent-scars > 0) )
      / ( # recognised same-stimulus re-exposure transitions )

Decided VALIDATED iff ``memory_path_dependence ≥ 1.0`` (every re-exposure of a
recognised probe lands on strictly more permanent scars) AND the whole-run
scar count is monotonic non-decreasing (no scar was ever reset). A scar reset
anywhere forces the observed value to 0.0 → REFUTED: the substrate's defining
invariant ("a scar cannot be reset") would have broken.

Supporting cross-check (scipy Spearman): does scar depth at re-exposure rise
with exposure ordinal? ρ > 0, p < 0.05 confirms memory deepens with
experience — a real statistical signal, not theatre (accumulation is
deterministic, so the *test* is on the ordinal trend, which is the meaningful
claim).
"""

from __future__ import annotations

import math
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
from ophamin.measuring.scenarios.memory_deformation_flow import (
    _DEFAULT_STIMULI,
    MemoryDeformationFlowScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

_concept_set = MemoryDeformationFlowScenario._concept_set
_jaccard = MemoryDeformationFlowScenario._jaccard


def _as_finite_float(value: Any) -> float | None:
    """Coerce a raw field to a finite float, or None.

    The Kimera runner serialises non-finite floats (NaN/Inf) as strings
    (``jsonable``), so a numeric field can arrive as a str. Treat anything
    non-finite or unparseable as absent rather than letting it poison a
    monotonicity / delta computation.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, str):
        try:
            f = float(value)
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


class MemoryPermanenceFlowScenario(Scenario):
    """Path-dependent memory in the scar/manifold substrate (not the concept layer).

    Construct with a re-exposure run shape; call ``run(adapter)`` with a live
    :class:`KimeraAdapter` in **batch** mode (state must accumulate across the
    batch — that accumulation IS the memory under test). ``run()`` is fully
    overridden; ``score()`` is unreachable.
    """

    name = "memory-permanence-flow"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "flow"
    runner_path = "examples/run_memory_permanence_flow.py"
    target = "entity"
    goal = (
        "Measure memory where the substrate actually keeps it — the permanent "
        "scars and the S4 manifold deformation — not the concept-recognition "
        "layer: when an identically-recognised probe is re-exposed, does it "
        "land on a strictly-deeper (more-scarred) manifold every time?"
    )
    explanation = (
        "Every prior memory scenario leads with concept-set Jaccard, which is "
        "RECOGNITION (content-deterministic by design, Session 013) — not "
        "memory. The owner's correction: memory IS the scars + the S4 "
        "manifold. This scenario reads Kimera's own permanent accumulators "
        "(vault_stats.total_scars_stored, arachne_web_coupling_frobenius, "
        "alexandria_knowledge_mass_cumulative, hypertree_total_nodes) across a "
        "re-exposure trajectory. The decisive memory-vs-re-derivation "
        "discriminator: a stateless re-deriver re-exposed to identical input "
        "is in an IDENTICAL state each time; Kimera is in a strictly DEEPER "
        "state each time (more permanent scars) while still recognising the "
        "input perfectly. That dissociation — recognition held constant, "
        "substrate permanently deeper — is path-dependent memory and is "
        "impossible for a stateless recompute. A scar reset anywhere "
        "(monotonicity violation) refutes the substrate's defining invariant."
    )
    method = "scar_path_dependence_with_recognition_held_constant"
    falsification_consequence = (
        "Either a re-exposed, recognised probe did NOT land on a deeper "
        "manifold (no scar accumulated across a whole gap — the substrate "
        "stopped forming memory; it is re-deriving, not remembering), or the "
        "permanent scar count decreased somewhere (a scar was reset — the "
        "'a scar cannot be reset' invariant broke). Either is a real substrate "
        "construction brief, not a measurement artefact."
    )

    def __init__(
        self,
        *,
        stimuli: tuple[str, ...] = _DEFAULT_STIMULI,
        n_exposures: int = 3,
        recognition_floor: float = 0.80,
        min_transitions: int = 6,
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
        self.min_transitions = int(min_transitions)
        self.corpus_label = str(corpus_label)
        # Static-trajectory scenario — base.run() is overridden.
        self.n_cycles = len(self.stimuli) * self.n_exposures

    # ------------------------------------------------------------- schedule --

    def build_schedule(self) -> list[tuple[int, str]]:
        """Interleaved re-exposure schedule: each stimulus appears
        ``n_exposures`` times, spaced by ``len(stimuli)`` cycles so a
        re-exposure always lands AFTER intervening cycles have written new
        scars (the path-dependence condition).

        Returns ``(stimulus_index, text)`` in cycle order.
        """
        schedule: list[tuple[int, str]] = []
        for _ in range(self.n_exposures):
            for idx, text in enumerate(self.stimuli):
                schedule.append((idx, text))
        return schedule

    # --------------------------------------------------------- extraction ----

    @staticmethod
    def _scar_count(result: CycleResult) -> int | None:
        """The canonical permanent scar count for a cycle.

        Priority: ``vault_stats.total_scars_stored`` (canonical;
        = vault_a.scar_count + vault_b.scar_count) → the sum of the two
        vault scar_counts → ``enhanced_vault_total_memories`` (top-level
        mirror). Returns None if none is readable.
        """
        if not result.success:
            return None
        raw = result.raw or {}
        vs = raw.get("vault_stats")
        if isinstance(vs, dict):
            tss = vs.get("total_scars_stored")
            if isinstance(tss, (int, float)) and not isinstance(tss, bool):
                return int(tss)
            a = vs.get("vault_a") or {}
            b = vs.get("vault_b") or {}
            if isinstance(a, dict) and isinstance(b, dict):
                ac, bc = a.get("scar_count"), b.get("scar_count")
                if isinstance(ac, (int, float)) and isinstance(bc, (int, float)):
                    return int(ac) + int(bc)
        evtm = raw.get("enhanced_vault_total_memories")
        if isinstance(evtm, (int, float)) and not isinstance(evtm, bool):
            return int(evtm)
        return None

    @staticmethod
    def _coupling(result: CycleResult) -> float | None:
        """The manifold coupling deformation (Arachne web Frobenius norm)."""
        if not result.success:
            return None
        return _as_finite_float((result.raw or {}).get("arachne_web_coupling_frobenius"))

    @staticmethod
    def _mass(result: CycleResult) -> float | None:
        """Cumulative semantic mass (Alexandria)."""
        if not result.success:
            return None
        raw = result.raw or {}
        m = _as_finite_float(raw.get("alexandria_knowledge_mass_cumulative"))
        return m if m is not None else _as_finite_float(raw.get("knowledge_mass"))

    @staticmethod
    def _phi(result: CycleResult) -> float | None:
        if not result.success:
            return None
        return _as_finite_float((result.raw or {}).get("phi"))

    @staticmethod
    def _halt(result: CycleResult) -> str | None:
        if result.halt_mode:
            return str(result.halt_mode)
        raw = result.raw or {}
        h = raw.get("halt_reason")
        return str(h) if h else None

    # --------------------------------------------------------------- claim ---

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "When an identically-recognised probe is re-exposed across a "
                "trajectory, it lands on a strictly-deeper (more-scarred) "
                "manifold every time: memory_path_dependence = (recognised "
                "re-exposure transitions with Δ permanent-scars > 0) / "
                "(recognised re-exposure transitions) >= 1.0, with the "
                "whole-run scar count monotonic non-decreasing (a scar cannot "
                "be reset). This measures memory where Kimera keeps it — the "
                "scars and the S4 manifold — not the content-recognition layer."
            ),
            operationalization=(
                f"Run {len(self.stimuli)} stimuli each re-exposed "
                f"{self.n_exposures}x, interleaved (gap = len(stimuli)), "
                "through Kimera's entity target (Takwin) in batch mode so the "
                "substrate accumulates across the batch. Per cycle read "
                "vault_stats.total_scars_stored (canonical permanent scars), "
                "arachne_web_coupling_frobenius (manifold deformation), and "
                "the concept set (recognition). For each same-stimulus "
                "consecutive exposure pair: recognised iff "
                f"Jaccard(concepts) >= {self.recognition_floor:.2f}; confirmed "
                "iff recognised AND Δ scars > 0. memory_path_dependence = "
                "confirmed / recognised. Forced to 0.0 (REFUTED) if the "
                "whole-run scar count ever decreases."
            ),
            threshold=Threshold(
                metric="memory_path_dependence",
                comparator=">=",
                value=1.0,
                units="proportion",
            ),
            h0=(
                "H0: memory_path_dependence < 1.0 — some re-exposure of a "
                "recognised probe did NOT land on more permanent scars (the "
                "substrate re-derives without accumulating), or a scar was "
                "reset; not path-dependent permanent memory"
            ),
            h1=(
                "H1: memory_path_dependence >= 1.0 — every re-exposure of a "
                "recognised probe lands on a strictly-deeper manifold and no "
                "scar is ever reset; path-dependent permanent memory in the "
                "scar/S4 substrate"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Build an interleaved re-exposure schedule ({len(self.stimuli)} "
            f"stimuli x {self.n_exposures} exposures, gap = "
            f"{len(self.stimuli)}); stream through Kimera's entity target in "
            "batch mode. Per cycle read the permanent scar count "
            "(vault_stats.total_scars_stored), the manifold coupling, the "
            "cumulative mass, the concept set, phi and halt. Headline: "
            "memory_path_dependence = fraction of recognised same-stimulus "
            "re-exposure transitions that land on strictly more permanent "
            f"scars; VALIDATED iff >= 1.0 AND whole-run scars monotonic. "
            f"INCONCLUSIVE if fewer than {self.min_transitions} recognised "
            "transitions. Cross-check (scipy Spearman): scar depth vs "
            "exposure ordinal, rho > 0 + p < 0.05. Permanence, accumulation "
            "slopes, halt-flip rate and phi-rigidity are reported as evidence; "
            "none post-hoc-claimable."
        )

    def score(self, cycle_results: list[CycleResult], records: list[Any]) -> ScenarioScore:
        raise NotImplementedError(
            "MemoryPermanenceFlowScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        if substrate is None:
            raise ValueError(
                "MemoryPermanenceFlowScenario.run needs a live substrate "
                "adapter (a memory-permanence proof measures a real, "
                "state-accumulating trajectory)."
            )

        schedule = self.build_schedule()
        texts = [t for _, t in schedule]
        results = substrate.run_batch(texts)

        # Per-cycle memory-substrate series (whole run, schedule order).
        scar_series: list[int | None] = [self._scar_count(r) for r in results]
        coupling_series = [self._coupling(r) for r in results]
        mass_series = [self._mass(r) for r in results]

        # ---- whole-run permanence: scar count must never decrease ---------
        scar_present = [(i, s) for i, s in enumerate(scar_series) if s is not None]
        scar_violations: list[dict[str, Any]] = []
        for (ia, a), (ib, b) in zip(scar_present, scar_present[1:]):
            if b < a:
                scar_violations.append(
                    {"cycle_a": ia, "cycle_b": ib, "scars_a": a, "scars_b": b}
                )
        permanence_holds = not scar_violations and len(scar_present) >= 2

        # ---- group per stimulus, preserving exposure order ----------------
        by_stim: dict[int, list[dict[str, Any]]] = {
            i: [] for i in range(len(self.stimuli))
        }
        for (idx, _text), r in zip(schedule, results):
            by_stim[idx].append({
                "cycle": r.cycle_index,
                "scars": self._scar_count(r),
                "coupling": self._coupling(r),
                "mass": self._mass(r),
                "concepts": _concept_set(r),
                "phi": self._phi(r),
                "halt": self._halt(r),
            })

        # ---- re-exposure transitions: the path-dependence test ------------
        transitions: list[dict[str, Any]] = []
        # ordinal series for the Spearman cross-check: (exposure_ordinal, scars)
        ordinal_scars: list[tuple[int, int]] = []
        for idx, exps in by_stim.items():
            for ordn, e in enumerate(exps):
                if e["scars"] is not None:
                    ordinal_scars.append((ordn, e["scars"]))
            for a, b in zip(exps, exps[1:]):
                ca, cb = a["concepts"], b["concepts"]
                if ca is None or cb is None:
                    continue  # cannot judge recognition for this pair
                recog = _jaccard(ca, cb)
                recognised = recog >= self.recognition_floor
                d_scars = (
                    (b["scars"] - a["scars"])
                    if (a["scars"] is not None and b["scars"] is not None)
                    else None
                )
                d_coupling = (
                    (b["coupling"] - a["coupling"])
                    if (a["coupling"] is not None and b["coupling"] is not None)
                    else None
                )
                d_phi = (
                    (b["phi"] - a["phi"])
                    if (a["phi"] is not None and b["phi"] is not None)
                    else None
                )
                deeper = (d_scars is not None and d_scars > 0)
                confirmed = recognised and deeper
                transitions.append({
                    "stimulus_index": idx,
                    "stimulus": self.stimuli[idx][:60],
                    "cycle_a": a["cycle"],
                    "cycle_b": b["cycle"],
                    "recognition_jaccard": round(recog, 6),
                    "recognised": recognised,
                    "scars_a": a["scars"],
                    "scars_b": b["scars"],
                    "delta_scars": d_scars,
                    "delta_coupling": (round(d_coupling, 6) if d_coupling is not None else None),
                    "delta_phi": (round(d_phi, 6) if d_phi is not None else None),
                    "halt_a": a["halt"],
                    "halt_b": b["halt"],
                    "halt_flipped": (a["halt"] != b["halt"]) if (a["halt"] and b["halt"]) else None,
                    "deeper_manifold": deeper,
                    "confirmed": confirmed,
                })

        recognised_trs = [t for t in transitions if t["recognised"]]
        n_recognised = len(recognised_trs)
        n_confirmed = sum(1 for t in recognised_trs if t["confirmed"])
        n_recog_fail = sum(1 for t in transitions if not t["recognised"])
        memory_path_dependence = (
            n_confirmed / n_recognised if n_recognised else 0.0
        )

        # Permanence is a hard precondition: a scar reset refutes the memory
        # claim outright (the "a scar cannot be reset" invariant broke), so
        # the honest observed value drops to 0.0 → REFUTED.
        observed = memory_path_dependence if permanence_holds else 0.0

        inconclusive = n_recognised < self.min_transitions

        # ---- accumulation slopes (supporting evidence) --------------------
        def _growth(series: list[Any]) -> dict[str, Any]:
            pres = [v for v in series if v is not None]
            if len(pres) < 2:
                return {"start": None, "end": None, "delta": None, "per_cycle": None}
            start, end = pres[0], pres[-1]
            return {
                "start": round(float(start), 6),
                "end": round(float(end), 6),
                "delta": round(float(end) - float(start), 6),
                "per_cycle": round((float(end) - float(start)) / (len(pres) - 1), 6),
            }

        accumulation = {
            "total_scars_stored": _growth(scar_series),
            "arachne_web_coupling_frobenius": _growth(coupling_series),
            "alexandria_knowledge_mass_cumulative": _growth(mass_series),
        }

        # ---- characterisations --------------------------------------------
        halt_flips = [t for t in transitions if t["halt_flipped"]]
        phi_deltas = [abs(t["delta_phi"]) for t in transitions if t["delta_phi"] is not None]
        recogs = [t["recognition_jaccard"] for t in transitions]
        recognition_floor_obs = min(recogs) if recogs else None

        # ---- cross-check: does scar depth rise with exposure ordinal? -----
        control = self._spearman_ordinal_depth(ordinal_scars)

        config = {
            "scenario": self.name, "scope": self.scope,
            "n_stimuli": len(self.stimuli), "n_exposures": self.n_exposures,
            "recognition_floor": self.recognition_floor,
            "schedule_len": len(schedule),
        }
        dataset = DatasetRef(
            name="kimera-memory-permanence-trajectory",
            content_hash=content_hash({"schedule": texts}),
            n_records=len(schedule),
            source=getattr(substrate, "name", "kimera-swm"),
            kind="substrate-trajectory+scar-accumulation",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config), data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        claim = self.build_claim()

        reasoning = (
            f"memory_path_dependence {memory_path_dependence:.4f} = "
            f"{n_confirmed}/{n_recognised} recognised re-exposure transitions "
            f"landed on strictly more permanent scars; "
            f"{n_recog_fail} transitions failed recognition (excluded). "
            f"Permanence: {'HOLDS' if permanence_holds else 'VIOLATED'} "
            f"({len(scar_violations)} scar-count decreases over the run). "
            f"Scars {accumulation['total_scars_stored']['start']}→"
            f"{accumulation['total_scars_stored']['end']}; coupling "
            f"{accumulation['arachne_web_coupling_frobenius']['start']}→"
            f"{accumulation['arachne_web_coupling_frobenius']['end']}"
        )
        if not permanence_holds and scar_violations:
            reasoning += (
                "; OBSERVED FORCED TO 0.0 — a scar was reset (the substrate's "
                "defining invariant broke)"
            )
        if phi_deltas:
            reasoning += (
                f"; phi |delta| mean {mean(phi_deltas):.4f} "
                f"(Φ-rigid → memory is in the scars/manifold, not Φ)"
            )
        if control.get("p_value") is not None:
            reasoning += (
                f"; scar-depth vs exposure-ordinal Spearman rho="
                f"{control.get('rho')}, p={control['p_value']:.2g} "
                f"({'deepens with experience' if control.get('significant') else 'not significant'})"
            )
        if inconclusive:
            reasoning += (
                f"; INCONCLUSIVE — fewer than {self.min_transitions} recognised "
                "re-exposure transitions"
            )

        verdict = Verdict.decide(
            observed=observed, threshold=claim.threshold,
            inconclusive=inconclusive, reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.flow.memory_path_dependence",
                statistic_name="memory_path_dependence",
                statistic_value=observed,
                library="ophamin",
                library_version=__version__,
                cross_check=control.get("status", "skipped"),
                p_value=control.get("p_value"),
                detail={
                    "scope": "flow",
                    "flow_metric_label": "path-dependent memory (recognised re-exposure lands deeper)",
                    "flow_unit_label": "re-exposure transition",
                    "flow_corpus_label": self.corpus_label,
                    "flow_mean": observed,
                    "memory_path_dependence": memory_path_dependence,
                    "observed_after_permanence_gate": observed,
                    "permanence_holds": permanence_holds,
                    "scar_monotonicity_violations": scar_violations,
                    "n_recognised_transitions": n_recognised,
                    "n_confirmed_transitions": n_confirmed,
                    "n_recognition_failures": n_recog_fail,
                    "recognition_floor_observed": recognition_floor_obs,
                    "recognition_floor_threshold": self.recognition_floor,
                    "accumulation": accumulation,
                    "halt_flip_rate": (
                        round(len(halt_flips) / len(transitions), 4) if transitions else None
                    ),
                    "n_halt_flips": len(halt_flips),
                    "phi_delta_abs_mean": (round(mean(phi_deltas), 6) if phi_deltas else None),
                    "phi_delta_abs_max": (round(max(phi_deltas), 6) if phi_deltas else None),
                    "control": control,
                    "transition_series": transitions,
                    "scar_series": scar_series,
                    "coupling_series": [
                        (round(c, 6) if c is not None else None) for c in coupling_series
                    ],
                    "n_stimuli": len(self.stimuli),
                    "n_exposures": self.n_exposures,
                    "schedule_len": len(schedule),
                    "interpretation": (
                        "memory_path_dependence>=1.0 + permanence + recognition "
                        "held = path-dependent permanent memory in the scar/S4 "
                        "substrate (identical recognised input lands on a "
                        "strictly-deeper manifold every time — impossible for a "
                        "stateless re-deriver). <1.0 or a scar reset = the "
                        "substrate re-derives / forgets, it does not remember."
                    ),
                    "grounding_anchor": (
                        "memory-as-deformation (Kimera CLAUDE.md / Session 013): "
                        "experience permanently carves the manifold; a scar "
                        "cannot be reset (SphericalMemoryVault monotonic_violations "
                        "invariant). Recognition stability is the control proving "
                        "the deepening is not because the input changed."
                    ),
                },
            ),
        ]

        prov = ProvenanceGraph()
        a_o = prov.agent("ophamin", role="experimentation_framework", version=__version__)
        a_k = prov.agent("kimera-swm", role="substrate_under_flow_test")
        de = prov.entity(f"corpus:{dataset.name}", content_hash=dataset.content_hash,
                         n_records=dataset.n_records, kind=dataset.kind)
        act = prov.activity(f"scenario:{self.name}", target=self.target, n_cycles=len(schedule))
        re_ = prov.entity(f"proof:{self.name}")
        prov.used(act, de)
        prov.was_associated_with(act, a_o)
        prov.was_associated_with(act, a_k)
        prov.was_generated_by(re_, act)
        prov.was_attributed_to(re_, a_k)
        prov.was_derived_from(re_, de)

        substrate_commit = ""
        getter = getattr(substrate, "git_commit", None)
        if callable(getter):
            try:
                substrate_commit = str(getter() or "")[:12]
            except Exception:  # noqa: BLE001 — provenance best-effort
                substrate_commit = ""

        proof = EmpiricalProofRecord(
            claim=claim, preregistration=prereg, datasets=[dataset],
            substrate_name=getattr(substrate, "name", "kimera-swm"),
            substrate_git_commit=substrate_commit,
            evidence=evidence, verdict=verdict,
            reproduction=Reproduction(command=self._build_reproduction_command()),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof

    @staticmethod
    def _spearman_ordinal_depth(ordinal_scars: list[tuple[int, int]]) -> dict[str, Any]:
        """Cross-check: does scar depth rise with exposure ordinal?

        Pools (exposure_ordinal, scar_count) over all stimuli and runs a
        one-sided Spearman (rho > 0). A positive significant rho means the
        substrate is measurably deeper at later encounters — memory deepens
        with experience.
        """
        out: dict[str, Any] = {
            "control": "scar_depth_vs_exposure_ordinal_spearman",
            "n_points": len(ordinal_scars),
        }
        if len(ordinal_scars) < 4:
            out.update({"status": "skipped", "reason": "too few points",
                        "rho": None, "p_value": None, "significant": False})
            return out
        ords = [o for o, _ in ordinal_scars]
        scars = [s for _, s in ordinal_scars]
        if len(set(ords)) < 2 or len(set(scars)) < 2:
            out.update({"status": "skipped", "reason": "no variance in one axis",
                        "rho": None, "p_value": None, "significant": False})
            return out
        try:
            from scipy.stats import spearmanr
            rho, p = spearmanr(ords, scars, alternative="greater")
            significant = bool((p < 0.05) and (rho > 0))
            out.update({
                "status": "passed" if significant else "failed",
                "rho": round(float(rho), 4), "p_value": float(p),
                "significant": significant, "library": "scipy",
            })
        except Exception as exc:  # noqa: BLE001 — control best-effort
            out.update({"status": "skipped", "reason": f"scipy: {exc}",
                        "rho": None, "p_value": None, "significant": False})
        return out
