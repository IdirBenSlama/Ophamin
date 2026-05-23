"""Hardening tests for the Move I wrap_as_proof helpers.

Both :meth:`AuditRecord.wrap_as_proof` and :meth:`DriftScan.wrap_as_proof`
take an audit / drift artifact (descriptive by default) and wrap it in
a pre-registered EmpiricalProofRecord (falsifiable). This is the
lightweight realization of the universalize-pre-registration deficit
(Gap I from the prior audit) — instead of inflating the
AuditRecord / DriftScan schemas to add per-record pre_registration,
the wrap pattern preserves the original artifact as-is and produces
a proof companion when the caller wants CI gating.
"""

from __future__ import annotations

from datetime import datetime, timezone


from ophamin import __version__
from ophamin.auditing.audit_record import AuditRecord, AuditSummary
from ophamin.auditing.base import Finding, FindingSeverity, PillarResult
from ophamin.comparing.drift_detection.river_detector import (
    DriftEvent,
    DriftScan,
    _hash_stream,
)
from ophamin.measuring.proof import (
    Claim,
    EmpiricalProofRecord,
    Threshold,
)


_SIGN_KEY = b"wrap-as-proof-test-key"


def _make_audit(n_findings: int = 3) -> AuditRecord:
    findings = tuple(
        Finding(
            pillar_name="p",
            rule_id=f"R{i}",
            severity=FindingSeverity.LOW,
            message=f"finding {i}",
            path=f"a_{i}.py",
        )
        for i in range(n_findings)
    )
    pr = PillarResult(
        pillar_name="p",
        tool_name="dummy",
        tool_version="1.0",
        status="ok",
        target_path="/tmp/x",
        findings=findings,
    )
    return AuditRecord(
        target_path="/tmp/x",
        target_content_hash="deadbeef" * 8,
        pillars=[pr],
        summary=AuditSummary.from_pillar_results([pr]),
        ophamin_version=__version__,
        ophamin_git_commit="cafebabe" * 5,
        captured_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def _make_drift_scan(n_events: int = 1) -> DriftScan:
    return DriftScan(
        detector_name="adwin",
        detector_config={"delta": 0.002},
        stream_name="phi_value",
        n_samples=200,
        stream_hash=_hash_stream(tuple(range(10))),
        events=tuple(
            DriftEvent(
                sample_index=10 + i,
                detector_name="adwin",
                value_at_event=float(i),
                detail={},
            )
            for i in range(n_events)
        ),
        ophamin_version=__version__,
        ophamin_git_commit="cafebabe" * 5,
        captured_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


# --- AuditRecord.wrap_as_proof --------------------------------------------


def test_audit_wrap_as_proof_returns_proof_record():
    audit = _make_audit(n_findings=5)
    claim = Claim(
        statement="total findings <= 10",
        operationalization="count of findings from the audit pillars",
        threshold=Threshold("total_findings", "<=", 10),
        h0="total_findings > 10",
        h1="total_findings <= 10",
    )
    proof = audit.wrap_as_proof(claim=claim, observed_value=5)
    assert isinstance(proof, EmpiricalProofRecord)


def test_audit_wrap_as_proof_threshold_satisfied_produces_validated():
    audit = _make_audit(n_findings=3)
    claim = Claim(
        statement="<= 10",
        operationalization="count",
        threshold=Threshold("total_findings", "<=", 10),
        h0=">10",
        h1="<=10",
    )
    proof = audit.wrap_as_proof(claim=claim, observed_value=3)
    assert proof.verdict.outcome == "VALIDATED"
    assert proof.verdict.observed_value == 3


def test_audit_wrap_as_proof_threshold_violated_produces_refuted():
    audit = _make_audit(n_findings=50)
    claim = Claim(
        statement="<= 10",
        operationalization="count",
        threshold=Threshold("total_findings", "<=", 10),
        h0=">10",
        h1="<=10",
    )
    proof = audit.wrap_as_proof(claim=claim, observed_value=50)
    assert proof.verdict.outcome == "REFUTED"


def test_audit_wrap_as_proof_carries_audit_id_in_evidence_detail():
    audit = _make_audit(n_findings=4)
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("total_findings", "<=", 100),
        h0="x", h1="x",
    )
    proof = audit.wrap_as_proof(claim=claim, observed_value=4)
    assert proof.evidence[0].detail["audit_id"] == audit.audit_id
    assert proof.evidence[0].detail["total_findings"] == 4


def test_audit_wrap_as_proof_with_sign_key_signs(tmp_path):
    audit = _make_audit()
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("total_findings", "<=", 100),
        h0="x", h1="x",
    )
    proof = audit.wrap_as_proof(claim=claim, observed_value=0, sign_key=_SIGN_KEY)
    assert proof.signature  # non-empty
    assert proof.verify_signature(_SIGN_KEY)


