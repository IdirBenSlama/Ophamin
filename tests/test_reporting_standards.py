"""Tests for the reporting gate — standards coverage + nomenclature.

CR7: the standards checks are SUBSTANTIVE, not structural-presence. A proof
that merely has the right *blocks* but empty/short/ill-formed content fails;
a proof whose content actually meets each standard passes. These tests pin
both — the real checks + the honest RO-Crate bundle-level boundary.
"""

from __future__ import annotations

import pytest

from ophamin.reporting.standards import (
    OUTPUT_FORMATS,
    REPORT_STANDARDS,
    report_conformance,
    report_standards_registry,
)


def _good_proof(**overrides):
    """A proof whose CONTENT actually satisfies every record-level standard:
    a real 64-hex signature, a PROV-O graph with agent+activity+entity, a
    prereg whose preregistered_at strictly precedes created_at, a complete
    dataset card, and substantive (multi-key) evidence detail."""
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
                      "statistic_value": 0.86,
                      "detail": {"n_pairs": 24, "scope": "flow",
                                 "per_stimulus_floor": {"0": 0.9}}}],
        "signature": "b" * 64,
        "provenance": {"agent": {"a": {}}, "activity": {"x": {}}, "entity": {"e": {}}},
        "preregistration": {"config_hash": "x", "analysis_plan": "stream + score",
                            "preregistered_at": "2026-05-22T09:59:59+00:00"},
        "data": {"datasets": [{"name": "enron", "content_hash": "c0ffee",
                               "n_records": 100, "source": "kimera", "kind": "corpus"}]},
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

    def test_record_level_standards_satisfied_except_ro_crate(self):
        # All record-verifiable standards pass on a substantively-good proof;
        # RO-Crate is bundle-level, so it's NOT satisfied without a bundle_dir.
        r = report_conformance(_good_proof())
        record_level = {s.id for s in REPORT_STANDARDS} - {"ro-crate"}
        assert record_level <= set(r["standards_satisfied"])
        assert "ro-crate" in r["standards_missing"]

    def test_ro_crate_satisfied_with_real_bundle(self, tmp_path):
        (tmp_path / "proof.json").write_text("{}", encoding="utf-8")
        (tmp_path / "proof.md").write_text("# proof", encoding="utf-8")
        r = report_conformance(_good_proof(), bundle_dir=str(tmp_path))
        assert "ro-crate" in r["standards_satisfied"]

    def test_ro_crate_missing_when_renders_absent(self, tmp_path):
        (tmp_path / "proof.json").write_text("{}", encoding="utf-8")  # json only
        r = report_conformance(_good_proof(), bundle_dir=str(tmp_path))
        assert "ro-crate" in r["standards_missing"]


class TestSubstantiveChecks:
    """The CR7 core: real content, not just block-presence."""

    def test_short_signature_fails_in_toto(self):
        r = report_conformance(_good_proof(signature="deadbeef"))  # 8 hex
        assert "in-toto/DSSE" in r["standards_missing"]

    def test_ed25519_length_signature_passes_in_toto(self):
        r = report_conformance(_good_proof(signature="c" * 128))
        assert "in-toto/DSSE" in r["standards_satisfied"]

    def test_empty_provenance_block_fails_prov_o(self):
        # the old structural check passed on any truthy block; now it needs
        # non-empty agent + activity + entity.
        r = report_conformance(_good_proof(provenance={"agents": []}))
        assert "w3c-prov-o" in r["standards_missing"]
        r2 = report_conformance(_good_proof(provenance={"agent": {"a": {}}}))  # missing activity/entity
        assert "w3c-prov-o" in r2["standards_missing"]

    def test_prereg_must_precede_result(self):
        # prereg AFTER the result is exactly the p-hacking the lock forbids.
        late = _good_proof(preregistration={
            "config_hash": "x", "analysis_plan": "p",
            "preregistered_at": "2026-05-22T10:00:01+00:00",  # after created_at
        })
        r = report_conformance(late)
        assert "osf-registered-reports" in r["standards_missing"]

    def test_prereg_without_timestamp_fails(self):
        no_ts = _good_proof(preregistration={"config_hash": "x", "analysis_plan": "p"})
        r = report_conformance(no_ts)
        assert "osf-registered-reports" in r["standards_missing"]

    def test_incomplete_dataset_card_fails_croissant(self):
        # hash present but no n_records / source — not a usable card.
        thin = _good_proof(data={"datasets": [{"name": "x", "content_hash": "h"}]})
        r = report_conformance(thin)
        assert "mlcommons-croissant" in r["standards_missing"]
        # full card passes
        full = _good_proof(data={"datasets": [
            {"name": "x", "content_hash": "h", "n_records": 5, "kind": "corpus"}]})
        assert "mlcommons-croissant" in report_conformance(full)["standards_satisfied"]

    def test_headline_only_detail_fails_helm(self):
        # a single scalar key is a headline number, not raw transparency.
        thin = _good_proof(evidence=[{"statistic_name": "m", "statistic_value": 1,
                                      "detail": {"n": 1}}])
        r = report_conformance(thin)
        assert "stanford-helm" in r["standards_missing"]

    def test_nested_detail_passes_helm(self):
        rich = _good_proof(evidence=[{"statistic_name": "m", "statistic_value": 1,
                                      "detail": {"series": [1, 2, 3]}}])
        r = report_conformance(rich)
        assert "stanford-helm" in r["standards_satisfied"]


class TestNomenclature:
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
            pytest.skip("no signed proofs in corpus")
        sample = proofs[0]
        data = json.loads(sample.read_text(encoding="utf-8"))
        r = report_conformance(data, bundle_dir=str(sample.parent))
        # A real signed proof must pass nomenclature.
        assert r["conformant"] is True, [
            i for i in r["nomenclature"] if not i["satisfied"]
        ]
        # And satisfy the substantive attestation standards — these are the
        # real checks now, not block-presence.
        assert "in-toto/DSSE" in r["standards_satisfied"]
        assert "w3c-prov-o" in r["standards_satisfied"]
        assert "osf-registered-reports" in r["standards_satisfied"]
        assert "ro-crate" in r["standards_satisfied"]  # bundle on disk
