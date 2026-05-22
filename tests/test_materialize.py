"""Tests for the scenario materializer — spec → runnable Scenario.

The connective tissue of the authoring pipeline. These pin that an accepted
spec materialises into the right scenario with the spec's threshold, and
that a non-conformant or unmappable spec is refused (no running ungrounded
experiments). Substrate-trajectory specs are used for the deterministic
cases (no corpus read); one corpus case exercises stimulus selection.
"""

from __future__ import annotations

import pytest

from ophamin.authoring import (
    DataSourceRef,
    GroundingRef,
    MaterializationError,
    ScenarioSpec,
    Threshold,
    materialization_plan,
    materialize_spec,
)


def _spec(**overrides) -> ScenarioSpec:
    base = dict(
        title="X", scope="flow", facet="neuro",
        claim_statement="A claim.", operationalization="how.",
        threshold=Threshold("recognition_jaccard_floor", ">=", 0.80, "jaccard"),
        grounding=(GroundingRef("paper", "Tononi 2004", "IIT"),),
        data_source=DataSourceRef("substrate-trajectory", "kimera-swm"),
        invariant_template="recognition",
        tools=("statsmodels",), authored_by="model",
    )
    base.update(overrides)
    return ScenarioSpec(**base)


class TestMaterialize:
    def test_recognition_maps_with_threshold(self):
        mat = materialize_spec(_spec(
            threshold=Threshold("recognition_jaccard_floor", ">=", 0.75, "jaccard")))
        assert mat.scenario_name == "memory-deformation-flow"
        assert type(mat.scenario).__name__ == "MemoryDeformationFlowScenario"
        assert mat.scenario.recognition_floor == 0.75   # spec threshold honoured
        assert mat.needs_substrate is True
        assert mat.scenario.corpus_label == "kimera-swm"

    def test_phi_maps_with_threshold(self):
        mat = materialize_spec(_spec(
            invariant_template="phi",
            threshold=Threshold("phi_floor", ">=", 0.05, "phi")))
        assert mat.scenario_name == "phi-stability-flow"
        assert mat.scenario.phi_floor == 0.05

    def test_manifold_topology_maps(self):
        mat = materialize_spec(_spec(
            scope="point", facet="math", invariant_template="manifold-topology",
            threshold=Threshold("manifold_betti_0_median", "==", 1, "count"),
            data_source=DataSourceRef("substrate-trajectory", "kimera-swm",
                                      detail={"n_cycles": 50})))
        assert mat.scenario_name == "manifold-topology"
        assert mat.scenario.n_cycles == 50

    def test_substrate_trajectory_uses_default_stimuli(self):
        mat = materialize_spec(_spec())
        # 8 curated default stimuli × 3 exposures = 24 cycles
        assert mat.scenario.n_cycles == 24

    def test_ungrounded_spec_refused(self):
        bad = _spec(grounding=(), data_source=DataSourceRef("synthetic", "x"))
        with pytest.raises(MaterializationError) as ei:
            materialize_spec(bad)
        codes = {v["code"] for v in ei.value.violations}
        assert "synthetic_data_forbidden" in codes
        assert "missing_grounding" in codes

    def test_unknown_template_refused(self):
        # Conformant spec but a template with no materialiser.
        spec = _spec(invariant_template="")  # blank template = custom, no materialiser
        with pytest.raises(MaterializationError):
            materialize_spec(spec)


class TestMaterializationPlan:
    def test_acceptable_plan(self):
        plan = materialization_plan(_spec())
        assert plan["acceptable"] is True
        assert plan["scenario_name"] == "memory-deformation-flow"
        assert plan["needs_substrate"] is True
        assert plan["plan"]["metric"] == "recognition_jaccard_floor"
        assert plan["plan"]["threshold"] == 0.80

    def test_non_conformant_plan_returns_violations(self):
        plan = materialization_plan(_spec(grounding=()))
        assert plan["acceptable"] is False
        assert plan["plan"] is None
        assert any(v["code"] == "missing_grounding" for v in plan["violations"])

    def test_unmappable_template_plan_returns_violation(self):
        plan = materialization_plan(_spec(invariant_template=""))
        assert plan["acceptable"] is False
        assert plan["plan"] is None


class TestCorpusSelection:
    def test_corpus_data_source_selects_real_stimuli(self):
        # Exercises real stimulus selection from a registered corpus.
        from ophamin.seeing.corpus import available_corpora
        if not available_corpora().get("enron"):
            pytest.skip("enron corpus not available")
        mat = materialize_spec(_spec(data_source=DataSourceRef("corpus", "enron")))
        assert mat.scenario.corpus_label == "enron (real)"
        # Real stimuli were selected (8 of them) → 24 cycles.
        assert mat.scenario.n_cycles == 24
        assert len(mat.scenario.stimuli) == 8
