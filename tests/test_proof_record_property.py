"""Property-based round-trip tests for proof-record value classes (Phase S6).

Round-trip means: any value class V with a ``to_dict / from_dict`` pair satisfies
``V.from_dict(v.to_dict()) == v`` AND ``to_dict(to_dict(v).from_dict()) == to_dict(v)``.
The framework's signature verification rests on the second leg — every
``Threshold(value=10)`` must canonicalize identically whether constructed
directly or rebuilt from disk, otherwise HMAC verification breaks.

Hypothesis generates wide value coverage; failures shrink to minimal
counter-examples so any drift surfaces with the simplest possible reproducer.
"""

from __future__ import annotations


import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ophamin.measuring.proof.record import (
    Claim,
    PillarEvidence,
    Threshold,
    Verdict,
)

# ----------------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------------

# Finite floats — Threshold.value must be finite for downstream comparators.
finite_floats = st.floats(
    allow_nan=False,
    allow_infinity=False,
    min_value=-1e9,
    max_value=1e9,
    width=64,
)

comparators = st.sampled_from([">=", "<=", ">", "<", "=="])
outcomes = st.sampled_from(["VALIDATED", "REFUTED", "INCONCLUSIVE"])
cross_checks = st.sampled_from(["passed", "skipped", "n/a"])
identifier_strings = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())
plain_strings = st.text(max_size=120)


@st.composite
def thresholds(draw: st.DrawFn) -> Threshold:
    return Threshold(
        metric=draw(identifier_strings),
        comparator=draw(comparators),
        value=draw(finite_floats),
        units=draw(plain_strings),
    )


@st.composite
def claims(draw: st.DrawFn) -> Claim:
    return Claim(
        statement=draw(plain_strings),
        operationalization=draw(plain_strings),
        threshold=draw(thresholds()),
        h0=draw(plain_strings),
        h1=draw(plain_strings),
    )


optional_finite = st.one_of(st.none(), finite_floats)


@st.composite
def pillar_evidence(draw: st.DrawFn) -> PillarEvidence:
    return PillarEvidence(
        pillar=draw(identifier_strings),
        statistic_name=draw(identifier_strings),
        statistic_value=draw(finite_floats),
        library=draw(identifier_strings),
        library_version=draw(plain_strings),
        effect_size=draw(optional_finite),
        ci_low=draw(optional_finite),
        ci_high=draw(optional_finite),
        p_value=draw(optional_finite),
        cross_check=draw(cross_checks),
        detail=draw(st.dictionaries(identifier_strings, plain_strings, max_size=3)),
    )


@st.composite
def verdicts(draw: st.DrawFn) -> Verdict:
    return Verdict(
        outcome=draw(outcomes),
        observed_value=draw(finite_floats),
        threshold=draw(thresholds()),
        reasoning=draw(plain_strings),
    )


# ----------------------------------------------------------------------------
# Round-trip identity tests
# ----------------------------------------------------------------------------


@given(thresholds())
@settings(max_examples=200, deadline=None)
def test_threshold_roundtrip_dict(t: Threshold) -> None:
    """Threshold.from_dict(t.to_dict()) reproduces a Threshold whose to_dict matches."""
    rebuilt = Threshold.from_dict(t.to_dict())
    assert rebuilt.to_dict() == t.to_dict()
    # Comparator semantics survive too — both Thresholds must agree on every
    # decision they're asked to make.
    for probe in (t.value - 1.0, t.value, t.value + 1.0):
        assert rebuilt.decide(probe) == t.decide(probe)


@given(claims())
@settings(max_examples=200, deadline=None)
def test_claim_roundtrip_dict(c: Claim) -> None:
    rebuilt = Claim.from_dict(c.to_dict())
    assert rebuilt.to_dict() == c.to_dict()


@given(pillar_evidence())
@settings(max_examples=200, deadline=None)
def test_pillar_evidence_roundtrip_dict(p: PillarEvidence) -> None:
    rebuilt = PillarEvidence.from_dict(p.to_dict())
    assert rebuilt.to_dict() == p.to_dict()


@given(verdicts())
@settings(max_examples=200, deadline=None)
def test_verdict_roundtrip_dict(v: Verdict) -> None:
    rebuilt = Verdict.from_dict(v.to_dict())
    assert rebuilt.to_dict() == v.to_dict()


