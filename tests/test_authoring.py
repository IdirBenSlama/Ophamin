"""Tests for the authoring layer — grounded ScenarioSpec + the grounding gate.

The gate's whole job: make an ungrounded or synthetic scenario impossible,
no matter who wrote it. These pin that contract.
"""

from __future__ import annotations

from ophamin.authoring import (
    DataSourceRef,
    GroundingRef,
    ScenarioSpec,
    Threshold,
    available_capabilities,
    is_acceptable,
    validate_spec,
    validate_spec_dict,
)


def _grounded(**overrides) -> ScenarioSpec:
    """A clean, grounded spec; override one field to test a single gate."""
    base = dict(
        title="Memory-as-deformation on real email",
        scope="flow",
        facet="neuro",
        claim_statement="Recognition holds across re-exposures on real text.",
        operationalization="min concept-set Jaccard over re-exposure pairs.",
        threshold=Threshold("recognition_jaccard_floor", ">=", 0.80, "jaccard"),
        grounding=(GroundingRef("paper", "Tononi 2004", "IIT"),),
        data_source=DataSourceRef("corpus", "enron"),
        invariant_template="recognition",
        tools=("statsmodels",),
        authored_by="model",
    )
    base.update(overrides)
    return ScenarioSpec(**base)


class TestCapabilities:
    def test_manifest_is_live_and_complete(self):
        caps = available_capabilities()
        # Real corpora from the live registry, not a hand list.
        names = {c["name"] for c in caps["corpora"]}
        assert {"enron", "linux", "flores", "cyber", "financial"} <= names
        assert caps["scopes"] == ["point", "flow", "campaign", "vertical"]
        assert "neuro" in caps["facets"] and "engineering" in caps["facets"]
        assert any(t["name"] == "recognition" for t in caps["invariant_templates"])
        assert any(t["id"] == "statsmodels" for t in caps["tools"])
        assert any(s["id"] == "osf-registered-reports" for s in caps["standards"])
        # Scenarios mirror the live scenario registry.
        scen_names = {s["name"] for s in caps["scenarios"]}
        assert "memory-deformation-flow" in scen_names


class TestGroundingGate:
    def test_grounded_spec_passes(self):
        assert is_acceptable(validate_spec(_grounded()))

    def test_synthetic_data_forbidden(self):
        v = validate_spec(_grounded(data_source=DataSourceRef("synthetic", "x")))
        assert not is_acceptable(v)
        assert any(x.code == "synthetic_data_forbidden" for x in v)

    def test_inline_and_mock_also_forbidden(self):
        for kind in ("inline", "mock", "fabricated", "hardcoded", "stub"):
            v = validate_spec(_grounded(data_source=DataSourceRef(kind, "x")))
            assert any(x.code == "synthetic_data_forbidden" for x in v), kind

    def test_missing_grounding_rejected(self):
        v = validate_spec(_grounded(grounding=()))
        assert not is_acceptable(v)
        assert any(x.code == "missing_grounding" for x in v)

    def test_non_falsifiable_threshold_rejected(self):
        v = validate_spec(_grounded(
            threshold=Threshold("", "~~", "high", "")))
        codes = {x.code for x in v}
        assert "missing_metric" in codes
        assert "bad_comparator" in codes
        assert "non_numeric_threshold" in codes
        assert not is_acceptable(v)

    def test_unknown_corpus_rejected(self):
        v = validate_spec(_grounded(data_source=DataSourceRef("corpus", "nope")))
        assert any(x.code == "unknown_corpus" for x in v)

    def test_unknown_template_and_tool_rejected(self):
        v = validate_spec(_grounded(invariant_template="nope", tools=("fake",)))
        codes = {x.code for x in v}
        assert "unknown_template" in codes
        assert "unknown_tool" in codes

    def test_bad_scope_and_facet_rejected(self):
        v = validate_spec(_grounded(scope="nope", facet="nope"))
        codes = {x.code for x in v}
        assert "bad_scope" in codes
        assert "bad_facet" in codes

    def test_substrate_trajectory_is_real_data(self):
        # A substrate trajectory is a real source (not synthetic) — passes.
        v = validate_spec(_grounded(
            data_source=DataSourceRef("substrate-trajectory", "kimera-swm")))
        assert is_acceptable(v)


class TestSpecRoundTrip:
    def test_to_from_dict(self):
        s = _grounded()
        d = s.to_dict()
        s2 = ScenarioSpec.from_dict(d)
        assert s2.to_dict() == d

    def test_validate_spec_dict_clean(self):
        result = validate_spec_dict(_grounded().to_dict())
        assert result["acceptable"] is True
        assert result["violations"] == []
        assert result["spec"]["data_source"]["name"] == "enron"

    def test_validate_spec_dict_malformed_is_finding_not_crash(self):
        # A wildly malformed dict surfaces as violations, never an exception.
        result = validate_spec_dict({"threshold": "not-a-dict"})
        assert result["acceptable"] is False
        assert len(result["violations"]) >= 1
