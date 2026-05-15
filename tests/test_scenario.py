"""Tests for the catastrophic-scenario layer.

The harness is exercised end-to-end with MockSubstrate (no Kimera needed); the
Immune Siege scoring is unit-tested with synthetic cycle results.
"""

import itertools
from datetime import datetime

import pytest

from ophamin.seeing.corpus import get_corpus
from ophamin.seeing.corpus.base import CorpusRecord
from ophamin.measuring.proof import VALIDATED, Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios import (
    ImmuneSiegeScenario,
    LogicTopologySiegeScenario,
    OrganizationalDissonanceScenario,
    RosettaScalingScenario,
    Scenario,
    ScenarioScore,
)
from ophamin.seeing.substrate import MockSubstrate
from ophamin.seeing.substrate.base import CycleResult


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


def test_immune_siege_is_caught_by_defense_stack():
    """Full-stack catch = GWF block OR manipulation_detected OR
    danger_theory_gated; _is_blocked stays GWF-only."""
    catch = ImmuneSiegeScenario._is_caught_by_defense_stack
    blocked = ImmuneSiegeScenario._is_blocked

    # entity: GWF cleared, but the manipulation detector caught it
    manip = CycleResult(
        0, True,
        raw={"gwf_verdict": "cleared", "manipulation_detected": True},
        halt_mode="exhausted",
    )
    assert catch(manip) and not blocked(manip)
    # entity: GWF cleared, manipulation false, Danger Theory Gate caught it
    danger = CycleResult(
        0, True,
        raw={"gwf_verdict": "cleared", "manipulation_detected": False,
             "danger_theory_gated": True},
        halt_mode="exhausted",
    )
    assert catch(danger) and not blocked(danger)
    # entity: fully clear — no layer caught it
    clear = CycleResult(
        0, True,
        raw={"gwf_verdict": "cleared", "manipulation_detected": False,
             "danger_theory_gated": False},
        halt_mode="amplitude_death",
    )
    assert not catch(clear) and not blocked(clear)
    # gwf direct target: no other layers → full-stack == _is_blocked
    direct_block = CycleResult(0, True, raw={"allowed": False, "threat": {}}, halt_mode=None)
    direct_ok = CycleResult(0, True, raw={"allowed": True, "threat": {}}, halt_mode=None)
    assert catch(direct_block) and blocked(direct_block)
    assert not catch(direct_ok) and not blocked(direct_ok)
    # adapter error → not a defense-layer catch
    err = CycleResult(0, False, raw={}, halt_mode="adapter_error", error="boom")
    assert not catch(err)


def test_immune_siege_score_emits_full_stack_pillars():
    """score() emits the 2 GWF pillars + 2 full-stack pillars; the full-stack
    rates are >= the GWF rates (the extra layers can only catch more)."""
    scenario = ImmuneSiegeScenario(target="entity")
    records = [_record("0") for _ in range(20)] + [_record("1") for _ in range(20)]
    results = []
    # benign: 1 GWF-blocked, +2 caught only by the manipulation detector
    for i in range(20):
        if i == 0:
            raw = {"gwf_verdict": "blocked:x", "manipulation_detected": False}
        elif i in (1, 2):
            raw = {"gwf_verdict": "cleared", "manipulation_detected": True}
        else:
            raw = {"gwf_verdict": "cleared", "manipulation_detected": False}
        results.append(CycleResult(0, True, raw=raw, halt_mode="exhausted"))
    # malicious: 8 GWF-blocked, +4 caught only by the manipulation detector
    for i in range(20):
        if i < 8:
            raw = {"gwf_verdict": "blocked:x", "manipulation_detected": False}
        elif i < 12:
            raw = {"gwf_verdict": "cleared", "manipulation_detected": True}
        else:
            raw = {"gwf_verdict": "cleared", "manipulation_detected": False}
        results.append(CycleResult(0, True, raw=raw, halt_mode="exhausted"))
    score = scenario.score(results, records)

    by = {e.statistic_name: e for e in score.evidence}
    assert set(by) == {
        "gwf_false_positive_rate", "gwf_detection_rate",
        "full_stack_false_positive_rate", "full_stack_detection_rate",
    }
    # GWF: 1/20 benign blocked, 8/20 malicious blocked
    assert by["gwf_false_positive_rate"].statistic_value == pytest.approx(0.05)
    assert by["gwf_detection_rate"].statistic_value == pytest.approx(0.40)
    # full-stack: 3/20 benign caught (1 GWF + 2 manip), 12/20 malicious (8 + 4)
    assert by["full_stack_false_positive_rate"].statistic_value == pytest.approx(0.15)
    assert by["full_stack_detection_rate"].statistic_value == pytest.approx(0.60)
    # full-stack rates >= GWF rates — extra layers can only add catches
    assert (
        by["full_stack_detection_rate"].statistic_value
        >= by["gwf_detection_rate"].statistic_value
    )
    # full-stack pillars carry the Wilson CI + the defense_layers detail
    fsd = by["full_stack_detection_rate"]
    assert fsd.ci_low is not None and fsd.ci_low <= fsd.statistic_value <= fsd.ci_high
    assert fsd.detail["defense_layers"] == [
        "gwf", "manipulation_detector", "danger_theory_gate",
    ]


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


