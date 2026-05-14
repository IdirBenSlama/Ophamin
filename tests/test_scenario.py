"""Tests for the catastrophic-scenario layer.

The harness is exercised end-to-end with MockSubstrate (no Kimera needed); the
Immune Siege scoring is unit-tested with synthetic cycle results.
"""

import itertools
from datetime import datetime

import pytest

from ophamin.corpus import get_corpus
from ophamin.corpus.base import CorpusRecord
from ophamin.proof import VALIDATED, Claim, PillarEvidence, Threshold
from ophamin.scenario import ImmuneSiegeScenario, Scenario, ScenarioScore
from ophamin.substrate import MockSubstrate
from ophamin.substrate.base import CycleResult


class _HarnessProbe(Scenario):
    """A trivial scenario for testing the harness end-to-end without Kimera."""

    name = "harness-probe"
    corpus_name = "flores"
    target = "entity"
    n_cycles = 6

    def build_claim(self) -> Claim:
        return Claim(
            statement="harness probe — every scenario run yields a well-formed proof",
            operationalization="probe metric is non-negative",
            threshold=Threshold("probe_metric", ">=", 0.0),
            h0="probe metric < 0",
            h1="probe metric >= 0",
        )

    def score(self, cycle_results, records) -> ScenarioScore:
        return ScenarioScore(
            observed_value=float(len(cycle_results)),
            evidence=[
                PillarEvidence(
                    "probe", "n_cycles", float(len(cycle_results)), "ophamin", "0.1.0"
                )
            ],
            reasoning=f"ran {len(cycle_results)} cycles",
        )


def test_harness_produces_a_valid_signed_proof():
    if not get_corpus("flores").is_available():
        pytest.skip("flores corpus not available")
    record = _HarnessProbe().run(MockSubstrate(seed=1))

    assert record.validate() == []  # well-formed: every bulletproof property holds
    assert record.verify_signature(b"ophamin-scenario-proof-key")
    assert record.verdict.outcome == VALIDATED
    assert record.datasets[0].name == "flores-200"
    assert len(record.evidence) == 1
    assert len(record.proof_id) == 64
    # pre-registration precedes the run
    assert datetime.fromisoformat(
        record.preregistration.preregistered_at
    ) <= datetime.fromisoformat(record.created_at)
    # the provenance graph is populated
    assert record.provenance.get("entity")
    assert record.provenance.get("activity")


# -- Immune Siege scoring (synthetic cycle results, no Kimera) --------------

def _record(label: str) -> CorpusRecord:
    return CorpusRecord(id=f"r-{label}", text="some adversarial input", metadata={"label": label})


def _result(blocked: bool, success: bool = True) -> CycleResult:
    return CycleResult(
        cycle_index=0,
        success=success,
        raw={},
        halt_mode="blocked" if blocked else "commit",
    )


class _FakeCyberCorpus:
    """Minimal corpus exposing records_from — emits all benign, then all
    malicious (the worst input ordering for balance)."""

    def __init__(self, n_benign: int, n_malicious: int) -> None:
        self._n_benign = n_benign
        self._n_malicious = n_malicious

    def records_from(self, source_name: str):
        for i in range(self._n_benign):
            yield CorpusRecord(id=f"b{i}", text="benign", metadata={"label": "0"})
        for i in range(self._n_malicious):
            yield CorpusRecord(id=f"m{i}", text="malicious", metadata={"label": "1"})


def test_immune_siege_score_computes_false_positive_and_detection_rates():
    scenario = ImmuneSiegeScenario(false_positive_ceiling=0.10)
    records = [_record("0") for _ in range(20)] + [_record("1") for _ in range(20)]
    results = (
        [_result(blocked=(i < 4)) for i in range(20)]  # 4/20 benign blocked => 0.20 FP
        + [_result(blocked=(i < 18)) for i in range(20)]  # 18/20 malicious caught
    )
    score = scenario.score(results, records)

    assert score.observed_value == pytest.approx(0.20)  # the false-positive rate
    assert not score.inconclusive
    fp = next(e for e in score.evidence if e.statistic_name == "gwf_false_positive_rate")
    det = next(e for e in score.evidence if e.statistic_name == "gwf_detection_rate")
    assert fp.statistic_value == pytest.approx(0.20)
    assert det.statistic_value == pytest.approx(0.90)
    # the stand-in feature extraction is flagged, not hidden
    assert fp.detail["feature_extraction"] == "ophamin_standin"
    # each rate carries a Wilson 95% CI that brackets the point estimate
    assert fp.ci_low is not None and fp.ci_high is not None
    assert 0.0 <= fp.ci_low <= fp.statistic_value <= fp.ci_high <= 1.0
    assert det.ci_low is not None and det.ci_high is not None
    assert det.ci_low <= det.statistic_value <= det.ci_high <= 1.0
    assert fp.detail["ci_method"] == "wilson_95"
    assert fp.library == "statsmodels"


def test_immune_siege_inconclusive_with_too_few_benign_samples():
    scenario = ImmuneSiegeScenario()
    records = [_record("0") for _ in range(5)] + [_record("1") for _ in range(20)]
    results = [_result(False) for _ in range(25)]
    assert scenario.score(results, records).inconclusive  # < 10 benign samples


