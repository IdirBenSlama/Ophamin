"""Hardening tests for `ReportRunner.run_batch` + `ophamin report-batch` (Move M)."""

from __future__ import annotations

import json
import subprocess
import sys
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
)
from ophamin.reporting import ReportFormat, ReportRunner


_SIGN_KEY = b"report-batch-test-key"


def _make_record(*, observed: float = 0.95) -> EmpiricalProofRecord:
    threshold = Threshold("m", ">=", 0.9)
    claim = Claim(statement="x", operationalization="x",
                  threshold=threshold, h0="x", h1="x")
    earlier = datetime.now(timezone.utc).replace(microsecond=0)
    prereg = PreRegistration(
        config_hash=content_hash({"x": 1}), data_hash=content_hash({"y": 1}),
        analysis_plan="x", preregistered_at=earlier.isoformat(),
    )
    dataset = DatasetRef(
        name="d", content_hash=content_hash({"z": 1}), n_records=1,
        source="hardcoded", kind="synthetic",
    )
    evidence = PillarEvidence(
        pillar="P", statistic_name="m", statistic_value=observed,
        library="pytest", library_version="1.0",
    )
    verdict = Verdict.decide(observed, threshold)
    return EmpiricalProofRecord(
        claim=claim, preregistration=prereg, datasets=[dataset],
        substrate_name="x", substrate_git_commit="deadbeef" * 5,
        evidence=[evidence], verdict=verdict,
        reproduction=Reproduction(command="pytest"),
        ophamin_version=__version__, ophamin_git_commit="cafebabe" * 5,
    )


def test_run_batch_renders_every_proof_into_out_dir(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    records_dir.mkdir()
    dump(_make_record().sign(_SIGN_KEY), records_dir / "a.json")
    dump(_make_record(observed=0.5).sign(_SIGN_KEY), records_dir / "b.json")
    summary = ReportRunner().run_batch(records_dir, out_dir, ReportFormat.MARKDOWN)
    assert summary["n_rendered"] == 2
    assert summary["n_skipped"] == 0
    assert (out_dir / "a.md").is_file()
    assert (out_dir / "b.md").is_file()
    assert (out_dir / "INDEX.md").is_file()


def test_run_batch_index_lists_every_rendered_record(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    records_dir.mkdir()
    dump(_make_record(observed=0.95).sign(_SIGN_KEY), records_dir / "validated.json")
    dump(_make_record(observed=0.50).sign(_SIGN_KEY), records_dir / "refuted.json")
    ReportRunner().run_batch(records_dir, out_dir, ReportFormat.MARKDOWN)
    index = (out_dir / "INDEX.md").read_text(encoding="utf-8")
    assert "VALIDATED" in index
    assert "REFUTED" in index
    assert "validated.json" in index
    assert "refuted.json" in index


def test_run_batch_html_format(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    records_dir.mkdir()
    dump(_make_record().sign(_SIGN_KEY), records_dir / "a.json")
    summary = ReportRunner().run_batch(records_dir, out_dir, ReportFormat.HTML)
    assert summary["n_rendered"] == 1
    assert (out_dir / "a.html").is_file()


def test_run_batch_latex_format(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    records_dir.mkdir()
    dump(_make_record().sign(_SIGN_KEY), records_dir / "a.json")
    summary = ReportRunner().run_batch(records_dir, out_dir, ReportFormat.LATEX)
    assert summary["n_rendered"] == 1
    assert (out_dir / "a.tex").is_file()


def test_run_batch_recurses_subdirectories(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    (records_dir / "tier_x").mkdir(parents=True)
    dump(_make_record().sign(_SIGN_KEY), records_dir / "tier_x" / "deep.json")
    summary = ReportRunner().run_batch(records_dir, out_dir, ReportFormat.MARKDOWN)
    assert summary["n_rendered"] == 1


def test_run_batch_skips_undecodable(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    records_dir.mkdir()
    dump(_make_record().sign(_SIGN_KEY), records_dir / "good.json")
    (records_dir / "broken.json").write_text("not json", encoding="utf-8")
    summary = ReportRunner().run_batch(records_dir, out_dir, ReportFormat.MARKDOWN)
    assert summary["n_rendered"] == 1
    assert summary["n_skipped"] == 1
    assert any("broken.json" in p for p, _ in summary["skipped_paths"])


def test_run_batch_empty_directory(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    records_dir.mkdir()
    summary = ReportRunner().run_batch(records_dir, out_dir, ReportFormat.MARKDOWN)
    assert summary["n_rendered"] == 0
    assert summary["n_skipped"] == 0
    assert (out_dir / "INDEX.md").is_file()


# --- CLI ---


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "report-batch", *args],
        capture_output=True, text=True,
    )


def test_cli_report_batch_smoke(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    records_dir.mkdir()
    dump(_make_record().sign(_SIGN_KEY), records_dir / "a.json")
    result = _run_cli(str(records_dir), "--out-dir", str(out_dir))
    assert result.returncode == 0
    assert "rendered 1 record(s)" in result.stdout
    assert (out_dir / "INDEX.md").is_file()


def test_cli_report_batch_html_format(tmp_path):
    records_dir = tmp_path / "proofs"
    out_dir = tmp_path / "rendered"
    records_dir.mkdir()
    dump(_make_record().sign(_SIGN_KEY), records_dir / "a.json")
    result = _run_cli(
        str(records_dir), "--out-dir", str(out_dir), "--format", "html"
    )
    assert result.returncode == 0
    assert (out_dir / "a.html").is_file()


def test_cli_report_batch_nonexistent_dir(tmp_path):
    result = _run_cli(str(tmp_path / "missing"))
    assert result.returncode == 2
