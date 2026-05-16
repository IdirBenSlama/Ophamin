"""Hardening tests for the proof-record codec module.

Covers every typed-error path in :mod:`ophamin.measuring.proof.codec` plus
the directory-walking helpers + the CLI surface end-to-end via
``subprocess`` against ``python -m ophamin.cli proof <action>``.

Per the framework's no-fallback rule, every codec failure mode raises a
typed exception — these tests pin which exception each failure produces
so future refactors can't silently swap one for another.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ophamin import __version__
from ophamin.measuring.proof import (
    EmpiricalProofRecord,
    PillarEvidence,
    Reproduction,
    SCHEMA_VERSION,
    Verdict,
)
from ophamin.measuring.proof.codec import (
    ProofCodecError,
    ProofDecodeError,
    ProofIndex,
    ProofListEntry,
    ProofSchemaError,
    ProofSchemaVersionMismatchError,
    ProofSignatureError,
    ProofValidationError,
    SCHEMA_PATH,
    ValidationReport,
    _family_from_filename,
    build_index,
    dump,
    ingest,
    iter_proofs,
    list_proofs,
    load,
    validate,
    validate_schema,
    verify_signature,
)
from ophamin.measuring.proof.record import (
    Claim,
    DatasetRef,
    PreRegistration,
    Threshold,
    build_environment_lock,
    content_hash,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY


# --- shared fixtures -------------------------------------------------------


_TEST_KEY = b"test-key-for-codec-hardening"


def _make_record(*, outcome: str = "VALIDATED", observed: float = 0.95) -> EmpiricalProofRecord:
    """Construct a minimal well-formed EmpiricalProofRecord for testing.

    Deliberately small so the test files round-trip quickly. The
    important property is that ``record.validate()`` returns an empty
    list — every test that exercises a happy-path code path starts here.
    """
    threshold = Threshold(metric="dummy_metric", comparator=">=", value=0.90, units="fraction")
    claim = Claim(
        statement="dummy claim for codec hardening — always passes",
        operationalization="observed_value vs threshold",
        threshold=threshold,
        h0="observed < 0.90",
        h1="observed >= 0.90",
    )
    # pre-registration must precede created_at; backdate it 1 second
    now = datetime.now(timezone.utc)
    earlier = now.replace(microsecond=0)
    prereg = PreRegistration(
        config_hash=content_hash({"scenario": "test"}),
        data_hash=content_hash({"records": 1}),
        analysis_plan="single-shot dummy test",
        preregistered_at=earlier.isoformat(),
    )
    dataset = DatasetRef(
        name="dummy-corpus",
        content_hash=content_hash({"records": ["one"]}),
        n_records=1,
        source="hardcoded fixture",
        kind="synthetic",
    )
    evidence = PillarEvidence(
        pillar="O.test.dummy",
        statistic_name="dummy_metric",
        statistic_value=observed,
        library="pytest",
        library_version="1.0",
    )
    verdict = Verdict.decide(observed, threshold)
    # explicitly override outcome only if caller asked for an unusual one
    if outcome != verdict.outcome:
        verdict = Verdict(outcome, observed, threshold, "test override")
    record = EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=[dataset],
        substrate_name="test-substrate",
        substrate_git_commit="deadbeef" * 5,
        evidence=[evidence],
        verdict=verdict,
        reproduction=Reproduction(command="pytest tests/test_proof_codec.py"),
        ophamin_version=__version__,
        ophamin_git_commit="cafebabe" * 5,
    )
    return record


@pytest.fixture
def signed_record(tmp_path) -> Path:
    """A signed, well-formed proof record written to disk."""
    record = _make_record().sign(_TEST_KEY)
    return dump(record, tmp_path / "signed.json")


@pytest.fixture
def unsigned_record(tmp_path) -> Path:
    """A well-formed record written WITHOUT signing."""
    record = _make_record()
    return dump(record, tmp_path / "unsigned.json")


# --- dump / load round-trip ------------------------------------------------


def test_dump_creates_parent_directories(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    out = tmp_path / "deeper" / "nested" / "proof.json"
    path = dump(record, out)
    assert path == out
    assert out.exists()


def test_dump_load_round_trip(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    path = dump(record, tmp_path / "rt.json")
    loaded = load(path)
    assert loaded.proof_id == record.proof_id
    assert loaded.signature == record.signature
    assert loaded.verify_signature(_TEST_KEY)


def test_load_missing_file_raises_decode_error(tmp_path):
    with pytest.raises(ProofDecodeError):
        load(tmp_path / "does-not-exist.json")


def test_load_malformed_json_raises_decode_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("this is not JSON {{{", encoding="utf-8")
    with pytest.raises(ProofDecodeError):
        load(p)


def test_load_missing_required_keys_raises_decode_error(tmp_path):
    p = tmp_path / "partial.json"
    p.write_text(json.dumps({"proof_id": "abc", "schema_version": "1.0"}), encoding="utf-8")
    with pytest.raises(ProofDecodeError):
        load(p)


# --- schema validation ------------------------------------------------------


def test_validate_schema_against_well_formed_record(signed_record):
    ok, errors = validate_schema(signed_record)
    assert ok is True
    assert errors == ()


def test_validate_schema_against_missing_required_field(tmp_path):
    """Drop the `evidence` array (which is `required` in the schema) and
    verify the schema layer catches it before we even try to load."""
    record = _make_record().sign(_TEST_KEY)
    data = record.to_dict()
    del data["evidence"]
    p = tmp_path / "no-evidence.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = validate_schema(p)
    assert ok is False
    assert any("evidence" in e for e in errors)


def test_validate_schema_against_unknown_enum_value(tmp_path):
    """Verdict.outcome must be VALIDATED / REFUTED / INCONCLUSIVE per the
    schema enum; an unknown value must surface as a schema error."""
    record = _make_record().sign(_TEST_KEY)
    data = record.to_dict()
    data["verdict"]["outcome"] = "MAYBE"
    p = tmp_path / "bad-verdict.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    ok, errors = validate_schema(p)
    assert ok is False


def test_validate_schema_passes_for_every_shipped_proof():
    """All 28 proofs in the repo's `proofs/` directory must validate
    against the official schema — drift here would mean a scenario is
    emitting non-schema-compliant records."""
    proofs_dir = Path(__file__).parent.parent / "proofs"
    if not proofs_dir.exists():
        pytest.skip("proofs/ directory not present in this checkout")
    failures = []
    for p in iter_proofs(proofs_dir):
        ok, errors = validate_schema(p)
        if not ok:
            failures.append((p.name, errors))
    assert not failures, f"{len(failures)} shipped proofs fail schema:\n{failures}"


def test_validate_schema_on_unreadable_file_raises_decode_error(tmp_path):
    with pytest.raises(ProofDecodeError):
        validate_schema(tmp_path / "no-such.json")


# --- signature verification ------------------------------------------------


def test_verify_signature_with_correct_key(signed_record):
    assert verify_signature(signed_record, _TEST_KEY) is True


def test_verify_signature_with_wrong_key(signed_record):
    assert verify_signature(signed_record, b"wrong-key") is False


def test_verify_signature_unsigned_returns_false(unsigned_record):
    assert verify_signature(unsigned_record, _TEST_KEY) is False


# --- validate report -------------------------------------------------------


def test_validate_full_report_happy_path(signed_record):
    report = validate(signed_record, key=_TEST_KEY)
    assert isinstance(report, ValidationReport)
    assert report.schema_ok is True
    assert report.schema_errors == ()
    assert report.record_ok is True
    assert report.record_problems == ()
    assert report.signature_ok is True
    assert report.all_ok is True


def test_validate_skips_signature_when_no_key_provided(signed_record):
    report = validate(signed_record)
    assert report.signature_ok is None
    assert report.all_ok is True


def test_validate_report_is_frozen():
    """ValidationReport is frozen — callers can't mutate after the fact."""
    report = ValidationReport(
        schema_ok=True,
        schema_errors=(),
        record_ok=True,
        record_problems=(),
        signature_ok=None,
    )
    with pytest.raises(Exception):  # dataclass FrozenInstanceError or AttributeError
        report.schema_ok = False  # type: ignore[misc]


