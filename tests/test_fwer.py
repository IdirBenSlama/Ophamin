"""Tests for the FWER / FDR multiplicity-correction module.

Three layers of evidence:

1. **Known-answer tests** — classic textbook examples (Holm 1979 + a BH
   demo) with hand-computed expected results, pinned to the byte.
2. **Property tests (Hypothesis)** — invariants every correction
   method must satisfy regardless of input: monotonicity, range,
   conservation (Holm ≥ BH ≥ raw), passthrough behaviour for missing
   p-values, idempotence on already-corrected families.
3. **Integration tests** — :func:`apply_correction` dispatch + the
   :class:`CorrectionFamily` aggregate's projections.

The module is pure-functional, so all tests are sub-millisecond.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ophamin.comparing.fwer import (
    SUPPORTED_METHODS,
    CorrectionInput,
    apply_correction,
    benjamini_hochberg,
    holm_bonferroni,
)


# ---------------------------------------------------------------------------
# CorrectionInput invariants
# ---------------------------------------------------------------------------


class TestCorrectionInputInvariants:
    """Validation must fire at construction time, not at call time."""

    def test_accepts_well_formed_input(self) -> None:
        c = CorrectionInput("a", "VALIDATED", 0.01)
        assert c.claim_id == "a"
        assert c.raw_verdict == "VALIDATED"
        assert c.p_value == 0.01

    def test_accepts_none_p_value(self) -> None:
        c = CorrectionInput("a", "VALIDATED", None)
        assert c.p_value is None

    def test_accepts_boundary_p_values(self) -> None:
        assert CorrectionInput("a", "V", 0.0).p_value == 0.0
        assert CorrectionInput("b", "V", 1.0).p_value == 1.0

    def test_rejects_empty_claim_id(self) -> None:
        with pytest.raises(ValueError, match="claim_id"):
            CorrectionInput("", "VALIDATED", 0.01)

    def test_rejects_empty_raw_verdict(self) -> None:
        with pytest.raises(ValueError, match="raw_verdict"):
            CorrectionInput("a", "", 0.01)

    def test_rejects_p_below_zero(self) -> None:
        with pytest.raises(ValueError, match="p_value must lie in"):
            CorrectionInput("a", "V", -0.001)

    def test_rejects_p_above_one(self) -> None:
        with pytest.raises(ValueError, match="p_value must lie in"):
            CorrectionInput("a", "V", 1.001)

    def test_rejects_non_numeric_p(self) -> None:
        with pytest.raises(TypeError, match="p_value must be"):
            CorrectionInput("a", "V", "0.05")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Known-answer tests
# ---------------------------------------------------------------------------


class TestHolmKnownAnswers:
    """Canonical Holm-Bonferroni hand-computed examples."""

    def test_holm_1979_textbook_example(self) -> None:
        """Five p-values: 0.005, 0.011, 0.02, 0.04, 0.13 with α=0.05.

        Holm's step-down: (n - j + 1) * p_(j) compared against α.
        j=1: 5 × 0.005 = 0.025 ≤ 0.05 → reject
        j=2: 4 × 0.011 = 0.044 ≤ 0.05 → reject
        j=3: 3 × 0.02  = 0.060 > 0.05 → stop; all subsequent fail
        Therefore 2 rejections (a, b), 3 demotions (c, d, e).
        """
        inputs = [
            CorrectionInput("a", "VALIDATED", 0.005),
            CorrectionInput("b", "VALIDATED", 0.011),
            CorrectionInput("c", "VALIDATED", 0.02),
            CorrectionInput("d", "VALIDATED", 0.04),
            CorrectionInput("e", "VALIDATED", 0.13),
        ]
        result = holm_bonferroni(inputs, alpha=0.05)
        assert result.method == "holm"
        assert result.family_size == 5
        assert result.n_with_p_value == 5
        assert result.n_rejections == 2
        by_id = {r.claim_id: r for r in result.results}
        assert by_id["a"].corrected_p_value == pytest.approx(0.025)
        assert by_id["b"].corrected_p_value == pytest.approx(0.044)
        assert by_id["c"].corrected_p_value == pytest.approx(0.060)
        assert by_id["d"].corrected_p_value == pytest.approx(0.080)
        assert by_id["e"].corrected_p_value == pytest.approx(0.130)
        # Verdict demotion
        assert by_id["a"].corrected_verdict == "VALIDATED"
        assert by_id["b"].corrected_verdict == "VALIDATED"
        assert by_id["c"].corrected_verdict == "INCONCLUSIVE"
        assert by_id["d"].corrected_verdict == "INCONCLUSIVE"
        assert by_id["e"].corrected_verdict == "INCONCLUSIVE"

    def test_holm_single_test_no_inflation(self) -> None:
        """With n=1, Holm leaves p unchanged (no multiplicity)."""
        inputs = [CorrectionInput("a", "VALIDATED", 0.04)]
        result = holm_bonferroni(inputs, alpha=0.05)
        assert result.results[0].corrected_p_value == pytest.approx(0.04)
        assert result.results[0].significant_after_correction is True

    def test_holm_all_tiny_p_values_all_reject(self) -> None:
        """Ten tiny p-values; Holm rejects all."""
        inputs = [
            CorrectionInput(f"c{i}", "VALIDATED", 0.0001) for i in range(10)
        ]
        result = holm_bonferroni(inputs, alpha=0.05)
        assert result.n_rejections == 10
        for r in result.results:
            assert r.corrected_verdict == "VALIDATED"

    def test_holm_all_large_p_values_all_demote(self) -> None:
        """Ten large p-values; Holm rejects none, demotes all VALIDATED."""
        inputs = [
            CorrectionInput(f"c{i}", "VALIDATED", 0.5) for i in range(10)
        ]
        result = holm_bonferroni(inputs, alpha=0.05)
        assert result.n_rejections == 0
        for r in result.results:
            assert r.corrected_verdict == "INCONCLUSIVE"


class TestBenjaminiHochbergKnownAnswers:
    """Canonical BH examples — less conservative than Holm."""

    def test_bh_same_inputs_as_holm_textbook(self) -> None:
        """Same five p-values as the Holm example.

        BH: p_(j) * m / j ≤ α.
        j=1: 0.005 × 5/1 = 0.025 ≤ 0.05 → reject
        j=2: 0.011 × 5/2 = 0.0275 ≤ 0.05 → reject
        j=3: 0.02 × 5/3 = 0.0333 ≤ 0.05 → reject
        j=4: 0.04 × 5/4 = 0.05 ≤ 0.05 → reject (boundary)
        j=5: 0.13 × 5/5 = 0.13 > 0.05 → fail
        Therefore 4 rejections (a, b, c, d), 1 demotion (e).
        """
        inputs = [
            CorrectionInput("a", "VALIDATED", 0.005),
            CorrectionInput("b", "VALIDATED", 0.011),
            CorrectionInput("c", "VALIDATED", 0.02),
            CorrectionInput("d", "VALIDATED", 0.04),
            CorrectionInput("e", "VALIDATED", 0.13),
        ]
        result = benjamini_hochberg(inputs, alpha=0.05)
        assert result.method == "bh"
        assert result.n_rejections == 4
        by_id = {r.claim_id: r for r in result.results}
        assert by_id["a"].corrected_p_value == pytest.approx(0.025)
        assert by_id["b"].corrected_p_value == pytest.approx(0.0275)
        assert by_id["c"].corrected_p_value == pytest.approx(1.0 / 30, rel=1e-6)
        assert by_id["d"].corrected_p_value == pytest.approx(0.05)
        assert by_id["e"].corrected_p_value == pytest.approx(0.13)
        assert by_id["e"].corrected_verdict == "INCONCLUSIVE"

    def test_bh_step_up_monotonicity(self) -> None:
        """BH-adjusted p-values must be non-decreasing in original p-rank."""
        inputs = [
            CorrectionInput(f"c{i}", "VALIDATED", p)
            for i, p in enumerate([0.001, 0.005, 0.04, 0.08, 0.5])
        ]
        result = benjamini_hochberg(inputs, alpha=0.05)
        adjusted = sorted(
            ((r.raw_p_value, r.corrected_p_value) for r in result.results),
            key=lambda t: t[0],  # type: ignore[arg-type, return-value]
        )
        adj_only = [t[1] for t in adjusted]
        for x, y in zip(adj_only, adj_only[1:]):
            assert x is not None and y is not None
            assert x <= y + 1e-12


# ---------------------------------------------------------------------------
# Passthrough / mixed inputs
# ---------------------------------------------------------------------------


class TestPassthrough:
    """Inputs with ``p_value is None`` must pass through unchanged."""

    @pytest.mark.parametrize("method", sorted(SUPPORTED_METHODS))
    def test_none_p_value_passes_through(self, method: str) -> None:
        inputs = [CorrectionInput("a", "VALIDATED", None)]
        result = apply_correction(inputs, method=method, alpha=0.05)
        assert result.results[0].raw_p_value is None
        assert result.results[0].corrected_p_value is None
        assert result.results[0].corrected_verdict == "VALIDATED"  # no demotion
        assert result.results[0].significant_after_correction is False

    @pytest.mark.parametrize("method", ["holm", "bh"])
    def test_mixed_none_and_value(self, method: str) -> None:
        """None entries count toward family_size but not n_with_p_value."""
        inputs = [
            CorrectionInput("a", "VALIDATED", 0.01),
            CorrectionInput("b", "VALIDATED", None),
            CorrectionInput("c", "VALIDATED", 0.02),
        ]
        result = apply_correction(inputs, method=method, alpha=0.05)
        assert result.family_size == 3
        assert result.n_with_p_value == 2
        by_id = {r.claim_id: r for r in result.results}
        assert by_id["b"].corrected_p_value is None
        assert by_id["b"].corrected_verdict == "VALIDATED"

    def test_refuted_passes_through_under_holm(self) -> None:
        """REFUTED + INCONCLUSIVE are never demoted, even with no rejection."""
        inputs = [
            CorrectionInput("r", "REFUTED", 0.99),
            CorrectionInput("i", "INCONCLUSIVE", 0.99),
        ]
        result = holm_bonferroni(inputs, alpha=0.05)
        by_id = {r.claim_id: r for r in result.results}
        assert by_id["r"].corrected_verdict == "REFUTED"
        assert by_id["i"].corrected_verdict == "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Property tests — Hypothesis
# ---------------------------------------------------------------------------


# Strategy: small families of corrections with p_values in [0, 1] and
# raw_verdict pulled from the canonical outcome set. Hypothesis exercises
# both pure-p families and mixed (with None) families.
@st.composite
def correction_family_strategy(  # type: ignore[no-untyped-def]
    draw,
    *,
    min_size: int = 1,
    max_size: int = 20,
    allow_none: bool = True,
):
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    inputs = []
    for i in range(n):
        verdict = draw(st.sampled_from(["VALIDATED", "REFUTED", "INCONCLUSIVE"]))
        if allow_none:
            p: float | None = draw(
                st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0))
            )
        else:
            p = draw(st.floats(min_value=0.0, max_value=1.0))
        inputs.append(CorrectionInput(f"c{i}", verdict, p))
    return inputs


class TestPropertyInvariants:
    @given(family=correction_family_strategy())
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_holm_corrected_p_in_unit_interval(
        self, family: list[CorrectionInput]
    ) -> None:
        result = holm_bonferroni(family, alpha=0.05)
        for r in result.results:
            if r.corrected_p_value is not None:
                assert 0.0 <= r.corrected_p_value <= 1.0

    @given(family=correction_family_strategy())
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_bh_corrected_p_in_unit_interval(
        self, family: list[CorrectionInput]
    ) -> None:
        result = benjamini_hochberg(family, alpha=0.05)
        for r in result.results:
            if r.corrected_p_value is not None:
                assert 0.0 <= r.corrected_p_value <= 1.0

    @given(family=correction_family_strategy(allow_none=False))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_holm_corrected_p_at_or_above_raw(
        self, family: list[CorrectionInput]
    ) -> None:
        """Holm's adjusted p ≥ raw p (correction can only inflate)."""
        result = holm_bonferroni(family, alpha=0.05)
        for r in result.results:
            assert r.raw_p_value is not None and r.corrected_p_value is not None
            assert r.corrected_p_value >= r.raw_p_value - 1e-12

    @given(family=correction_family_strategy(allow_none=False))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_bh_corrected_p_at_or_above_raw(
        self, family: list[CorrectionInput]
    ) -> None:
        """BH's adjusted p ≥ raw p (correction can only inflate)."""
        result = benjamini_hochberg(family, alpha=0.05)
        for r in result.results:
            assert r.raw_p_value is not None and r.corrected_p_value is not None
            assert r.corrected_p_value >= r.raw_p_value - 1e-12

    @given(family=correction_family_strategy(allow_none=False, min_size=2))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_holm_is_at_least_as_conservative_as_bh(
        self, family: list[CorrectionInput]
    ) -> None:
        """For every input, Holm-adjusted p ≥ BH-adjusted p.

        Holm controls FWER (stricter); BH controls FDR (looser). On the
        same family, Holm's adjusted values are component-wise ≥ BH's
        for every record with a p-value.
        """
        holm = {r.claim_id: r for r in holm_bonferroni(family).results}
        bh = {r.claim_id: r for r in benjamini_hochberg(family).results}
        for claim_id, holm_r in holm.items():
            bh_r = bh[claim_id]
            assert holm_r.corrected_p_value is not None
            assert bh_r.corrected_p_value is not None
            assert holm_r.corrected_p_value >= bh_r.corrected_p_value - 1e-12

    @given(family=correction_family_strategy(allow_none=False, min_size=2))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_holm_rejections_subset_of_bh_rejections(
        self, family: list[CorrectionInput]
    ) -> None:
        """Holm rejects ⊆ BH rejects (FWER ⊆ FDR rejections)."""
        holm = holm_bonferroni(family, alpha=0.05)
        bh = benjamini_hochberg(family, alpha=0.05)
        holm_rej = {
            r.claim_id for r in holm.results if r.significant_after_correction
        }
        bh_rej = {
            r.claim_id for r in bh.results if r.significant_after_correction
        }
        assert holm_rej.issubset(bh_rej)

    @given(family=correction_family_strategy(allow_none=False))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_holm_adjusted_is_monotone_in_p_value_order(
        self, family: list[CorrectionInput]
    ) -> None:
        """Sorting by raw p, corrected p must be non-decreasing (step-down monotone)."""
        result = holm_bonferroni(family, alpha=0.05)
        sorted_results = sorted(
            result.results, key=lambda r: (r.raw_p_value, r.claim_id)  # type: ignore[arg-type, return-value]
        )
        prev: float = -1.0
        for r in sorted_results:
            assert r.corrected_p_value is not None
            assert r.corrected_p_value >= prev - 1e-12
            prev = r.corrected_p_value

    @given(family=correction_family_strategy(allow_none=False))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_bh_adjusted_is_monotone_in_p_value_order(
        self, family: list[CorrectionInput]
    ) -> None:
        """Same monotonicity must hold for BH (step-up monotonized)."""
        result = benjamini_hochberg(family, alpha=0.05)
        sorted_results = sorted(
            result.results, key=lambda r: (r.raw_p_value, r.claim_id)  # type: ignore[arg-type, return-value]
        )
        prev: float = -1.0
        for r in sorted_results:
            assert r.corrected_p_value is not None
            assert r.corrected_p_value >= prev - 1e-12
            prev = r.corrected_p_value

    @given(family=correction_family_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_input_order_preserved_in_output(
        self, family: list[CorrectionInput]
    ) -> None:
        """``results`` index aligns with ``inputs`` index for both methods."""
        for method in ("holm", "bh"):
            result = apply_correction(family, method=method, alpha=0.05)
            assert len(result.results) == len(family)
            for i, inp in enumerate(family):
                assert result.results[i].claim_id == inp.claim_id
                assert result.results[i].raw_verdict == inp.raw_verdict
                assert result.results[i].raw_p_value == inp.p_value

    @given(family=correction_family_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_demotion_targets_only_validated(
        self, family: list[CorrectionInput]
    ) -> None:
        """Correction can only demote VALIDATED → INCONCLUSIVE."""
        for method in ("holm", "bh"):
            result = apply_correction(family, method=method, alpha=0.05)
            for inp, r in zip(family, result.results):
                if inp.raw_verdict != "VALIDATED":
                    assert r.corrected_verdict == inp.raw_verdict

    @given(
        family=correction_family_strategy(),
        alpha=st.floats(min_value=0.001, max_value=0.999),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_significance_flag_matches_adjusted_p_vs_alpha(
        self, family: list[CorrectionInput], alpha: float
    ) -> None:
        """``significant_after_correction`` == (corrected_p ≤ alpha)."""
        for method in ("holm", "bh"):
            result = apply_correction(family, method=method, alpha=alpha)
            for r in result.results:
                if r.corrected_p_value is None:
                    assert r.significant_after_correction is False
                else:
                    expected = r.corrected_p_value <= alpha
                    assert r.significant_after_correction is expected


# ---------------------------------------------------------------------------
# Idempotence: re-correcting a corrected family doesn't change anything
# ---------------------------------------------------------------------------


class TestIdempotence:
    """Re-running correction on a corrected family is a no-op modulo
    re-projection. Property: the *rejection set* is stable under re-correction
    of the corrected p-values."""

    @given(family=correction_family_strategy(allow_none=False, min_size=2))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_holm_rejection_set_stable_under_second_pass(
        self, family: list[CorrectionInput]
    ) -> None:
        first = holm_bonferroni(family, alpha=0.05)
        second_inputs = [
            CorrectionInput(r.claim_id, r.corrected_verdict, r.corrected_p_value)
            for r in first.results
        ]
        second = holm_bonferroni(second_inputs, alpha=0.05)
        first_rej = {
            r.claim_id for r in first.results if r.significant_after_correction
        }
        second_rej = {
            r.claim_id for r in second.results if r.significant_after_correction
        }
        # Holm is conservative: re-running can only shrink the rejection set.
        assert second_rej.issubset(first_rej)


# ---------------------------------------------------------------------------
# Dispatcher + family aggregate
# ---------------------------------------------------------------------------


class TestDispatcher:
    def test_apply_correction_dispatches_holm(self) -> None:
        inputs = [CorrectionInput("a", "VALIDATED", 0.01)]
        result = apply_correction(inputs, method="holm")
        assert result.method == "holm"

    def test_apply_correction_dispatches_bh(self) -> None:
        inputs = [CorrectionInput("a", "VALIDATED", 0.01)]
        result = apply_correction(inputs, method="bh")
        assert result.method == "bh"

    def test_apply_correction_dispatches_none(self) -> None:
        inputs = [CorrectionInput("a", "VALIDATED", 0.01)]
        result = apply_correction(inputs, method="none")
        assert result.method == "none"
        # No correction → raw p flows through unchanged
        assert result.results[0].corrected_p_value == 0.01

    def test_apply_correction_rejects_unknown_method(self) -> None:
        inputs = [CorrectionInput("a", "VALIDATED", 0.01)]
        with pytest.raises(ValueError, match="method must be one of"):
            apply_correction(inputs, method="bonferroni")  # close but not supported

    def test_apply_correction_rejects_invalid_alpha(self) -> None:
        inputs = [CorrectionInput("a", "VALIDATED", 0.01)]
        with pytest.raises(ValueError, match="alpha must lie in"):
            apply_correction(inputs, method="holm", alpha=0.0)
        with pytest.raises(ValueError, match="alpha must lie in"):
            apply_correction(inputs, method="holm", alpha=1.5)


class TestCorrectionFamilyProjection:
    def test_verdicts_returns_claim_id_to_corrected_verdict_map(self) -> None:
        inputs = [
            CorrectionInput("a", "VALIDATED", 0.001),
            CorrectionInput("b", "VALIDATED", 0.99),
        ]
        result = holm_bonferroni(inputs, alpha=0.05)
        verdicts = result.verdicts()
        assert verdicts["a"] == "VALIDATED"
        assert verdicts["b"] == "INCONCLUSIVE"
        assert set(verdicts.keys()) == {"a", "b"}

    def test_empty_family_returns_empty_family(self) -> None:
        result = apply_correction([], method="holm")
        assert result.family_size == 0
        assert result.n_with_p_value == 0
        assert result.n_rejections == 0
        assert result.results == ()
        assert result.verdicts() == {}


# ---------------------------------------------------------------------------
# Convergence with n=1: no correction needed
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_n1_holm_unchanged(self) -> None:
        inp = [CorrectionInput("a", "VALIDATED", 0.03)]
        result = holm_bonferroni(inp, alpha=0.05)
        assert result.results[0].corrected_p_value == pytest.approx(0.03)
        assert result.results[0].significant_after_correction is True

    def test_n1_bh_unchanged(self) -> None:
        inp = [CorrectionInput("a", "VALIDATED", 0.03)]
        result = benjamini_hochberg(inp, alpha=0.05)
        assert result.results[0].corrected_p_value == pytest.approx(0.03)
        assert result.results[0].significant_after_correction is True

    def test_zero_p_value_remains_zero(self) -> None:
        inputs = [
            CorrectionInput("a", "VALIDATED", 0.0),
            CorrectionInput("b", "VALIDATED", 0.5),
        ]
        result = holm_bonferroni(inputs, alpha=0.05)
        by_id = {r.claim_id: r for r in result.results}
        assert by_id["a"].corrected_p_value == 0.0  # 2 × 0 = 0
        assert by_id["a"].significant_after_correction is True

    def test_supported_methods_constant_matches_dispatcher(self) -> None:
        for method in SUPPORTED_METHODS:
            inputs = [CorrectionInput("a", "VALIDATED", 0.01)]
            apply_correction(inputs, method=method)
