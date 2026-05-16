"""Phase S3 — synthesis-wheel micro-benches.

Pinned baselines for the campaign-level surfaces:

- ``summarize_directory`` over N=100 proofs
- ``compute_regression_alert`` on a 50-proof before/after pair
- ``build_index`` over N=100 proofs
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ophamin import __version__
from ophamin.comparing.regression_alert import compute_regression_alert
from ophamin.comparing.synthesis import summarize_directory
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    build_index,
    content_hash,
    dump,
)


_SIGN_KEY = b"bench-synthesis-key"


def _make_record(family: str = "family", observed: float = 0.95) -> EmpiricalProofRecord:
    threshold = Threshold("m", ">=", 0.9)
    claim = Claim(statement=family, operationalization="x",
                  threshold=threshold, h0="x", h1="x")
    prereg = PreRegistration(
        config_hash=content_hash({"x": 1, "family": family}),
        data_hash=content_hash({"y": 1, "family": family}),
        analysis_plan="x",
        preregistered_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    dataset = DatasetRef(
        name="d", content_hash=content_hash({"z": 1}), n_records=1,
        source="bench", kind="synthetic",
    )
    evidence = PillarEvidence(
        pillar="O.bench", statistic_name="m", statistic_value=observed,
        library="pytest-benchmark", library_version="5.0",
    )
    verdict = Verdict.decide(observed, threshold)
    return EmpiricalProofRecord(
        claim=claim, preregistration=prereg, datasets=[dataset],
        substrate_name="bench", substrate_git_commit="deadbeef" * 5,
        evidence=[evidence], verdict=verdict,
        reproduction=Reproduction(command="pytest tests/bench/"),
        ophamin_version=__version__, ophamin_git_commit="cafebabe" * 5,
    )


@pytest.fixture
def proofs_n100(tmp_path: Path) -> Path:
    for i in range(100):
        family = f"fam_{i % 10}"
        record = _make_record(family=family, observed=0.5 + (i % 50) / 100.0).sign(_SIGN_KEY)
        dump(record, tmp_path / f"{family}_{i:03d}.json")
    return tmp_path


def test_bench_summarize_directory_n100(benchmark, proofs_n100: Path) -> None:
    benchmark(summarize_directory, proofs_n100)


def test_bench_build_index_n100(benchmark, proofs_n100: Path) -> None:
    benchmark(build_index, proofs_n100)


def test_bench_compute_regression_alert_n50_pair(benchmark, tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    for i in range(50):
        family = f"fam_{i % 5}"
        # Same threshold both sides; different observed values to maximise pair-key hits
        rec_before = _make_record(family=family, observed=0.95).sign(_SIGN_KEY)
        rec_after = _make_record(family=family, observed=0.50 if i < 10 else 0.95).sign(_SIGN_KEY)
        dump(rec_before, before / f"{family}_{i:03d}.json")
        dump(rec_after, after / f"{family}_{i:03d}.json")
    benchmark(compute_regression_alert, before, after)