# -- Rosetta Scaling scoring (synthetic cycle results, no Kimera) -----------


class _FakeFloresCorpus:
    """Minimal corpus yielding aligned FLORES-style records (no real files)."""

    def __init__(self, n_groups: int, n_langs: int) -> None:
        self._n_groups = n_groups
        self._langs = [f"lang_{i:03d}" for i in range(n_langs)]

    def records(self):
        for i in range(self._n_groups):
            translations = {lang: f"sentence-{i}-in-{lang}" for lang in self._langs}
            yield CorpusRecord(
                id=f"flores-dev-{i}",
                text=translations[self._langs[0]],
                metadata={
                    "translations": translations,
                    "n_languages": len(self._langs),
                },
            )


def _rosetta_result(
    *,
    cycle_index: int = 0,
    canonical: str | None = None,
    composite: int | None = None,
    success: bool = True,
    halt_mode: str = "commit",
) -> CycleResult:
    raw: dict = {}
    if canonical is not None:
        raw["canonical"] = canonical
    if composite is not None:
        raw["composite"] = composite
    return CycleResult(
        cycle_index=cycle_index,
        success=success,
        raw=raw,
        halt_mode=halt_mode,
    )


def test_rosetta_scaling_select_records_yields_k_max_per_group_deterministically():
    scenario = RosettaScalingScenario(n_cycles=999, k_max=4, primary_k=3, seed=42)
    corpus = _FakeFloresCorpus(n_groups=3, n_langs=10)
    out = list(itertools.islice(scenario.select_records(corpus), 999))
    # 3 groups * 4 langs = 12 records
    assert len(out) == 12
    # exactly k_max records per group
    by_group: dict[str, list[CorpusRecord]] = {}
    for rec in out:
        by_group.setdefault(rec.metadata["sentence_group_id"], []).append(rec)
    assert all(len(v) == 4 for v in by_group.values())
    # determinism — re-running with same seed yields the same language ordering
    again = list(itertools.islice(scenario.select_records(corpus), 999))
    assert [r.id for r in out] == [r.id for r in again]
    # slots are 0..k_max-1 within each group
    for entries in by_group.values():
        slots = sorted(e.metadata["slot_index"] for e in entries)
        assert slots == list(range(4))


def test_rosetta_scaling_select_records_skips_groups_with_too_few_langs():
    scenario = RosettaScalingScenario(n_cycles=99, k_max=20, primary_k=5)
    corpus = _FakeFloresCorpus(n_groups=2, n_langs=10)  # only 10 langs, k_max=20
    out = list(itertools.islice(scenario.select_records(corpus), 99))
    assert out == []


def test_rosetta_scaling_canonical_extraction_is_shape_aware():
    # primary key
    r1 = _rosetta_result(canonical="water")
    assert RosettaScalingScenario._canonical(r1) == "water"
    # fallback to canonical_form
    r2 = CycleResult(cycle_index=0, success=True, raw={"canonical_form": "eau"}, halt_mode="commit")
    assert RosettaScalingScenario._canonical(r2) == "eau"
    # missing -> None
    r3 = CycleResult(cycle_index=0, success=True, raw={}, halt_mode="commit")
    assert RosettaScalingScenario._canonical(r3) is None
    # failed cycle -> None even if canonical present
    r4 = CycleResult(cycle_index=0, success=False, raw={"canonical": "water"}, halt_mode="error")
    assert RosettaScalingScenario._canonical(r4) is None


