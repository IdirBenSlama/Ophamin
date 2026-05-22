"""The seatbelt fires — a scenario whose live substrate is missing a required
OrchestratorResult field must FAIL LOUD, not silently produce a meaningless proof.

This is the guardrail for the exact trap this session nearly hit twice: the
canonical scar count moving from `total_scars` to `vault_stats.total_scars_stored`,
and a Φ-drift observable that didn't carry the signal. The flow scenarios override
``run()``, so they call ``_enforce_field_contract`` after their first batch; this
test proves that path raises on drift.
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.base import ScenarioFieldContractViolation
from ophamin.measuring.scenarios.memory_permanence_flow import (
    MemoryPermanenceFlowScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class _DriftedAdapter(SubstrateUnderTest):
    """Emits everything memory-permanence needs EXCEPT vault_stats — i.e. the
    canonical scar field was renamed/removed Kimera-side (schema drift)."""

    def __init__(self, *, include_vault_stats: bool) -> None:
        self.name = "drift-fake"
        self._include = include_vault_stats
        self._n = 0

    def git_commit(self) -> str:
        return "fakecommit01"

    def reset(self) -> None:
        self._n = 0

    def metadata(self) -> dict:
        return {"name": self.name, "git_commit": self.git_commit()}

    def run_cycle(self, stimulus, params=None) -> CycleResult:  # pragma: no cover
        return self.run_batch([stimulus])[0]

    def run_batch(self, texts, params=None) -> list[CycleResult]:
        out = []
        for i, t in enumerate(texts):
            self._n += 1
            raw = {
                "concepts": [w.lower() for w in t.split()[:5]],
                "arachne_web_coupling_frobenius": 1.0 + 0.1 * self._n,
                "alexandria_knowledge_mass_cumulative": float(self._n),
                "phi": 0.7,
                "halt_reason": "exhausted",
            }
            if self._include:
                raw["vault_stats"] = {"total_scars_stored": self._n,
                                      "vault_a": {"scar_count": self._n},
                                      "vault_b": {"scar_count": 0}}
            out.append(CycleResult(cycle_index=i, success=True,
                                   halt_mode="exhausted", raw=raw))
        return out


def _scenario():
    stim = tuple(f"probe number {i} carries meaning {i} structure {i}" for i in range(4))
    return MemoryPermanenceFlowScenario(stimuli=stim, n_exposures=3, min_transitions=4)


def test_seatbelt_raises_on_missing_required_field():
    # vault_stats (the canonical scar field) is gone -> loud failure
    with pytest.raises(ScenarioFieldContractViolation) as exc:
        _scenario().run(_DriftedAdapter(include_vault_stats=False))
    # the violation names the missing field
    assert any(v.field_name == "vault_stats" for v in exc.value.violations)
    assert any(v.kind == "missing_required" for v in exc.value.violations)


def test_seatbelt_passes_when_field_present():
    # same scenario, field present -> no contract failure (runs to a verdict)
    rec = _scenario().run(_DriftedAdapter(include_vault_stats=True))
    assert rec.verdict.outcome in {"VALIDATED", "REFUTED", "INCONCLUSIVE"}


def test_contract_declared():
    c = _scenario().field_contract()
    assert c is not None
    required = {fc.field_name for fc in c.contracts if fc.required}
    assert "vault_stats" in required