# ----------------------------------------------------------------------------
# Canonical-form invariance — the load-bearing property for signatures
# ----------------------------------------------------------------------------


@given(
    metric=identifier_strings,
    comparator=comparators,
    int_value=st.integers(min_value=-1_000_000, max_value=1_000_000),
)
@settings(max_examples=100, deadline=None)
def test_threshold_int_float_canonicalization(
    metric: str, comparator: str, int_value: int
) -> None:
    """Move L canonical form: Threshold(value=10) and Threshold(value=10.0)
    must produce IDENTICAL to_dict output — otherwise signature verification
    breaks silently on round-trip.
    """
    t_int = Threshold(metric=metric, comparator=comparator, value=int_value)  # type: ignore[arg-type]
    t_float = Threshold(metric=metric, comparator=comparator, value=float(int_value))
    assert t_int.to_dict() == t_float.to_dict()
    assert t_int.value == t_float.value
    assert isinstance(t_int.value, float)


@given(
    outcome=outcomes,
    int_observed=st.integers(min_value=-1_000_000, max_value=1_000_000),
    threshold=thresholds(),
    reasoning=plain_strings,
)
@settings(max_examples=100, deadline=None)
def test_verdict_observed_int_float_canonicalization(
    outcome: str,
    int_observed: int,
    threshold: Threshold,
    reasoning: str,
) -> None:
    """Same coercion property for Verdict.observed_value."""
    v_int = Verdict(
        outcome=outcome,
        observed_value=int_observed,  # type: ignore[arg-type]
        threshold=threshold,
        reasoning=reasoning,
    )
    v_float = Verdict(
        outcome=outcome,
        observed_value=float(int_observed),
        threshold=threshold,
        reasoning=reasoning,
    )
    assert v_int.to_dict() == v_float.to_dict()
    assert isinstance(v_int.observed_value, float)


# ----------------------------------------------------------------------------
# Threshold.decide — comparator semantics are total
# ----------------------------------------------------------------------------


@given(t=thresholds(), probe=finite_floats)
@settings(max_examples=200, deadline=None)
def test_threshold_decide_total(t: Threshold, probe: float) -> None:
    """decide() returns a bool for every comparator/value combo — no exceptions."""
    result = t.decide(probe)
    assert isinstance(result, bool)


# ----------------------------------------------------------------------------
# Verdict.decide — outcome respects comparator semantics
# ----------------------------------------------------------------------------


@given(t=thresholds(), observed=finite_floats)
@settings(max_examples=200, deadline=None)
def test_verdict_decide_matches_threshold(t: Threshold, observed: float) -> None:
    """Verdict.decide produces VALIDATED iff Threshold.decide is True."""
    v = Verdict.decide(observed, t)
    if t.decide(observed):
        assert v.outcome == "VALIDATED"
    else:
        assert v.outcome == "REFUTED"
    # observed_value normalized to float
    assert isinstance(v.observed_value, float)


@given(t=thresholds(), observed=finite_floats, reasoning=plain_strings)
@settings(max_examples=50, deadline=None)
def test_verdict_inconclusive_path(
    t: Threshold, observed: float, reasoning: str
) -> None:
    """The inconclusive shortcut on Verdict.decide returns INCONCLUSIVE regardless."""
    v = Verdict.decide(observed, t, inconclusive=True, reasoning=reasoning)
    assert v.outcome == "INCONCLUSIVE"
    if reasoning:
        assert v.reasoning == reasoning


# ----------------------------------------------------------------------------
# Boundary cases
# ----------------------------------------------------------------------------


def test_threshold_rejects_unknown_comparator() -> None:
    with pytest.raises(ValueError, match="comparator must be one of"):
        Threshold(metric="m", comparator="~=", value=0.0)


def test_verdict_rejects_unknown_outcome() -> None:
    threshold = Threshold(metric="m", comparator=">=", value=0.0)
    with pytest.raises(ValueError, match="outcome must be one of"):
        Verdict(
            outcome="MAYBE",
            observed_value=0.0,
            threshold=threshold,
            reasoning="",
        )


def test_threshold_value_is_float_after_construction() -> None:
    """Move L: int → float coercion happens in __post_init__."""
    t = Threshold(metric="m", comparator=">=", value=10)  # type: ignore[arg-type]
    assert isinstance(t.value, float)
    assert t.value == 10.0
    # to_dict produces a stable canonical form
    assert t.to_dict()["value"] == 10.0