def test_audit_wrap_as_proof_without_sign_key_returns_unsigned():
    audit = _make_audit()
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("total_findings", "<=", 100),
        h0="x", h1="x",
    )
    proof = audit.wrap_as_proof(claim=claim, observed_value=0)
    assert proof.signature == ""


def test_audit_wrap_as_proof_dataset_carries_target_hash():
    audit = _make_audit()
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("total_findings", "<=", 100),
        h0="x", h1="x",
    )
    proof = audit.wrap_as_proof(claim=claim, observed_value=0)
    assert proof.datasets[0].content_hash == audit.target_content_hash
    assert audit.target_path in proof.datasets[0].source


# --- DriftScan.wrap_as_proof ---------------------------------------------


def test_drift_wrap_as_proof_returns_proof_record():
    scan = _make_drift_scan(n_events=2)
    claim = Claim(
        statement="no drift events",
        operationalization="count of detected drift events",
        threshold=Threshold("n_drift_events", "<=", 0),
        h0=">0",
        h1="<=0",
    )
    proof = scan.wrap_as_proof(claim=claim)
    assert isinstance(proof, EmpiricalProofRecord)
    # n_events default observed_value
    assert proof.verdict.observed_value == 2


def test_drift_wrap_as_proof_default_observed_is_n_events():
    scan = _make_drift_scan(n_events=5)
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    proof = scan.wrap_as_proof(claim=claim)
    assert proof.verdict.observed_value == 5


def test_drift_wrap_as_proof_explicit_observed_value():
    scan = _make_drift_scan(n_events=5)
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("drift_severity_score", "<=", 0.5),
        h0="x", h1="x",
    )
    proof = scan.wrap_as_proof(claim=claim, observed_value=0.3)
    assert proof.verdict.observed_value == 0.3
    assert proof.verdict.outcome == "VALIDATED"


def test_drift_wrap_as_proof_signing(tmp_path):
    scan = _make_drift_scan()
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    proof = scan.wrap_as_proof(claim=claim, sign_key=_SIGN_KEY)
    assert proof.verify_signature(_SIGN_KEY)


def test_drift_wrap_as_proof_dataset_carries_stream_hash():
    scan = _make_drift_scan()
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    proof = scan.wrap_as_proof(claim=claim)
    assert proof.datasets[0].content_hash == scan.stream_hash
    assert "river.adwin" in proof.datasets[0].source


def test_drift_wrap_as_proof_evidence_carries_event_indices():
    scan = _make_drift_scan(n_events=3)
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    proof = scan.wrap_as_proof(claim=claim)
    detail = proof.evidence[0].detail
    assert detail["scan_id"] == scan.scan_id
    assert detail["n_events"] == 3
    assert list(detail["event_indices"]) == [10, 11, 12]


def test_drift_wrap_as_proof_pillar_is_o_drift():
    scan = _make_drift_scan()
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    proof = scan.wrap_as_proof(claim=claim)
    assert proof.evidence[0].pillar == "O.drift"
