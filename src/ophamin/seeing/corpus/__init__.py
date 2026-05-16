"""Massive-dataset corpus layer.

Real open-source datasets, content-addressed and streamable, for feeding the
substrate under test in concentrated batches.

    get_corpus("enron")   EnronCorpus         organisational dissonance
    get_corpus("linux")   LinuxKernelCorpus   logic / topology siege
    get_corpus("cyber")   CyberPayloadCorpus  concentrated immune siege
    get_corpus("flores")  FloresCorpus        Rosetta scaling limit

Each corpus reports ``is_available()`` — the raw data must be downloaded first;
operations on a missing corpus raise ``CorpusUnavailableError`` (loud, never
silent).
"""

from __future__ import annotations

import os
from pathlib import Path

from ophamin.seeing.corpus.base import Corpus, CorpusRecord, CorpusUnavailableError
from ophamin.seeing.corpus.connectors import (
    EnronCorpus,
    FinancialCorpus,
    FloresCorpus,
    LinuxKernelCorpus,
    OffensiveSecurityCorpus,
    TheWellCorpus,
)

#: default location of the downloaded raw datasets (<project>/data/raw).
#: Path is anchored on the package root rather than directory-depth so the
#: three-ring reorg (corpus moved from ophamin/corpus to ophamin/seeing/corpus)
#: doesn't break the path resolution. ``parents[4]`` walks:
#:   __init__.py -> corpus/ -> seeing/ -> ophamin/ -> src/ -> <project_root>
DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[4] / "data" / "raw"

#: The Well + the wider foreign corpus live on a separate volume (tens of GB of
#: physics HDF5, not text downloads). Overridable via OPHAMIN_FOREIGN_CORPUS_ROOT.
FOREIGN_CORPUS_ROOT = Path(
    os.environ.get("OPHAMIN_FOREIGN_CORPUS_ROOT", "/Volumes/Kaido/Foreign_Corpus")
)

#: Public registry of corpus factories — Move N (2026-05-16). Maps each
#: corpus name to a callable ``factory(data_root: Path) -> Corpus``. Third-
#: party corpora register via :func:`register_corpus_factory` (declared
#: below) — the same pattern :func:`ophamin.registry.register_pillar`
#: uses for the Pillar Protocol.
CORPUS_FACTORIES: dict[str, "_CorpusFactory"] = {
    "enron": lambda root: EnronCorpus(root / "enron"),
    "linux": lambda root: LinuxKernelCorpus(root / "linux"),
    "cyber": lambda root: OffensiveSecurityCorpus(root),
    "flores": lambda root: FloresCorpus(root / "flores"),
    "financial": lambda root: FinancialCorpus(root / "financial"),
    # the_well lives on the foreign-corpus volume, not under data_root — the
    # lambda's `root` arg is intentionally unused for this one corpus
    "the_well": lambda root: TheWellCorpus(FOREIGN_CORPUS_ROOT / "the_well"),
}

# Backward-compat alias for callers that imported the private name.
_REGISTRY = CORPUS_FACTORIES

# Type alias for clarity in the registration helper.
from typing import Callable as _Callable  # noqa: E402

_CorpusFactory = _Callable[[Path], Corpus]


def register_corpus_factory(name: str, factory: _CorpusFactory) -> None:
    """Register a third-party corpus factory under ``name``.

    Loud-failure on duplicate registration — mirrors the Pillar
    Protocol's :func:`ophamin.registry.register_pillar` shape.
    Re-registering the same factory (identity) is idempotent.
    """
    existing = CORPUS_FACTORIES.get(name)
    if existing is factory:
        return  # idempotent
    if existing is not None:
        raise ValueError(
            f"corpus {name!r} is already registered; cannot register a "
            f"different factory under the same name"
        )
    CORPUS_FACTORIES[name] = factory


def list_corpus_names() -> tuple[str, ...]:
    """Return every registered corpus name in sorted order."""
    return tuple(sorted(CORPUS_FACTORIES))


def get_corpus(name: str, data_root: str | Path | None = None) -> Corpus:
    """Construct a corpus connector by name (``enron`` / ``linux`` / ``cyber`` / ``flores``)."""
    if name not in CORPUS_FACTORIES:
        raise ValueError(
            f"unknown corpus {name!r}; choose from {sorted(CORPUS_FACTORIES)}"
        )
    root = Path(data_root) if data_root is not None else DEFAULT_DATA_ROOT
    return CORPUS_FACTORIES[name](root)


def available_corpora(data_root: str | Path | None = None) -> dict[str, bool]:
    """Map every registered corpus name to whether its raw data is downloaded."""
    return {name: get_corpus(name, data_root).is_available() for name in CORPUS_FACTORIES}


__all__ = [
    "Corpus",
    "CorpusRecord",
    "CorpusUnavailableError",
    "CORPUS_FACTORIES",
    "EnronCorpus",
    "LinuxKernelCorpus",
    "OffensiveSecurityCorpus",
    "FloresCorpus",
    "FinancialCorpus",
    "TheWellCorpus",
    "get_corpus",
    "available_corpora",
    "list_corpus_names",
    "register_corpus_factory",
    "DEFAULT_DATA_ROOT",
    "FOREIGN_CORPUS_ROOT",
]
