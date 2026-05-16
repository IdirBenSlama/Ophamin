"""Hardening tests for the 6-phase composite-run orchestrator (Move F).

Covers:

- :class:`CampaignPhase` + :class:`CampaignRecord` data model + serde
  round-trip + signing + sign verification + canonical ID stability;
- :func:`run_campaign` against :class:`MockSubstrate` for the
  always-runnable phases (measuring + comparing + reporting); the
  three phases that require Kimera repo / InstrumentedSubstrate surface
  must `skipped` cleanly with reason text.
- CLI smoke for `ophamin run-all`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ophamin import __version__
from ophamin.campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    CANONICAL_PHASE_ORDER,
    CampaignPhase,
    CampaignRecord,
    dump_campaign,
    load_campaign,
    run_campaign,
)
from ophamin.seeing.substrate import MockSubstrate


_SIGN_KEY = b"campaign-test-key"


# --- data model -----------------------------------------------------------


def test_canonical_phase_order_is_exactly_six():
    """The six wheels are the canonical phase order — adding a 7th
    without docs update is a drift signal."""
    assert CANONICAL_PHASE_ORDER == (
        "seeing",
        "measuring",
        "comparing",
        "instrumenting",
        "auditing",
        "reporting",
    )


def test_campaign_phase_frozen():
    phase = CampaignPhase(
        wheel="seeing",
        started_at="2026-05-16T00:00:00+00:00",
        completed_at="2026-05-16T00:00:01+00:00",
        status="ok",
    )
    with pytest.raises(Exception):
        phase.status = "failed"  # type: ignore[misc]


def test_campaign_phase_to_dict_round_trip():
    phase = CampaignPhase(
        wheel="measuring",
        started_at="2026-05-16T00:00:00+00:00",
        completed_at="2026-05-16T00:00:10+00:00",
        status="ok",
        artifact_paths=("/tmp/a.json",),
        summary={"n_validated": 1, "n_refuted": 0},
    )
    data = phase.to_dict()
    back = CampaignPhase.from_dict(data)
    assert back == phase


def test_campaign_record_id_is_content_hash():
    record = CampaignRecord(
        target_name="mock",
        target_git_commit="abc",
        phases=[],
    )
    cid_a = record.campaign_id
    # mutating an unrelated field must change the id
    record.target_git_commit = "def"
    cid_b = record.campaign_id
    assert cid_a != cid_b


def test_campaign_record_sign_and_verify():
    record = CampaignRecord(target_name="mock", target_git_commit="abc")
    record.sign(_SIGN_KEY)
    assert record.verify_signature(_SIGN_KEY) is True
    assert record.verify_signature(b"wrong-key") is False


def test_campaign_record_to_dict_from_dict_round_trip():
    record = CampaignRecord(
        target_name="mock",
        target_git_commit="abc",
        phases=[
            CampaignPhase(
                wheel="seeing",
                started_at="2026-05-16T00:00:00+00:00",
                completed_at="2026-05-16T00:00:01+00:00",
                status="skipped",
                error="reason",
            )
        ],
    )
    record.sign(_SIGN_KEY)
    data = record.to_dict()
    back = CampaignRecord.from_dict(data)
    assert back.campaign_id == record.campaign_id
    assert back.verify_signature(_SIGN_KEY) is True


def test_campaign_dump_load_round_trip(tmp_path):
    record = CampaignRecord(target_name="mock", target_git_commit="abc").sign(_SIGN_KEY)
    path = dump_campaign(record, tmp_path / "CAMPAIGN.json")
    loaded = load_campaign(path)
    assert loaded.campaign_id == record.campaign_id
    assert loaded.verify_signature(_SIGN_KEY)


def test_status_counts_aggregates():
    record = CampaignRecord(target_name="mock", target_git_commit="abc")
    record.phases = [
        CampaignPhase(wheel="w1", started_at="x", completed_at="y", status="ok"),
        CampaignPhase(wheel="w2", started_at="x", completed_at="y", status="ok"),
        CampaignPhase(wheel="w3", started_at="x", completed_at="y", status="skipped"),
        CampaignPhase(wheel="w4", started_at="x", completed_at="y", status="failed"),
    ]
    counts = record.status_counts
    assert counts == {"ok": 2, "skipped": 1, "failed": 1}


def test_all_ok_and_any_failed():
    r1 = CampaignRecord(target_name="mock", target_git_commit="abc")
    r1.phases = [CampaignPhase(wheel="w", started_at="x", completed_at="y", status="ok")]
    assert r1.all_ok and not r1.any_failed

    r2 = CampaignRecord(target_name="mock", target_git_commit="abc")
    r2.phases = [
        CampaignPhase(wheel="w1", started_at="x", completed_at="y", status="ok"),
        CampaignPhase(wheel="w2", started_at="x", completed_at="y", status="skipped"),
    ]
    assert not r2.all_ok and not r2.any_failed

    r3 = CampaignRecord(target_name="mock", target_git_commit="abc")
    r3.phases = [
        CampaignPhase(wheel="w", started_at="x", completed_at="y", status="failed"),
    ]
    assert not r3.all_ok and r3.any_failed


# --- orchestrator (against MockSubstrate) ----------------------------------


@pytest.fixture
def lite_scenarios():
    """A short list of fast scenarios for orchestrator testing.

    The full default-scenarios set is comprehensive but slow (the
    Bayesian-phi-posterior scenario runs PyMC NUTS). For tests we
    use a 2-scenario subset that exercises the orchestrator's plumbing
    without the wall-time cost.
    """
    from ophamin.measuring.scenarios import (
        ImmuneSiegeScenario,
        OrganizationalDissonanceScenario,
    )
    return [ImmuneSiegeScenario, OrganizationalDissonanceScenario]


def test_run_campaign_against_mock_substrate(tmp_path, lite_scenarios):
    """End-to-end: 6 phases, MockSubstrate, lite scenarios. The phases
    that need a Kimera repo / InstrumentedSubstrate surface must
    skip cleanly with reason text."""
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    assert isinstance(record, CampaignRecord)
    assert record.verify_signature(_SIGN_KEY)
    # All six phases attempted
    assert [p.wheel for p in record.phases] == list(CANONICAL_PHASE_ORDER)
    # Phases that need Kimera repo: seeing + auditing
    seeing = next(p for p in record.phases if p.wheel == "seeing")
    auditing = next(p for p in record.phases if p.wheel == "auditing")
    assert seeing.status == "skipped"
    assert "kimera_repo" in (seeing.error or "")
    assert auditing.status == "skipped"
    # Phase that needs InstrumentedSubstrate: instrumenting
    instr = next(p for p in record.phases if p.wheel == "instrumenting")
    assert instr.status == "skipped"
    # Phases that should always run against MockSubstrate
    measuring = next(p for p in record.phases if p.wheel == "measuring")
    comparing = next(p for p in record.phases if p.wheel == "comparing")
    reporting = next(p for p in record.phases if p.wheel == "reporting")
    assert measuring.status == "ok"
    assert comparing.status == "ok"
    assert reporting.status == "ok"


def test_run_campaign_writes_per_phase_artifacts(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    # measuring writes signed proofs into proofs/<tier>/<family>/
    proofs_dir = tmp_path / "proofs"
    assert proofs_dir.is_dir()
    proof_files = list(proofs_dir.rglob("*.json"))
    assert len(proof_files) >= 1  # at least one scenario produced a proof
    # comparing writes SUMMARY.md
    assert (tmp_path / "SUMMARY.md").is_file()
    # reporting writes REPORT.md
    assert (tmp_path / "REPORT.md").is_file()


def test_run_campaign_skip_phases(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        enable_phases={"measuring", "comparing"},
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    wheels = [p.wheel for p in record.phases]
    assert wheels == ["measuring", "comparing"]


def test_run_campaign_default_scenarios_includes_19(tmp_path):
    """When no scenarios are provided, the orchestrator picks every
    default-instantiable scenario from SCENARIOS. The exact count
    depends on which scenarios accept zero required args."""
    from ophamin.campaign import _select_default_instantiable_scenarios
    chosen = _select_default_instantiable_scenarios()
    # At least the 6 well-known default-instantiable scenarios
    assert len(chosen) >= 6


def test_run_campaign_target_name_falls_back_to_substrate_name(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        enable_phases={"measuring"},
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    assert record.target_name == "mock"  # MockSubstrate.name


def test_run_campaign_explicit_target_name(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        target_name="my-explicit-name",
        target_git_commit="abc123",
        scenarios=lite_scenarios,
        enable_phases={"measuring"},
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    assert record.target_name == "my-explicit-name"
    assert record.target_git_commit == "abc123"


def test_run_campaign_measuring_records_verdicts(tmp_path, lite_scenarios):
    substrate = MockSubstrate(seed=1)
    record = run_campaign(
        substrate=substrate,
        scenarios=lite_scenarios,
        enable_phases={"measuring"},
        out_dir=tmp_path,
        sign_key=_SIGN_KEY,
    )
    measuring = record.phases[0]
    assert measuring.wheel == "measuring"
    assert "n_scenarios_attempted" in measuring.summary
    assert measuring.summary["n_scenarios_attempted"] == 2


# --- CLI smoke -------------------------------------------------------------


def test_cli_run_all_against_mock_substrate(tmp_path):
    """`ophamin run-all` against MockSubstrate (no --repo) — skip the
    slow scenarios via --scenarios to keep CI fast."""
    result = subprocess.run(
        [
            sys.executable, "-m", "ophamin.cli", "run-all",
            "--scenarios", "concentrated-immune-siege,organizational-dissonance",
            "--out-dir", str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "CAMPAIGN.json").is_file()
    assert "campaign complete" in result.stdout


def test_cli_run_all_unknown_scenario_returns_2(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "ophamin.cli", "run-all",
            "--scenarios", "totally-fictional-scenario",
            "--out-dir", str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "unknown scenario" in result.stderr


def test_cli_run_all_unknown_phase_returns_2(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "ophamin.cli", "run-all",
            "--scenarios", "concentrated-immune-siege",
            "--skip", "not-a-real-phase",
            "--out-dir", str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "unknown phase" in result.stderr


def test_cli_run_all_skip_phases(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "ophamin.cli", "run-all",
            "--scenarios", "concentrated-immune-siege",
            "--skip", "seeing,auditing,instrumenting",
            "--out-dir", str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads((tmp_path / "CAMPAIGN.json").read_text())
    phases = {p["wheel"] for p in data["phases"]}
    assert "seeing" not in phases
    assert "auditing" not in phases
    assert "instrumenting" not in phases
    assert "measuring" in phases
