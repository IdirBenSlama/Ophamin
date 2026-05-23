"""The Cued-Recall Flow scenario — isolate MEMORY from deterministic re-derivation.

The memory-horizon proof showed perfect recall of full re-shown items at long
lag — but a flat 1.0 curve cannot tell *path-dependent memory* (the substrate
recalls because it experienced the item) from *deterministic re-derivation*
(same text in → same concepts out, no memory needed). A 1M-token LLM also
"recognises" identical re-shown text. This proof removes that confound with the
classic cued-recall / pattern-completion paradigm (Hopfield associative
memory): probe with a **partial cue**, and contrast a **seen** item against a
**never-seen** control at the *same* corruption level.

Both arms get the same impoverished input (a partial cue), so any
content-determinism is held constant. The ONLY difference is prior exposure.
The signal is the **memory lift**:

    memory_lift = mean( recall | seen, partial cue )
                − mean( recall | never-seen, partial cue )

where recall = Jaccard(concepts from the partial cue, the item's full concept
set). If lift ≤ 0, the horizon's perfect recall was pure re-derivation — no
memory beyond a window (an honest, useful refutation: a Kimera construction
brief). If lift > 0 *and significant*, the prior exposure completed the cue —
**path-dependent memory**, the foundation of the infinite-context claim.

The never-seen arm is the built-in fair baseline ("no memory"); no external
RAG/long-context harness is needed for THIS proof — that comparison is the
separate, later "beat the industry" step.

Pre-registered invariant
========================

    memory_lift > 0   (seen partial-cue recall exceeds never-seen)

decided only when the seen-vs-control Mann-Whitney is significant; otherwise
INCONCLUSIVE.
"""

from __future__ import annotations

from statistics import mean, median, pstdev
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


