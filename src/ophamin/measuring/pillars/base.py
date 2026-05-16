"""Base class for Pillar-Protocol adapters.

Each existing pillar module under ``ophamin.measuring.pillars/*`` ships
domain-specific dataclasses + functions (SPC charts, SPRT solvers,
MixedLM wrappers, …). Those APIs are the canonical surface for
scenarios that want the rich per-pillar shape.

This module adds a thin **adapter** layer so the pillar count + library
attribution + a uniform discovery surface is reachable through the
registry that :mod:`ophamin.registry` exposes. Adapters subclass
:class:`PillarBase` and:

- declare ``pillar_name`` (e.g. ``"O.spc"``), ``library`` (the upstream
  package the pillar delegates to, e.g. ``"numpy"``), and
  ``library_version`` (resolved via :func:`importlib.metadata.version`
  at adapter construction);
- implement ``compute(cycle_results, records=None, **kwargs)`` —
  best-effort uniform entry point. Per-pillar compute signatures
  diverge (sequential testing vs cross-validation vs control charts
  are different shapes) so adapters MAY raise
  :class:`NonUniformComputeError` and point the caller at the
  module's own functions. The metadata fields (pillar_name + library +
  library_version) are the load-bearing promise; the compute() shape
  is convenience-only.

The :class:`Pillar` Protocol in :mod:`ophamin.protocols` is a
``runtime_checkable`` mirror — every :class:`PillarBase` instance
satisfies ``isinstance(instance, Pillar)`` by structural shape.
"""

from __future__ import annotations

import abc
from importlib import metadata as _metadata
from typing import Any, Iterable


def _pkg_version(name: str) -> str:
    """Resolve the installed version of ``name`` via importlib.metadata.

    Falls back to ``"unknown"`` if the package isn't installed under the
    given name (e.g. a transitive shipped under a different distribution
    name). Adapters can override ``library_version`` directly if they
    need the exact attribution string the upstream library exposes.
    """
    try:
        return _metadata.version(name)
    except _metadata.PackageNotFoundError:
        return "unknown"


class NonUniformComputeError(NotImplementedError):
    """Raised by an adapter whose pillar's compute shape doesn't fit
    the uniform ``compute(cycle_results, records)`` signature.

    The message includes a pointer to the module's actual API. This is
    NOT a silent fallback — it's the explicit acknowledgement that a
    given pillar's native interface is what the caller should use.
    """


class PillarBase(abc.ABC):
    """Abstract base for every :class:`Pillar`-Protocol-satisfying adapter.

    Class attributes the subclass must set (or override):

    - ``pillar_name`` — short OFAMIN-style identifier
      (e.g. ``"O.spc"`` / ``"M.mixed_effects"`` / ``"diagnostics.inertia"``).
    - ``library`` — the upstream library this pillar delegates to.
    - ``library_version`` — the upstream library's installed version.
      Subclasses typically populate this at class-body time via
      :func:`_pkg_version`.

    Instance method:

    - ``compute(cycle_results, records=None, **kwargs)`` — uniform
      entry point. Subclasses provide a best-effort implementation OR
      raise :class:`NonUniformComputeError` pointing at the module's
      canonical API.
    """

    pillar_name: str = ""
    library: str = ""
    library_version: str = ""

    @abc.abstractmethod
    def compute(
        self,
        cycle_results: Iterable[Any],
        records: Iterable[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Per-pillar best-effort compute. Override or raise
        :class:`NonUniformComputeError`."""

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} pillar_name={self.pillar_name!r} "
            f"library={self.library!r} version={self.library_version!r}>"
        )


__all__ = [
    "NonUniformComputeError",
    "PillarBase",
    "_pkg_version",
]
