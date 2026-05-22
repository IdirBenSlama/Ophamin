"""Tests for the shared substrate-observable toolbox.

These are the canonical extractors the memory/finance scenarios now share; the
behaviours they encode (None on gap, non-finite floats → None, dict/str concept
normalisation, the vault_stats scar-count priority) used to be copy-pasted.
"""

from __future__ import annotations

import pytest

from ophamin.seeing.substrate.base import CycleResult
from ophamin.seeing.substrate.observables import (
    as_finite_float,
    concept_set,
    jaccard,
    prime_set,
    scar_count,
    state_vector,
)


def _r(raw, success=True):
    return CycleResult(cycle_index=0, success=success, halt_mode="exhausted", raw=raw)


class TestAsFiniteFloat:
    def test_parses_numbers(self):
        assert as_finite_float(2) == pytest.approx(2.0)
        assert as_finite_float("1.5") == pytest.approx(1.5)

    def test_rejects_non_finite_and_bool(self):
        assert as_finite_float("nan") is None
        assert as_finite_float("inf") is None
        assert as_finite_float(float("nan")) is None
        assert as_finite_float(True) is None
        assert as_finite_float("notanumber") is None


class TestConceptSet:
    def test_str_and_dict_concepts(self):
        assert concept_set(_r({"concepts": ["a", " b "]})) == frozenset({"a", "b"})
        assert concept_set(_r({"concepts": [{"name": "x"}, {"label": "y"}]})) == frozenset({"x", "y"})

    def test_none_on_gap(self):
        assert concept_set(_r({"concepts": []})) is None
        assert concept_set(_r({})) is None
        assert concept_set(_r({"concepts": ["a"]}, success=False)) is None


class TestPrimeSet:
    def test_from_chain(self):
        assert prime_set(_r({"prime_chain": [2, 3, 5, 5]})) == frozenset({"2", "3", "5"})

    def test_fallback_to_rosetta(self):
        assert prime_set(_r({"rosetta_primes": {"11": 1, "13": 1}})) == frozenset({"11", "13"})

    def test_none_on_gap(self):
        assert prime_set(_r({})) is None
        assert prime_set(_r({"prime_chain": []})) is None


class TestScarCount:
    def test_prefers_total_scars_stored(self):
        assert scar_count(_r({"vault_stats": {"total_scars_stored": 7,
                                              "vault_a": {"scar_count": 3},
                                              "vault_b": {"scar_count": 2}}})) == 7

    def test_falls_back_to_vault_sum(self):
        assert scar_count(_r({"vault_stats": {"vault_a": {"scar_count": 3},
                                              "vault_b": {"scar_count": 2}}})) == 5

    def test_falls_back_to_enhanced_total(self):
        assert scar_count(_r({"enhanced_vault_total_memories": 9})) == 9

    def test_none_on_gap_and_failure(self):
        assert scar_count(_r({})) is None
        assert scar_count(_r({"vault_stats": {"total_scars_stored": 1}}, success=False)) is None


class TestStateVector:
    def test_mapping_and_sequence(self):
        raw = {"arachne_web_coupling_frobenius": 1.5, "knowledge_mass": 10.0}
        assert state_vector(_r(raw), {"coupling": "arachne_web_coupling_frobenius"}) == {"coupling": 1.5}
        assert state_vector(_r(raw), ["knowledge_mass"]) == {"knowledge_mass": 10.0}

    def test_none_when_nothing_present(self):
        assert state_vector(_r({}), ["missing"]) is None


class TestJaccard:
    def test_basic(self):
        assert jaccard(frozenset({"a", "b"}), frozenset({"b", "c"})) == pytest.approx(1 / 3)

    def test_two_empty_are_identical(self):
        assert jaccard(frozenset(), frozenset()) == pytest.approx(1.0)
