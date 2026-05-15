"""Experiment orchestration — parent/child runs that apply the six pillars.

This is the integration layer. ``ExperimentRunner`` exercises a substrate over
many cycles, applies the pillars to the resulting metric stream, and records
everything through the lineage store with a PROV-O graph.

Run hierarchy mirrors the blueprint's parent/child structure:

    parent run   the overarching experiment (one sweep)
    child run    one sweep point — cycles + per-run pillars (O, A, N)
    parent-level the cross-child pillars (I cumulative synthesis, M effects)

Pillars that are not applicable to a given configuration are reported with
``status="skipped"`` and an explicit reason — never silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ophamin.measuring.pillars.adaptive.sprt import MixtureSPRT
from ophamin.config.sweep import SweepSpec, get_in
from ophamin.measuring.pillars.diagnostics.anticipatory import (
    AnticipatoryFailureClassifier,
    ConformalPredictor,
)
from ophamin.measuring.pillars.diagnostics.inertia import CognitiveInertiaMeter
from ophamin.measuring.pillars.effects.mea import MultiExperimentAnalysis
from ophamin.measuring.pillars.effects.mixed_effects import RandomInterceptModel
from ophamin.measuring.metrics.tiers import MetricBundle
from ophamin.measuring.pillars.observability.spc import IndividualsChart
from ophamin.measuring.pillars.observability.srm import SRMDetector
from ophamin.comparing.provenance.lineage import LineageStore, make_run_id
from ophamin.comparing.provenance.prov import ProvenanceGraph
from ophamin.measuring.pillars.robustness.cross_validation import monte_carlo_cv
from ophamin.seeing.substrate.base import SubstrateUnderTest
from ophamin.measuring.pillars.synthesis.cma import CumulativeMetaAnalysis

_KNOWN_BAD_HALTS = {"rollback", "amplitude_death", "collapse"}


@dataclass
class PillarOutcome:
    """The result of applying one pillar to a run."""

    pillar: str            # e.g. "O.spc", "A.msprt", "I.cma"
    status: str            # "ok" | "alert" | "skipped"
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pillar": self.pillar,
            "status": self.status,
            "summary": self.summary,
            "detail": self.detail,
        }


@dataclass
class RunResult:
    """One child run: its cycles, metric summary and per-run pillar outcomes."""

    run_id: str
    parent_run_id: str | None
    config: dict[str, Any]
    sweep_point: dict[str, Any]
    n_cycles: int
    n_warmup: int
    metric_summary: dict[str, float]
    pillars: list[PillarOutcome] = field(default_factory=list)
    cycle_metrics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "sweep_point": self.sweep_point,
            "n_cycles": self.n_cycles,
            "n_warmup": self.n_warmup,
            "metric_summary": self.metric_summary,
            "pillars": [p.to_dict() for p in self.pillars],
        }


@dataclass
class ExperimentResult:
    """A full sweep: the parent run plus its children and cross-child pillars."""

    parent_run_id: str
    name: str
    children: list[RunResult] = field(default_factory=list)
    pillars: list[PillarOutcome] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"experiment '{self.name}'  parent={self.parent_run_id}  "
            f"children={len(self.children)}"
        ]
        for child in self.children:
            alerts = [p.pillar for p in child.pillars if p.status == "alert"]
            tag = f"  [alerts: {', '.join(alerts)}]" if alerts else ""
            lines.append(f"  child {child.run_id}  point={child.sweep_point}{tag}")
        for p in self.pillars:
            lines.append(f"  {p.pillar:<16} [{p.status}] {p.summary}")
        return "\n".join(lines)


def _series(bundles: list[MetricBundle], flat_key: str) -> np.ndarray:
    """Extract a finite numeric series for one flattened metric key."""
    vals: list[float] = []
    for b in bundles:
        v = b.flat().get(flat_key)
        if isinstance(v, (int, float)) and np.isfinite(v):
            vals.append(float(v))
    return np.asarray(vals, dtype=float)


class ExperimentRunner:
    """Runs sweeps and single runs, applying the OFAMIN pillars and recording lineage."""

    def __init__(
        self,
        lineage_store: LineageStore,
        primary_metric: str = "t1.gauge.phi",
        latency_metric: str = "t1.timer.cycle_latency_ns.mean",
    ) -> None:
        self.lineage = lineage_store
        self.primary_metric = primary_metric
        self.latency_metric = latency_metric

    # -- single (child) run -------------------------------------------------

    def run_single(
        self,
        sut: SubstrateUnderTest,
        config: dict[str, Any],
        stimuli: list[Any],
        *,
        parent_run_id: str | None = None,
        sweep_point: dict[str, Any] | None = None,
        diagnostics: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> RunResult:
        """Exercise the substrate over many cycles and apply the per-run pillars."""
        sweep_point = sweep_point or {}
        diagnostics = diagnostics or {}
        n_cycles = int(get_in(config, "experiment.cycles_per_run", 200))
        n_warmup = int(get_in(config, "experiment.warmup_cycles", 1))
        seed = int(get_in(config, "experiment.seed", 0))
        substrate_params = dict(get_in(config, "substrate.params", {}) or {})
        variant_split = substrate_params.pop("variant_split", None)
        if n_cycles < 2:
            raise ValueError("experiment.cycles_per_run must be >= 2")

        rng = np.random.default_rng(seed)
        sut.reset()

        bundles: list[MetricBundle] = []
        variants: list[Any] = []
        halts: list[str | None] = []
        successes: list[bool] = []

        for i in range(n_cycles):
            stimulus = stimuli[i % len(stimuli)] if stimuli else None
            params = dict(substrate_params)
            if variant_split:
                labels = list(variant_split)
                probs = np.array([variant_split[k] for k in labels], dtype=float)
                probs = probs / probs.sum()
                variant = labels[int(rng.choice(len(labels), p=probs))]
                params["variant"] = variant
                variants.append(variant)
            result = sut.run_cycle(stimulus, params)
            bundle = result.to_metric_bundle()
            bundle.cycle_index = i
            bundles.append(bundle)
            halts.append(result.halt_mode)
            successes.append(result.success)

        measured = bundles[n_warmup:] if n_warmup < len(bundles) else bundles
        primary = _series(measured, self.primary_metric)
        metric_summary = self._summarise(measured)

        pillars: list[PillarOutcome] = []
        pillars.append(self._pillar_spc(config, measured))
        pillars.append(self._pillar_srm(config, variants[n_warmup:] if variant_split else []))
        pillars.append(self._pillar_msprt(config, primary))
        pillars.append(self._pillar_mccv(config, primary))
        if diagnostics.get("anticipatory_failure"):
            pillars.append(
                self._diag_anticipatory(measured, halts[n_warmup:], successes[n_warmup:])
            )
        if diagnostics.get("cognitive_inertia"):
            pillars.append(self._diag_inertia(measured, successes[n_warmup:]))

        rid = run_id or make_run_id({"config": config, "sweep_point": sweep_point})
        run_result = RunResult(
            run_id=rid,
            parent_run_id=parent_run_id,
            config=config,
            sweep_point=sweep_point,
            n_cycles=n_cycles,
            n_warmup=n_warmup,
            metric_summary=metric_summary,
            pillars=pillars,
            cycle_metrics=[b.flat() for b in bundles],
        )
        self._record(run_result, sut, parent_run_id)
        return run_result

    # -- sweep (parent) run -------------------------------------------------

    def run_sweep(
        self, sut: SubstrateUnderTest, sweep: SweepSpec
    ) -> ExperimentResult:
        """Run every sweep point as a child run, then apply the cross-child pillars."""
        parent_run_id = make_run_id(
            {"name": sweep.parent_name, "grid": sweep.grid}, unique=True
        )
        children: list[RunResult] = []
        for child_config, point in sweep.expand():
            child = self.run_single(
                sut,
                child_config,
                sweep.stimuli,
                parent_run_id=parent_run_id,
                sweep_point=point,
                diagnostics=sweep.diagnostics,
            )
            children.append(child)

        parent_pillars: list[PillarOutcome] = []
        parent_pillars.append(self._pillar_cma(children))
        parent_pillars.append(self._pillar_mixed_effects(children))
        parent_pillars.append(self._pillar_mea(sweep, children))

        experiment = ExperimentResult(
            parent_run_id=parent_run_id,
            name=sweep.parent_name,
            children=children,
            pillars=parent_pillars,
        )
        self._record_parent(experiment, sut, sweep)
        return experiment

    # -- per-run pillars ----------------------------------------------------

    def _summarise(self, bundles: list[MetricBundle]) -> dict[str, float]:
        keys = set()
        for b in bundles:
            keys.update(k for k, v in b.flat().items() if isinstance(v, (int, float)))
        summary: dict[str, float] = {}
        for k in sorted(keys):
            s = _series(bundles, k)
            if s.size:
                summary[f"{k}.mean"] = float(s.mean())
                summary[f"{k}.std"] = float(s.std(ddof=1)) if s.size > 1 else 0.0
        return summary

    def _pillar_spc(self, config: dict, bundles: list[MetricBundle]) -> PillarOutcome:
        series = _series(bundles, self.latency_metric)
        if series.size < 2:
            return PillarOutcome(
                "O.spc", "skipped", f"no '{self.latency_metric}' series available"
            )
        sigma_limit = float(get_in(config, "observability.spc.sigma_limit", 3.0))
        chart = IndividualsChart(sigma_limit=sigma_limit).fit(series)
        result = chart.evaluate(series)
        special = sorted(
            set(result.out_of_control) | {v.index for v in result.violations}
        )
        status = "alert" if special else "ok"
        return PillarOutcome(
            "O.spc",
            status,
            f"latency control chart — {len(special)} special-cause point(s); "
            + result.summary(),
            {
                "special_cause_indices": special,
                "center": result.center,
                "ucl": result.ucl,
                "lcl": result.lcl,
                "violations": [
                    {"rule": v.rule, "index": v.index, "description": v.description}
                    for v in result.violations
                ],
            },
        )

    def _pillar_srm(self, config: dict, variants: list[Any]) -> PillarOutcome:
        expected = get_in(config, "observability.srm.expected_ratios", None)
        if not expected or not variants:
            return PillarOutcome(
                "O.srm",
                "skipped",
                "no variant assignment in cycles (set substrate.params.variant_split)",
            )
        alpha = float(get_in(config, "observability.srm.alpha", 0.001))
        observed: dict[str, int] = {k: 0 for k in expected}
        for v in variants:
            key = str(v)
            if key in observed:
                observed[key] += 1
        detector = SRMDetector(expected_ratios={str(k): float(v) for k, v in expected.items()}, alpha=alpha)
        result = detector.check(observed)
        return PillarOutcome(
            "O.srm",
            "alert" if result.is_mismatch else "ok",
            result.summary(),
            {
                "chi2": result.chi2,
                "pvalue": result.pvalue,
                "observed": result.observed,
                "expected": result.expected,
            },
        )

    def _pillar_msprt(self, config: dict, primary: np.ndarray) -> PillarOutcome:
        if primary.size < 3:
            return PillarOutcome("A.msprt", "skipped", "primary metric series too short")
        # H0: the metric mean equals its early-window baseline; detect drift away.
        baseline_window = max(2, primary.size // 10)
        mu0 = float(primary[:baseline_window].mean())
        sigma = float(primary.std(ddof=1)) or 1e-6
        tau2 = float(get_in(config, "adaptive.msprt_mixing_variance", 1.0)) * sigma**2
        alpha = float(get_in(config, "adaptive.msprt_alpha", 0.05))
        msprt = MixtureSPRT(mu0=mu0, sigma=sigma, tau2=tau2)
        cycles_to_decision = None
        for i, x in enumerate(primary):
            msprt.update(float(x))
            if cycles_to_decision is None and msprt.decision(alpha) == "reject_h0":
                cycles_to_decision = i + 1
        decided = cycles_to_decision is not None
        return PillarOutcome(
            "A.msprt",
            "alert" if decided else "ok",
            f"sequential drift monitor: "
            + (
                f"H0 rejected after {cycles_to_decision} cycles"
                if decided
                else "no significant drift detected"
            )
            + f" (p={msprt.always_valid_pvalue:.4g}, mu0={mu0:.4g})",
            {
                "baseline_mu0": mu0,
                "always_valid_pvalue": msprt.always_valid_pvalue,
                "cycles_to_decision": cycles_to_decision,
                "decision": msprt.decision(alpha),
            },
        )

    def _pillar_mccv(self, config: dict, primary: np.ndarray) -> PillarOutcome:
        if primary.size < 6:
            return PillarOutcome("N.mccv", "skipped", "primary metric series too short")
        n_iter = int(get_in(config, "robustness.n_iterations", 200))
        train_frac = float(get_in(config, "robustness.train_fraction", 0.7))
        seed = int(get_in(config, "experiment.seed", 0))
        # evaluator: the test-subset mean. Low spread across random shuffles =>
        # the metric does not depend on which cycles, or in which order, are seen.
        result = monte_carlo_cv(
            list(primary),
            evaluator=lambda _train, test: float(np.mean(test)),
            n_iterations=n_iter,
            train_fraction=train_frac,
            rng=seed,
        )
        return PillarOutcome(
            "N.mccv",
            "ok",
            f"order-robustness of {self.primary_metric}: {result.summary()}",
            {
                "mean": result.mean,
                "std": result.std,
                "ci_low": result.ci_low,
                "ci_high": result.ci_high,
                "n_splits": result.n_splits,
            },
        )

    # -- diagnostics --------------------------------------------------------

    def _diag_anticipatory(
        self,
        bundles: list[MetricBundle],
        halts: list[str | None],
        successes: list[bool],
    ) -> PillarOutcome:
        phi = _series(bundles, self.primary_metric)
        drift = _series(bundles, "t2.drift_score")
        if phi.size < 12 or drift.size != phi.size:
            return PillarOutcome(
                "diag.anticipatory",
                "skipped",
                "primary-metric / drift-score series unavailable or too short",
            )
        # features (cycle position + drift) -> outcome (the primary metric)
        features = np.column_stack([np.arange(phi.size, dtype=float), drift])
        split = max(8, phi.size // 3)
        if split >= phi.size - 1:
            return PillarOutcome(
                "diag.anticipatory", "skipped", "not enough cycles to calibrate and assess"
            )
        conformal = ConformalPredictor(confidence_level=0.9).calibrate(
            features[:split], phi[:split], random_state=0
        )
        classifier = AnticipatoryFailureClassifier(conformal)
        known_bad = {"amplitude_death", "rollback", "collapse"}
        for idx in range(split, phi.size):
            known = halts[idx] in known_bad if idx < len(halts) else False
            classifier.assess(features[idx], float(phi[idx]), known_failure_signal=known)
        report = classifier.report()
        status = (
            "alert"
            if (report.missed_failures or report.world_model_gap > 0.25)
            else "ok"
        )
        return PillarOutcome(
            "diag.anticipatory",
            status,
            report.summary(),
            {
                "world_model_gap": report.world_model_gap,
                "empirical_miscoverage": report.empirical_miscoverage,
                "world_model_mae": report.world_model_mae,
                "missed_failures": report.missed_failures,
                "false_alarms": report.false_alarms,
                "predicted_counts": report.predicted_counts,
                "observed_counts": report.observed_counts,
            },
        )

    def _diag_inertia(
        self, bundles: list[MetricBundle], successes: list[bool]
    ) -> PillarOutcome:
        evidence = _series(bundles, "t2.drift_score")
        observed_shift = np.abs(_series(bundles, "t3.prime_deformation_delta"))
        if evidence.size < 3 or observed_shift.size != evidence.size:
            return PillarOutcome(
                "diag.inertia", "skipped", "drift-score / deformation series unavailable"
            )
        meter = CognitiveInertiaMeter()
        for i in range(evidence.size):
            meter.observe(
                evidence_strength=float(evidence[i]),
                expected_shift=float(evidence[i]),
                observed_shift=float(observed_shift[i]),
                accepted=bool(successes[i]) if i < len(successes) else True,
            )
        report = meter.report()
        return PillarOutcome(
            "diag.inertia",
            "alert" if report.stagnant else "ok",
            report.summary(),
            {
                "inertia_index": report.inertia_index,
                "defensive_rejection_rate": report.defensive_rejection_rate,
                "bayesian_adaptation_rate": report.bayesian_adaptation_rate,
                "balance": report.balance,
            },
        )

    # -- parent-level pillars ----------------------------------------------

    def _pillar_cma(self, children: list[RunResult]) -> PillarOutcome:
        key_mean = f"{self.primary_metric}.mean"
        key_std = f"{self.primary_metric}.std"
        cma = CumulativeMetaAnalysis(random_effects=True, tau2_fixed_after=8)
        used = 0
        for child in children:
            mean = child.metric_summary.get(key_mean)
            std = child.metric_summary.get(key_std)
            n = max(1, child.n_cycles - child.n_warmup)
            if mean is None or std is None:
                continue
            variance = (std**2) / n if std > 0 else 1e-9
            cma.add(float(mean), float(variance))
            used += 1
        if used < 1:
            return PillarOutcome(
                "I.cma", "skipped", f"no '{key_mean}' available across child runs"
            )
        result = cma.result()
        return PillarOutcome(
            "I.cma",
            "ok",
            f"cumulative synthesis over {used} child run(s): {result.summary()}; "
            f"first stable significance at k="
            f"{cma.first_significant_k()}",
            {
                "estimate": result.estimate,
                "ci_low": result.ci_low,
                "ci_high": result.ci_high,
                "tau2": result.tau2,
                "i_squared": result.i_squared,
                "first_significant_k": cma.first_significant_k(),
                "trajectory": [
                    {"k": r.k, "estimate": r.estimate, "ci_low": r.ci_low, "ci_high": r.ci_high}
                    for r in cma.trajectory()
                ],
            },
        )

    def _numeric_sweep_keys(self, children: list[RunResult]) -> list[str]:
        if not children:
            return []
        keys = list(children[0].sweep_point.keys())
        numeric = []
        for k in keys:
            if all(isinstance(c.sweep_point.get(k), (int, float)) for c in children):
                numeric.append(k)
        return numeric

    def _pillar_mixed_effects(self, children: list[RunResult]) -> PillarOutcome:
        if len(children) < 2:
            return PillarOutcome(
                "M.mixed_effects", "skipped", "need >= 2 child runs for a grouped model"
            )
        numeric_keys = self._numeric_sweep_keys(children)
        if not numeric_keys:
            return PillarOutcome(
                "M.mixed_effects",
                "skipped",
                "no numeric swept parameters to use as fixed effects",
            )
        y: list[float] = []
        X: list[list[float]] = []
        groups: list[str] = []
        for child in children:
            for row in child.cycle_metrics[child.n_warmup :]:
                val = row.get(self.primary_metric)
                if not isinstance(val, (int, float)) or not np.isfinite(val):
                    continue
                y.append(float(val))
                X.append([float(child.sweep_point[k]) for k in numeric_keys])
                groups.append(child.run_id)
        if len(set(groups)) < 2 or len(y) < len(numeric_keys) + 3:
            return PillarOutcome(
                "M.mixed_effects", "skipped", "insufficient pooled cycles for the model"
            )
        model = RandomInterceptModel().fit(
            np.array(y), np.array(X), groups, feature_names=numeric_keys
        )
        return PillarOutcome(
            "M.mixed_effects",
            "ok",
            f"random-intercept model on '{self.primary_metric}' "
            f"(groups=child runs): ICC={model.icc:.4f}, "
            f"sigma_u^2={model.sigma_u2:.4g}, sigma_e^2={model.sigma_e2:.4g}",
            {
                "icc": model.icc,
                "sigma_u2": model.sigma_u2,
                "sigma_e2": model.sigma_e2,
                "fixed_effects": dict(
                    zip(model.feature_names, [float(b) for b in model.fixed_effects])
                ),
                "fixed_effects_se": dict(
                    zip(model.feature_names, [float(s) for s in model.fixed_effects_se])
                ),
                "converged": model.converged,
            },
        )

    def _pillar_mea(
        self, sweep: SweepSpec, children: list[RunResult]
    ) -> PillarOutcome:
        if len(sweep.grid) < 2:
            return PillarOutcome(
                "M.mea", "skipped", "sweep grid has < 2 dimensions — no overlap to analyse"
            )
        if len(children) < 4:
            return PillarOutcome(
                "M.mea", "skipped", "MEA needs >= 4 child runs"
            )
        keys = list(sweep.grid)
        assignments = {
            k: [str(c.sweep_point.get(k)) for c in children] for k in keys
        }
        key_mean = f"{self.primary_metric}.mean"
        outcome = [c.metric_summary.get(key_mean) for c in children]
        if any(o is None for o in outcome):
            return PillarOutcome(
                "M.mea", "skipped", f"'{key_mean}' missing for some child runs"
            )
        try:
            mea = MultiExperimentAnalysis(assignments, [float(o) for o in outcome])
            marginal = {}
            for exp in keys:
                try:
                    effects = mea.marginal_effect(exp)
                    marginal[exp] = {
                        str(v): {"effect": e.effect, "p_value": e.p_value}
                        for v, e in effects.items()
                    }
                except ValueError:
                    marginal[exp] = {"_note": "insufficient units per arm"}
            interaction = None
            if len(keys) >= 2:
                try:
                    inter = mea.interaction_test(keys[0], keys[1])
                    interaction = {
                        "experiments": [keys[0], keys[1]],
                        "f_stat": inter.f_stat,
                        "p_value": inter.p_value,
                    }
                except ValueError:
                    interaction = {"_note": "interaction test not estimable"}
        except ValueError as exc:
            return PillarOutcome("M.mea", "skipped", f"MEA not estimable: {exc}")
        return PillarOutcome(
            "M.mea",
            "ok",
            f"multi-experiment analysis over {len(keys)} overlapping factors, "
            f"{len(children)} child runs",
            {"marginal_effects": marginal, "interaction": interaction},
        )

    # -- lineage recording --------------------------------------------------

    def _record(
        self, run: RunResult, sut: SubstrateUnderTest, parent_run_id: str | None
    ) -> None:
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent("ophamin", role="experimentation_framework")
        agent_sut = prov.agent(sut.name, role="substrate_under_test", **sut.metadata())
        config_entity = prov.entity(f"config:{run.run_id}", **{"sweep_point": run.sweep_point})
        activity = prov.activity(
            f"run:{run.run_id}", cycles=run.n_cycles, warmup=run.n_warmup
        )
        result_entity = prov.entity(
            f"result:{run.run_id}", metric_summary_keys=sorted(run.metric_summary)
        )
        prov.used(activity, config_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_sut)
        prov.was_generated_by(result_entity, activity)
        prov.was_attributed_to(result_entity, agent_sut)
        if parent_run_id:
            prov.was_informed_by(activity, prov.activity(f"run:{parent_run_id}"))

        self.lineage.record_run(
            run_id=run.run_id,
            config=run.config,
            sut_metadata=sut.metadata(),
            metrics={
                "metric_summary": run.metric_summary,
                "pillars": [p.to_dict() for p in run.pillars],
            },
            provenance=prov,
            parent_run_id=parent_run_id,
        )

    def _record_parent(
        self, experiment: ExperimentResult, sut: SubstrateUnderTest, sweep: SweepSpec
    ) -> None:
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent("ophamin", role="experimentation_framework")
        agent_sut = prov.agent(sut.name, role="substrate_under_test", **sut.metadata())
        activity = prov.activity(
            f"run:{experiment.parent_run_id}",
            kind="sweep",
            n_children=len(experiment.children),
        )
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_sut)
        for child in experiment.children:
            child_entity = prov.entity(f"result:{child.run_id}")
            prov.was_derived_from(
                prov.entity(f"result:{experiment.parent_run_id}"), child_entity
            )
        self.lineage.record_run(
            run_id=experiment.parent_run_id,
            config={"grid": sweep.grid, "base_config": sweep.base_config},
            sut_metadata=sut.metadata(),
            metrics={
                "name": experiment.name,
                "children": [c.run_id for c in experiment.children],
                "pillars": [p.to_dict() for p in experiment.pillars],
            },
            provenance=prov,
            parent_run_id=None,
        )