def test_rosetta_scaling_prime_extraction_is_shape_aware():
    # scalar-top-level (synthetic substrates / unit tests)
    r1 = _rosetta_result(composite=232453)
    assert RosettaScalingScenario._prime(r1) == 232453
    r2 = CycleResult(
        cycle_index=0, success=True, raw={"prime": 17881}, halt_mode="commit"
    )
    assert RosettaScalingScenario._prime(r2) == 17881
    # nested-dict (real Kimera shape: raw["prime"] is the prime-bundle dict)
    r_nested = CycleResult(
        cycle_index=0,
        success=True,
        raw={
            "canonical": "the boy went to the store",
            "prime": {
                "composite": 506413,
                "p_thermo": 17,
                "p_identity": 29789,
                "canonical": "the boy went to the store",
            },
        },
        halt_mode="commit",
    )
    assert RosettaScalingScenario._prime(r_nested) == 506413
    # bad scalar -> None (don't silently accept)
    r3 = CycleResult(
        cycle_index=0, success=True, raw={"composite": "not-int"}, halt_mode="commit"
    )
    assert RosettaScalingScenario._prime(r3) is None
    r4 = _rosetta_result(canonical="water")  # canonical present, no prime
    assert RosettaScalingScenario._prime(r4) is None


def test_rosetta_scaling_scores_full_agreement_at_k():
    scenario = RosettaScalingScenario(n_cycles=99, k_max=3, primary_k=3, agreement_threshold=0.50)
    # 12 groups × 3 langs, all collapse to canonical="water" + composite=232453.
    # 12 clears the n_groups>=10 inconclusive guard (matches Immune Siege's
    # benign-denominator threshold).
    records: list[CorpusRecord] = []
    results: list[CycleResult] = []
    for g in range(12):
        for slot in range(3):
            records.append(
                CorpusRecord(
                    id=f"g{g}:slot{slot}",
                    text="any",
                    metadata={
                        "sentence_group_id": f"g{g}",
                        "language": f"L{slot}",
                        "slot_index": slot,
                        "k_max": 3,
                    },
                )
            )
            results.append(_rosetta_result(canonical="water", composite=232453))
    score = scenario.score(results, records)
    assert score.observed_value == pytest.approx(1.0)
    assert not score.inconclusive
    primary = next(
        e for e in score.evidence
        if e.statistic_name == "rosetta_canonical_agreement_at_k3"
    )
    assert primary.detail["n_groups"] == 12
    assert primary.detail["agreed_groups"] == 12
    # Wilson CI populated
    assert primary.ci_low is not None and primary.ci_high is not None


def test_rosetta_scaling_scores_partial_agreement_at_k():
    scenario = RosettaScalingScenario(n_cycles=99, k_max=3, primary_k=3, agreement_threshold=0.50)
    # 4 groups: 2 fully agree on canonical, 2 disagree on one slot
    records: list[CorpusRecord] = []
    results: list[CycleResult] = []
    layouts = [
        ("water", "water", "water"),       # agree
        ("water", "eau", "water"),         # disagree
        ("water", "water", "water"),       # agree
        ("agua", "agua", "water"),         # disagree
    ]
    for g, triple in enumerate(layouts):
        for slot, canon in enumerate(triple):
            records.append(
                CorpusRecord(
                    id=f"g{g}:s{slot}",
                    text="any",
                    metadata={
                        "sentence_group_id": f"g{g}",
                        "language": f"L{slot}",
                        "slot_index": slot,
                        "k_max": 3,
                    },
                )
            )
            results.append(_rosetta_result(canonical=canon))
    score = scenario.score(results, records)
    assert score.observed_value == pytest.approx(2 / 4)
    # too few groups -> inconclusive
    assert score.inconclusive


def test_rosetta_scaling_inconclusive_when_substrate_not_exercised():
    scenario = RosettaScalingScenario(n_cycles=99, k_max=3, primary_k=3)
    records: list[CorpusRecord] = []
    results: list[CycleResult] = []
    # 12 groups but all adapter errors -> majority adapter errors -> inconclusive
    for g in range(12):
        for slot in range(3):
            records.append(
                CorpusRecord(
                    id=f"g{g}:s{slot}",
                    text="any",
                    metadata={
                        "sentence_group_id": f"g{g}",
                        "language": f"L{slot}",
                        "slot_index": slot,
                        "k_max": 3,
                    },
                )
            )
            results.append(
                CycleResult(
                    cycle_index=0,
                    success=False,
                    raw={},
                    halt_mode="adapter_error",
                )
            )
    score = scenario.score(results, records)
    assert score.inconclusive
    assert "not exercised" in score.reasoning or "too few" in score.reasoning


