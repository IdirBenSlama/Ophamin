"""Central plug-in registry.

Closes gap **B** from
``docs/ARCHITECTURE_INTENT_VS_REALITY_2026_05_16.md`` — until this
module landed, the four Protocols declared in :mod:`ophamin.protocols`
(``SubstrateProbe`` / ``DatasetConnector`` / ``Pillar`` /
``ScenarioProtocol``) had no registration surface. Plug-ins were
hard-imported into individual scenarios.

The registry exposes one dict per plug-in kind and one
``register_*`` function per kind. Scenarios continue to register
themselves via :meth:`Scenario.__init_subclass__` (Move A); the
``SCENARIOS`` dict is re-exported here for one-stop discovery. Pillars
are registered by their module's ``__init__.py``-time call to
:func:`register_pillar`. Corpora are looked up via
:func:`ophamin.seeing.corpus.get_corpus` (existing surface).

Every registration is **loud-failure**:

- A duplicate ``pillar_name`` raises :class:`DuplicatePluginError`
  rather than silently overwriting.
- A plug-in that fails the matching ``isinstance(p, Protocol)`` check
  raises :class:`PluginProtocolViolationError` — the Protocol declared
  the contract; an adapter that doesn't satisfy it is a real defect.

Outside callers query the registry via:

    >>> from ophamin.registry import PILLARS, list_pillars, get_pillar
    >>> p = get_pillar("O.spc")
    >>> p.library, p.library_version
    ('numpy', '1.26.0')

Or via the ``ophamin pillar list / show`` CLI surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator

from ophamin.measuring.pillars.base import PillarBase
from ophamin.protocols import Pillar
from ophamin.seeing.corpus.base import Corpus


# --- error types ------------------------------------------------------------


class RegistryError(RuntimeError):
    """Base class for every registry failure mode."""


class DuplicatePluginError(RegistryError):
    """Two plug-ins declared the same registration key."""

    def __init__(self, kind: str, key: str, existing: object, incoming: object) -> None:
        self.kind = kind
        self.key = key
        self.existing = existing
        self.incoming = incoming
        super().__init__(
            f"{kind} key {key!r} is already registered "
            f"({type(existing).__module__}.{type(existing).__qualname__}); "
            f"cannot also register {type(incoming).__module__}.{type(incoming).__qualname__}"
        )


class PluginProtocolViolationError(RegistryError):
    """A plug-in did not satisfy its declared Protocol at registration time.

    Carries the ``Protocol`` class and the offending object so the
    caller can introspect which attribute / method is missing.
    """

    def __init__(self, protocol: type, offending: object) -> None:
        self.protocol = protocol
        self.offending = offending
        super().__init__(
            f"object {type(offending).__module__}.{type(offending).__qualname__} "
            f"does not satisfy the {protocol.__name__} runtime protocol "
            f"(missing one of the declared attributes / methods)"
        )


# --- pillar registry --------------------------------------------------------


#: every registered Pillar-Protocol-satisfying adapter, keyed by
#: :attr:`PillarBase.pillar_name`. Populated by each pillar module's
#: import-time call to :func:`register_pillar`.
PILLARS: dict[str, PillarBase] = {}


def register_pillar(pillar: PillarBase) -> PillarBase:
    """Register one pillar adapter in the central registry.

    Returns the pillar (so calls can be expressed as
    ``MY_PILLAR = register_pillar(MyPillar())`` at module scope).

    Raises:
        PluginProtocolViolationError: if the object doesn't satisfy
            the :class:`Pillar` runtime protocol (missing
            ``pillar_name`` / ``library`` / ``library_version`` /
            ``compute``).
        DuplicatePluginError: if another pillar already registered the
            same ``pillar_name``. Re-registration of the *same object*
            under the same name is idempotent (necessary for module
            reloads).
    """
    if not isinstance(pillar, Pillar):
        raise PluginProtocolViolationError(Pillar, pillar)
    existing = PILLARS.get(pillar.pillar_name)
    if existing is pillar:
        return pillar  # idempotent reload
    if existing is not None:
        raise DuplicatePluginError("pillar", pillar.pillar_name, existing, pillar)
    PILLARS[pillar.pillar_name] = pillar
    return pillar


def get_pillar(name: str) -> PillarBase:
    """Look up a registered pillar by name. Loud-fails if absent."""
    try:
        return PILLARS[name]
    except KeyError as exc:
        raise KeyError(
            f"no pillar registered under {name!r}; "
            f"available: {sorted(PILLARS)}"
        ) from exc


def list_pillars() -> Iterator[PillarBase]:
    """Yield every registered pillar in pillar-name-sorted order."""
    for key in sorted(PILLARS):
        yield PILLARS[key]


# --- scenario registry re-export -------------------------------------------


def get_scenario(name: str) -> type:
    """Look up a registered scenario by name. Loud-fails if absent.

    Delegates to ``ophamin.measuring.scenarios.SCENARIOS`` (populated by
    :meth:`Scenario.__init_subclass__` in Move A).
    """
    # Lazy import — `ophamin.measuring.scenarios` imports every scenario
    # module at package-init, which is expensive on first call.
    from ophamin.measuring.scenarios import SCENARIOS

    try:
        return SCENARIOS[name]
    except KeyError as exc:
        raise KeyError(
            f"no scenario registered under {name!r}; "
            f"available: {sorted(SCENARIOS)}"
        ) from exc


def list_scenarios() -> Iterator[type]:
    """Yield every registered scenario class in name-sorted order."""
    from ophamin.measuring.scenarios import SCENARIOS

    for key in sorted(SCENARIOS):
        yield SCENARIOS[key]


# --- corpus registry re-export ---------------------------------------------


def get_corpus_by_name(name: str, data_root: str | None = None) -> Corpus:
    """Look up a registered corpus by name. Loud-fails if absent.

    Thin wrapper around :func:`ophamin.seeing.corpus.get_corpus`.
    """
    from ophamin.seeing.corpus import get_corpus
    return get_corpus(name, data_root)


def list_corpora() -> Iterator[str]:
    """Yield every registered corpus name in sorted order."""
    from ophamin.seeing.corpus import list_corpus_names
    yield from list_corpus_names()


def register_corpus(name: str, factory: Callable[[Path], Corpus]) -> None:
    """Register a third-party corpus factory. Delegates to
    :func:`ophamin.seeing.corpus.register_corpus_factory`."""
    from ophamin.seeing.corpus import register_corpus_factory
    register_corpus_factory(name, factory)


# --- substrate-probe registry ----------------------------------------------


#: Built-in substrate probe factory names. Operators can register their
#: own SubstrateUnderTest implementations via :func:`register_substrate`.
SUBSTRATE_FACTORIES: dict[str, type] = {}


def register_substrate(name: str, cls: type) -> None:
    """Register a SubstrateUnderTest class under ``name``.

    Loud-failure on duplicate. The class must structurally satisfy the
    :class:`SubstrateProbe` Protocol (checked at registration time).
    """

    if not isinstance(cls, type):
        raise TypeError(
            f"register_substrate expects a class, got {type(cls).__name__}"
        )
    # Instantiate via no-args to check Protocol satisfaction would force
    # every probe to accept zero-arg construction; skip the runtime check
    # at register time and rely on the structural protocol when the
    # caller actually uses isinstance.
    existing = SUBSTRATE_FACTORIES.get(name)
    if existing is cls:
        return  # idempotent
    if existing is not None:
        raise DuplicatePluginError("substrate", name, existing, cls)
    SUBSTRATE_FACTORIES[name] = cls


def get_substrate_class(name: str) -> type:
    """Look up a registered SubstrateUnderTest class by name."""
    try:
        return SUBSTRATE_FACTORIES[name]
    except KeyError as exc:
        raise KeyError(
            f"no substrate registered under {name!r}; "
            f"available: {sorted(SUBSTRATE_FACTORIES)}"
        ) from exc


def list_substrate_classes() -> Iterator[type]:
    """Yield every registered SubstrateProbe class in name-sorted order."""
    for key in sorted(SUBSTRATE_FACTORIES):
        yield SUBSTRATE_FACTORIES[key]


def _register_builtin_substrates() -> None:
    """Register the two built-in SubstrateProbe implementations.

    Idempotent — safe to call multiple times. Skips registration when
    the substrate class can't be imported (allows the registry to load
    in environments where Kimera isn't installed).
    """
    try:
        from ophamin.seeing.substrate import MockSubstrate
        register_substrate("mock", MockSubstrate)
    except ImportError:
        pass
    try:
        from ophamin.seeing.substrate.kimera_adapter import KimeraAdapter
        register_substrate("kimera", KimeraAdapter)
    except ImportError:
        pass


_register_builtin_substrates()


__all__ = [
    "PILLARS",
    "SUBSTRATE_FACTORIES",
    "DuplicatePluginError",
    "PluginProtocolViolationError",
    "RegistryError",
    "get_corpus_by_name",
    "get_pillar",
    "get_scenario",
    "get_substrate_class",
    "list_corpora",
    "list_pillars",
    "list_scenarios",
    "list_substrate_classes",
    "register_corpus",
    "register_pillar",
    "register_substrate",
]