def test_validate_all_ok_false_when_schema_fails(tmp_path):
    p = tmp_path / "broken-schema.json"
    p.write_text(json.dumps({}), encoding="utf-8")
    report = validate(p)
    assert report.schema_ok is False
    assert report.all_ok is False


def test_validate_all_ok_false_when_signature_wrong(signed_record):
    report = validate(signed_record, key=b"different-key")
    assert report.signature_ok is False
    assert report.all_ok is False


# --- ingest ---------------------------------------------------------------


def test_ingest_happy_path_returns_record(signed_record):
    record = ingest(signed_record)
    assert isinstance(record, EmpiricalProofRecord)


def test_ingest_with_strict_signature_and_correct_key(signed_record):
    record = ingest(signed_record, key=_TEST_KEY, strict_signature=True)
    assert isinstance(record, EmpiricalProofRecord)


def test_ingest_strict_signature_without_key_raises(signed_record):
    with pytest.raises(ProofSignatureError):
        ingest(signed_record, strict_signature=True)


def test_ingest_strict_signature_with_wrong_key_raises(signed_record):
    with pytest.raises(ProofSignatureError):
        ingest(signed_record, key=b"wrong-key", strict_signature=True)


def test_ingest_with_schema_violation_raises_schema_error(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    data = record.to_dict()
    del data["claim"]
    p = tmp_path / "no-claim.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProofSchemaError):
        ingest(p)


def test_ingest_with_wrong_schema_version_raises_version_mismatch(tmp_path):
    """A record whose schema_version differs from the required one must
    raise loud — version drift is a real upgrade-path signal."""
    record = _make_record().sign(_TEST_KEY)
    data = record.to_dict()
    # We can't easily change schema_version via to_dict without breaking
    # the schema check (the schema pins schema_version="1.0" exactly).
    # So we'd need a future schema_version to test this — for v1.0 the
    # require_schema_version="2.0" path is the testable shape.
    p = tmp_path / "v1-but-need-v2.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProofSchemaVersionMismatchError):
        ingest(p, require_schema_version="2.0")


def test_ingest_allow_any_schema_version_accepts(signed_record):
    record = ingest(signed_record, require_schema_version=None)
    assert isinstance(record, EmpiricalProofRecord)


def test_ingest_decode_error_propagates(tmp_path):
    p = tmp_path / "not-json.json"
    p.write_text("garbage", encoding="utf-8")
    with pytest.raises(ProofCodecError):  # ProofDecodeError via load
        ingest(p)


# --- directory walking -----------------------------------------------------


def test_iter_proofs_is_sorted_deterministic(tmp_path):
    for name in ("b.json", "a.json", "c.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    paths = list(iter_proofs(tmp_path))
    assert [p.name for p in paths] == ["a.json", "b.json", "c.json"]


def test_iter_proofs_recurses_subdirectories(tmp_path):
    (tmp_path / "outer.json").write_text("{}", encoding="utf-8")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "inner.json").write_text("{}", encoding="utf-8")
    paths = list(iter_proofs(tmp_path))
    assert len(paths) == 2


def test_iter_proofs_skips_non_json(tmp_path):
    (tmp_path / "ok.json").write_text("{}", encoding="utf-8")
    (tmp_path / "skip.md").write_text("# heading", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("text", encoding="utf-8")
    paths = list(iter_proofs(tmp_path))
    assert [p.name for p in paths] == ["ok.json"]


def test_list_proofs_returns_entries(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "good.json")
    entries = list_proofs(tmp_path, key=_TEST_KEY)
    assert len(entries) == 1
    e = entries[0]
    assert isinstance(e, ProofListEntry)
    assert e.verdict == "VALIDATED"
    assert e.signature_ok is True
    assert e.error is None


def test_list_proofs_signature_ok_none_when_no_key(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "good.json")
    entries = list_proofs(tmp_path)
    assert entries[0].signature_ok is None


def test_list_proofs_continues_past_broken_file(tmp_path):
    """A broken JSON file produces an entry with `error` set; the walk
    does NOT stop — surfacing every record in the directory matters
    more than failing on the first bad one."""
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "good.json")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    entries = list_proofs(tmp_path)
    assert len(entries) == 2
    by_name = {e.path.name: e for e in entries}
    assert by_name["good.json"].error is None
    assert by_name["broken.json"].error is not None
    assert by_name["broken.json"].verdict is None


def test_list_proofs_empty_directory(tmp_path):
    assert list_proofs(tmp_path) == ()


# --- build_index ------------------------------------------------------------


def test_build_index_empty_directory(tmp_path):
    index = build_index(tmp_path)
    assert isinstance(index, ProofIndex)
    assert index.total == 0
    assert index.n_decode_errors == 0
    assert index.by_verdict == {}
    assert index.by_family == {}
    assert index.entries == ()


def test_build_index_aggregates_verdicts(tmp_path):
    """Three records with three different verdicts must produce the
    matching `by_verdict` counts."""
    r1 = _make_record(outcome="VALIDATED", observed=0.95)
    r2 = _make_record(outcome="REFUTED", observed=0.50)
    r3 = _make_record(outcome="INCONCLUSIVE", observed=0.85)
    dump(r1.sign(_TEST_KEY), tmp_path / "scenario_a_1.json")
    dump(r2.sign(_TEST_KEY), tmp_path / "scenario_b_1.json")
    dump(r3.sign(_TEST_KEY), tmp_path / "scenario_c_1.json")
    index = build_index(tmp_path)
    assert index.total == 3
    assert index.by_verdict == {"VALIDATED": 1, "REFUTED": 1, "INCONCLUSIVE": 1}
    assert set(index.by_family.keys()) == {"scenario"}
    assert index.by_family["scenario"] == 3


def test_build_index_counts_decode_errors(tmp_path):
    """A broken JSON contributes one entry with `ERROR` verdict + bumps
    n_decode_errors."""
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "good.json")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    index = build_index(tmp_path)
    assert index.total == 2
    assert index.n_decode_errors == 1
    assert index.by_verdict.get("ERROR") == 1
    assert index.by_verdict.get("VALIDATED") == 1


