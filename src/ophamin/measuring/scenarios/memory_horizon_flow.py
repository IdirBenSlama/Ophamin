"""The Memory-Horizon Flow scenario — how far back does the substrate recall?

This is the first proof aimed at the *infinite-context-memory* gap, and it is
deliberately OBSERVATIONAL: we do not assert in advance how far Kimera's memory
reaches — the substrate tells us. We stream a long sequence of distinct
experiences ONCE, then re-probe a spread of earlier items and measure recall
(concept-set Jaccard between an item's first exposure and its later probe) as a
function of LAG — the number of intervening cycles between the two.

The lag→recall curve is the discovery: it is the substrate's *memory horizon*,
revealed, not predicted. A fixed-context model cannot recall anything beyond
its window by construction; RAG retrieves but does not accumulate or deform.
Kimera's claim is accumulation + path-dependent topological recall — so the
question this proof answers empirically is: **does recall hold at lags that
exceed a reference context window?**

Pre-registered invariant (LTL safety form)
==========================================

    □ ( for every probe whose lag exceeds the reference window:
            recall_jaccard ≥ recall_floor )

``window_ref`` is a reference context window expressed in ITEMS (default 256 —
roughly a 128K-token window at ~500 tokens/item). A probe with lag > window_ref
is recalling something a fixed window of that size would already have dropped.
The falsifiable statistic is ``recall_floor_beyond_window`` — the worst recall
over those beyond-window probes. REFUTED is an honest, useful outcome: it
locates the substrate's true horizon and becomes a construction brief.

Output — generic flow shape
===========================

Emits the generic flow-evidence keys (``flow_metric_label``, ``flow_unit_label``
= "lag", ``flow_mean``, ``worst_unit``) so the Console Flow screen renders it
with no scenario-specific code, plus the full ``lag_curve`` for analysis.
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

# Reuse the recognition primitives — one definition of "concept set" and
# "Jaccard" across the memory proofs (DRY; no second, drifting copy).
_concept_set = MemoryDeformationFlowScenario._concept_set
_jaccard = MemoryDeformationFlowScenario._jaccard


class MemoryHorizonFlowScenario(Scenario):
    """How far back the substrate recalls — recall vs lag across a long stream.

    Stream ``stimuli`` once (the experiences), then re-probe ``n_probes`` items
    spread across the stream and measure recall (Jaccard of the concept set at
    first exposure vs at probe) against the LAG between them. The pre-registered
    invariant is recall ≥ ``recall_floor`` for every probe whose lag exceeds
    ``window_ref`` (a reference context window in items). ``run()`` is fully
    overridden — trajectory scenario — so ``score()`` is unreachable.
    """

    name = "memory-horizon-flow"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "flow"
    runner_path = "examples/run_memory_horizon_flow.py"
    target = "entity"
    goal = (
        "Measure how far back the substrate recalls: recall (concept-set "
        "Jaccard) as a function of lag across a long single-pass stream, and "
        "whether it holds beyond a reference context window."
    )
    explanation = (
        "The first proof aimed at the infinite-context-memory gap, and "
        "deliberately observational: the substrate reveals its own memory "
        "horizon. Stream N distinct experiences once, re-probe a spread of "
        "earlier items, measure recall vs lag. The pre-registered invariant is "
        "recall ≥ floor for probes whose lag exceeds window_ref (a reference "
        "context window in items) — i.e. recall of something a fixed window "
        "that size would have dropped. The lag→recall curve is the discovery; "
        "REFUTED honestly locates the true horizon."
    )
    method = "recall_vs_lag_over_single_pass_stream"
    falsification_consequence = (
        "Recall fell below the floor for items recalled beyond the reference "
        "window — the substrate's memory horizon is shorter than that window "
        "on this corpus (a real, locatable limit, not a window-size win)."
    )

    def __init__(
        self,
        *,
        stimuli: tuple[str, ...] = _DEFAULT_STIMULI,
        n_probes: int = 12,
        window_ref: int = 256,
        recall_floor: float = 0.50,
        min_beyond_window: int = 3,
        corpus_label: str = "kimera-genesis",
    ) -> None:
        if not stimuli:
            raise ValueError("stimuli must be non-empty")
        if n_probes < 2:
            raise ValueError(f"n_probes must be >= 2, got {n_probes}")
        if window_ref < 1:
            raise ValueError(f"window_ref must be >= 1, got {window_ref}")
        if not 0.0 < recall_floor <= 1.0:
            raise ValueError(f"recall_floor must be in (0, 1], got {recall_floor}")
        # need at least n_probes distinct items to probe
        self.stimuli = tuple(stimuli)
        self.n_probes = min(int(n_probes), len(self.stimuli))
        self.window_ref = int(window_ref)
        self.recall_floor = float(recall_floor)
        self.min_beyond_window = int(min_beyond_window)
        self.corpus_label = str(corpus_label)
        self.n_stream = len(self.stimuli)
        self.n_cycles = self.n_stream + self.n_probes

    # ------------------------------------------------------------- schedule --

    def _probe_positions(self) -> list[int]:
        """Original-stream positions to re-probe, evenly spread over [0, N).

        Oldest-first so probe order yields a clean lag spectrum: the oldest
        item gets the largest lag, the most-recent the smallest.
        """
        n, p = self.n_stream, self.n_probes
        if p == 1:
            return [0]
        return [round(j * (n - 1) / (p - 1)) for j in range(p)]

    def build_schedule(self) -> list[tuple[int, str, str]]:
        """``(stimulus_index, text, phase)`` in cycle order.

        Phase 1 (``"stream"``): every stimulus once, in order. Phase 2
        (``"probe"``): the chosen positions re-streamed oldest-first.
        """
        schedule: list[tuple[int, str, str]] = [
            (i, text, "stream") for i, text in enumerate(self.stimuli)
        ]
        for pos in self._probe_positions():
            schedule.append((pos, self.stimuli[pos], "probe"))
        return schedule

    # ---------------------------------------------------------------- claim --

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "Across a long single-pass stream, the substrate still "
                "recalls earlier experiences beyond a fixed context window: "
                "□ (for every probe whose lag exceeds window_ref="
                f"{self.window_ref}, recall Jaccard ≥ {self.recall_floor:.2f}). "
                "The reported floor is the worst beyond-window probe."
            ),
            operationalization=(
                f"Stream {self.n_stream} distinct stimuli once through Kimera's "
                f"entity target, then re-probe {self.n_probes} positions spread "
                "over the stream. For each probe, recall = Jaccard(concept set "
                "at first exposure, concept set at probe); lag = intervening "
                "cycles. recall_floor_beyond_window = min recall over probes "
                f"with lag > {self.window_ref}; the □ invariant holds iff that "
                f"floor ≥ {self.recall_floor:.2f}."
            ),
            threshold=Threshold(
                metric="recall_floor_beyond_window",
                comparator=">=",
                value=self.recall_floor,
                units="jaccard",
            ),
            h0=(
                f"H0: recall < {self.recall_floor:.2f} for some item recalled "
                f"beyond window_ref={self.window_ref} — the horizon is shorter "
                "than the reference window"
            ),
            h1=(
                f"H1: recall ≥ {self.recall_floor:.2f} for every beyond-window "
                "probe — memory reaches past a fixed window of that size"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Stream {self.n_stream} stimuli once, then re-probe {self.n_probes} "
            f"evenly-spread positions. Per probe compute recall = Jaccard(first "
            f"exposure concepts, probe concepts) and lag = probe_cycle − "
            f"exposure_cycle. Partition probes at window_ref={self.window_ref}. "
            f"Decide □: min recall over beyond-window probes ≥ "
            f"{self.recall_floor:.2f}. INCONCLUSIVE if fewer than "
            f"{self.min_beyond_window} beyond-window probes are valid. The "
            f"lag→recall curve, memory horizon (max lag with recall ≥ floor), "
            f"and the negative control are descriptive."
        )

    def score(
        self, cycle_results: list[CycleResult], records: list[Any],
    ) -> ScenarioScore:
        """Never called — base.run() is overridden for trajectory control."""
        raise NotImplementedError(
            "MemoryHorizonFlowScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    # ------------------------------------------------------------------ run --

    @staticmethod
    def _control_crosscheck(
        beyond_recalls: list[float], cross: list[float],
    ) -> dict[str, Any]:
        """Negative control: beyond-window recall vs cross-item Jaccard.

        Recall at long lag is only real if it beats the Jaccard you'd get
        between UNRELATED items. scipy Mann-Whitney (one-sided, recall > cross).
        """
        out: dict[str, Any] = {
            "control": "beyond_window_recall_vs_cross_item_jaccard",
            "n_beyond": len(beyond_recalls),
            "n_cross": len(cross),
            "beyond_median": round(median(beyond_recalls), 6) if beyond_recalls else 0.0,
            "cross_median": round(median(cross), 6) if cross else 0.0,
        }
        if len(beyond_recalls) < 3 or len(cross) < 3:
            out.update({"status": "skipped", "reason": "too few pairs for a test",
                        "p_value": None, "cl_effect_size": None,
                        "recall_significant": False})
            return out
        try:
            from scipy.stats import mannwhitneyu
            u, p = mannwhitneyu(beyond_recalls, cross, alternative="greater")
            cl = float(u) / (len(beyond_recalls) * len(cross))
            significant = (p < 0.05) and (out["beyond_median"] > out["cross_median"])
            out.update({
                "status": "passed" if significant else "failed",
                "p_value": float(p), "cl_effect_size": round(cl, 4),
                "recall_significant": bool(significant), "library": "scipy",
            })
        except Exception as exc:  # noqa: BLE001 — control is best-effort
            out.update({"status": "skipped", "reason": f"scipy: {exc}",
                        "p_value": None, "cl_effect_size": None,
                        "recall_significant": False})
        return out

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        if substrate is None:
            raise ValueError(
                "MemoryHorizonFlowScenario.run needs a live substrate adapter "
                "(a flow proof measures a real trajectory)."
            )

        schedule = self.build_schedule()
        stimuli_text = [text for _, text, _ in schedule]
        cycle_results = substrate.run_batch(stimuli_text)

        # First-exposure concept set per stream position (phase 1).
        exposure: dict[int, frozenset[str]] = {}
        all_sets: list[frozenset[str]] = []  # for the cross-item control
        n_stream_cycles = self.n_stream
        for pos, (sched, result) in enumerate(zip(schedule, cycle_results)):
            if pos >= n_stream_cycles:
                break
            cs = _concept_set(result)
            if cs is not None:
                exposure[sched[0]] = cs
                all_sets.append(cs)

        # Probe phase: recall vs lag.
        lag_curve: list[dict[str, Any]] = []
        beyond_recalls: list[float] = []
        n_failed = 0
        worst_unit: dict[str, Any] | None = None
        for pos in range(n_stream_cycles, len(schedule)):
            stim_idx, _text, _phase = schedule[pos]
            result = cycle_results[pos]
            cs = _concept_set(result)
            origin = exposure.get(stim_idx)
            if cs is None or origin is None:
                n_failed += 1
                continue
            recall = _jaccard(origin, cs)
            lag = pos - stim_idx  # probe cycle − original exposure cycle
            beyond = lag > self.window_ref
            point = {
                "stimulus_index": stim_idx,
                "exposure_cycle": stim_idx,
                "probe_cycle": pos,
                "lag": lag,
                "recall": round(recall, 6),
                "beyond_window": beyond,
            }
            lag_curve.append(point)
            if beyond:
                beyond_recalls.append(recall)
                if worst_unit is None or recall < worst_unit["value"]:
                    worst_unit = {
                        "stimulus_index": stim_idx, "cycle": pos,
                        "lag": lag, "value": round(recall, 6),
                    }

        n_beyond = len(beyond_recalls)
        floor = min(beyond_recalls) if beyond_recalls else 0.0
        recall_mean = mean(beyond_recalls) if beyond_recalls else 0.0
        recall_std = pstdev(beyond_recalls) if len(beyond_recalls) > 1 else 0.0
        max_lag = max((p["lag"] for p in lag_curve), default=0)
        # memory horizon: the largest lag at which recall still cleared the floor
        horizon = max(
            (p["lag"] for p in lag_curve if p["recall"] >= self.recall_floor),
            default=0,
        )

        # negative control — beyond-window recall vs cross-item Jaccard
        from itertools import combinations as _comb
        cross = [_jaccard(a, b) for a, b in _comb(all_sets, 2)]
        control = self._control_crosscheck(beyond_recalls, cross)

        inconclusive = n_beyond < self.min_beyond_window

        config = {
            "scenario": self.name, "scope": self.scope,
            "n_stream": self.n_stream, "n_probes": self.n_probes,
            "window_ref": self.window_ref, "recall_floor": self.recall_floor,
        }
        dataset = DatasetRef(
            name="kimera-memory-horizon-stream",
            content_hash=content_hash({"schedule": stimuli_text}),
            n_records=len(schedule),
            source=getattr(substrate, "name", "kimera-swm"),
            kind="substrate-trajectory+single-pass-stream",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        claim = self.build_claim()

        reasoning = (
            f"recall floor {floor:.4f} over {n_beyond} beyond-window probes "
            f"(lag > {self.window_ref}); mean recall {recall_mean:.4f}, stdev "
            f"{recall_std:.4f}; memory horizon (max lag with recall ≥ "
            f"{self.recall_floor:.2f}) = {horizon} cycles; max lag measured "
            f"{max_lag}; {self.n_stream}-item single-pass stream; {n_failed} "
            f"probes produced no concept set"
        )
        if worst_unit is not None:
            reasoning += (
                f"; worst beyond-window probe: stimulus "
                f"{worst_unit['stimulus_index']} @ lag {worst_unit['lag']} "
                f"= {worst_unit['value']:.4f}"
            )
        if control.get("p_value") is not None:
            reasoning += (
                f"; control: beyond-window recall median "
                f"{control['beyond_median']:.3f} vs cross-item median "
                f"{control['cross_median']:.3f}, Mann-Whitney "
                f"p={control['p_value']:.2g}"
                f"{' (recall real beyond window)' if control.get('recall_significant') else ''}"
            )
        if inconclusive:
            reasoning += (
                f"; too few beyond-window probes (<{self.min_beyond_window}) "
                "to decide — widen the stream or lower window_ref"
            )

        verdict = Verdict.decide(
            observed=floor, threshold=claim.threshold,
            inconclusive=inconclusive, reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.flow.memory_horizon",
                statistic_name="recall_floor_beyond_window",
                statistic_value=floor,
                library="ophamin",
                library_version=__version__,
                cross_check=control.get("status", "skipped"),
                p_value=control.get("p_value"),
                detail={
                    "scope": "flow",
                    "flow_metric_label": "recall (concept Jaccard)",
                    "flow_unit_label": "lag",
                    "flow_corpus_label": self.corpus_label,
                    "flow_mean": recall_mean,
                    "control": control,
                    "ltl_invariant": (
                        f"ALWAYS(recall >= {self.recall_floor:.2f}) for probes "
                        f"with lag > window_ref={self.window_ref}"
                    ),
                    "recall_floor_beyond_window": floor,
                    "recall_mean_beyond_window": recall_mean,
                    "recall_stdev_beyond_window": recall_std,
                    "window_ref": self.window_ref,
                    "memory_horizon": horizon,
                    "max_lag_measured": max_lag,
                    "n_stream": self.n_stream,
                    "n_probes": self.n_probes,
                    "n_beyond_window": n_beyond,
                    "n_failed_probes": n_failed,
                    "worst_unit": worst_unit,
                    "lag_curve": lag_curve,
                    "threshold_anchor": (
                        f"recall_floor={self.recall_floor:.2f} pre-registered "
                        "as 'meaningfully recalled'; the lag→recall curve is "
                        "the observational discovery (the substrate's horizon)"
                    ),
                },
            ),
        ]

        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_kimera = prov.agent("kimera-swm", role="substrate_under_flow_test")
        data_entity = prov.entity(
            f"corpus:{dataset.name}", content_hash=dataset.content_hash,
            n_records=dataset.n_records, kind=dataset.kind,
        )
        activity = prov.activity(
            f"scenario:{self.name}", target=self.target, n_cycles=len(schedule),
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