class MemoryCuedRecallFlowScenario(Scenario):
    """Partial-cue recall: seen vs never-seen, isolating memory from re-derivation.

    Construct with a ``stimuli`` stream (the seen experiences) and a disjoint
    ``control_stimuli`` set (never streamed). ``run()`` streams the seen set,
    then probes partial cues of both seen and control items and measures the
    memory lift. ``run()`` is fully overridden, so ``score()`` is unreachable.
    """

    name = "memory-cued-recall-flow"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "flow"
    runner_path = "examples/run_memory_cued_recall_flow.py"
    target = "entity"
    goal = (
        "Isolate path-dependent memory from deterministic re-derivation: does a "
        "partial cue of a SEEN item recall its full content better than a "
        "partial cue of a never-seen item (memory lift > 0)?"
    )
    explanation = (
        "Settles the determinism confound the memory-horizon proof surfaced. "
        "Cued-recall / pattern-completion (Hopfield): probe with a partial cue "
        "and contrast a seen item vs a never-seen control at the same corruption "
        "level. Both arms get the same impoverished input, so content-"
        "determinism is held constant; only prior exposure differs. memory_lift "
        "= mean(recall|seen) − mean(recall|never-seen). lift ≤ 0 ⇒ the horizon "
        "recall was re-derivation (no memory); lift > 0 + significant ⇒ real "
        "path-dependent memory. The never-seen arm is the built-in fair "
        "baseline."
    )
    method = "partial_cue_recall_seen_vs_never_seen"
    falsification_consequence = (
        "A partial cue of a seen item recalls no better than a partial cue of a "
        "never-seen item — the substrate's 'recall' is deterministic "
        "re-derivation, not memory. (Honest: a Kimera flow/wiring construction "
        "brief, not a measurement artifact.)"
    )

    def __init__(
        self,
        *,
        stimuli: tuple[str, ...] = _DEFAULT_STIMULI,
        control_stimuli: tuple[str, ...] | None = None,
        n_probes: int = 25,
        cue_fraction: float = 0.4,
        min_probes: int = 5,
        corpus_label: str = "kimera-genesis",
    ) -> None:
        if not stimuli:
            raise ValueError("stimuli (seen set) must be non-empty")
        if not 0.0 < cue_fraction < 1.0:
            raise ValueError(f"cue_fraction must be in (0, 1), got {cue_fraction}")
        # control set: disjoint, never streamed. Default: split the tail off
        # stimuli if no explicit control given (keeps the scenario runnable on
        # the genesis set for tests).
        seen = tuple(stimuli)
        ctrl = tuple(control_stimuli) if control_stimuli else ()
        if not ctrl:
            if len(seen) < 4:
                raise ValueError(
                    "need control_stimuli, or >=4 stimuli to split a control set")
            cut = max(1, len(seen) // 4)
            ctrl, seen = seen[-cut:], seen[:-cut]
        overlap = set(seen) & set(ctrl)
        if overlap:
            raise ValueError(
                f"seen and control sets must be disjoint; {len(overlap)} shared")
        self.stimuli = seen
        self.control_stimuli = ctrl
        self.n_probes = min(int(n_probes), len(self.stimuli))
        self.n_control = min(int(n_probes), len(self.control_stimuli))
        self.cue_fraction = float(cue_fraction)
        self.min_probes = int(min_probes)
        self.corpus_label = str(corpus_label)
        self.n_cycles = (
            len(self.stimuli) + self.n_probes + 2 * self.n_control
        )

    # ----------------------------------------------------------- corruption --

    def _partial_cue(self, text: str) -> str:
        """A leading partial cue: the first ``cue_fraction`` of the words.

        Cued recall uses an impoverished version of the original; the leading
        fragment is the simplest content-preserving corruption.
        """
        words = text.split()
        if not words:
            return text
        k = max(1, int(len(words) * self.cue_fraction))
        return " ".join(words[:k])

    # --------------------------------------------------------------- claim ---

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "A partial cue of a SEEN experience recalls its full content "
                "better than a partial cue of a never-seen item: memory_lift = "
                "mean(recall|seen) − mean(recall|never-seen) > 0. Both arms get "
                "the same impoverished cue, so this isolates path-dependent "
                "memory from deterministic re-derivation."
            ),
            operationalization=(
                f"Stream {len(self.stimuli)} seen items; never stream "
                f"{len(self.control_stimuli)} control items. Probe partial cues "
                f"(first {self.cue_fraction:.0%} of words) of {self.n_probes} "
                f"seen and {self.n_control} control items. recall = "
                "Jaccard(concepts(partial cue), concepts(full item)). "
                "memory_lift = mean(recall seen) − mean(recall control); decided "
                "VALIDATED iff lift > 0 with a significant seen>control "
                "Mann-Whitney."
            ),
            threshold=Threshold(
                metric="memory_lift", comparator=">", value=0.0, units="jaccard",
            ),
            h0=(
                "H0: memory_lift ≤ 0 — a seen partial cue recalls no better than "
                "a never-seen one; 'recall' is deterministic re-derivation"
            ),
            h1=(
                "H1: memory_lift > 0 — prior exposure completes the partial cue; "
                "path-dependent memory beyond re-derivation"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Stream {len(self.stimuli)} seen items (record full concept sets). "
            f"Probe partial cues (first {self.cue_fraction:.0%} of words) of "
            f"{self.n_probes} seen items (warm) and {self.n_control} never-seen "
            f"control items (cold; full run after the cue to get the target). "
            f"recall = Jaccard(cue concepts, full concepts). memory_lift = "
            f"mean(recall seen) − mean(recall control). INCONCLUSIVE if fewer "
            f"than {self.min_probes} valid probes per arm or the Mann-Whitney "
            f"is not significant; else VALIDATED iff lift > 0. The per-arm "
            f"distributions are descriptive."
        )

    def score(self, cycle_results: list[CycleResult], records: list[Any]) -> ScenarioScore:
        raise NotImplementedError(
            "MemoryCuedRecallFlowScenario uses a custom run() loop; "
            "score() is unreachable.")

    # ------------------------------------------------------------------ run --

    def build_schedule(self) -> list[tuple[str, str]]:
        """``(text, phase)`` in cycle order: stream → seen cues → control
        (cue then full, so the cold cue runs with no prior exposure)."""
        sched: list[tuple[str, str]] = [(t, "stream") for t in self.stimuli]
        for t in self.stimuli[: self.n_probes]:
            sched.append((self._partial_cue(t), "seen_cue"))
        for t in self.control_stimuli[: self.n_control]:
            sched.append((self._partial_cue(t), "control_cue"))
            sched.append((t, "control_full"))
        return sched

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: object = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        if substrate is None:
            raise ValueError(
                "MemoryCuedRecallFlowScenario.run needs a live substrate adapter.")

        schedule = self.build_schedule()
        texts = [t for t, _ in schedule]
        results = substrate.run_batch(texts)

        n_stream = len(self.stimuli)
        # Phase 1: seen full → target concept sets (by stream order).
        seen_target: list[frozenset[str] | None] = []
        for i in range(n_stream):
            seen_target.append(_concept_set(results[i]))

        # Phase 2: seen partial cues → recall_seen.
        recall_seen: list[float] = []
        pos = n_stream
        for j in range(self.n_probes):
            cue_cs = _concept_set(results[pos])
            pos += 1
            target = seen_target[j]
            if cue_cs is not None and target is not None:
                recall_seen.append(_jaccard(cue_cs, target))

        # Phase 3: control (cue cold, then full target) → recall_control.
        recall_control: list[float] = []
        for _j in range(self.n_control):
            cue_cs = _concept_set(results[pos])
            pos += 1
            full_cs = _concept_set(results[pos])
            pos += 1
            if cue_cs is not None and full_cs is not None:
                recall_control.append(_jaccard(cue_cs, full_cs))

        n_seen = len(recall_seen)
        n_ctrl = len(recall_control)
        seen_mean = mean(recall_seen) if recall_seen else 0.0
        ctrl_mean = mean(recall_control) if recall_control else 0.0
        memory_lift = seen_mean - ctrl_mean

        control = self._significance(recall_seen, recall_control)
        inconclusive = (
            n_seen < self.min_probes or n_ctrl < self.min_probes
            or control.get("status") == "skipped"
            or not control.get("significant", False)
        )

        config = {
            "scenario": self.name, "scope": self.scope,
            "n_seen": len(self.stimuli), "n_control": len(self.control_stimuli),
            "n_probes": self.n_probes, "cue_fraction": self.cue_fraction,
        }
        dataset = DatasetRef(
            name="kimera-cued-recall-stream",
            content_hash=content_hash({"schedule": texts}),
            n_records=len(schedule),
            source=getattr(substrate, "name", "kimera-swm"),
            kind="substrate-trajectory+partial-cue-recall",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config), data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        claim = self.build_claim()

        reasoning = (
            f"memory_lift {memory_lift:+.4f} = seen recall {seen_mean:.4f} "
            f"(n={n_seen}) − control recall {ctrl_mean:.4f} (n={n_ctrl}); "
            f"partial cue = first {self.cue_fraction:.0%} of words"
        )
        if control.get("p_value") is not None:
            reasoning += (
                f"; seen>control Mann-Whitney p={control['p_value']:.2g}"
                f"{' (significant — real memory)' if control.get('significant') else ' (NOT significant)'}"
            )
        if inconclusive:
            reasoning += (
                "; INCONCLUSIVE — "
                + ("too few valid probes per arm"
                   if (n_seen < self.min_probes or n_ctrl < self.min_probes)
                   else "lift not statistically significant")
            )

        verdict = Verdict.decide(
            observed=memory_lift, threshold=claim.threshold,
            inconclusive=inconclusive, reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.flow.cued_recall",
                statistic_name="memory_lift",
                statistic_value=memory_lift,
                library="ophamin",
                library_version=__version__,
                cross_check=control.get("status", "skipped"),
                p_value=control.get("p_value"),
                detail={
                    "scope": "flow",
                    "flow_metric_label": "memory lift (seen − never-seen recall)",
                    "flow_unit_label": "arm",
                    "flow_corpus_label": self.corpus_label,
                    "flow_mean": memory_lift,
                    "control": control,
                    "memory_lift": memory_lift,
                    "seen_recall_mean": seen_mean,
                    "seen_recall_median": median(recall_seen) if recall_seen else 0.0,
                    "seen_recall_stdev": pstdev(recall_seen) if len(recall_seen) > 1 else 0.0,
                    "control_recall_mean": ctrl_mean,
                    "control_recall_median": median(recall_control) if recall_control else 0.0,
                    "control_recall_stdev": pstdev(recall_control) if len(recall_control) > 1 else 0.0,
                    "n_seen_probes": n_seen,
                    "n_control_probes": n_ctrl,
                    "cue_fraction": self.cue_fraction,
                    "n_stream": len(self.stimuli),
                    "recall_seen": [round(r, 6) for r in recall_seen],
                    "recall_control": [round(r, 6) for r in recall_control],
                    "interpretation": (
                        "lift>0 + significant = path-dependent memory (the cue "
                        "was completed by prior exposure); lift<=0 = the recall "
                        "is deterministic re-derivation, not memory."
                    ),
                    "grounding_anchor": (
                        "cued recall / pattern completion (Hopfield associative "
                        "memory); seen-vs-never-seen control holds content-"
                        "determinism constant."
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
    def _significance(seen: list[float], control: list[float]) -> dict[str, Any]:
        """Mann-Whitney: does seen partial-cue recall exceed never-seen?"""
        out: dict[str, Any] = {
            "control": "seen_vs_never_seen_partial_cue_recall",
            "n_seen": len(seen), "n_control": len(control),
            "seen_median": round(median(seen), 6) if seen else 0.0,
            "control_median": round(median(control), 6) if control else 0.0,
        }
        if len(seen) < 3 or len(control) < 3:
            out.update({"status": "skipped", "reason": "too few probes per arm",
                        "p_value": None, "cl_effect_size": None, "significant": False})
            return out
        try:
            from scipy.stats import mannwhitneyu
            u, p = mannwhitneyu(seen, control, alternative="greater")
            cl = float(u) / (len(seen) * len(control))
            significant = (p < 0.05) and (out["seen_median"] > out["control_median"])
            out.update({
                "status": "passed" if significant else "failed",
                "p_value": float(p), "cl_effect_size": round(cl, 4),
                "significant": bool(significant), "library": "scipy",
            })
        except Exception as exc:  # noqa: BLE001 — control best-effort
            out.update({"status": "skipped", "reason": f"scipy: {exc}",
                        "p_value": None, "cl_effect_size": None, "significant": False})
        return out
