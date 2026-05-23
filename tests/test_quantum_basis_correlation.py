"""Tests for QuantumBasisCorrelationScenario."""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import REFUTED, VALIDATED
from ophamin.measuring.scenarios.quantum_basis_correlation import (
    QuantumBasisCorrelationScenario,
)


def _make_synthetic_trajectory(
    tmp_path,
    *,
    n_axiom: int = 50,
    n_mixed: int = 50,
    axiom_high_qbe_rate: float = 0.20,
    mixed_high_qbe_rate: float = 0.60,
):
    """Build a synthetic trajectory with controlled QBE per stimulus class."""
    import random
    rng = random.Random(0)
    traj = []
    idx = 0
    for sc, n, rate in (("axiom", n_axiom, axiom_high_qbe_rate),
                        ("mixed", n_mixed, mixed_high_qbe_rate)):
        for i in range(n):
            qbe = 3.5 if rng.random() < rate else 0.0
            chain_len = 7 if qbe > 0 else 11
            traj.append({
                "cycle_index": idx,
                "stimulus": f"{sc}_{i}",
                "stimulus_class": sc,
                "quantum_prime_basis_entropy": qbe,
                "prime_chain": [10000003 + j for j in range(chain_len)],
                "halt_reason": "exhausted",
                "phi": 0.4 if qbe > 0 else 0.35,
            })
            idx += 1
    out = tmp_path / "synth.json"
    out.write_text(json.dumps({"kimera_commit": "synthetic", "trajectory": traj}))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        QuantumBasisCorrelationScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_threshold(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="high_qbe_threshold"):
        QuantumBasisCorrelationScenario(trajectory_path=str(p),
                                        high_qbe_threshold=0)
    with pytest.raises(ValueError, match="class_difference_floor"):
        QuantumBasisCorrelationScenario(trajectory_path=str(p),
                                        class_difference_floor=0)


def test_score_unreachable(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    s = QuantumBasisCorrelationScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_strong_class_difference_validates(tmp_path):
    """50pp difference → VALIDATED at 15pp threshold."""
    p = _make_synthetic_trajectory(
        tmp_path,
        n_axiom=100, n_mixed=100,
        axiom_high_qbe_rate=0.10,
        mixed_high_qbe_rate=0.60,
    )
    s = QuantumBasisCorrelationScenario(trajectory_path=str(p),
                                        class_difference_floor=0.15)
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value >= 0.40  # ~50pp


def test_no_class_difference_refutes(tmp_path):
    """Identical rates per class → REFUTED at 15pp threshold."""
    p = _make_synthetic_trajectory(
        tmp_path,
        axiom_high_qbe_rate=0.40,
        mixed_high_qbe_rate=0.40,
    )
    s = QuantumBasisCorrelationScenario(trajectory_path=str(p),
                                        class_difference_floor=0.15)
    proof = s.run()
    assert proof.verdict.outcome == REFUTED
    assert proof.verdict.observed_value < 0.10


def test_per_class_summary_carries_qbe_stats(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    s = QuantumBasisCorrelationScenario(trajectory_path=str(p))
    proof = s.run()
    d = proof.evidence[0].detail
    classes = {row["stimulus_class"] for row in d["per_class_summary"]}
    assert classes == {"axiom", "mixed"}
    for row in d["per_class_summary"]:
        assert "high_qbe_rate" in row
        assert "qbe_mean" in row
        assert "qbe_median" in row


def test_halt_reason_x_qbe_state_cross_tab(tmp_path):
    """The cross-tab dict must carry the 3 QBE states for each halt_reason."""
    p = _make_synthetic_trajectory(tmp_path)
    s = QuantumBasisCorrelationScenario(trajectory_path=str(p))
    proof = s.run()
    d = proof.evidence[0].detail
    halt_tab = d["halt_reason_x_qbe_state"]
    assert "exhausted" in halt_tab
    for state in ("zero_qbe", "high_qbe", "middle_qbe"):
        assert state in halt_tab["exhausted"]


def test_prime_chain_length_per_state(tmp_path):
    """Synthetic data: high-QBE cycles have chain_len=7, zero-QBE have 11."""
    p = _make_synthetic_trajectory(tmp_path)
    s = QuantumBasisCorrelationScenario(trajectory_path=str(p))
    proof = s.run()
    chain_summary = proof.evidence[0].detail["prime_chain_length_per_qbe_state"]
    if "high_qbe" in chain_summary:
        assert chain_summary["high_qbe"]["mean"] == 7.0
    if "zero_qbe" in chain_summary:
        assert chain_summary["zero_qbe"]["mean"] == 11.0


def test_signed_proof_carries_provenance(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    s = QuantumBasisCorrelationScenario(trajectory_path=str(p))
    proof = s.run()
    assert proof.signature
    agents = proof.provenance.get("agent", {})
    assert "ophamin:kimera-swm" in agents


def test_empty_trajectory_raises(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"kimera_commit": "x", "trajectory": []}))
    s = QuantumBasisCorrelationScenario(trajectory_path=str(p))
    with pytest.raises(ValueError, match="trajectory is empty"):
        s.run()
