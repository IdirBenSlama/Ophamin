"""Tests for the Empirical Proof Record — the official result artifact.

These pin the six properties that make a proof bulletproof: falsifiable,
pre-registered, traceable, reproducible, attributed, tamper-evident.
"""

import json
from datetime import datetime, timedelta

import pytest

from ophamin.proof import (
    INCONCLUSIVE,
    REFUTED,
    SCHEMA_PATH,
    VALIDATED,
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
)


def _complete_record(**overrides) -> EmpiricalProofRecord:
    threshold = Threshold(metric="dissonance_slope", comparator=">=", value=0.1, units="per cycle")
    claim = Claim(
        statement="Substrate doubt rises as internal emails contradict public filings.",
        operationalization="I.cma pooled slope of the zetetic dissonance gradient",
        threshold=threshold,
        h0="dissonance slope <= 0.1 per cycle",
        h1="dissonance slope > 0.1 per cycle",
    )
    prereg = PreRegistration(
        config_hash="cfg" + "0" * 61,
        data_hash="dat" + "0" * 61,
        analysis_plan="cumulative meta-analysis over chronological email batches",
        sweep_grid={"batch_size": [1000, 5000]},
    )
    datasets = [
        DatasetRef(
            name="enron-corpus",
            content_hash="abc" + "0" * 61,
            n_records=517401,
            source="https://www.cs.cmu.edu/~enron/",
            kind="email_corpus",
        )
    ]
    evidence = [
        PillarEvidence(
            pillar="I.cma",
            statistic_name="pooled_slope",
            statistic_value=0.18,
            library="statsmodels",
            library_version="0.14.6",
            effect_size=0.18,
            ci_low=0.14,
            ci_high=0.22,
            p_value=1e-9,
            cross_check="passed",
        )
    ]
    record = EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=datasets,
        substrate_name="kimera-swm",
        substrate_git_commit="9596c681092358be",
        evidence=evidence,
        verdict=Verdict.decide(0.18, threshold),
        reproduction=Reproduction(command="ophamin sweep config/enron_dissonance.yaml"),
        provenance={"entity": {}, "activity": {}, "agent": {}},
        ophamin_version="0.1.0",
        ophamin_git_commit="deadbeefcafe",
    )
    for key, value in overrides.items():
        setattr(record, key, value)
    return record


def test_complete_record_is_valid():
    record = _complete_record()
    assert record.validate() == []
    assert record.is_valid


def test_proof_id_is_content_addressed():
    record = _complete_record()
    assert record.proof_id == record.proof_id  # deterministic
    assert len(record.proof_id) == 64
    original = record.proof_id
    record.claim.statement = "a materially different claim"
    assert record.proof_id != original  # body change -> id change


def test_signature_is_tamper_evident():
    key = b"ophamin-signing-key"
    record = _complete_record().sign(key)
    assert record.signature
    assert record.verify_signature(key)
    assert not record.verify_signature(b"the-wrong-key")
    record.verdict.reasoning = "tampered after signing"
    assert not record.verify_signature(key)


def test_threshold_comparators():
    assert Threshold("m", ">=", 0.1).decide(0.1)
    assert not Threshold("m", ">=", 0.1).decide(0.09)
    assert Threshold("m", "<", 0.1).decide(0.05)
    assert not Threshold("m", "<", 0.1).decide(0.1)
    with pytest.raises(ValueError):
        Threshold("m", "approximately", 0.1)


def test_verdict_decide_validated_refuted_inconclusive():
    thr = Threshold("slope", ">=", 0.1)
    assert Verdict.decide(0.2, thr).outcome == VALIDATED
    assert Verdict.decide(0.05, thr).outcome == REFUTED
    assert Verdict.decide(0.2, thr, inconclusive=True).outcome == INCONCLUSIVE


def test_refuted_record_is_a_valid_proof():
    # disproving a claim IS a result — a REFUTED record must still validate
    thr = Threshold("slope", ">=", 0.1)
    record = _complete_record(verdict=Verdict.decide(0.04, thr))
    record.claim.threshold = thr
    assert record.verdict.outcome == REFUTED
    assert record.validate() == []


def test_validate_catches_preregistration_after_run():
    record = _complete_record()
    later = (
        datetime.fromisoformat(record.created_at) + timedelta(hours=1)
    ).isoformat()
    record.preregistration.preregistered_at = later
    assert any("pre-registration lock" in p for p in record.validate())


def test_validate_catches_missing_library_attribution():
    record = _complete_record()
    record.evidence[0].library_version = ""
    assert any("library attribution" in p for p in record.validate())


def test_validate_catches_no_datasets():
    record = _complete_record(datasets=[])
    assert any("real data" in p for p in record.validate())


def test_validate_catches_verdict_contradicting_threshold():
    thr = Threshold("slope", ">=", 0.1)
    record = _complete_record()
    record.claim.threshold = thr
    record.verdict = Verdict(VALIDATED, 0.05, thr, "inconsistent on purpose")
    assert any("contradicts the threshold" in p for p in record.validate())


def test_to_json_conforms_to_official_schema():
    record = _complete_record().sign(b"k")
    payload = json.loads(record.to_json())
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    for key in schema["required"]:
        assert key in payload, f"proof.json missing top-level key: {key}"
    for key in schema["properties"]["claim"]["required"]:
        assert key in payload["claim"]
    for key in schema["properties"]["verdict"]["required"]:
        assert key in payload["verdict"]
    for key in schema["$defs"]["threshold"]["required"]:
        assert key in payload["claim"]["threshold"]
    for evidence in payload["evidence"]:
        for key in schema["$defs"]["pillar_evidence"]["required"]:
            assert key in evidence
    assert len(payload["proof_id"]) == 64


def test_to_json_round_trips(tmp_path):
    record = _complete_record().sign(b"k")
    path = tmp_path / "proof.json"
    record.to_json(str(path))
    payload = json.loads(path.read_text())
    assert payload["proof_id"] == record.proof_id
    assert payload["signature"] == record.signature
    assert payload["verdict"]["outcome"] == VALIDATED


def test_to_markdown_renders_the_verdict(tmp_path):
    record = _complete_record().sign(b"k")
    path = tmp_path / "PROOF.md"
    md = record.to_markdown(str(path))
    assert "Ophamin Empirical Proof Record" in md
    assert record.verdict.outcome in md
    assert record.proof_id in md
    assert path.exists()
