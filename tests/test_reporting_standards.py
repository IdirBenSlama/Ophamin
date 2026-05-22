"""Tests for the reporting gate — standards coverage + nomenclature.

The output analog of the authoring grounding gate: a well-formed signed
proof is conformant and declares its standards; a malformed one fails the
nomenclature checks with an actionable list.
"""

from __future__ import annotations

from ophamin.reporting.standards import (
    OUTPUT_FORMATS,
    REPORT_STANDARDS,
    report_conformance,
    report_standards_registry,
)


def _good_proof(**overrides):
    p = {
        "proof_id": "a" * 64,
        "claim": {
            "statement": "Recognition holds across re-exposures.",
            "threshold": {"metric": "recognition_jaccard_floor",
                          "comparator": ">=", "value": 0.80},
        },
        "verdict": {"outcome": "VALIDATED", "observed_value": 0.86,
                    "reasoning": "floor 0.86 over 24 pairs"},
        "evidence": [{"statistic_name": "recognition_jaccard_floor",
                      "statistic_value": 0.86, "detail": {"n_pairs": 24}}],
        "signature": "deadbeef",
        "provenance": {"agents": []},
        "preregistration": {"config_hash": "x", "analysis_plan": "stream + score"},
        "data": {"datasets": [{"name": "enron", "content_hash": "c0ffee"}]},
        "identity": {"created_at": "2026-05-22T10:00:00+00:00"},
    }
    p.update(overrides)
    return p


class TestRegistry:
    def test_registry_lists_standards_and_formats(self):
        reg = report_standards_registry()
        ids = {s["id"] for s in reg["standards"]}
        assert {"in-toto/DSSE", "w3c-prov-o", "osf-registered-reports",
                "mlcommons-croissant", "stanford-helm", "ro-crate"} <= ids
        assert "markdown" in reg["output_formats"]
        assert "pdf" in reg["output_formats"]
        assert reg["verdict_vocabulary"] == ["VALIDATED", "REFUTED", "INCONCLUSIVE"]
        assert "snake_case" in reg["metric_convention"]


class TestConformance:
    def test_well_formed_proof_is_conformant(self):
        r = report_conformance(_good_proof())
        assert r["conformant"] is True
        assert not [i for i in r["nomenclature"] if not i["satisfied"]]

    def test_well_formed_proof_satisfies_all_standards(self):
        r = report_conformance(_good_proof())
        # The fixture carries signature/provenance/prereg/datasets/evidence-detail.
        assert set(r["standards_satisfied"]) == {s.id for s in REPORT_STANDARDS}
        assert r["standards_missing"] == []

    def test_croissant_reads_nested_datasets(self):
        # Datasets live under data.datasets in the serialised record.
        r = report_conformance(_good_proof())
        assert "mlcommons-croissant" in r["standards_satisfied"]
        # Remove the content_hash -> Croissant drops out.
        bad = _good_proof(data={"datasets": [{"name": "x"}]})
        r2 = report_conformance(bad)
        assert "mlcommons-croissant" in r2["standards_missing"]

    def test_bad_metric_naming_flagged(self):
        bad = _good_proof(claim={
            "statement": "x",
            "threshold": {"metric": "BadMetricName", "comparator": ">=", "value": 0.5},
        })
        r = report_conformance(bad)
        assert r["conformant"] is False
        fails = {i["id"] for i in r["nomenclature"] if not i["satisfied"]}
        assert "metric_is_snake_case" in fails

    def test_bad_verdict_vocabulary_flagged(self):
        bad = _good_proof(verdict={"outcome": "MAYBE", "observed_value": 1})
        r = report_conformance(bad)
        fails = {i["id"] for i in r["nomenclature"] if not i["satisfied"]}
        assert "verdict_vocabulary" in fails

    def test_non_hash_proof_id_flagged(self):
        r = report_conformance(_good_proof(proof_id="not-a-hash!"))
        fails = {i["id"] for i in r["nomenclature"] if not i["satisfied"]}
        assert "proof_id_is_content_hash" in fails

    def test_unsigned_proof_misses_in_toto(self):
        r = report_conformance(_good_proof(signature=""))
        assert "in-toto/DSSE" in r["standards_missing"]

    def test_bundle_name_requires_date_and_verdict(self):
        bad = _good_proof(identity={"created_at": "not-a-date"})
        r = report_conformance(bad)
        fails = {i["id"] for i in r["nomenclature"] if not i["satisfied"]}
        assert "bundle_name_derivable" in fails

    def test_output_formats_reported(self):
        r = report_conformance(_good_proof())
        assert set(r["output_formats"]) == set(OUTPUT_FORMATS)


class TestRealCorpusProof:
    def test_a_real_signed_proof_is_conformant(self):
        # Validate the gate against the actual corpus, not just fixtures.
        import json
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / "proofs"
        proofs = list(root.rglob("proof.json"))
        if not proofs:
            import pytest
            pytest.skip("no signed proofs in corpus")
        sample = json.loads(proofs[0].read_text(encoding="utf-8"))
        r = report_conformance(sample)
        # A real signed proof must pass nomenclature.
        assert r["conformant"] is True, [
            i for i in r["nomenclature"] if not i["satisfied"]
        ]
        # And satisfy the core attestation standards.
        assert "in-toto/DSSE" in r["standards_satisfied"]
        assert "w3c-prov-o" in r["standards_satisfied"]
