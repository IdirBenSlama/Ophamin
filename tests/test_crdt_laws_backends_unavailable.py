"""crdt-laws must report INCONCLUSIVE (not REFUTED) when its Yjs backends are
unavailable.

This is the CI-only failure the substrate-free self-test hit: with pycrdt / y_py
absent, every op sequence threw at backend instantiation, so n_total stayed 0 and
the convergence rate defaulted to 0.0 → REFUTED. That is a *false* refutation —
"backends absent" is "not measurable here", not "the backends disagree 100% of
the time". This test forces the backends-absent path via monkeypatch (so it runs
regardless of whether the [crdt] extra is installed) and pins the honest verdict.
"""

from __future__ import annotations

import ophamin.comparing.crdt_state as crdt_state
from ophamin.measuring.scenarios.crdt_laws import CRDTLawsScenario


def test_crdt_laws_inconclusive_when_backends_unavailable(monkeypatch):
    class _UnavailableBackend:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Yjs backend unavailable in this environment")

    monkeypatch.setattr(crdt_state, "YDocFacade", _UnavailableBackend)

    record = CRDTLawsScenario(n_sequences=4, ops_per_sequence=3).run(substrate=None)

    assert record.verdict.outcome == "INCONCLUSIVE"
    assert record.verdict.outcome != "REFUTED"  # the false-refutation must not fire
