"""CLI smoke + behavior tests for `ophamin schema` (Phase L4).

Three actions are exercised:

- ``list``: prints every documented schema; exit 0.
- ``info``: detects kind + version of a record; exit 0.
- ``validate``: validates a record (and optionally its signature); exit
  0 on success, 2 on failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    dump,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _signed_proof_record() -> EmpiricalProofRecord:
    """Build a minimal valid EmpiricalProofRecord for schema tests."""
    threshold = Threshold(
        metric="rate", comparator=">=", value=0.5, units="fraction"
    )
    record = EmpiricalProofRecord(
        claim=Claim(
            statement="rate ≥ 0.5",
            operationalization="count successful cycles",
            threshold=threshold,
            h0="rate < 0.5",
            h1="rate ≥ 0.5",
        ),
        preregistration=PreRegistration(
            config_hash="0" * 64,
            data_hash="1" * 64,
            analysis_plan="run the substrate, count successes",
        ),
        datasets=[
            DatasetRef(
                name="synthetic-test",
                content_hash="2" * 64,
                n_records=10,
                source="in-memory",
                kind="synthetic",
            )
        ],
        substrate_name="mock",
        substrate_git_commit="deadbeef",
        evidence=[
            PillarEvidence(
                pillar="harness",
                statistic_name="rate",
                statistic_value=0.75,
                library="ophamin",
                library_version="0.7.2",
            )
        ],
        verdict=Verdict(
            outcome="VALIDATED",
            observed_value=0.75,
            threshold=threshold,
            reasoning="0.75 satisfies the threshold",
        ),
        reproduction=Reproduction(
            command="ophamin test",
            environment={"python": "3.14"},
            lineage_chain=[],
        ),
        ophamin_version="0.7.2",
        ophamin_git_commit="",
    )
    record.sign(b"test-key")
    return record


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "schema", *args],
        capture_output=True,
        text=True,
    )


# ----------------------------------------------------------------------------
# `schema list`
# ----------------------------------------------------------------------------


def test_schema_list_emits_every_documented_schema() -> None:
    """`schema list` must mention every signed-record schema by name."""
    result = _run("list")
    assert result.returncode == 0, result.stderr
    for name in (
        "EmpiricalProofRecord",
        "AuditRecord",
        "CampaignRecord",
        "RegressionAlertRecord",
        "DriftScan",
    ):
        assert name in result.stdout, f"{name!r} missing from `schema list` output"


def test_schema_list_mentions_schemas_md() -> None:
    """The list view points readers at SCHEMAS.md for the full policy."""
    result = _run("list")
    assert "SCHEMAS.md" in result.stdout


# ----------------------------------------------------------------------------
# `schema info`
# ----------------------------------------------------------------------------


def test_schema_info_detects_proof_record(tmp_path: Path) -> None:
    record = _signed_proof_record()
    path = tmp_path / "proof.json"
    dump(record, path)
    result = _run("info", str(path))
    assert result.returncode == 0, result.stderr
    assert "detected kind:  proof" in result.stdout
    assert "schema_version: 1.0" in result.stdout
    assert "signature:" in result.stdout


def test_schema_info_reports_missing_file(tmp_path: Path) -> None:
    result = _run("info", str(tmp_path / "no-such-file.json"))
    assert result.returncode == 2
    assert "not a file" in result.stderr


def test_schema_info_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "array.json"
    path.write_text(json.dumps([1, 2, 3]))
    result = _run("info", str(path))
    assert result.returncode == 2
    assert "top level must be an object" in result.stderr


def test_schema_info_handles_unrecognised_schema(tmp_path: Path) -> None:
    path = tmp_path / "mystery.json"
    path.write_text(json.dumps({"foo": "bar"}))
    result = _run("info", str(path))
    # info doesn't error on unrecognised — it just reports None
    assert result.returncode == 0
    assert "detected kind:  <unrecognised>" in result.stdout


# ----------------------------------------------------------------------------
# `schema validate`
# ----------------------------------------------------------------------------


def test_schema_validate_passes_signed_proof_with_correct_key(tmp_path: Path) -> None:
    record = _signed_proof_record()
    path = tmp_path / "proof.json"
    dump(record, path)
    result = _run("validate", str(path), "--key", "test-key")
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
    assert "signature verified" in result.stdout
    assert "1 ok, 0 failed" in result.stdout


def test_schema_validate_structure_only_without_key(tmp_path: Path) -> None:
    record = _signed_proof_record()
    path = tmp_path / "proof.json"
    dump(record, path)
    result = _run("validate", str(path))
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
    # without --key the signature is NOT mentioned as verified
    assert "signature verified" not in result.stdout


def test_schema_validate_fails_wrong_key(tmp_path: Path) -> None:
    record = _signed_proof_record()
    path = tmp_path / "proof.json"
    dump(record, path)
    result = _run("validate", str(path), "--key", "wrong-key")
    assert result.returncode == 2
    assert "FAIL" in result.stdout
    assert "signature verification failed" in result.stdout


def test_schema_validate_fails_on_unrecognised(tmp_path: Path) -> None:
    path = tmp_path / "mystery.json"
    path.write_text(json.dumps({"foo": "bar"}))
    result = _run("validate", str(path))
    assert result.returncode == 2
    assert "unrecognised schema" in result.stdout


def test_schema_validate_directory_recursive(tmp_path: Path) -> None:
    record = _signed_proof_record()
    # Drop two records into a nested layout
    (tmp_path / "scientific" / "x").mkdir(parents=True)
    dump(record, tmp_path / "scientific" / "x" / "a.json")
    dump(record, tmp_path / "scientific" / "x" / "b.json")
    result = _run("validate", str(tmp_path), "--recursive")
    assert result.returncode == 0, result.stderr
    assert "2 ok, 0 failed" in result.stdout


def test_schema_validate_directory_without_recursive_errors(tmp_path: Path) -> None:
    result = _run("validate", str(tmp_path))
    assert result.returncode == 2
    assert "pass --recursive" in result.stderr


def test_schema_validate_recursive_empty_dir(tmp_path: Path) -> None:
    result = _run("validate", str(tmp_path), "--recursive")
    assert result.returncode == 2
    assert "no .json files" in result.stderr


def test_schema_validate_version_mismatch_rejected(tmp_path: Path) -> None:
    """A bogus schema_version on a proof record should be rejected by default."""
    record = _signed_proof_record()
    path = tmp_path / "proof.json"
    dump(record, path)
    # Forge the schema version
    payload = json.loads(path.read_text())
    payload["schema_version"] = "99.0"
    path.write_text(json.dumps(payload))
    result = _run("validate", str(path))
    assert result.returncode == 2
    assert "schema_version mismatch" in result.stdout


def test_schema_validate_allow_any_schema_version_bypasses(tmp_path: Path) -> None:
    """--allow-any-schema-version is the documented forensic escape."""
    record = _signed_proof_record()
    path = tmp_path / "proof.json"
    dump(record, path)
    payload = json.loads(path.read_text())
    payload["schema_version"] = "99.0"
    path.write_text(json.dumps(payload))
    # The signature was over the v1.0 body; after forging schema_version
    # the signature won't verify. So just check that the version-gate
    # passes when --allow-any-schema-version is set; we don't pass --key.
    result = _run("validate", str(path), "--allow-any-schema-version")
    # Structural load_proof may still raise (it validates against schema.json);
    # but it should not raise BECAUSE of schema_version. Either OK (0) or a
    # different FAIL line — never the "schema_version mismatch" string.
    assert "schema_version mismatch" not in result.stdout
