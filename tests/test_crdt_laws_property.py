"""Property-based tests for CRDT-law primitives (Phase S6).

A YDoc-backed CRDT must satisfy three operational laws:

  1. **Convergence** — any two replicas that have applied the same set of
     operations (in any order, with any interleaving) must reach the same
     state.
  2. **Idempotence** — applying the same state-update bytes twice must
     leave the receiving replica unchanged.
  3. **Cross-backend agreement** — the two Yrs-Rust-backed Python bindings
     (pycrdt + y-py) must agree, because they share the same core CRDT.

Hypothesis generates the operation sequences; the YDocFacade is exercised
under each law.
"""

from __future__ import annotations

import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ophamin.comparing.crdt_state import (
    YDocFacade,
    cross_backend_convergence,
)


# Stay inside the ASCII printable range so we don't pull surrogate-pair
# pathologies into the CRDT — those are deferred to a separate stress
# campaign.
_SAFE_CHARS = string.ascii_letters + string.digits + " _-"
short_text = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=12)


@st.composite
def insert_ops_for_doc(draw: st.DrawFn, max_len: int = 60) -> list[tuple[str, int, str]]:
    """Build a sequence of (kind, position, value) insert ops with positions
    bounded to the running length so every op is valid (no out-of-range insert).
    """
    n = draw(st.integers(min_value=1, max_value=10))
    ops: list[tuple[str, int, str]] = []
    cur_len = 0
    for _ in range(n):
        value = draw(short_text)
        pos = draw(st.integers(min_value=0, max_value=min(cur_len, max_len)))
        ops.append(("insert", pos, value))
        cur_len = min(max_len, cur_len + len(value))
    return ops


# ----------------------------------------------------------------------------
# Cross-backend agreement (Yrs core)
# ----------------------------------------------------------------------------


@given(insert_ops_for_doc())
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_pycrdt_and_y_py_converge(ops: list[tuple[str, int, str]]) -> None:
    """pycrdt and y-py YDocs converge to byte-identical text for any insert sequence."""
    try:
        result = cross_backend_convergence(ops)
    except ImportError:
        pytest.skip("pycrdt and y-py both required for cross-backend check")
    assert result["agreed"], (
        f"pycrdt={result['pycrdt_text']!r} vs y-py={result['y_py_text']!r}"
    )


# ----------------------------------------------------------------------------
# Idempotence — applying the same state twice is a no-op
# ----------------------------------------------------------------------------


def _assert_idempotent(ops: list[tuple[str, int, str]], *, backend: str) -> None:
    try:
        sender = YDocFacade(backend=backend)
    except ImportError:
        pytest.skip(f"{backend} not installed")
    for _, pos, value in ops:
        sender.insert_text("main", pos, value)
    state = sender.encode_state()
    receiver = YDocFacade(backend=backend)
    receiver.apply_state(state)
    before = receiver.get_text("main")
    # Apply the SAME state again — CRDT semantics: idempotent.
    receiver.apply_state(state)
    after = receiver.get_text("main")
    assert before == after, (
        f"applying the same state twice changed the doc: {before!r} -> {after!r}"
    )


@given(insert_ops_for_doc())
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_pycrdt_apply_state_is_idempotent(ops: list[tuple[str, int, str]]) -> None:
    _assert_idempotent(ops, backend="pycrdt")


@given(insert_ops_for_doc())
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_y_py_apply_state_is_idempotent(ops: list[tuple[str, int, str]]) -> None:
    _assert_idempotent(ops, backend="y_py")


# ----------------------------------------------------------------------------
# Convergence — two replicas that exchanged states reach the same text
# ----------------------------------------------------------------------------


@st.composite
def two_op_streams(draw: st.DrawFn) -> tuple[list[tuple[str, int, str]],
                                              list[tuple[str, int, str]]]:
    """Two independent op streams — each replica applies its own."""
    a = draw(insert_ops_for_doc())
    b = draw(insert_ops_for_doc())
    return a, b


@given(two_op_streams())
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_pycrdt_two_replicas_converge_after_exchange(
    streams: tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]],
) -> None:
    """Two replicas with different ops, after exchanging states, agree on text."""
    a_ops, b_ops = streams
    try:
        alice = YDocFacade(backend="pycrdt")
        bob = YDocFacade(backend="pycrdt")
    except ImportError:
        pytest.skip("pycrdt not installed")
    for _, pos, value in a_ops:
        alice.insert_text("main", pos, value)
    for _, pos, value in b_ops:
        bob.insert_text("main", pos, value)
    # Exchange — each side applies the other's state.
    alice.apply_state(bob.encode_state())
    bob.apply_state(alice.encode_state())
    assert alice.get_text("main") == bob.get_text("main"), (
        f"replicas diverged: alice={alice.get_text('main')!r} "
        f"bob={bob.get_text('main')!r}"
    )


# ----------------------------------------------------------------------------
# Boundary cases
# ----------------------------------------------------------------------------


def test_empty_op_stream_produces_empty_text() -> None:
    try:
        doc = YDocFacade(backend="pycrdt")
    except ImportError:
        pytest.skip("pycrdt not installed")
    assert doc.get_text("main") == ""


def test_unknown_backend_raises() -> None:
    with pytest.raises(ValueError, match="backend must be"):
        YDocFacade(backend="redis")


def test_cross_backend_rejects_non_insert_op() -> None:
    try:
        with pytest.raises(ValueError, match="only 'insert' op"):
            cross_backend_convergence([("delete", 0, "x")])
    except ImportError:
        pytest.skip("pycrdt + y-py both required for cross-backend check")