def test_build_index_family_from_filename(tmp_path):
    """Family is derived from the filename's first underscore-segment."""
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "immune_siege_a.json")
    dump(record, tmp_path / "immune_siege_b.json")
    dump(record, tmp_path / "rosetta_scaling_a.json")
    index = build_index(tmp_path)
    assert index.by_family == {"immune": 2, "rosetta": 1}


def test_family_helper_with_no_underscore_returns_stem(tmp_path):
    """A file like `lonely.json` has no underscore — the family is the
    full stem."""
    assert _family_from_filename(tmp_path / "lonely.json") == "lonely"


def test_build_index_markdown_has_canonical_sections(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "a_thing.json")
    index = build_index(tmp_path)
    md = index.to_markdown()
    assert "# Proof corpus index" in md
    assert "## By verdict" in md
    assert "## By family" in md
    assert "## All records" in md
    assert "VALIDATED" in md


def test_proof_index_is_frozen():
    """ProofIndex is frozen — callers can't mutate after the fact."""
    from pathlib import Path
    index = ProofIndex(
        root=Path("."),
        generated_at="2026-01-01T00:00:00+00:00",
        total=0,
        n_decode_errors=0,
        by_verdict={},
        by_family={},
        entries=(),
    )
    with pytest.raises(Exception):
        index.total = 1  # type: ignore[misc]


