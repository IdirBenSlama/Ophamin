"""Tests for CR6 — the reproducibility check.

reproduce() re-runs a scenario N times and reports what reproduces. The honest
contract: the VERDICT and the cross-check CONCLUSION reproduce, the falsifiable
metric reproduces within a measured drift band, and proof_ids are distinct by
design (each embeds created_at) — not a reproducibility signal. These tests pin
all of that with controllable fake records (no substrate needed).
"""

from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from ophamin.reproducing import reproduce


def _rec(outcome, observed, cross, pid, *, metric="recognition_jaccard_floor", thr=0.80):
    ev = NS(detail={"scope": "flow"}, cross_check=cross)
    return NS(
        verdict=NS(
            outcome=outcome,
            observed_value=observed,
            threshold=NS(metric=metric, value=thr),
        ),
        proof_id=pid,
        evidence=[ev],
    )


class _FakeScenario:
    """Returns pre-built records, one per run() call — drives reproduce()
    deterministically so every layer can be pinned without a substrate."""

    name = "fake-repro"

    def __init__(self, records):
        self._records = list(records)
        self._i = 0

    def run(self, substrate=None, *, sign_key=b""):
        r = self._records[self._i]
        self._i += 1
        return r


class TestReproduce:
    def test_deterministic_run_reproduces_everything(self):
        recs = [_rec("VALIDATED", 0.86, "passed", f"id{i}") for i in range(3)]
        rep = reproduce(_FakeScenario(recs), n_runs=3)
        assert rep.verdict_reproducible is True
        assert rep.cross_check_reproducible is True
        assert rep.observed_drift == 0.0
        assert rep.proof_ids_distinct is True
        assert rep.verdicts == ["VALIDATED"] * 3

    def test_drift_but_stable_verdict(self):
        # substrate float-drift: same verdict + cross-check, observed moves.
        recs = [
            _rec("VALIDATED", 0.86, "passed", "a"),
            _rec("VALIDATED", 0.88, "passed", "b"),
            _rec("VALIDATED", 0.85, "passed", "c"),
        ]
        rep = reproduce(_FakeScenario(recs), n_runs=3)
        assert rep.verdict_reproducible is True
        assert rep.cross_check_reproducible is True
        assert rep.observed_drift == pytest.approx(0.03)
        assert rep.observed_min == pytest.approx(0.85)
        assert rep.observed_max == pytest.approx(0.88)
        assert rep.observed_stdev > 0.0

    def test_flipping_verdict_is_not_reproducible(self):
        recs = [
            _rec("VALIDATED", 0.82, "passed", "a"),
            _rec("REFUTED", 0.78, "failed", "b"),
            _rec("VALIDATED", 0.81, "passed", "c"),
        ]
        rep = reproduce(_FakeScenario(recs), n_runs=3)
        assert rep.verdict_reproducible is False
        assert rep.cross_check_reproducible is False
        assert "DID NOT reproduce" in rep.notes

    def test_cross_check_variation_flagged(self):
        recs = [
            _rec("VALIDATED", 0.86, "passed", "a"),
            _rec("VALIDATED", 0.86, "skipped", "b"),
        ]
        rep = reproduce(_FakeScenario(recs), n_runs=2)
        assert rep.verdict_reproducible is True
        assert rep.cross_check_reproducible is False

    def test_proof_ids_distinct_documented(self):
        # proof_id is per-event (timestamp in body) — distinct across runs.
        recs = [_rec("VALIDATED", 0.86, "passed", f"id{i}") for i in range(3)]
        rep = reproduce(_FakeScenario(recs), n_runs=3)
        assert rep.proof_ids_distinct is True
        assert "not a reproducibility signal" in rep.notes

    def test_degenerate_identical_proof_ids_detected(self):
        # If a (broken) substrate produced identical proof_ids, surface it.
        recs = [_rec("VALIDATED", 0.86, "passed", "same") for _ in range(3)]
        rep = reproduce(_FakeScenario(recs), n_runs=3)
        assert rep.proof_ids_distinct is False

    def test_threshold_carried_through(self):
        recs = [_rec("VALIDATED", 0.86, "passed", f"id{i}", thr=0.80) for i in range(2)]
        rep = reproduce(_FakeScenario(recs), n_runs=2)
        assert rep.threshold_metric == "recognition_jaccard_floor"
        assert rep.threshold_value == 0.80

    def test_n_runs_must_be_at_least_two(self):
        recs = [_rec("VALIDATED", 0.86, "passed", "a")]
        with pytest.raises(ValueError):
            reproduce(_FakeScenario(recs), n_runs=1)

    def test_to_dict_round_trips_fields(self):
        recs = [_rec("VALIDATED", 0.86, "passed", f"id{i}") for i in range(2)]
        rep = reproduce(_FakeScenario(recs), n_runs=2)
        d = rep.to_dict()
        assert d["verdict_reproducible"] is True
        assert d["n_runs"] == 2
        assert d["observed_drift"] == 0.0
        assert set(["verdicts", "observed_values", "cross_checks", "notes"]) <= set(d)
