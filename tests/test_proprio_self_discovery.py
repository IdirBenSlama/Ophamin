"""Tests for ProprioSelfDiscoveryScenario — substrate_git_commit capture."""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord
from ophamin.measuring.scenarios.proprio_self_discovery import ProprioSelfDiscoveryScenario
from ophamin.seeing.substrate import MockSubstrate


@pytest.fixture()
def phase_reports(tmp_path):
    """Minimal phase report files that satisfy ProprioSelfDiscoveryScenario."""
    p2 = tmp_path / "phase_2_report.json"
    p2.write_text(json.dumps({
        "gate": "test-gate",
        "aggregate": {"sec_v2": {"headline_r_squared": 0.8, "headline_equation": "y=x"}},
    }))
    p3 = tmp_path / "phase_3_report.json"
    p3.write_text(json.dumps({
        "gate": "test-gate",
        "n_classified": {"events": 90},
        "n_total": {"events": 100},
        "scar_absorption_pct": 0.5,
    }))
    p4 = tmp_path / "phase_4_report.json"
    p4.write_text(json.dumps({
        "gate": "test-gate",
        "sinew_verdict": "STRONG",
        "sinew_reason": "triad matched",
        "sinew_result": {"triad": ["pressure", "tension", "scar"]},
        "control_matched_newton": False,
    }))
    return p2, p3, p4


def test_proprio_substrate_commit_from_kimera_commit_param(phase_reports):
    """kimera_commit kwarg populates substrate_git_commit in the proof record."""
    p2, p3, p4 = phase_reports
    s = ProprioSelfDiscoveryScenario(
        str(p2), str(p3), str(p4),
        kimera_commit="abc123def456",
    )
    proof = s.run()
    assert isinstance(proof, EmpiricalProofRecord)
    assert proof.substrate_git_commit == "abc123def456"
    assert proof.substrate_name == "kimera-swm"


def test_proprio_substrate_commit_from_substrate_arg(phase_reports):
    """When substrate is provided, git_commit() is used to populate the proof."""
    p2, p3, p4 = phase_reports
    s = ProprioSelfDiscoveryScenario(str(p2), str(p3), str(p4))
    # MockSubstrate.git_commit() returns "mock-<seed:07d>"
    proof = s.run(substrate=MockSubstrate(seed=42))
    assert isinstance(proof, EmpiricalProofRecord)
    assert proof.substrate_git_commit == "mock-0000042"
    assert proof.substrate_name == "kimera-swm"


def test_proprio_kimera_commit_takes_priority_over_substrate(phase_reports):
    """Explicit kimera_commit wins over the substrate's git_commit()."""
    p2, p3, p4 = phase_reports
    s = ProprioSelfDiscoveryScenario(
        str(p2), str(p3), str(p4),
        kimera_commit="explicit-sha",
    )
    proof = s.run(substrate=MockSubstrate(seed=1))
    assert proof.substrate_git_commit == "explicit-sha"


def test_proprio_proof_is_signed_and_content_addressed(phase_reports):
    """run() returns a signed, content-addressed proof."""
    p2, p3, p4 = phase_reports
    s = ProprioSelfDiscoveryScenario(
        str(p2), str(p3), str(p4),
        kimera_commit="deadbeef1234",
    )
    proof = s.run()
    assert proof.signature
    assert len(proof.proof_id) == 64