def test_build_index_via_module_export():
    """build_index is accessible from the package facade."""
    from ophamin.measuring.proof import build_index as facade_build_index
    assert facade_build_index is build_index


# --- CLI smoke tests (via subprocess) ---------------------------------------


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke `python -m ophamin.cli` with the given args; return result."""
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "proof", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_cli_proof_show_smoke(signed_record):
    result = _run_cli("show", str(signed_record))
    assert result.returncode == 0, result.stderr
    assert "Ophamin Empirical Proof Record" in result.stdout


def test_cli_proof_verify_with_matching_key(tmp_path):
    record = _make_record().sign(DEFAULT_SIGN_KEY)
    path = dump(record, tmp_path / "default-signed.json")
    result = _run_cli("verify", str(path))  # uses default key
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_proof_verify_with_wrong_key(signed_record):
    result = _run_cli("verify", str(signed_record), "--key=different")
    assert result.returncode == 1


def test_cli_proof_validate_smoke(signed_record):
    result = _run_cli("validate", str(signed_record), "--with-signature", "--key=test-key-for-codec-hardening")
    assert result.returncode == 0
    assert "all_ok:         True" in result.stdout


def test_cli_proof_ingest_smoke(signed_record):
    result = _run_cli("ingest", str(signed_record), "--strict-signature", "--key=test-key-for-codec-hardening")
    assert result.returncode == 0
    assert "OK: ingested" in result.stdout


def test_cli_proof_ingest_fails_on_bad_signature(signed_record):
    result = _run_cli(
        "ingest", str(signed_record), "--strict-signature", "--key=wrong-key"
    )
    assert result.returncode == 1
    assert "ophamin proof ingest" in result.stderr


def test_cli_proof_list_smoke(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "a.json")
    dump(record, tmp_path / "b.json")
    result = _run_cli("list", str(tmp_path))
    assert result.returncode == 0
    assert "VALIDATED" in result.stdout


def test_cli_proof_list_json_output(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "a.json")
    result = _run_cli("list", str(tmp_path), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload[0]["verdict"] == "VALIDATED"


def test_cli_proof_list_on_nonexistent_directory(tmp_path):
    result = _run_cli("list", str(tmp_path / "does-not-exist"))
    assert result.returncode == 2
    assert "is not a directory" in result.stderr


def test_cli_proof_index_to_stdout(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "scenario_a.json")
    result = _run_cli("index", str(tmp_path))
    assert result.returncode == 0
    assert "# Proof corpus index" in result.stdout
    assert "VALIDATED" in result.stdout


def test_cli_proof_index_to_file(tmp_path):
    record = _make_record().sign(_TEST_KEY)
    dump(record, tmp_path / "scenario_a.json")
    out = tmp_path / "INDEX.md"
    result = _run_cli("index", str(tmp_path), "--out", str(out))
    assert result.returncode == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "# Proof corpus index" in text


def test_cli_proof_index_on_nonexistent_directory(tmp_path):
    result = _run_cli("index", str(tmp_path / "does-not-exist"))
    assert result.returncode == 2
    assert "is not a directory" in result.stderr


# --- schema asset itself ---------------------------------------------------


def test_schema_path_exists_and_loads():
    """The schema asset must be present and parseable as JSON."""
    assert SCHEMA_PATH.exists()
    json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_path_re_exported_at_codec_module():
    """`SCHEMA_PATH` is exported from both `proof` and `proof.codec` —
    callers can import from either location."""
    from ophamin.measuring.proof import SCHEMA_PATH as proof_schema_path
    from ophamin.measuring.proof.codec import SCHEMA_PATH as codec_schema_path
    assert proof_schema_path == codec_schema_path
