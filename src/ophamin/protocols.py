"""The plug-in surfaces of the Ophamin observatory.

Ophamin is built to accept plug-in datasets, plug-in substrate probes, plug-in
analytic pillars, and plug-in scenarios. This module declares the protocols
each plug-in must satisfy. A new plug-in implements the protocol; nothing
inside Ophamin's core has to change.

The protocols are intentionally narrow — each one names a single contract:

    SubstrateProbe   the thing being observed (e.g. KimeraAdapter, MockSubstrate)
    DatasetConnector a corpus the observatory feeds the substrate from
    Pillar           a library-backed analytic that turns cycle results into
                     PillarEvidence (one statistical method per pillar)
    ScenarioProtocol a corpus + target + pre-registered claim runner

A protocol is `Protocol`-typed and `runtime_checkable` so callers can verify
plug-ins at registration time (``isinstance(plugin, Pillar)``) without
inheritance.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator, Protocol, runtime_checkable


# --------------------------------------------------------------------------
# SubstrateProbe — the thing being observed
# --------------------------------------------------------------------------


@runtime_checkable
class SubstrateProbe(Protocol):
    """A substrate-under-test the observatory can drive.

    Any concrete substrate (Kimera, mock, future substrates) implements this
    contract. The existing ``ophamin.seeing.substrate.base.SubstrateUnderTest``
    abstract class is the canonical example.
    """

    name: str

    def reset(self) -> None: ...

    def run_cycle(self, stimulus: Any, params: dict[str, Any] | None = ...) -> Any: ...

    def run_batch(
        self, stimuli: list[Any], params: dict[str, Any] | None = ...
    ) -> list[Any]: ...

    def git_commit(self) -> str: ...


# --------------------------------------------------------------------------
# DatasetConnector — plug-in datasets
# --------------------------------------------------------------------------


@runtime_checkable
class DatasetConnector(Protocol):
    """A corpus the observatory can stream records from.

    The existing ``ophamin.seeing.corpus.base.Corpus`` abstract class is the
    canonical example. Each corpus is content-addressable (its content hash
    appears in every signed proof record).
    """

    name: str
    kind: str
    source: str

    def is_available(self) -> bool: ...

    def records(self) -> Iterator[Any]: ...

    def content_hash(self) -> str: ...

    def count(self) -> int: ...


# --------------------------------------------------------------------------
# Pillar — a library-backed analytic plug-in
# --------------------------------------------------------------------------


@runtime_checkable
class Pillar(Protocol):
    """One analytic pillar — a statistical method that turns observations into
    PillarEvidence.

    A Pillar declares its name + the library it delegates to (library +
    version go into every signed proof record). Different pillars implement
    different statistical methods: SPC, SPRT, mixed-effects, etc.

    The current six pillars (O / F / A / M / I / N) live under
    ``ophamin.measuring.pillars/*``; this protocol describes the contract a
    new pillar must satisfy to be registrable.

    As of Move G (2026-05-16) eleven adapter classes in
    ``ophamin.measuring.pillars._adapters`` satisfy this Protocol and
    register themselves with :data:`ophamin.registry.PILLARS` at module
    import time. Out-of-tree pillars register the same way:
    construct an instance of a :class:`PillarBase` subclass and call
    :func:`ophamin.registry.register_pillar`. Per-pillar ``compute``
    signatures diverge (sequential testing vs control charts vs
    cross-validation are different shapes); the Protocol is metadata-
    backed-by-compute — adapters whose pillar doesn't fit the uniform
    ``compute(cycle_results, records)`` shape raise
    :class:`ophamin.measuring.pillars.base.NonUniformComputeError`
    with a pointer to the canonical per-pillar API.
    """

    pillar_name: str
    library: str
    library_version: str

    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = ...,
        **kwargs: Any,
    ) -> Any: ...


# --------------------------------------------------------------------------
# ScenarioProtocol — corpus + target + pre-registered claim
# --------------------------------------------------------------------------


@runtime_checkable
class ScenarioProtocol(Protocol):
    """A scenario binds a corpus + target + pre-registered claim and produces
    a signed Empirical Proof Record.

    The existing ``ophamin.measuring.scenarios.base.Scenario`` abstract class
    is the canonical implementation. As of 2026-05-16 the framework ships
    nineteen scenarios across five tiers (Scientific / Engineering /
    Philosophical / Empirical-deep / Measurement-machinery); see the
    README scenarios table for the full list.

    The pre-registration discipline is preserved across plug-ins: every
    ScenarioProtocol implementation must produce a claim whose threshold is
    *falsifiable* (a value the substrate could fail to meet), before the run.

    .. note::

       Eleven of the nineteen scenarios are not currently registered in
       ``ophamin.measuring.scenarios.__init__.SCENARIOS``, which means
       they are reachable from Python imports but not from the
       ``ophamin scenario <name>`` CLI surface. See
       ``docs/ARCHITECTURE_INTENT_VS_REALITY_2026_05_16.md`` for the gap.
    """

    name: str
    corpus_name: str
    target: str
    n_cycles: int

    def build_claim(self) -> Any: ...

    def score(self, cycle_results: list[Any], records: list[Any]) -> Any: ...

    def run(
        self, substrate: SubstrateProbe, *, data_root: Any = ..., sign_key: bytes = ...
    ) -> Any: ...


__all__ = [
    "DatasetConnector",
    "Pillar",
    "ScenarioProtocol",
    "SubstrateProbe",
]
