"""Massive-dataset corpus layer — base abstraction.

A ``Corpus`` locates a downloaded open-source dataset on disk, content-addresses
it, counts its records, and streams them as ``CorpusRecord`` objects — so a
catastrophic-testing scenario can feed *real data* through the substrate in
concentrated batches.

The four connectors (``connectors.py``):

    EnronCorpus         ~500k real executive emails        — organisational dissonance
    LinuxKernelCorpus   ~1.4M commit messages              — logic / topology siege
    CyberPayloadCorpus  Metasploit modules + injection sets — concentrated immune siege
    FloresCorpus        FLORES-200, 200 parallel languages — Rosetta scaling limit

Content hashes and record counts are computed once and cached to disk
(``.ophamin_<name>_content_hash`` / ``_count``) so a 1.7 GB archive is not
re-hashed on every run.
"""

from __future__ import annotations

import abc
import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


class CorpusUnavailableError(RuntimeError):
    """Raised when a corpus's raw data has not been downloaded — loud, never silent."""


@dataclass
class CorpusRecord:
    """One item from a corpus — an email, a commit message, a payload, a sentence."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Corpus(abc.ABC):
    """A downloaded open-source dataset, content-addressed and streamable."""

    name: str = "corpus"
    kind: str = "corpus"
    source: str = ""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._cached_hash: str | None = None
        self._cached_count: int | None = None

    # -- per-connector contract --------------------------------------------

    @abc.abstractmethod
    def is_available(self) -> bool:
        """True iff the raw data is present on disk."""

    @abc.abstractmethod
    def records(self) -> Iterator[CorpusRecord]:
        """Stream every record. Must be a generator — corpora do not fit in memory."""

    @abc.abstractmethod
    def _compute_content_hash(self) -> str:
        """Deterministic content hash of the raw data (called once, then cached)."""

    @abc.abstractmethod
    def _compute_count(self) -> int:
        """Total record count (called once, then cached)."""

    # -- shared machinery --------------------------------------------------

    def require_available(self) -> None:
        if not self.is_available():
            raise CorpusUnavailableError(
                f"corpus '{self.name}' is not available at {self.root} — "
                f"download it first (source: {self.source})"
            )

    def content_hash(self) -> str:
        """Content-addressed hash of the corpus, cached in-memory and on disk."""
        if self._cached_hash is not None:
            return self._cached_hash
        cache_file = self.root / f".ophamin_{self.name}_content_hash"
        if cache_file.exists():
            self._cached_hash = cache_file.read_text(encoding="utf-8").strip()
            return self._cached_hash
        self.require_available()
        digest = self._compute_content_hash()
        try:
            cache_file.write_text(digest, encoding="utf-8")
        except OSError:
            pass
        self._cached_hash = digest
        return digest

    def count(self) -> int:
        """Total record count, cached in-memory and on disk."""
        if self._cached_count is not None:
            return self._cached_count
        cache_file = self.root / f".ophamin_{self.name}_count"
        if cache_file.exists():
            self._cached_count = int(cache_file.read_text(encoding="utf-8").strip())
            return self._cached_count
        self.require_available()
        n = self._compute_count()
        try:
            cache_file.write_text(str(n), encoding="utf-8")
        except OSError:
            pass
        self._cached_count = n
        return n

    def sample(self, n: int, seed: int = 0) -> list[CorpusRecord]:
        """A deterministic reservoir sample of ``n`` records (single streaming pass)."""
        if n < 1:
            raise ValueError("sample size must be >= 1")
        self.require_available()
        rng = random.Random(seed)
        reservoir: list[CorpusRecord] = []
        for i, record in enumerate(self.records()):
            if i < n:
                reservoir.append(record)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = record
        return reservoir

    def chunks(
        self, size: int, limit: int | None = None
    ) -> Iterator[list[CorpusRecord]]:
        """Yield records in batches of ``size`` — concentrated-batch density feeding.

        ``limit`` caps the total number of records emitted across all batches.
        """
        if size < 1:
            raise ValueError("chunk size must be >= 1")
        self.require_available()
        batch: list[CorpusRecord] = []
        emitted = 0
        for record in self.records():
            if limit is not None and emitted >= limit:
                break
            batch.append(record)
            emitted += 1
            if len(batch) >= size:
                yield batch
                batch = []
        if batch:
            yield batch

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def dataset_ref(self):
        """Produce the proof-record ``DatasetRef`` for this corpus."""
        from ophamin.proof import DatasetRef

        return DatasetRef(
            name=self.name,
            content_hash=self.content_hash(),
            n_records=self.count(),
            source=self.source,
            kind=self.kind,
        )

    def __repr__(self) -> str:
        state = "available" if self.is_available() else "NOT DOWNLOADED"
        return f"{type(self).__name__}(root={self.root}, {state})"
