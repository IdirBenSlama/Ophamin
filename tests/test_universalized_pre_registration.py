"""Hardening tests for Move L — schema-wide pre-registration discipline.

Closes gap I (full universalization) from the prior architecture audit.

AuditRecord schema bumps audit/1.0 → audit/1.1; DriftScan schema bumps
v1 → v2. Both add optional ``pre_registration`` + ``pre_registered_metric``
+ ``verdict`` fields. v1.0 / v1 records load cleanly under the new codec
(backward-compat). The ``attach_pre_registration`` method on each is the
in-place / new-instance way to stamp the optional fields.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ophamin import __version__
from ophamin.auditing.audit_record import (
    AuditRecord,
    AuditSummary,
    SCHEMA_VERSION as AUDIT_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS as AUDIT_SUPPORTED_SCHEMA_VERSIONS,
)
from ophamin.auditing.base import Finding, FindingSeverity, PillarResult
from ophamin.auditing.codec import (
    AuditSchemaVersionMismatchError,
    dump as audit_dump,
    ingest as audit_ingest,
    load as audit_load,
)
from ophamin.comparing.drift_detection.river_detector import (
    DRIFT_SCHEMA_VERSION,
    DRIFT_SUPPORTED_SCHEMA_VERSIONS,
    DriftEvent,
    DriftScan,
    _hash_stream,
)
from ophamin.measuring.proof import (
    Claim,
    Threshold,
)


_SIGN_KEY = b"move-l-test-key"


# --- AuditRecord schema bump + backward-compat ----------------------------


def _make_audit(n_findings: int = 2) -> AuditRecord:
    pillar = PillarResult(
        pillar_name="p",
        tool_name="dummy",
        tool_version="1.0",
        status="ok",
        target_path="/tmp/x",
        findings=tuple(
            Finding(
                pillar_name="p",
                rule_id=f"R{i}",
                severity=FindingSeverity.LOW,
                message="m",
                path=f"f_{i}.py",
            )
            for i in range(n_findings)
        ),
    )
    return AuditRecord(
        target_path="/tmp/audit-target",
        target_content_hash="deadbeef" * 8,
        pillars=[pillar],
        summary=AuditSummary.from_pillar_results([pillar]),
        ophamin_version=__version__,
        ophamin_git_commit="cafebabe" * 5,
        captured_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def test_audit_schema_version_bumped():
    assert AUDIT_SCHEMA_VERSION == "audit/1.1"


def test_audit_supported_schema_versions_includes_legacy():
    assert "audit/1.0" in AUDIT_SUPPORTED_SCHEMA_VERSIONS
    assert "audit/1.1" in AUDIT_SUPPORTED_SCHEMA_VERSIONS


def test_audit_legacy_v10_loads_cleanly(tmp_path):
    """A schema audit/1.0 file (no preregistration/verdict fields) must
    load through the v1.1 codec without raising."""
    record = _make_audit()
    record.schema_version = "audit/1.0"
    path = audit_dump(record.sign(_SIGN_KEY), tmp_path / "legacy.json")
    loaded = audit_load(path)
    assert loaded.schema_version == "audit/1.0"
    assert loaded.pre_registration is None
    assert loaded.verdict is None


def test_audit_ingest_accepts_v10_by_default(tmp_path):
    """The default ``ingest()`` accepts both 1.0 and 1.1 without an
    explicit ``allowed_schema_versions``."""
    record = _make_audit()
    record.schema_version = "audit/1.0"
    path = audit_dump(record.sign(_SIGN_KEY), tmp_path / "legacy.json")
    loaded = audit_ingest(path)
    assert loaded.schema_version == "audit/1.0"


def test_audit_ingest_rejects_unknown_schema_version(tmp_path):
    record = _make_audit()
    record.schema_version = "audit/99.0"
    path = audit_dump(record.sign(_SIGN_KEY), tmp_path / "unknown.json")
    with pytest.raises(AuditSchemaVersionMismatchError):
        audit_ingest(path)


def test_audit_attach_pre_registration_stamps_fields():
    record = _make_audit(n_findings=3)
    claim = Claim(
        statement="<=10 findings", operationalization="count",
        threshold=Threshold("total_findings", "<=", 10),
        h0=">10", h1="<=10",
    )
    record.attach_pre_registration(claim=claim, observed_value=3)
    assert record.schema_version == "audit/1.1"
    assert record.pre_registration is not None
    assert record.pre_registered_metric == "total_findings"
    assert record.verdict is not None
    assert record.verdict.outcome == "VALIDATED"


def test_audit_attach_then_round_trip_preserves_pre_registration(tmp_path):
    record = _make_audit()
    claim = Claim(
        statement="<=10", operationalization="x",
        threshold=Threshold("total_findings", "<=", 10),
        h0="x", h1="x",
    )
    # pass observed_value as float so the int→float coercion in
    # Verdict.from_dict doesn't change the canonical signature bytes
    record.attach_pre_registration(claim=claim, observed_value=2.0)
    record.sign(_SIGN_KEY)  # re-sign after attach
    path = audit_dump(record, tmp_path / "v11.json")
    loaded = audit_load(path)
    assert loaded.schema_version == "audit/1.1"
    assert loaded.pre_registration is not None
    assert loaded.pre_registered_metric == "total_findings"
    assert loaded.verdict is not None
    assert loaded.verdict.outcome == "VALIDATED"
    assert loaded.verify_signature(_SIGN_KEY)


def test_audit_attach_refuted_verdict():
    record = _make_audit(n_findings=50)
    claim = Claim(
        statement="<=10", operationalization="x",
        threshold=Threshold("total_findings", "<=", 10),
        h0="x", h1="x",
    )
    record.attach_pre_registration(claim=claim, observed_value=50)
    assert record.verdict.outcome == "REFUTED"


def test_audit_body_includes_preregistration_only_when_attached():
    """The body dict (basis of audit_id + signature) must NOT include
    preregistration/verdict keys when they're None — keeps schema 1.0
    records bit-identical for signature stability."""
    record = _make_audit()
    body = record._body()
    assert "preregistration" not in body
    assert "verdict" not in body
    # After attach, the keys appear
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("total_findings", "<=", 10),
        h0="x", h1="x",
    )
    record.attach_pre_registration(claim=claim, observed_value=0)
    body = record._body()
    assert "preregistration" in body
    assert "verdict" in body


# --- DriftScan schema bump + backward-compat ------------------------------


def _make_scan(n_events: int = 1) -> DriftScan:
    return DriftScan(
        detector_name="adwin",
        detector_config={"delta": 0.002},
        stream_name="phi_value",
        n_samples=100,
        stream_hash=_hash_stream(tuple(range(10))),
        events=tuple(
            DriftEvent(
                sample_index=10 + i,
                detector_name="adwin",
                value_at_event=float(i),
            )
            for i in range(n_events)
        ),
        ophamin_version=__version__,
        ophamin_git_commit="cafebabe" * 5,
        captured_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def test_drift_schema_version_bumped():
    assert DRIFT_SCHEMA_VERSION == 2


def test_drift_supported_schema_versions_includes_legacy():
    assert 1 in DRIFT_SUPPORTED_SCHEMA_VERSIONS
    assert 2 in DRIFT_SUPPORTED_SCHEMA_VERSIONS


def test_drift_legacy_v1_loads_cleanly():
    """A schema v1 scan (no preregistration/verdict) loads through the
    v2 codec — confirm by from_dict round-trip."""
    scan = _make_scan()
    data = scan.to_dict()
    # Force the schema_version back to v1 + remove any move-L fields
    data["schema_version"] = 1
    data.pop("preregistration", None)
    data.pop("verdict", None)
    loaded = DriftScan.from_dict(data)
    assert loaded.schema_version == 1
    assert loaded.pre_registration is None
    assert loaded.verdict is None


def test_drift_attach_returns_new_instance_with_fields():
    scan = _make_scan(n_events=3)
    claim = Claim(
        statement="<=0 drift events", operationalization="count",
        threshold=Threshold("n_drift_events", "<=", 0),
        h0=">0", h1="<=0",
    )
    new_scan = scan.attach_pre_registration(claim=claim)
    # NEW instance, frozen — original untouched
    assert new_scan is not scan
    assert scan.pre_registration is None
    assert scan.verdict is None
    assert new_scan.pre_registration is not None
    assert new_scan.pre_registered_metric == "n_drift_events"
    assert new_scan.verdict is not None
    # n_events=3, threshold <=0 → REFUTED
    assert new_scan.verdict.outcome == "REFUTED"
    assert new_scan.schema_version == 2


def test_drift_attach_default_observed_is_n_events():
    scan = _make_scan(n_events=5)
    claim = Claim(
        statement="<=10", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    new_scan = scan.attach_pre_registration(claim=claim)
    assert new_scan.verdict.observed_value == 5
    assert new_scan.verdict.outcome == "VALIDATED"


def test_drift_attach_explicit_observed_value():
    scan = _make_scan(n_events=5)
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("drift_severity", "<=", 0.5),
        h0="x", h1="x",
    )
    new_scan = scan.attach_pre_registration(
        claim=claim, observed_value=0.3, metric="drift_severity",
    )
    assert new_scan.verdict.observed_value == 0.3
    assert new_scan.pre_registered_metric == "drift_severity"


def test_drift_attach_invalidates_signature():
    """The new instance has signature='' because the body changed."""
    scan = _make_scan().sign(_SIGN_KEY)
    assert scan.signature  # was signed
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    new_scan = scan.attach_pre_registration(claim=claim)
    assert new_scan.signature == ""
    # Caller re-signs (DriftScan exposes `verify()`, not `verify_signature()`).
    re_signed = new_scan.sign(_SIGN_KEY)
    assert re_signed.verify(_SIGN_KEY)


def test_drift_body_includes_preregistration_only_when_attached():
    """The body dict (basis of scan_id + signature) must NOT include
    preregistration/verdict keys when they're None."""
    scan = _make_scan()
    body = scan._body()
    assert "preregistration" not in body
    assert "verdict" not in body
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    new_scan = scan.attach_pre_registration(claim=claim)
    body = new_scan._body()
    assert "preregistration" in body
    assert "verdict" in body


def test_drift_attach_then_dict_round_trip():
    scan = _make_scan(n_events=1)
    claim = Claim(
        statement="x", operationalization="x",
        threshold=Threshold("n_drift_events", "<=", 10),
        h0="x", h1="x",
    )
    attached = scan.attach_pre_registration(claim=claim)
    data = attached.to_dict()
    loaded = DriftScan.from_dict(data)
    assert loaded.schema_version == 2
    assert loaded.pre_registration is not None
    assert loaded.verdict is not None
    assert loaded.verdict.outcome == "VALIDATED"