def test_immune_siege_inconclusive_when_substrate_not_exercised():
    """A dead / timed-out subprocess turns every cycle into an adapter error;
    that must resolve to INCONCLUSIVE, never a VALIDATED 0% false-positive."""
    scenario = ImmuneSiegeScenario(false_positive_ceiling=0.10)
    records = [_record("0") for _ in range(20)] + [_record("1") for _ in range(20)]
    # the whole batch failed -- run_batch surfaces one adapter_error per stimulus
    results = [
        CycleResult(0, success=False, raw={}, halt_mode="adapter_error", error="timeout")
        for _ in range(40)
    ]
    score = scenario.score(results, records)
    assert score.inconclusive  # NOT validated, despite fp_rate == 0.0
    assert score.observed_value == 0.0
    assert "adapter error" in score.reasoning.lower()
    fp = next(e for e in score.evidence if e.statistic_name == "gwf_false_positive_rate")
    assert fp.detail["adapter_errors"] == 40


def test_immune_siege_feature_extraction_is_target_aware():
    """The proof record must honestly say whether the GWF saw Ophamin's stand-in
    features (gwf target) or Kimera's native pipeline (entity target)."""
    records = [_record("0") for _ in range(12)] + [_record("1") for _ in range(12)]
    results = [_result(False) for _ in range(24)]

    gwf_fp = next(
        e
        for e in ImmuneSiegeScenario(target="gwf").score(results, records).evidence
        if e.statistic_name == "gwf_false_positive_rate"
    )
    entity_fp = next(
        e
        for e in ImmuneSiegeScenario(target="entity").score(results, records).evidence
        if e.statistic_name == "gwf_false_positive_rate"
    )
    assert gwf_fp.detail["feature_extraction"] == "ophamin_standin"
    assert gwf_fp.detail["target"] == "gwf"
    assert entity_fp.detail["feature_extraction"] == "kimera_native"
    assert entity_fp.detail["target"] == "entity"


def test_immune_siege_rejects_unknown_target():
    with pytest.raises(ValueError, match="must be 'gwf'"):
        ImmuneSiegeScenario(target="walker")


def test_immune_siege_select_records_interleaves_balanced():
    """select_records interleaves benign/malicious so islice(n) is balanced —
    even when the corpus emits one class entirely before the other."""
    scenario = ImmuneSiegeScenario()
    sample = list(
        itertools.islice(scenario.select_records(_FakeCyberCorpus(100, 80)), 40)
    )
    labels = [scenario._label_of(r) for r in sample]
    assert labels.count("benign") == 20
    assert labels.count("malicious") == 20
    assert all(labels[i] != labels[i + 1] for i in range(len(labels) - 1))


def test_immune_siege_is_blocked_heuristic():
    by_verdict = CycleResult(0, True, raw={"verdict": "BLOCK"}, halt_mode="commit")
    allowed = CycleResult(0, True, raw={"verdict": "allow"}, halt_mode="commit")
    by_flag = CycleResult(0, True, raw={"blocked": True}, halt_mode=None)
    by_halt = CycleResult(0, True, raw={}, halt_mode="lockdown")
    adapter_error = CycleResult(0, False, raw={}, halt_mode="adapter_error", error="boom")

    assert ImmuneSiegeScenario._is_blocked(by_verdict)
    assert not ImmuneSiegeScenario._is_blocked(allowed)
    assert ImmuneSiegeScenario._is_blocked(by_flag)
    assert ImmuneSiegeScenario._is_blocked(by_halt)
    assert not ImmuneSiegeScenario._is_blocked(adapter_error)  # adapter error != GWF block


def test_immune_siege_is_blocked_real_kimera_shapes():
    """Pin the two real Kimera GWF shapes (ophamin_gwf_shape_probe.py, 2026-05-14)."""
    # gwf direct target -- GWFVerdict.allowed
    gwf_block = CycleResult(0, True, raw={"allowed": False, "threat": {}}, halt_mode=None)
    gwf_allow = CycleResult(0, True, raw={"allowed": True, "threat": {}}, halt_mode=None)
    assert ImmuneSiegeScenario._is_blocked(gwf_block)
    assert not ImmuneSiegeScenario._is_blocked(gwf_allow)

    # entity target -- Takwin's flattened inline GWF screen
    entity_block = CycleResult(
        0,
        True,
        raw={
            "gwf_verdict": "blocked:CRITICAL threat (torque/stiffness=22.6000)",
            "gwf_lockdown": False,
        },
        halt_mode="exhausted",
    )
    entity_clear = CycleResult(
        0,
        True,
        raw={"gwf_verdict": "cleared", "gwf_lockdown": False},
        halt_mode="amplitude_death",  # Walker cognitive mode, NOT a GWF signal
    )
    entity_lockdown = CycleResult(
        0, True, raw={"gwf_verdict": "cleared", "gwf_lockdown": True}, halt_mode="commit"
    )
    assert ImmuneSiegeScenario._is_blocked(entity_block)
    assert not ImmuneSiegeScenario._is_blocked(entity_clear)  # amplitude_death != block
    assert ImmuneSiegeScenario._is_blocked(entity_lockdown)  # lockdown overrides verdict


def test_immune_siege_claim_is_falsifiable_and_pre_registerable():
    claim = ImmuneSiegeScenario(false_positive_ceiling=0.10).build_claim()
    assert claim.threshold.comparator == "<="
    assert claim.threshold.value == pytest.approx(0.10)
    assert claim.h0 and claim.h1
    assert claim.statement.strip()
