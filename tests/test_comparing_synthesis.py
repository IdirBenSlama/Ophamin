"""Hardening tests for the comparing/synthesis module + CLI surface.

Three operations exercised:

- :func:`summarize_directory` → :class:`CampaignSummary`
- :func:`diagnose_proof` → :class:`Diagnostic`
- :func:`analyze_metric` → :class:`MetricTrajectory`

CLI tests run via subprocess against ``python -m ophamin.cli summarize
/ diagnose / analyze``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ophamin import __version__
from ophamin.comparing.synthesis import (
    CampaignSummary,
    Diagnostic,
    MetricTrajectory,
    VerdictFlip,
    analyze_metric,
    diagnose_proof,
    summarize_directory,
)
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


_SIGN_KEY = b"synthesis-test-key"


def _make_record(
    *,
    statistic_name: str = "test_metric",
    statistic_value: float = 0.95,
    threshold_value: float = 0.90,
    comparator: str = ">=",
    substrate_commit: str = "deadbeef" * 5,
) -> EmpiricalProofRecord:
    threshold = Threshold(
        metric=statistic_name, comparator=comparator, value=threshold_value,
    )
    claim = Claim(
        statement="dummy synthesis-test claim",
        operationalization="observed vs threshold",
        threshold=threshold,
        h0=f"observed {('<' if comparator == '>=' else '>')} {threshold_value}",
        h1=f"observed {comparator} {threshold_value}",
    )
    earlier = datetime.now(timezone.utc).replace(microsecond=0)
    prereg = PreRegistration(
        config_hash=content_hash({"scenario": "test"}),
        data_hash=content_hash({"records": 1}),
        analysis_plan="dummy",
        preregistered_at=earlier.isoformat(),
    )
    dataset = DatasetRef(
        name="dummy-corpus",
        content_hash=content_hash({"r": 1}),
        n_records=1,
        source="hardcoded",
        kind="synthetic",
    )
    evidence = PillarEvidence(
        pillar="O.test.dummy",
        statistic_name=statistic_name,
        statistic_value=statistic_value,
        library="pytest",
        library_version="1.0",
    )
    verdict = Verdict.decide(statistic_value, threshold)
    return EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=[dataset],
        substrate_name="test-substrate",
        substrate_git_commit=substrate_commit,
        evidence=[evidence],
        verdict=verdict,
        reproduction=Reproduction(command="pytest"),
        ophamin_version=__version__,
        ophamin_git_commit="cafebabe" * 5,
    )


# --- summarize_directory --------------------------------------------------


def test_summarize_empty_directory(tmp_path):
    summary = summarize_directory(tmp_path)
    assert isinstance(summary, CampaignSummary)
    assert summary.total == 0
    assert summary.by_verdict == {}
    assert summary.verdict_flips == ()


def test_summarize_counts_verdicts(tmp_path):
    dump(_make_record(statistic_value=0.95).sign(_SIGN_KEY), tmp_path / "fam_a.json")
    dump(_make_record(statistic_value=0.50).sign(_SIGN_KEY), tmp_path / "fam_b.json")
    summary = summarize_directory(tmp_path)
    assert summary.total == 2
    assert summary.by_verdict.get("VALIDATED") == 1
    assert summary.by_verdict.get("REFUTED") == 1


def test_summarize_family_grouping_from_filename(tmp_path):
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "immune_siege_a.json")
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "immune_siege_b.json")
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "rosetta_scaling.json")
    summary = summarize_directory(tmp_path)
    assert summary.by_family == {"immune": 2, "rosetta": 1}


def test_summarize_per_substrate_commit_breakdown(tmp_path):
    dump(_make_record(substrate_commit="aa" * 20).sign(_SIGN_KEY), tmp_path / "fam_a.json")
    dump(_make_record(substrate_commit="bb" * 20).sign(_SIGN_KEY), tmp_path / "fam_b.json")
    summary = summarize_directory(tmp_path)
    assert set(summary.by_substrate_commit) == {"aa" * 6, "bb" * 6}


def test_summarize_detects_verdict_flip_same_family(tmp_path):
    """Two records, same family, different commits, different verdicts."""
    dump(
        _make_record(statistic_value=0.95, substrate_commit="aa" * 20).sign(_SIGN_KEY),
        tmp_path / "immune_a.json",
    )
    dump(
        _make_record(statistic_value=0.50, substrate_commit="bb" * 20).sign(_SIGN_KEY),
        tmp_path / "immune_b.json",
    )
    summary = summarize_directory(tmp_path)
    assert len(summary.verdict_flips) == 1
    flip = summary.verdict_flips[0]
    assert flip.family == "immune"
    assert {flip.verdict_a, flip.verdict_b} == {"VALIDATED", "REFUTED"}


def test_summarize_no_flip_when_same_verdict(tmp_path):
    dump(
        _make_record(statistic_value=0.95, substrate_commit="aa" * 20).sign(_SIGN_KEY),
        tmp_path / "immune_a.json",
    )
    dump(
        _make_record(statistic_value=0.99, substrate_commit="bb" * 20).sign(_SIGN_KEY),
        tmp_path / "immune_b.json",
    )
    summary = summarize_directory(tmp_path)
    assert summary.verdict_flips == ()


def test_summarize_continues_past_decode_errors(tmp_path):
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "fam_a.json")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    summary = summarize_directory(tmp_path)
    assert summary.total == 2
    assert summary.n_decode_errors == 1
    assert summary.by_verdict.get("ERROR") == 1


def test_campaign_summary_markdown_has_sections(tmp_path):
    dump(_make_record(substrate_commit="aa" * 20).sign(_SIGN_KEY), tmp_path / "fam.json")
    summary = summarize_directory(tmp_path)
    md = summary.to_markdown()
    assert "# Campaign summary" in md
    assert "## Verdict distribution" in md
    assert "## Family distribution" in md
    assert "## Per-substrate-commit" in md


def test_campaign_summary_is_frozen(tmp_path):
    summary = summarize_directory(tmp_path)
    with pytest.raises(Exception):
        summary.total = 999  # type: ignore[misc]


# --- diagnose_proof -------------------------------------------------------


def test_diagnose_returns_diagnostic_for_known_proof(tmp_path):
    path = tmp_path / "scenario_a.json"
    dump(_make_record().sign(_SIGN_KEY), path)
    diag = diagnose_proof(path)
    assert isinstance(diag, Diagnostic)
    assert diag.verdict_outcome == "VALIDATED"


def test_diagnose_finds_same_family_siblings(tmp_path):
    target = tmp_path / "immune_a.json"
    dump(_make_record().sign(_SIGN_KEY), target)
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "immune_b.json")
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "rosetta_a.json")
    diag = diagnose_proof(target)
    paths = {s.path.name for s in diag.closest_family_siblings}
    assert paths == {"immune_b.json"}


def test_diagnose_with_explicit_corpus_dir(tmp_path):
    target_dir = tmp_path / "tier"
    target_dir.mkdir()
    target = target_dir / "immune.json"
    dump(_make_record().sign(_SIGN_KEY), target)
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "immune_other.json")
    diag = diagnose_proof(target, corpus_dir=tmp_path)
    sibling_names = {s.path.name for s in diag.closest_family_siblings}
    assert "immune_other.json" in sibling_names


def test_diagnose_on_missing_file_raises(tmp_path):
    from ophamin.measuring.proof.codec import ProofDecodeError
    with pytest.raises(ProofDecodeError):
        diagnose_proof(tmp_path / "does-not-exist.json")


def test_diagnostic_markdown_renders(tmp_path):
    target = tmp_path / "scenario_a.json"
    dump(_make_record().sign(_SIGN_KEY), target)
    diag = diagnose_proof(target)
    md = diag.to_markdown()
    assert "# Proof diagnostic" in md
    assert "VALIDATED" in md


def test_diagnostic_is_frozen(tmp_path):
    target = tmp_path / "x.json"
    dump(_make_record().sign(_SIGN_KEY), target)
    diag = diagnose_proof(target)
    with pytest.raises(Exception):
        diag.verdict_outcome = "MAYBE"  # type: ignore[misc]


# --- analyze_metric -------------------------------------------------------


def test_analyze_metric_finds_matching_evidence(tmp_path):
    dump(_make_record(statistic_name="my_metric", statistic_value=0.5).sign(_SIGN_KEY),
         tmp_path / "a.json")
    dump(_make_record(statistic_name="my_metric", statistic_value=0.7).sign(_SIGN_KEY),
         tmp_path / "b.json")
    dump(_make_record(statistic_name="other_metric", statistic_value=0.9).sign(_SIGN_KEY),
         tmp_path / "c.json")
    traj = analyze_metric("my_metric", tmp_path)
    assert traj.n_values == 2
    assert traj.minimum == 0.5
    assert traj.maximum == 0.7
    assert traj.mean == pytest.approx(0.6)


def test_analyze_metric_empty_when_no_match(tmp_path):
    dump(_make_record(statistic_name="other_metric").sign(_SIGN_KEY), tmp_path / "a.json")
    traj = analyze_metric("nonexistent_metric", tmp_path)
    assert traj.n_values == 0
    assert traj.values == ()
    assert traj.mean is None
    assert traj.stdev is None


def test_analyze_metric_stdev_none_when_one_value(tmp_path):
    dump(_make_record(statistic_name="m").sign(_SIGN_KEY), tmp_path / "a.json")
    traj = analyze_metric("m", tmp_path)
    assert traj.n_values == 1
    assert traj.stdev is None


def test_analyze_metric_stdev_present_when_multiple(tmp_path):
    dump(_make_record(statistic_name="m", statistic_value=0.0).sign(_SIGN_KEY),
         tmp_path / "a.json")
    dump(_make_record(statistic_name="m", statistic_value=1.0).sign(_SIGN_KEY),
         tmp_path / "b.json")
    traj = analyze_metric("m", tmp_path)
    assert traj.stdev is not None
    assert traj.stdev > 0


def test_analyze_metric_skips_decode_errors(tmp_path):
    dump(_make_record(statistic_name="m").sign(_SIGN_KEY), tmp_path / "a.json")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    traj = analyze_metric("m", tmp_path)
    assert traj.n_proofs_scanned == 2
    assert traj.n_values == 1


def test_metric_trajectory_is_frozen(tmp_path):
    traj = analyze_metric("m", tmp_path)
    with pytest.raises(Exception):
        traj.n_values = 999  # type: ignore[misc]


def test_metric_trajectory_markdown_empty(tmp_path):
    traj = analyze_metric("m", tmp_path)
    md = traj.to_markdown()
    assert "Metric trajectory" in md
    assert "no PillarEvidence" in md


def test_metric_trajectory_markdown_populated(tmp_path):
    dump(_make_record(statistic_name="m", statistic_value=0.5).sign(_SIGN_KEY),
         tmp_path / "a.json")
    traj = analyze_metric("m", tmp_path)
    md = traj.to_markdown()
    assert "## Summary statistics" in md
    assert "## All values" in md
    assert "0.5" in md


# --- CLI smoke tests ------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", *args],
        capture_output=True,
        text=True,
    )


def test_cli_summarize_smoke(tmp_path):
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "fam.json")
    result = _run_cli("summarize", str(tmp_path))
    assert result.returncode == 0
    assert "# Campaign summary" in result.stdout


def test_cli_summarize_json(tmp_path):
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "fam.json")
    result = _run_cli("summarize", str(tmp_path), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["total"] == 1
    assert "VALIDATED" in payload["by_verdict"]


def test_cli_summarize_writes_out_file(tmp_path):
    dump(_make_record().sign(_SIGN_KEY), tmp_path / "fam.json")
    out = tmp_path / "summary.md"
    result = _run_cli("summarize", str(tmp_path), "--out", str(out))
    assert result.returncode == 0
    assert out.exists()
    assert "# Campaign summary" in out.read_text(encoding="utf-8")


def test_cli_summarize_on_nonexistent_directory(tmp_path):
    result = _run_cli("summarize", str(tmp_path / "missing"))
    assert result.returncode == 2


def test_cli_diagnose_smoke(tmp_path):
    target = tmp_path / "x.json"
    dump(_make_record().sign(_SIGN_KEY), target)
    result = _run_cli("diagnose", str(target))
    assert result.returncode == 0
    assert "# Proof diagnostic" in result.stdout


def test_cli_diagnose_on_missing_file(tmp_path):
    result = _run_cli("diagnose", str(tmp_path / "missing.json"))
    assert result.returncode == 2


def test_cli_analyze_smoke(tmp_path):
    dump(_make_record(statistic_name="m", statistic_value=0.42).sign(_SIGN_KEY),
         tmp_path / "a.json")
    result = _run_cli("analyze", "m", "--across", str(tmp_path))
    assert result.returncode == 0
    assert "Metric trajectory" in result.stdout


def test_cli_analyze_json(tmp_path):
    dump(_make_record(statistic_name="m", statistic_value=0.42).sign(_SIGN_KEY),
         tmp_path / "a.json")
    result = _run_cli("analyze", "m", "--across", str(tmp_path), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["n_values"] == 1
    assert payload["values"][0]["value"] == 0.42


def test_cli_analyze_on_nonexistent_directory(tmp_path):
    result = _run_cli("analyze", "m", "--across", str(tmp_path / "missing"))
    assert result.returncode == 2
