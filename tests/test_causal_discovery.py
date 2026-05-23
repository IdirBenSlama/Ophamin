"""Tests for CausalDiscoveryScenario."""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import VALIDATED
from ophamin.measuring.scenarios.causal_discovery import (
    CausalDiscoveryScenario,
    DEFAULT_CHANNELS,
)


pytest.importorskip("tigramite")


def _write_synthetic_trajectory(tmp_path, n_cycles: int = 60, *,
                                inject_causal: bool = True):
    """Write a synthetic trajectory with optional injected causal structure."""
    import random
    rng = random.Random(0)
    traj = []
    prev_kuramoto = 0.5
    for i in range(n_cycles):
        kuramoto = max(0.0, min(1.0, prev_kuramoto + rng.gauss(0, 0.1)))
        if inject_causal:
            # phi(t) = 0.6 * kuramoto(t-1) + noise → kuramoto causes phi
            # dissonance(t) = 0.5 * phi(t) + noise → phi causes dissonance
            phi = 0.6 * prev_kuramoto + rng.gauss(0, 0.05)
            dissonance = max(0, int(0.5 * phi * 20 + rng.gauss(0, 1)))
        else:
            phi = rng.uniform(0, 1)
            dissonance = rng.randint(0, 20)
        traj.append({
            "cycle_index": i,
            "phi": float(phi),
            "kuramoto_order_parameter": float(kuramoto),
            "dissonance_events_count": int(dissonance),
            "arachne_web_order_parameter": float(rng.gauss(0.5, 0.1)),
            "alexandria_knowledge_mass_cumulative": float(i),
        })
        prev_kuramoto = kuramoto
    out = tmp_path / "synth_traj.json"
    out.write_text(json.dumps({"kimera_commit": "synthetic", "trajectory": traj}))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        CausalDiscoveryScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_channels(tmp_path):
    p = _write_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="≥ 2 entries"):
        CausalDiscoveryScenario(trajectory_path=str(p), channels=("phi",))


def test_constructor_validates_max_lag(tmp_path):
    p = _write_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="max_lag must be"):
        CausalDiscoveryScenario(trajectory_path=str(p), max_lag=0)


def test_constructor_validates_pc_alpha(tmp_path):
    p = _write_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="pc_alpha must be"):
        CausalDiscoveryScenario(trajectory_path=str(p), pc_alpha=1.0)


def test_score_unreachable(tmp_path):
    p = _write_synthetic_trajectory(tmp_path)
    s = CausalDiscoveryScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_default_channels_uses_canonical_substrate_names():
    """DEFAULT_CHANNELS uses canonical names per 2026-05-15 catalog refresh."""
    assert "phi" in DEFAULT_CHANNELS
    assert "kuramoto_order_parameter" in DEFAULT_CHANNELS
    assert "phi_value" not in DEFAULT_CHANNELS  # legacy alias should not be here


def test_claim_well_formed(tmp_path):
    p = _write_synthetic_trajectory(tmp_path)
    s = CausalDiscoveryScenario(trajectory_path=str(p), max_lag=2, pc_alpha=0.05)
    claim = s.build_claim()
    assert "PCMCI" in claim.statement
    assert claim.threshold.metric == "significant_causal_link_count"
    assert claim.threshold.comparator == ">="
    assert claim.threshold.value == 1.0
    assert claim.h0
    assert claim.h1


def test_too_few_complete_cycles_raises(tmp_path):
    p = _write_synthetic_trajectory(tmp_path, n_cycles=10)  # < 20 minimum
    s = CausalDiscoveryScenario(
        trajectory_path=str(p),
        channels=("phi", "kuramoto_order_parameter", "dissonance_events_count",
                  "arachne_web_order_parameter",
                  "alexandria_knowledge_mass_cumulative"),
    )
    with pytest.raises(RuntimeError, match="too few complete cycles"):
        s.run()


def test_injected_causal_structure_detected(tmp_path):
    """Synthetic trajectory with kuramoto→phi→dissonance should yield links."""
    p = _write_synthetic_trajectory(tmp_path, n_cycles=60, inject_causal=True)
    s = CausalDiscoveryScenario(
        trajectory_path=str(p),
        channels=("phi", "kuramoto_order_parameter",
                  "dissonance_events_count"),
        max_lag=2,
        pc_alpha=0.05,
    )
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value >= 1
    assert proof.signature
    assert proof.proof_id
    detail = proof.evidence[0].detail
    assert detail["n_links"] >= 1
    assert detail["n_complete_cycles_used"] >= 20


def test_signed_proof_carries_provenance(tmp_path):
    p = _write_synthetic_trajectory(tmp_path, n_cycles=60)
    s = CausalDiscoveryScenario(
        trajectory_path=str(p),
        channels=("phi", "kuramoto_order_parameter",
                  "dissonance_events_count"),
    )
    proof = s.run()
    agents = proof.provenance.get("agent", {})
    assert "ophamin:tigramite" in agents
    assert "ophamin:kimera-swm" in agents


def test_evidence_records_link_provenance_per_arrow(tmp_path):
    """Each detected link carries parent/child/lag/p_value + groundtruth flag."""
    p = _write_synthetic_trajectory(tmp_path, n_cycles=60, inject_causal=True)
    s = CausalDiscoveryScenario(
        trajectory_path=str(p),
        channels=("phi", "kuramoto_order_parameter",
                  "dissonance_events_count"),
    )
    proof = s.run()
    for L in proof.evidence[0].detail["links"]:
        assert "parent" in L and "child" in L and "lag" in L and "p_value" in L
        assert "is_expected_groundtruth" in L
        assert "is_t4_disambiguator" in L
