"""Property-based tests for drift-report value classes (Phase S6).

DeltaEntry and DriftReport have ``to_dict`` only (no ``from_dict``) — they
are *derived* artefacts built from a pair of proof records. The property
tests here pin the load-bearing invariants of the derivation:

  * ci_overlaps is commutative
  * a DeltaEntry's ``significant`` flag agrees with ``ci_overlap``
  * a DriftReport with non-overlapping CIs reports significant drift
  * verdict_changed reflects the before/after outcomes
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from ophamin.comparing.drift.delta_report import (
    DeltaEntry,
    DriftReport,
    ci_overlaps,
)


finite_floats = st.floats(
    allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6, width=64,
)
optional_floats = st.one_of(st.none(), finite_floats)
plain_strings = st.text(max_size=120)
identifier_strings = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())


@st.composite
def ci_pairs(draw: st.DrawFn) -> tuple[float | None, float | None]:
    """Generate (lo, hi) pairs with lo <= hi when both present."""
    a = draw(optional_floats)
    b = draw(optional_floats)
    if a is not None and b is not None:
        lo, hi = (a, b) if a <= b else (b, a)
        return (lo, hi)
    return (a, b)


@st.composite
def delta_entries(draw: st.DrawFn) -> DeltaEntry:
    before = draw(finite_floats)
    after = draw(finite_floats)
    ci_before = draw(ci_pairs())
    ci_after = draw(ci_pairs())
    overlap = ci_overlaps(ci_before, ci_after)
    return DeltaEntry(
        statistic_name=draw(identifier_strings),
        value_before=before,
        value_after=after,
        delta=after - before,
        ci_before=ci_before,
        ci_after=ci_after,
        ci_overlap=overlap,
        # the canonical builder sets significant = (overlap is False); when
        # overlap is None we treat it as non-significant (no information).
        significant=(overlap is False),
    )


@st.composite
def drift_reports(draw: st.DrawFn) -> DriftReport:
    return DriftReport(
        statistic_name=draw(identifier_strings),
        kimera_commit_before=draw(plain_strings),
        kimera_commit_after=draw(plain_strings),
        captured_at_before=draw(plain_strings),
        captured_at_after=draw(plain_strings),
        verdict_before=draw(st.sampled_from(["VALIDATED", "REFUTED", "INCONCLUSIVE"])),
        verdict_after=draw(st.sampled_from(["VALIDATED", "REFUTED", "INCONCLUSIVE"])),
        primary_delta=draw(delta_entries()),
        pillar_deltas=tuple(draw(st.lists(delta_entries(), max_size=4))),
    )


# ----------------------------------------------------------------------------
# Invariants
# ----------------------------------------------------------------------------


@given(ci_pairs(), ci_pairs())
@settings(max_examples=200, deadline=None)
def test_ci_overlaps_commutative(a: tuple[float | None, float | None],
                                 b: tuple[float | None, float | None]) -> None:
    """ci_overlaps(a, b) == ci_overlaps(b, a) for all CI pairs."""
    assert ci_overlaps(a, b) == ci_overlaps(b, a)


@given(ci_pairs())
@settings(max_examples=100, deadline=None)
def test_ci_overlaps_reflexive(a: tuple[float | None, float | None]) -> None:
    """A CI always overlaps itself (when both endpoints present)."""
    lo, hi = a
    if lo is None or hi is None:
        assert ci_overlaps(a, a) is None
    else:
        assert ci_overlaps(a, a) is True


@given(delta_entries())
@settings(max_examples=200, deadline=None)
def test_delta_entry_delta_consistent(d: DeltaEntry) -> None:
    """delta exactly equals (value_after - value_before)."""
    assert d.delta == d.value_after - d.value_before


@given(delta_entries())
@settings(max_examples=200, deadline=None)
def test_delta_entry_to_dict_shape(d: DeltaEntry) -> None:
    """to_dict surfaces every field with the expected key names + value types."""
    out = d.to_dict()
    assert out["statistic_name"] == d.statistic_name
    assert out["value_before"] == d.value_before
    assert out["value_after"] == d.value_after
    assert out["delta"] == d.delta
    # CIs are serialised as lists (JSON-compatible)
    assert out["ci_before"] == list(d.ci_before)
    assert out["ci_after"] == list(d.ci_after)
    assert out["ci_overlap"] == d.ci_overlap
    assert out["significant"] == d.significant


@given(delta_entries())
@settings(max_examples=200, deadline=None)
def test_delta_significance_matches_overlap(d: DeltaEntry) -> None:
    """significant is True only when ci_overlap is exactly False.

    None overlap (missing CI) → not significant (no information).
    """
    if d.significant:
        assert d.ci_overlap is False


@given(drift_reports())
@settings(max_examples=100, deadline=None)
def test_drift_report_verdict_changed_matches(r: DriftReport) -> None:
    assert r.verdict_changed() == (r.verdict_before != r.verdict_after)


@given(drift_reports())
@settings(max_examples=100, deadline=None)
def test_drift_report_has_significant_drift_matches_any(r: DriftReport) -> None:
    expected = r.primary_delta.significant or any(d.significant for d in r.pillar_deltas)
    assert r.has_significant_drift() == expected


@given(drift_reports())
@settings(max_examples=100, deadline=None)
def test_drift_report_to_dict_complete(r: DriftReport) -> None:
    out = r.to_dict()
    assert set(out.keys()) >= {
        "statistic_name",
        "kimera_commit_before",
        "kimera_commit_after",
        "captured_at_before",
        "captured_at_after",
        "verdict_before",
        "verdict_after",
        "verdict_changed",
        "has_significant_drift",
        "primary_delta",
        "pillar_deltas",
    }
    assert out["verdict_changed"] == r.verdict_changed()
    assert out["has_significant_drift"] == r.has_significant_drift()
    assert isinstance(out["pillar_deltas"], list)
    assert len(out["pillar_deltas"]) == len(r.pillar_deltas)


# ----------------------------------------------------------------------------
# Boundary cases — explicit examples that the property tests rely on
# ----------------------------------------------------------------------------


def test_ci_overlaps_returns_none_when_either_endpoint_missing() -> None:
    assert ci_overlaps((None, 1.0), (0.0, 2.0)) is None
    assert ci_overlaps((0.0, 1.0), (None, 2.0)) is None
    assert ci_overlaps((None, None), (0.0, 1.0)) is None


def test_ci_overlaps_disjoint_intervals_are_false() -> None:
    assert ci_overlaps((0.0, 1.0), (2.0, 3.0)) is False
    assert ci_overlaps((10.0, 20.0), (-5.0, -1.0)) is False


def test_ci_overlaps_touching_intervals_are_true() -> None:
    """Closed intervals — touching at a point counts as overlap."""
    assert ci_overlaps((0.0, 1.0), (1.0, 2.0)) is True


def test_ci_overlaps_nested_intervals_are_true() -> None:
    assert ci_overlaps((0.0, 10.0), (3.0, 7.0)) is True
    assert ci_overlaps((3.0, 7.0), (0.0, 10.0)) is True
