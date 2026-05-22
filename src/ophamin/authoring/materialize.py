"""The materializer — turn an accepted ScenarioSpec into a runnable Scenario.

This is the connective tissue that makes the authoring pipeline actually
flow: ``describe → ScenarioSpec → [grounding gate] → materialize → run →
signed proof``. The grounding gate (``validate_spec``) guarantees the spec
is non-synthetic + grounded; the materializer refuses to build anything from
a non-conformant spec, so an ungrounded experiment can never reach a run.

Mapping (invariant_template → concrete Scenario):

  * ``recognition``        → MemoryDeformationFlowScenario (flow, neuro)
  * ``phi``                → PhiStabilityFlowScenario       (flow, neuro)
  * ``manifold-topology``  → ManifoldTopologyScenario       (point, math)

Stimuli come from the spec's real ``data_source``:

  * ``corpus``               → substantial records selected from the named,
                               registered corpus (never synthetic);
  * ``substrate-trajectory`` → the scenario's curated genesis stimuli.

Flow / cycle scenarios need a live substrate adapter to run; the
materializer reports ``needs_substrate`` so the caller wires the
``KimeraAdapter``. No LLM is involved — materialization is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ophamin.authoring.spec import ScenarioSpec
from ophamin.authoring.validation import is_acceptable, validate_spec

# Default stimulus-selection bounds (mirror the parametric corpus runner).
_N_STIMULI = 8
_MIN_BODY, _MAX_BODY = 120, 1500


class MaterializationError(RuntimeError):
    """Raised when a spec cannot be materialised.

    Carries the structured violations (for a non-conformant spec) so the
    caller — a Console, a runner, or an authoring model — gets the same
    actionable punch list the gate produced. No-fallback: we never build a
    scenario from an ungrounded spec.
    """

    def __init__(self, message: str, *, violations: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.violations = violations or []


@dataclass(frozen=True)
class MaterializedScenario:
    """An accepted spec turned into a concrete, runnable scenario."""

    scenario: Any                       # the Scenario instance
    scenario_name: str
    invariant_template: str
    needs_substrate: bool               # flow/cycle → needs KimeraAdapter
    plan: dict[str, Any]                # human-readable build plan (dry-run)


def _select_corpus_stimuli(corpus_name: str, n: int = _N_STIMULI) -> list[str]:
    """Pick ``n`` substantial, distinct records from a registered corpus."""
    from ophamin.seeing.corpus import get_corpus

    corpus = get_corpus(corpus_name)
    out: list[str] = []
    seen: set[str] = set()
    for rec in corpus.records():
        body = (rec.text or "").strip()
        if _MIN_BODY <= len(body) <= _MAX_BODY and body not in seen:
            out.append(body)
            seen.add(body)
        if len(out) >= n:
            break
    return out


def _stimuli_for(spec: ScenarioSpec) -> tuple[list[str], str]:
    """Return (stimuli, corpus_label) from the spec's data source.

    Empty list means "use the scenario's curated defaults" (substrate
    trajectory). Raises MaterializationError if a corpus can't yield enough
    substantial records — a flow proof on too-thin data is not run.
    """
    ds = spec.data_source
    if ds.kind == "corpus":
        stimuli = _select_corpus_stimuli(ds.name)
        if len(stimuli) < _N_STIMULI:
            raise MaterializationError(
                f"corpus {ds.name!r} yielded only {len(stimuli)} suitable "
                f"records (need {_N_STIMULI}); cannot materialise a flow run."
            )
        return stimuli, f"{ds.name} (real)"
    # substrate-trajectory (or any other real source) → curated defaults.
    return [], ds.name or "kimera-genesis"


def materialize_spec(spec: ScenarioSpec, *, validate: bool = True) -> MaterializedScenario:
    """Build a runnable Scenario from an accepted ScenarioSpec.

    Refuses (MaterializationError) a non-conformant spec or an unknown
    invariant template. No-fallback: only grounded, registered, real-data
    specs become scenarios.
    """
    if validate:
        violations = validate_spec(spec)
        if not is_acceptable(violations):
            raise MaterializationError(
                "spec failed the grounding gate; cannot materialise",
                violations=[v.to_dict() for v in violations],
            )

    template = spec.invariant_template
    threshold_value = float(spec.threshold.value)

    if template == "recognition":
        from ophamin.measuring.scenarios import MemoryDeformationFlowScenario

        stimuli, label = _stimuli_for(spec)
        kwargs: dict[str, Any] = {
            "n_exposures": 3, "recognition_floor": threshold_value,
            "corpus_label": label,
        }
        if stimuli:
            kwargs["stimuli"] = tuple(stimuli)
        scen = MemoryDeformationFlowScenario(**kwargs)
        plan = {
            "scenario_class": "MemoryDeformationFlowScenario",
            "scope": "flow", "facet": "neuro",
            "metric": "recognition_jaccard_floor", "threshold": threshold_value,
            "corpus_label": label, "n_stimuli": len(stimuli) or 8,
            "n_exposures": 3, "n_cycles": scen.n_cycles,
        }
        return MaterializedScenario(scen, "memory-deformation-flow", template, True, plan)

    if template == "phi":
        from ophamin.measuring.scenarios import PhiStabilityFlowScenario

        stimuli, label = _stimuli_for(spec)
        kwargs = {"n_passes": 3, "phi_floor": threshold_value, "corpus_label": label}
        if stimuli:
            kwargs["stimuli"] = tuple(stimuli)
        scen = PhiStabilityFlowScenario(**kwargs)
        plan = {
            "scenario_class": "PhiStabilityFlowScenario",
            "scope": "flow", "facet": "neuro",
            "metric": "phi_floor", "threshold": threshold_value,
            "corpus_label": label, "n_stimuli": len(stimuli) or 8,
            "n_passes": 3, "n_cycles": scen.n_cycles,
        }
        return MaterializedScenario(scen, "phi-stability-flow", template, True, plan)

    if template == "manifold-topology":
        from ophamin.measuring.scenarios import ManifoldTopologyScenario

        # n_cycles can be carried in the data-source detail; default modest.
        n_cycles = int(spec.data_source.detail.get("n_cycles", 200))
        scen = ManifoldTopologyScenario(n_cycles=n_cycles)
        plan = {
            "scenario_class": "ManifoldTopologyScenario",
            "scope": "point", "facet": "math",
            "metric": "manifold_betti_0_median", "threshold": threshold_value,
            "n_cycles": n_cycles,
        }
        return MaterializedScenario(scen, "manifold-topology", template, True, plan)

    raise MaterializationError(
        f"invariant_template {template!r} has no materialiser. "
        "Known: recognition / phi / manifold-topology. "
        "(A custom-scored spec must ship its own Scenario subclass.)"
    )


def materialization_plan(spec: ScenarioSpec) -> dict[str, Any]:
    """Validate + describe what would be built — a dry run, no execution.

    Safe over HTTP: validates the spec, and if acceptable builds the
    scenario instance (cheap) to report the exact run plan, without running
    it. Returns ``acceptable`` + violations OR the plan.
    """
    violations = validate_spec(spec)
    if not is_acceptable(violations):
        return {
            "acceptable": False,
            "violations": [v.to_dict() for v in violations],
            "plan": None,
        }
    try:
        mat = materialize_spec(spec, validate=False)
    except MaterializationError as exc:
        return {
            "acceptable": False,
            "violations": exc.violations or [{
                "field": "invariant_template", "code": "no_materialiser",
                "severity": "error", "message": str(exc),
                "fix": "Use a template with a materialiser, or ship a Scenario subclass.",
            }],
            "plan": None,
        }
    return {
        "acceptable": True,
        "violations": [],
        "scenario_name": mat.scenario_name,
        "needs_substrate": mat.needs_substrate,
        "plan": mat.plan,
    }
