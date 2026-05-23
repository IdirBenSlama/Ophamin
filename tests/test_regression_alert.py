"""Hardening tests for the regression-alert daemon (Move J)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


from ophamin import __version__
from ophamin.comparing.regression_alert import (
    REGRESSION_ALERT_SCHEMA_VERSION,
    ProofSnapshot,
    RegressionAlertRecord,
    classify_transition,
    compute_regression_alert,
    dump_alert,
    load_alert,
    scan_proof_directory,
    snapshot_one,
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


_SIGN_KEY = b"regression-alert-test-key"


def _make_record(
    *,
    family_prefix: str = "scenario_a",
    observed: float = 0.95,
    threshold_value: float = 0.90,
    comparator: str = ">=",
    metric: str = "test_metric",
    commit: str = "deadbeef" * 5,
) -> EmpiricalProofRecord:
    threshold = Threshold(metric=metric, comparator=comparator, value=threshold_value)
    claim = Claim(
        statement="dummy",
        operationalization="dummy",
        threshold=threshold,
        h0="x",
        h1="x",
    )
    earlier = datetime.now(timezone.utc).replace(microsecond=0)
    prereg = PreRegistration(
        config_hash=content_hash({"x": 1}),
        data_hash=content_hash({"y": 1}),
        analysis_plan="x",
        preregistered_at=earlier.isoformat(),
    )
    dataset = DatasetRef(
        name="dummy",
        content_hash=content_hash({"z": 1}),
        n_records=1,
        source="hardcoded",
        kind="synthetic",
    )
    evidence = PillarEvidence(
        pillar="O.test", statistic_name=metric, statistic_value=observed,
        library="pytest", library_version="1.0",
    )
    verdict = Verdict.decide(observed, threshold)
    return EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=[dataset],
        substrate_name="kimera-test",
        substrate_git_commit=commit,
        evidence=[evidence],
        verdict=verdict,
        reproduction=Reproduction(command="pytest"),
        ophamin_version=__version__,
        ophamin_git_commit="cafebabe" * 5,
    )


def _write_proof(tmp_path: Path, name: str, **kwargs) -> Path:
    """Helper: write a proof to `tmp_path/<name>.json` and return the path."""
    record = _make_record(**kwargs).sign(_SIGN_KEY)
    return dump(record, tmp_path / f"{name}.json")


# --- classify_transition --------------------------------------------------


def test_classify_transition_regression_from_validated():
    assert classify_transition("VALIDATED", "REFUTED") == "regression"


def test_classify_transition_regression_from_inconclusive():
    assert classify_transition("INCONCLUSIVE", "REFUTED") == "regression"


def test_classify_transition_recovery():
    assert classify_transition("REFUTED", "VALIDATED") == "recovery"


def test_classify_transition_lateral_refuted_to_inconclusive():
    assert classify_transition("REFUTED", "INCONCLUSIVE") == "lateral"


def test_classify_transition_lateral_validated_to_inconclusive():
    assert classify_transition("VALIDATED", "INCONCLUSIVE") == "lateral"


def test_classify_transition_unchanged():
    for v in ("VALIDATED", "REFUTED", "INCONCLUSIVE"):
        assert classify_transition(v, v) == "unchanged"


# --- snapshot scanning ----------------------------------------------------


def test_snapshot_one_extracts_metadata(tmp_path):
    path = _write_proof(tmp_path, "scenario_a_proof", observed=0.5, threshold_value=0.4)
    from ophamin.measuring.proof.codec import load
    record = load(path)
    snap = snapshot_one(record, path)
    assert isinstance(snap, ProofSnapshot)
    assert snap.family == "scenario"  # filename "scenario_a_proof" → family "scenario"
    assert snap.verdict == "VALIDATED"
    assert snap.observed_value == 0.5
    assert snap.threshold_value == 0.4


def test_scan_proof_directory_skips_undecodable(tmp_path):
    _write_proof(tmp_path, "good")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    snapshots = scan_proof_directory(tmp_path)
    assert len(snapshots) == 1
    assert snapshots[0].family == "good"


def test_pair_key_includes_family_metric_threshold():
    """Two snapshots with same family but different threshold value
    have DIFFERENT pair_keys — so different-threshold variants of the
    same scenario don't accidentally pair."""
    snap_a = ProofSnapshot(
        path=Path("a.json"), family="immune", verdict="VALIDATED",
        observed_value=0.05, threshold_metric="fp_rate", threshold_comparator="<=",
        threshold_value=0.10, substrate_git_commit="aa", claim_statement_hash="x",
    )
    snap_b = ProofSnapshot(
        path=Path("b.json"), family="immune", verdict="VALIDATED",
        observed_value=0.05, threshold_metric="fp_rate", threshold_comparator="<=",
        threshold_value=0.20, substrate_git_commit="aa", claim_statement_hash="x",
    )
    assert snap_a.pair_key != snap_b.pair_key