def test_rosetta_scaling_per_k_evidence_reports_all_requested_ks():
    scenario = RosettaScalingScenario(n_cycles=99, k_max=20, primary_k=5)
    # 15 groups × 20 slots all agreeing — should report at K=3,5,10,20
    records: list[CorpusRecord] = []
    results: list[CycleResult] = []
    for g in range(15):
        for slot in range(20):
            records.append(
                CorpusRecord(
                    id=f"g{g}:s{slot}",
                    text="any",
                    metadata={
                        "sentence_group_id": f"g{g}",
                        "language": f"L{slot}",
                        "slot_index": slot,
                        "k_max": 20,
                    },
                )
            )
            results.append(_rosetta_result(canonical="water", composite=232453))
    score = scenario.score(results, records)
    primary = next(
        e for e in score.evidence
        if e.statistic_name == "rosetta_canonical_agreement_at_k5"
    )
    per_k = primary.detail["per_k"]
    for k in (3, 5, 10, 20):
        assert k in per_k, f"K={k} missing from per_k report"
        assert per_k[k]["n_groups"] == 15
        assert per_k[k]["agreed_canonical"] == 15
        assert per_k[k]["canonical_rate"] == pytest.approx(1.0)


def test_rosetta_scaling_rejects_bad_parameters():
    with pytest.raises(ValueError):
        RosettaScalingScenario(k_max=1)  # k_max < 2
    with pytest.raises(ValueError):
        RosettaScalingScenario(k_max=5, primary_k=10)  # primary_k > k_max
    with pytest.raises(ValueError):
        RosettaScalingScenario(agreement_threshold=1.5)  # out of [0, 1]


def test_rosetta_scaling_claim_is_falsifiable_and_pre_registerable():
    # default 0.80 = Rosetta's own blueprint promise ("every language -> one prime")
    claim = RosettaScalingScenario(primary_k=10).build_claim()
    assert claim.threshold.comparator == ">="
    assert claim.threshold.value == pytest.approx(0.80)
    assert "k10" in claim.threshold.metric
    assert claim.h0 and claim.h1
    assert claim.statement.strip()


# -- Organizational Dissonance scoring (synthetic cycle results, no Kimera) --


