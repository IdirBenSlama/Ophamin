"""Phase S3 — codec micro-benches.

Pinned baselines for:

- ``dump → load → verify_signature`` round-trip per proof
- HMAC-only ``sign`` cost
- JSON-Schema ``validate_schema`` cost
- ``list_proofs`` over an N=100-record directory

The benches use a small in-memory record so the time measured is the
codec's overhead, not the size of the payload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ophamin import __version__
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
    dump,
    list_proofs,
    load,
    validate_schema,
    verify_signature,
)


_SIGN_KEY = b"bench-codec-key"


def _make_record() -> EmpiricalProofRecord:
    threshold = Threshold("m", ">=", 0.9)
    claim = Claim(statement="x", operationalization="x",
                  threshold=threshold, h0="x", h1="x")
    prereg = PreRegistration(
        config_hash=content_hash({"x": 1}),
        data_hash=content_hash({"y": 1}),
        analysis_plan="x",
        preregistered_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    dataset = DatasetRef(
        name="d", content_hash=content_hash({"z": 1}), n_records=1,
        source="bench", kind="synthetic",
    )
    evidence = PillarEvidence(
        pillar="O.bench", statistic_name="m", statistic_value=0.95,
        library="pytest-benchmark", library_version="5.0",
    )
    verdict = Verdict.decide(0.95, threshold)
    return EmpiricalProofRecord(
        claim=claim, preregistration=prereg, datasets=[dataset],
        substrate_name="bench", substrate_git_commit="deadbeef" * 5,
        evidence=[evidence], verdict=verdict,
        reproduction=Reproduction(command="pytest tests/bench/"),
        ophamin_version=__version__, ophamin_git_commit="cafebabe" * 5,
    )


@pytest.fixture(scope="module")
def signed_record() -> EmpiricalProofRecord:
    return _make_record().sign(_SIGN_KEY)


@pytest.fixture
def proof_path(tmp_path: Path, signed_record: EmpiricalProofRecord) -> Path:
    return dump(signed_record, tmp_path / "bench.json")


# --- dump / load / verify round-trip ---------------------------------------


def test_bench_proof_dump_load_verify_round_trip(
    benchmark, tmp_path: Path, signed_record: EmpiricalProofRecord
) -> None:
    path = tmp_path / "round_trip.json"

    def _round_trip() -> None:
        dump(signed_record, path)
        loaded = load(path)
        assert loaded.verify_signature(_SIGN_KEY)

    benchmark(_round_trip)


def test_bench_proof_sign_hmac_only(benchmark) -> None:
    record = _make_record()
    benchmark(record.sign, _SIGN_KEY)


def test_bench_proof_verify_signature(benchmark, proof_path: Path) -> None:
    benchmark(verify_signature, proof_path, _SIGN_KEY)


def test_bench_proof_validate_schema(benchmark, proof_path: Path) -> None:
    benchmark(validate_schema, proof_path)


# --- list_proofs over a small corpus ---------------------------------------


def test_bench_list_proofs_n100(
    benchmark, tmp_path: Path, signed_record: EmpiricalProofRecord
) -> None:
    for i in range(100):
        dump(signed_record, tmp_path / f"proof_{i:03d}.json")
    benchmark(list_proofs, tmp_path)
