"""Tests for the Kimera-co-evolution drift detector (Layer C of the stack).

Distinct from ``test_drift.py``, which covers the observability pillar's
river-backed change-point detector. This module exercises
``ophamin.comparing.drift.*`` — cross-Kimera-commit drift on signed Empirical Proof
Records.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ophamin.comparing.drift import (
    DriftReport,
    ProofIndex,
    ProofIndexEntry,
    ci_overlaps,
    detect_drift,
)
from ophamin.measuring.proof import (
    Claim,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
)
from ophamin.measuring.proof.record import DatasetRef


# --------------------------------------------------------------------------
# CI-overlap helper
# --------------------------------------------------------------------------


def test_ci_overlaps_overlap_yes():
    assert ci_overlaps((0.1, 0.5), (0.3, 0.7)) is True


def test_ci_overlaps_overlap_no():
    assert ci_overlaps((0.1, 0.3), (0.5, 0.7)) is False


def test_ci_overlaps_touching_at_boundary():
    # touching intervals overlap (inclusive bound)
    assert ci_overlaps((0.1, 0.5), (0.5, 0.9)) is True


def test_ci_overlaps_returns_none_when_missing():
    assert ci_overlaps((None, 0.5), (0.3, 0.7)) is None
    assert ci_overlaps((0.1, 0.5), (None, None)) is None


# --------------------------------------------------------------------------
# Synthetic-record builder
# --------------------------------------------------------------------------


def _build_synthetic_record(
    *,
    statistic: str,
    observed: float,
    threshold_value: float,
    kimera_commit: str,
    captured_at: str,
    verdict_outcome: str = "VALIDATED",
    ci_low: float | None = None,
    ci_high: float | None = None,
    pillar_evidence: list[PillarEvidence] | None = None,
) -> EmpiricalProofRecord:
    threshold = Threshold(statistic, ">=", threshold_value, "fraction")
    primary_evidence = PillarEvidence(
        pillar="test",
        statistic_name=statistic,
        statistic_value=observed,
        library="statsmodels",
        library_version="0.14",
        ci_low=ci_low,
        ci_high=ci_high,
        cross_check="n/a",
    )
    return EmpiricalProofRecord(
        claim=Claim(
            statement=f"test claim for {statistic}",
            operationalization="test op",
            threshold=threshold,
            h0="< threshold",
            h1=">= threshold",
        ),
        preregistration=PreRegistration(
            config_hash="h", data_hash="h", analysis_plan="p"
        ),
        datasets=[DatasetRef("test", "h", 10, "test://", "test_kind")],
        substrate_name="kimera-swm",
        substrate_git_commit=kimera_commit,
        evidence=[primary_evidence] + (pillar_evidence or []),
        verdict=Verdict(
            outcome=verdict_outcome,
            observed_value=observed,
            threshold=threshold,
            reasoning="test",
        ),
        reproduction=Reproduction(command="test"),
        provenance={},
        ophamin_version="0.1.0",
        ophamin_git_commit="o",
        created_at=captured_at,
    )


def _write_record(record: EmpiricalProofRecord, path: Path) -> None:
    record.sign(b"k")
    path.write_text(record.to_json())


def _entry_from_record(record: EmpiricalProofRecord, path: Path) -> ProofIndexEntry:
    return ProofIndexEntry(path=path, record=record)


# --------------------------------------------------------------------------
# ProofIndex
# --------------------------------------------------------------------------


def test_proof_index_loads_real_records(tmp_path):
    r1 = _build_synthetic_record(
        statistic="gwf_fp_rate",
        observed=0.03,
        threshold_value=0.10,
        kimera_commit="abc111",
        captured_at="2026-05-01T00:00:00+00:00",
        ci_low=0.02, ci_high=0.05,
    )
    r2 = _build_synthetic_record(
        statistic="gwf_fp_rate",
        observed=0.08,
        threshold_value=0.10,
        kimera_commit="def222",
        captured_at="2026-05-15T00:00:00+00:00",
        ci_low=0.06, ci_high=0.10,
    )
    _write_record(r1, tmp_path / "r1.json")
    _write_record(r2, tmp_path / "r2.json")

    idx = ProofIndex.from_directory(tmp_path)
    assert len(idx) == 2
    assert idx.statistic_names() == ("gwf_fp_rate",)
    assert idx.commits_for("gwf_fp_rate") == ("abc111", "def222")
    records = idx.records_for("gwf_fp_rate")
    assert records[0].primary_observed_value == pytest.approx(0.03)
    assert records[1].primary_observed_value == pytest.approx(0.08)


def test_proof_index_skips_non_proof_json(tmp_path):
    r = _build_synthetic_record(
        statistic="x", observed=0.5, threshold_value=0.5,
        kimera_commit="c", captured_at="2026-05-15T00:00:00+00:00",
    )
    _write_record(r, tmp_path / "proof.json")
    (tmp_path / "stray.json").write_text(json.dumps({"not": "a proof"}))
    idx = ProofIndex.from_directory(tmp_path)
    assert len(idx) == 1


def test_proof_index_rejects_non_directory(tmp_path):
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("hello")
    with pytest.raises(NotADirectoryError):
        ProofIndex.from_directory(not_a_dir)


def test_proof_index_groups_by_commit(tmp_path):
    for i, commit in enumerate(["a", "a", "b"]):
        r = _build_synthetic_record(
            statistic="m", observed=0.5, threshold_value=0.5,
            kimera_commit=commit,
            captured_at=f"2026-05-{i+1:02d}T00:00:00+00:00",
        )
        _write_record(r, tmp_path / f"r{i}.json")
    idx = ProofIndex.from_directory(tmp_path)
    grouped = idx.records_by_commit("m")
    assert set(grouped) == {"a", "b"}
    assert len(grouped["a"]) == 2
    assert len(grouped["b"]) == 1


# --------------------------------------------------------------------------
# DriftReport
# --------------------------------------------------------------------------


def test_drift_report_significant_when_cis_disjoint(tmp_path):
    before = _build_synthetic_record(
        statistic="rate", observed=0.10, threshold_value=0.50,
        kimera_commit="a", captured_at="2026-05-01T00:00:00+00:00",
        ci_low=0.05, ci_high=0.15,
    )
    after = _build_synthetic_record(
        statistic="rate", observed=0.60, threshold_value=0.50,
        kimera_commit="b", captured_at="2026-05-15T00:00:00+00:00",
        ci_low=0.50, ci_high=0.70,
    )
    drift = DriftReport.from_proofs(
        _entry_from_record(before, tmp_path / "a"),
        _entry_from_record(after, tmp_path / "b"),
    )
    assert drift.primary_delta.delta == pytest.approx(0.50)
    assert drift.primary_delta.ci_overlap is False
    assert drift.primary_delta.significant is True
    assert drift.has_significant_drift() is True


def test_drift_report_not_significant_when_cis_overlap(tmp_path):
    before = _build_synthetic_record(
        statistic="rate", observed=0.30, threshold_value=0.50,
        kimera_commit="a", captured_at="2026-05-01T00:00:00+00:00",
        ci_low=0.20, ci_high=0.40,
    )
    after = _build_synthetic_record(
        statistic="rate", observed=0.35, threshold_value=0.50,
        kimera_commit="b", captured_at="2026-05-15T00:00:00+00:00",
        ci_low=0.25, ci_high=0.45,
    )
    drift = DriftReport.from_proofs(
        _entry_from_record(before, tmp_path / "a"),
        _entry_from_record(after, tmp_path / "b"),
    )
    assert drift.primary_delta.ci_overlap is True
    assert drift.primary_delta.significant is False


def test_drift_report_verdict_flip_is_surfaced(tmp_path):
    before = _build_synthetic_record(
        statistic="r", observed=0.10, threshold_value=0.20,
        kimera_commit="a", captured_at="2026-05-01T00:00:00+00:00",
        verdict_outcome="VALIDATED",
    )
    after = _build_synthetic_record(
        statistic="r", observed=0.30, threshold_value=0.20,
        kimera_commit="b", captured_at="2026-05-15T00:00:00+00:00",
        verdict_outcome="REFUTED",
    )
    drift = DriftReport.from_proofs(
        _entry_from_record(before, tmp_path / "a"),
        _entry_from_record(after, tmp_path / "b"),
    )
    assert drift.verdict_changed() is True


def test_drift_report_rejects_mismatched_statistics(tmp_path):
    before = _build_synthetic_record(
        statistic="rate_a", observed=0.10, threshold_value=0.50,
        kimera_commit="a", captured_at="2026-05-01T00:00:00+00:00",
    )
    after = _build_synthetic_record(
        statistic="rate_b", observed=0.20, threshold_value=0.50,
        kimera_commit="b", captured_at="2026-05-15T00:00:00+00:00",
    )
    with pytest.raises(ValueError, match="different primary statistics"):
        DriftReport.from_proofs(
            _entry_from_record(before, tmp_path / "a"),
            _entry_from_record(after, tmp_path / "b"),
        )


def test_drift_report_includes_pillar_deltas(tmp_path):
    pillar_b = PillarEvidence(
        pillar="extra", statistic_name="extra_metric",
        statistic_value=0.20,
        library="ophamin", library_version="0.1",
        ci_low=0.10, ci_high=0.30, cross_check="n/a",
    )
    pillar_a = PillarEvidence(
        pillar="extra", statistic_name="extra_metric",
        statistic_value=0.70,
        library="ophamin", library_version="0.1",
        ci_low=0.60, ci_high=0.80, cross_check="n/a",
    )
    before = _build_synthetic_record(
        statistic="primary", observed=0.10, threshold_value=0.50,
        kimera_commit="a", captured_at="2026-05-01T00:00:00+00:00",
        ci_low=0.05, ci_high=0.15,
        pillar_evidence=[pillar_b],
    )
    after = _build_synthetic_record(
        statistic="primary", observed=0.20, threshold_value=0.50,
        kimera_commit="b", captured_at="2026-05-15T00:00:00+00:00",
        ci_low=0.15, ci_high=0.25,
        pillar_evidence=[pillar_a],
    )
    drift = DriftReport.from_proofs(
        _entry_from_record(before, tmp_path / "a"),
        _entry_from_record(after, tmp_path / "b"),
    )
    assert len(drift.pillar_deltas) == 1
    extra = drift.pillar_deltas[0]
    assert extra.statistic_name == "extra_metric"
    assert extra.delta == pytest.approx(0.50)
    assert extra.significant is True


# --------------------------------------------------------------------------
# detect_drift
# --------------------------------------------------------------------------


def test_detect_drift_single_commit_returns_status_marker(tmp_path):
    r = _build_synthetic_record(
        statistic="m", observed=0.5, threshold_value=0.5,
        kimera_commit="a", captured_at="2026-05-01T00:00:00+00:00",
    )
    _write_record(r, tmp_path / "r.json")
    idx = ProofIndex.from_directory(tmp_path)
    report = detect_drift(idx)
    assert report["m"]["status"] == "single_commit"


def test_detect_drift_two_commits_returns_full_report(tmp_path):
    before = _build_synthetic_record(
        statistic="r", observed=0.10, threshold_value=0.50,
        kimera_commit="a", captured_at="2026-05-01T00:00:00+00:00",
        ci_low=0.05, ci_high=0.15,
    )
    after = _build_synthetic_record(
        statistic="r", observed=0.40, threshold_value=0.50,
        kimera_commit="b", captured_at="2026-05-15T00:00:00+00:00",
        ci_low=0.35, ci_high=0.45,
    )
    _write_record(before, tmp_path / "a.json")
    _write_record(after, tmp_path / "b.json")
    idx = ProofIndex.from_directory(tmp_path)
    report = detect_drift(idx)
    entry = report["r"]
    assert entry["primary_delta"]["delta"] == pytest.approx(0.30)
    assert entry["primary_delta"]["ci_overlap"] is False
    assert entry["primary_delta"]["significant"] is True
    assert entry["has_significant_drift"] is True


def test_proof_record_from_dict_roundtrip(tmp_path):
    """The new EmpiricalProofRecord.from_dict roundtrips back to to_dict cleanly."""
    original = _build_synthetic_record(
        statistic="x", observed=0.5, threshold_value=0.5,
        kimera_commit="abc", captured_at="2026-05-15T00:00:00+00:00",
        ci_low=0.4, ci_high=0.6,
    )
    original.sign(b"key")
    payload = original.to_dict()
    rebuilt = EmpiricalProofRecord.from_dict(payload)
    # round-trip the heavy fields
    assert rebuilt.claim.threshold.metric == "x"
    assert rebuilt.verdict.observed_value == pytest.approx(0.5)
    assert rebuilt.substrate_git_commit == "abc"
    assert rebuilt.signature == original.signature
    # the signature still verifies against the original key
    assert rebuilt.verify_signature(b"key")