class _FakeEnronCorpus:
    """Minimal corpus yielding email-style records with varied body lengths."""

    def __init__(self, n_records: int, body_lengths: list[int] | None = None) -> None:
        self._n = n_records
        self._lengths = body_lengths

    def records(self):
        for i in range(self._n):
            length = self._lengths[i] if self._lengths and i < len(self._lengths) else 200
            yield CorpusRecord(
                id=f"enron-{i}",
                text=("Routine business email content. " * (length // 30 + 1))[:length],
                metadata={"from": f"alice{i}@enron.com", "subject": "Status update"},
            )


def _entity_result(
    *,
    gwf_verdict: str = "cleared",
    gwf_lockdown: bool = False,
    dissonance_events_count: int = 15,
    productive_dissonance_score: float = 0.5,
    manipulation_detected: bool = False,
    success: bool = True,
    halt_mode: str = "amplitude_death",
) -> CycleResult:
    raw = {
        "gwf_verdict": gwf_verdict,
        "gwf_lockdown": gwf_lockdown,
        "dissonance_events": [{"id": j} for j in range(dissonance_events_count)],
        "productive_dissonance_score": productive_dissonance_score,
        "manipulation_detected": manipulation_detected,
    }
    return CycleResult(cycle_index=0, success=success, raw=raw, halt_mode=halt_mode)


def test_organizational_dissonance_select_records_filters_short_bodies():
    scenario = OrganizationalDissonanceScenario(n_cycles=99, active_floor=0.90)
    # 5 records: lengths 30 (too short), 150, 200, 300, 50 (too short)
    corpus = _FakeEnronCorpus(5, body_lengths=[30, 150, 200, 300, 50])
    out = list(itertools.islice(scenario.select_records(corpus), 99))
    # only the records with body >= 100 chars survive
    assert len(out) == 3
    assert all(rec.metadata["body_length"] >= 100 for rec in out)


def test_organizational_dissonance_select_records_truncates_long_bodies():
    scenario = OrganizationalDissonanceScenario(n_cycles=99)
    # one very long body (10000 chars) -> truncated to MAX_BODY_LENGTH
    corpus = _FakeEnronCorpus(1, body_lengths=[10000])
    out = list(itertools.islice(scenario.select_records(corpus), 99))
    assert len(out) == 1
    assert out[0].metadata["body_truncated"] is True
    assert out[0].metadata["body_length"] == scenario._MAX_BODY_LENGTH


def test_organizational_dissonance_gwf_cleared_shape_aware():
    cleared = _entity_result(gwf_verdict="cleared")
    blocked = _entity_result(gwf_verdict="blocked:CRITICAL threat")
    locked = _entity_result(gwf_verdict="cleared", gwf_lockdown=True)
    assert OrganizationalDissonanceScenario._gwf_cleared(cleared)
    assert not OrganizationalDissonanceScenario._gwf_cleared(blocked)
    assert not OrganizationalDissonanceScenario._gwf_cleared(locked)


def test_organizational_dissonance_dissonance_count_extractor():
    r1 = _entity_result(dissonance_events_count=22)
    assert OrganizationalDissonanceScenario._dissonance_count(r1) == 22
    # zero-event case (e.g. GWF-blocked short-circuit)
    r0 = _entity_result(gwf_verdict="blocked:foo", dissonance_events_count=0)
    assert OrganizationalDissonanceScenario._dissonance_count(r0) == 0
    # fallback path: dissonance_event_count int
    r_int = CycleResult(
        cycle_index=0,
        success=True,
        raw={"dissonance_event_count": 7, "gwf_verdict": "cleared"},
        halt_mode="commit",
    )
    assert OrganizationalDissonanceScenario._dissonance_count(r_int) == 7
    # failed cycle -> 0
    r_fail = _entity_result(success=False)
    assert OrganizationalDissonanceScenario._dissonance_count(r_fail) == 0


def test_organizational_dissonance_score_passes_when_layer_fires_reliably():
    scenario = OrganizationalDissonanceScenario(n_cycles=99, active_floor=0.90)
    records = [CorpusRecord(id=f"e{i}", text="x" * 200, metadata={}) for i in range(15)]
    results = [_entity_result(dissonance_events_count=12) for _ in range(15)]
    score = scenario.score(results, records)
    assert score.observed_value == pytest.approx(1.0)
    assert not score.inconclusive
    primary = next(
        e for e in score.evidence
        if e.statistic_name == "dissonance_active_rate_on_cleared"
    )
    assert primary.detail["cleared_active"] == 15
    assert primary.detail["cleared_total"] == 15
    assert primary.ci_low is not None


def test_organizational_dissonance_score_refutes_when_layer_silent():
    scenario = OrganizationalDissonanceScenario(n_cycles=99, active_floor=0.90)
    records = [CorpusRecord(id=f"e{i}", text="x" * 200, metadata={}) for i in range(20)]
    # 20 cleared cycles, but only 5 fire dissonance -> 25% active rate, REFUTED
    results = [
        _entity_result(dissonance_events_count=(5 if i < 5 else 0))
        for i in range(20)
    ]
    score = scenario.score(results, records)
    assert score.observed_value == pytest.approx(5 / 20)
    assert not score.inconclusive


def test_organizational_dissonance_score_inconclusive_when_too_few_cleared():
    scenario = OrganizationalDissonanceScenario(n_cycles=99)
    # mostly GWF-blocked -> not enough cleared cycles for a Wilson CI
    records = [CorpusRecord(id=f"e{i}", text="x" * 200, metadata={}) for i in range(15)]
    results = [
        _entity_result(gwf_verdict="blocked:foo", dissonance_events_count=0)
        for _ in range(15)
    ]
    score = scenario.score(results, records)
    assert score.inconclusive
    assert "too few" in score.reasoning


def test_organizational_dissonance_score_inconclusive_when_substrate_not_exercised():
    scenario = OrganizationalDissonanceScenario(n_cycles=99)
    records = [CorpusRecord(id=f"e{i}", text="x" * 200, metadata={}) for i in range(20)]
    results = [
        CycleResult(cycle_index=0, success=False, raw={}, halt_mode="adapter_error")
        for _ in range(20)
    ]
    score = scenario.score(results, records)
    assert score.inconclusive
    assert "not exercised" in score.reasoning or "too few" in score.reasoning


def test_organizational_dissonance_score_reports_descriptive_evidence():
    scenario = OrganizationalDissonanceScenario(n_cycles=99, active_floor=0.90)
    records = [CorpusRecord(id=f"e{i}", text="x" * 200, metadata={}) for i in range(20)]
    # mix: 15 cleared all firing, 3 GWF-blocked, 2 manipulation_detected (+cleared)
    results = []
    for i in range(15):
        results.append(_entity_result(dissonance_events_count=10 + i))
    for _ in range(3):
        results.append(_entity_result(gwf_verdict="blocked:x", dissonance_events_count=0))
    for _ in range(2):
        results.append(_entity_result(manipulation_detected=True, dissonance_events_count=5))
    score = scenario.score(results, records)
    # gwf_block_rate = 3 / 20 = 0.15
    gwf_block_ev = next(
        e for e in score.evidence
        if e.statistic_name == "gwf_block_rate_on_enron"
    )
    assert gwf_block_ev.statistic_value == pytest.approx(3 / 20)
    # manipulation_rate = 2 / 20 = 0.10
    manip_ev = next(
        e for e in score.evidence
        if e.statistic_name == "manipulation_detected_rate_on_enron"
    )
    assert manip_ev.statistic_value == pytest.approx(2 / 20)
    # dissonance intensity distribution carries n + median
    diss_ev = next(
        e for e in score.evidence
        if e.statistic_name == "dissonance_events_count_median"
    )
    dist = diss_ev.detail["distribution"]
    assert dist["n"] == 17  # 15 + 2 cleared (the 3 GWF-blocked are excluded)


def test_organizational_dissonance_rejects_bad_parameters():
    with pytest.raises(ValueError):
        OrganizationalDissonanceScenario(active_floor=1.5)  # out of [0, 1]
    with pytest.raises(ValueError):
        OrganizationalDissonanceScenario(active_floor=-0.1)


def test_organizational_dissonance_claim_is_falsifiable_and_pre_registerable():
    claim = OrganizationalDissonanceScenario(active_floor=0.90).build_claim()
    assert claim.threshold.comparator == ">="
    assert claim.threshold.value == pytest.approx(0.90)
    assert claim.threshold.metric == "dissonance_active_rate_on_cleared"
    assert claim.h0 and claim.h1
    assert claim.statement.strip()


# -- Logic-Topology Siege scoring (synthetic cycle results, no Kimera) -------


class _FakeLinuxCorpus:
    """Minimal corpus yielding kernel-commit-style records."""

    def __init__(self, n_records: int, body_lengths: list[int] | None = None) -> None:
        self._n = n_records
        self._lengths = body_lengths

    def records(self):
        for i in range(self._n):
            length = self._lengths[i] if self._lengths and i < len(self._lengths) else 200
            yield CorpusRecord(
                id=f"linux-{i:040x}",
                text=("Technical commit message body. " * (length // 30 + 1))[:length],
                metadata={"author": "kernel.dev@linux.org", "date": "2026-01-01"},
            )


def _topology_result(
    *,
    gwf_verdict: str = "cleared",
    halt_mode: str = "exhausted",
    dissonance_events_count: int = 20,
    phi_value: float = 0.25,
    success: bool = True,
) -> CycleResult:
    raw = {
        "gwf_verdict": gwf_verdict,
        "dissonance_events": [{"id": j} for j in range(dissonance_events_count)],
        "phi_value": phi_value,
    }
    return CycleResult(cycle_index=0, success=success, raw=raw, halt_mode=halt_mode)


def test_logic_topology_select_records_filters_short_bodies():
    scenario = LogicTopologySiegeScenario(n_cycles=99)
    corpus = _FakeLinuxCorpus(5, body_lengths=[30, 100, 200, 300, 50])
    out = list(itertools.islice(scenario.select_records(corpus), 99))
    # only records >= MIN (80) survive — lengths 100, 200, 300
    assert len(out) == 3
    assert all(r.metadata["body_length"] >= 80 for r in out)


def test_logic_topology_halt_mode_normalization():
    r1 = _topology_result(halt_mode="EXHAUSTED")
    assert LogicTopologySiegeScenario._halt_mode(r1) == "exhausted"
    r2 = _topology_result(halt_mode=" amplitude_death ")
    assert LogicTopologySiegeScenario._halt_mode(r2) == "amplitude_death"
    r3 = CycleResult(cycle_index=0, success=True, raw={}, halt_mode=None)
    assert LogicTopologySiegeScenario._halt_mode(r3) == ""


def test_logic_topology_phi_extraction_shape_aware():
    r1 = _topology_result(phi_value=0.42)
    assert LogicTopologySiegeScenario._phi_value(r1) == pytest.approx(0.42)
    r2 = CycleResult(
        cycle_index=0,
        success=True,
        raw={"phi": 0.7, "gwf_verdict": "cleared"},
        halt_mode="exhausted",
    )
    assert LogicTopologySiegeScenario._phi_value(r2) == pytest.approx(0.7)
    r3 = CycleResult(cycle_index=0, success=True, raw={}, halt_mode="exhausted")
    assert LogicTopologySiegeScenario._phi_value(r3) == 0.0


def test_logic_topology_score_passes_on_sustained_traversal():
    scenario = LogicTopologySiegeScenario(n_cycles=99, sustained_floor=0.60)
    records = [CorpusRecord(id=f"l{i}", text="x" * 200, metadata={}) for i in range(15)]
    # 15 cleared, all exhausted -> 100% sustained rate, VALIDATED
    results = [_topology_result(halt_mode="exhausted") for _ in range(15)]
    score = scenario.score(results, records)
    assert score.observed_value == pytest.approx(1.0)
    assert not score.inconclusive


def test_logic_topology_score_refutes_when_walker_collapses():
    scenario = LogicTopologySiegeScenario(n_cycles=99, sustained_floor=0.60)
    records = [CorpusRecord(id=f"l{i}", text="x" * 200, metadata={}) for i in range(20)]
    # 20 cleared, 5 exhausted + 15 amplitude_death -> 25% sustained -> REFUTED
    results = []
    for _ in range(5):
        results.append(_topology_result(halt_mode="exhausted"))
    for _ in range(15):
        results.append(_topology_result(halt_mode="amplitude_death"))
    score = scenario.score(results, records)
    assert score.observed_value == pytest.approx(5 / 20)
    assert not score.inconclusive
    # halt mode distribution is reported descriptively
    dist_ev = next(
        e for e in score.evidence
        if e.statistic_name == "halt_modes_observed_count"
    )
    dist = dist_ev.detail["distribution"]
    assert dist["exhausted"] == 5
    assert dist["amplitude_death"] == 15


def test_logic_topology_score_inconclusive_when_too_few_cleared():
    scenario = LogicTopologySiegeScenario(n_cycles=99)
    records = [CorpusRecord(id=f"l{i}", text="x" * 200, metadata={}) for i in range(15)]
    results = [
        _topology_result(gwf_verdict="blocked:foo", halt_mode="exhausted")
        for _ in range(15)
    ]
    score = scenario.score(results, records)
    assert score.inconclusive
    assert "too few" in score.reasoning


def test_logic_topology_amplitude_death_rate_reported():
    scenario = LogicTopologySiegeScenario(n_cycles=99)
    records = [CorpusRecord(id=f"l{i}", text="x" * 200, metadata={}) for i in range(20)]
    # 10 exhausted, 8 amplitude_death, 2 selective on cleared cycles
    results = []
    for _ in range(10):
        results.append(_topology_result(halt_mode="exhausted"))
    for _ in range(8):
        results.append(_topology_result(halt_mode="amplitude_death"))
    for _ in range(2):
        results.append(_topology_result(halt_mode="selective"))
    score = scenario.score(results, records)
    ad_ev = next(
        e for e in score.evidence
        if e.statistic_name == "amplitude_death_rate_on_cleared"
    )
    assert ad_ev.statistic_value == pytest.approx(8 / 20)


def test_logic_topology_rejects_bad_parameters():
    with pytest.raises(ValueError):
        LogicTopologySiegeScenario(sustained_floor=1.5)
    with pytest.raises(ValueError):
        LogicTopologySiegeScenario(sustained_floor=-0.1)


def test_logic_topology_claim_is_falsifiable_and_pre_registerable():
    claim = LogicTopologySiegeScenario(sustained_floor=0.60).build_claim()
    assert claim.threshold.comparator == ">="
    assert claim.threshold.value == pytest.approx(0.60)
    assert claim.threshold.metric == "sustained_traversal_rate_on_cleared"
    assert claim.h0 and claim.h1
    assert claim.statement.strip()
