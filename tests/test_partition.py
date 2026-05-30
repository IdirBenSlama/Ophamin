"""Partition observation — the re-performable wire-unit, and how faithful the
substrate's current emission of it is.

A faithful partition (CLAUDE.md) = primes + Echoform operator sequence + Cronos
timestamp + GWF signature. These tests pin that Ophamin assembles it honestly from
the emission, marks the not-yet-emitted Echoform operator sequence as a gap (never
fabricated), and measures the gap as a faithfulness fraction — the Echoform-emission
spec's value made into a number.
"""

from ophamin.seeing.substrate.base import CycleResult
from ophamin.seeing.substrate.observables import partition, partition_faithfulness


def _cycle(raw, success=True):
    return CycleResult(cycle_index=0, success=success, raw=raw)


# What a healthy cycle emits TODAY: primes + state stamp + GWF verdict, NO echoform seq.
TODAY = {
    "prime_chain": ["2", "3", "5"],
    "substrate_state_stamp": 408021,
    "gwf_verdict": "cleared",
}


def test_partition_assembles_present_constituents():
    p = partition(_cycle(TODAY))
    assert p is not None
    assert p["primes"] == ("2", "3", "5")
    assert p["cronos_timestamp"] == 408021
    assert p["gwf_signature"] == "cleared"


def test_echoform_sequence_is_an_honest_gap_today():
    # The substrate emits echoform_event (a dict), NOT the operator sequence.
    p = partition(_cycle({**TODAY, "echoform_event": {"op": "fuse"}}))
    assert p["echoform_sequence"] is None  # a single event is NOT the ΔS sequence


def test_faithfulness_is_three_quarters_today():
    # The measured size of the gap the Echoform spec closes.
    assert partition_faithfulness(_cycle(TODAY)) == 0.75


def test_faithfulness_reaches_one_when_echoform_sequence_lands():
    full = {**TODAY, "echoform_sequence": [{"op": "fuse", "delta_s": 0.1}]}
    assert partition_faithfulness(_cycle(full)) == 1.0


def test_failed_cycle_is_a_gap_not_a_fabricated_partition():
    assert partition(_cycle(TODAY, success=False)) is None
    assert partition_faithfulness(_cycle(TODAY, success=False)) is None


def test_empty_emission_is_low_faithfulness_not_a_crash():
    f = partition_faithfulness(_cycle({}))
    assert f is not None and f <= 0.25