# --- compute_regression_alert ---------------------------------------------


def test_alert_detects_regression(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    # Same scenario name + same threshold; verdict flips
    _write_proof(before, "immune_a", observed=0.05, threshold_value=0.10, comparator="<=",
                 metric="fp_rate", commit="aa" * 20)
    _write_proof(after, "immune_a", observed=0.30, threshold_value=0.10, comparator="<=",
                 metric="fp_rate", commit="bb" * 20)
    alert = compute_regression_alert(before, after)
    assert alert.has_regressions
    assert alert.n_regressions == 1
    t = alert.transitions[0]
    assert t.transition_class == "regression"
    assert t.before_verdict == "VALIDATED"
    assert t.after_verdict == "REFUTED"


def test_alert_detects_recovery(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    _write_proof(before, "immune_a", observed=0.30, threshold_value=0.10, comparator="<=",
                 metric="fp_rate", commit="aa" * 20)
    _write_proof(after, "immune_a", observed=0.05, threshold_value=0.10, comparator="<=",
                 metric="fp_rate", commit="bb" * 20)
    alert = compute_regression_alert(before, after)
    assert not alert.has_regressions
    assert alert.n_recoveries == 1


def test_alert_no_regressions_when_unchanged(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    _write_proof(before, "immune_a", observed=0.05, threshold_value=0.10, comparator="<=",
                 metric="fp_rate", commit="aa" * 20)
    _write_proof(after, "immune_a", observed=0.04, threshold_value=0.10, comparator="<=",
                 metric="fp_rate", commit="bb" * 20)
    alert = compute_regression_alert(before, after)
    assert not alert.has_regressions
    assert alert.n_unchanged == 1


def test_alert_unmatched_in_each_direction(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    _write_proof(before, "only_in_before", observed=0.5, threshold_value=0.4,
                 metric="m_only_before")
    _write_proof(after, "only_in_after", observed=0.5, threshold_value=0.4,
                 metric="m_only_after")
    alert = compute_regression_alert(before, after)
    assert alert.transitions == []
    assert len(alert.unmatched_in_before) == 1
    assert len(alert.unmatched_in_after) == 1


def test_alert_mixed_outcomes(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    # 1 regression + 1 recovery + 1 unchanged
    _write_proof(before, "regress_a", observed=0.05, threshold_value=0.10, comparator="<=",
                 metric="r_metric", commit="aa" * 20)
    _write_proof(after, "regress_a", observed=0.30, threshold_value=0.10, comparator="<=",
                 metric="r_metric", commit="bb" * 20)
    _write_proof(before, "recover_a", observed=0.30, threshold_value=0.10, comparator="<=",
                 metric="rec_metric", commit="aa" * 20)
    _write_proof(after, "recover_a", observed=0.05, threshold_value=0.10, comparator="<=",
                 metric="rec_metric", commit="bb" * 20)
    _write_proof(before, "stable_a", observed=0.95, threshold_value=0.90, comparator=">=",
                 metric="stable_metric", commit="aa" * 20)
    _write_proof(after, "stable_a", observed=0.99, threshold_value=0.90, comparator=">=",
                 metric="stable_metric", commit="bb" * 20)
    alert = compute_regression_alert(before, after)
    assert alert.n_regressions == 1
    assert alert.n_recoveries == 1
    assert alert.n_unchanged == 1


# --- record IO / signing --------------------------------------------------


def test_record_sign_and_verify(tmp_path):
    before = tmp_path / "before"; before.mkdir()
    after = tmp_path / "after"; after.mkdir()
    _write_proof(before, "x_a", observed=0.5, threshold_value=0.4)
    _write_proof(after, "x_a", observed=0.6, threshold_value=0.4)
    alert = compute_regression_alert(before, after).sign(_SIGN_KEY)
    assert alert.verify_signature(_SIGN_KEY)
    assert not alert.verify_signature(b"wrong")


def test_record_dump_load_round_trip(tmp_path):
    before = tmp_path / "before"; before.mkdir()
    after = tmp_path / "after"; after.mkdir()
    _write_proof(before, "x_a", observed=0.05, threshold_value=0.10, comparator="<=",
                 metric="x_metric", commit="aa" * 20)
    _write_proof(after, "x_a", observed=0.30, threshold_value=0.10, comparator="<=",
                 metric="x_metric", commit="bb" * 20)
    alert = compute_regression_alert(before, after).sign(_SIGN_KEY)
    path = dump_alert(alert, tmp_path / "alert.json")
    loaded = load_alert(path)
    assert loaded.alert_id == alert.alert_id
    assert loaded.verify_signature(_SIGN_KEY)
    assert loaded.has_regressions == alert.has_regressions


def test_record_alert_id_is_content_hash():
    a1 = RegressionAlertRecord(before_root="a", after_root="b", n_before=0, n_after=0)
    a2 = RegressionAlertRecord(before_root="x", after_root="y", n_before=0, n_after=0)
    assert a1.alert_id != a2.alert_id


def test_record_markdown_has_canonical_sections(tmp_path):
    before = tmp_path / "before"; before.mkdir()
    after = tmp_path / "after"; after.mkdir()
    _write_proof(before, "x_a", observed=0.05, threshold_value=0.10, comparator="<=",
                 metric="x_metric", commit="aa" * 20)
    _write_proof(after, "x_a", observed=0.30, threshold_value=0.10, comparator="<=",
                 metric="x_metric", commit="bb" * 20)
    alert = compute_regression_alert(before, after)
    md = alert.to_markdown()
    assert "# Regression alert" in md
    assert "Regressions" in md  # only present when n_regressions > 0


def test_record_schema_version_is_pinned():
    assert REGRESSION_ALERT_SCHEMA_VERSION == "regression-alert/1.0"


# --- CLI smoke tests ------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "watch-proofs", *args],
        capture_output=True, text=True,
    )


def test_cli_watch_proofs_exit_0_on_no_regressions(tmp_path):
    before = tmp_path / "before"; before.mkdir()
    after = tmp_path / "after"; after.mkdir()
    _write_proof(before, "x_a", observed=0.5)
    _write_proof(after, "x_a", observed=0.6)
    result = _run_cli("--before", str(before), "--after", str(after), "--no-sign")
    assert result.returncode == 0


def test_cli_watch_proofs_exit_1_on_regression(tmp_path):
    before = tmp_path / "before"; before.mkdir()
    after = tmp_path / "after"; after.mkdir()
    _write_proof(before, "x_a", observed=0.05, threshold_value=0.10, comparator="<=",
                 metric="m", commit="aa" * 20)
    _write_proof(after, "x_a", observed=0.30, threshold_value=0.10, comparator="<=",
                 metric="m", commit="bb" * 20)
    result = _run_cli("--before", str(before), "--after", str(after), "--no-sign")
    assert result.returncode == 1


def test_cli_watch_proofs_writes_out_file(tmp_path):
    before = tmp_path / "before"; before.mkdir()
    after = tmp_path / "after"; after.mkdir()
    _write_proof(before, "x_a", observed=0.5)
    _write_proof(after, "x_a", observed=0.6)
    out = tmp_path / "alert.json"
    result = _run_cli(
        "--before", str(before), "--after", str(after), "--out", str(out), "--no-sign"
    )
    assert result.returncode == 0
    assert out.exists()


def test_cli_watch_proofs_json_output(tmp_path):
    before = tmp_path / "before"; before.mkdir()
    after = tmp_path / "after"; after.mkdir()
    _write_proof(before, "x_a", observed=0.5)
    _write_proof(after, "x_a", observed=0.6)
    result = _run_cli("--before", str(before), "--after", str(after), "--json", "--no-sign")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "alert_id" in payload
    assert payload["n_before"] == 1
    assert payload["n_after"] == 1


def test_cli_watch_proofs_missing_before_dir_returns_2(tmp_path):
    after = tmp_path / "after"; after.mkdir()
    result = _run_cli("--before", str(tmp_path / "missing"), "--after", str(after))
    assert result.returncode == 2


def test_cli_watch_proofs_missing_after_dir_returns_2(tmp_path):
    before = tmp_path / "before"; before.mkdir()
    result = _run_cli("--before", str(before), "--after", str(tmp_path / "missing"))
    assert result.returncode == 2
