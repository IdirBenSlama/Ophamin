"""Tests for the massive-dataset corpus layer.

Exercised against the real downloaded datasets. A connector whose raw data is
not yet present is skipped (a download may still be in progress) rather than
failing — re-running once the data lands gives full coverage.
"""

import itertools

import pytest

from ophamin.seeing.corpus import (
    CorpusUnavailableError,
    EnronCorpus,
    TheWellCorpus,
    available_corpora,
    get_corpus,
)
from ophamin.seeing.corpus.base import CorpusRecord
from ophamin.measuring.proof import DatasetRef


def _first(corpus, n: int) -> list[CorpusRecord]:
    return list(itertools.islice(corpus.records(), n))


@pytest.mark.parametrize(
    "name", ["enron", "linux", "cyber", "flores", "financial", "the_well"]
)
def test_connector_streams_valid_records(name):
    corpus = get_corpus(name)
    if not corpus.is_available():
        pytest.skip(f"corpus '{name}' not downloaded yet")
    records = _first(corpus, 5)
    assert len(records) == 5
    for rec in records:
        assert isinstance(rec, CorpusRecord)
        assert rec.id
        assert isinstance(rec.text, str)
        assert rec.text.strip()  # real, non-empty content


def test_flores_full_contract():
    corpus = get_corpus("flores")
    if not corpus.is_available():
        pytest.skip("flores not downloaded")
    digest = corpus.content_hash()
    assert len(digest) == 64
    assert digest == corpus.content_hash()  # stable
    assert corpus.count() > 0

    rec = _first(corpus, 1)[0]
    assert rec.metadata["n_languages"] > 100  # FLORES-200
    assert "eng_Latn" in rec.metadata["translations"]

    ref = corpus.dataset_ref()
    assert isinstance(ref, DatasetRef)
    assert ref.content_hash == digest
    assert ref.n_records == corpus.count()

    assert len(corpus.sample(10, seed=1)) == 10
    batches = list(corpus.chunks(size=50, limit=120))
    assert sum(len(b) for b in batches) == 120


def test_linux_content_hash_and_count():
    corpus = get_corpus("linux")
    if not corpus.is_available():
        pytest.skip("linux kernel not downloaded")
    assert len(corpus.content_hash()) == 64
    assert corpus.count() > 1_000_000  # the kernel has ~1.4M commits
    rec = _first(corpus, 1)[0]
    assert "author" in rec.metadata


def test_offensive_security_corpus_aggregates_sota_sources():
    corpus = get_corpus("cyber")
    if not corpus.is_available():
        pytest.skip("offensive-security corpora not downloaded")
    # it aggregates multiple SOTA sources, transparently reporting which are present
    included = corpus.included_sources()
    assert "metasploit" in included
    assert len(included) >= 2  # SOTA sources beyond the original metasploit set
    records = _first(corpus, 20)
    assert all(r.metadata["origin"] == "offensive_security" for r in records)
    assert all(r.metadata.get("source") in included for r in records)
    # content hash is fast (git HEAD shas) and stable
    digest = corpus.content_hash()
    assert len(digest) == 64
    assert digest == corpus.content_hash()


def test_unavailable_corpus_raises_loudly(tmp_path):
    corpus = EnronCorpus(tmp_path / "empty")
    assert not corpus.is_available()
    with pytest.raises(CorpusUnavailableError):
        list(corpus.records())
    with pytest.raises(CorpusUnavailableError):
        corpus.content_hash()


def test_financial_corpus_aggregates_sources():
    corpus = get_corpus("financial")
    if not corpus.is_available():
        pytest.skip("financial corpora not downloaded")
    included = corpus.included_sources()
    assert "fred" in included or "phrasebank" in included
    records = _first(corpus, 10)
    assert len(records) == 10
    for rec in records:
        assert rec.metadata.get("source") in included
        assert rec.text.strip()
    digest = corpus.content_hash()
    assert len(digest) == 64
    assert digest == corpus.content_hash()


def test_the_well_corpus_streams_physics_records():
    """The Well connector streams lazy (trajectory, timestep) physics records and
    materialises field arrays on demand — physics never touches a text encoder."""
    corpus = get_corpus("the_well")
    if not corpus.is_available():
        pytest.skip("the-well corpus not downloaded / volume not mounted")
    datasets = corpus.included_datasets()
    assert datasets  # at least one physics dataset present
    records = _first(corpus, 5)
    assert len(records) == 5
    for rec in records:
        assert rec.id.startswith("the-well/")
        assert rec.text.strip()  # the descriptor label
        meta = rec.metadata
        assert meta["dataset"] in datasets
        assert meta["hdf5_path"].endswith(".hdf5")
        assert isinstance(meta["trajectory"], int)
        assert isinstance(meta["timestep"], int)
        assert meta["fields"]  # at least one physics-field spec

    # lazy materialisation — load_snapshot reads the real arrays for one record
    import numpy as np

    snapshot = TheWellCorpus.load_snapshot(records[0])
    assert snapshot
    for fname, arr in snapshot.items():
        assert isinstance(arr, np.ndarray)
        assert fname in records[0].metadata["fields"]

    # records_from targets a single named dataset
    one = list(itertools.islice(corpus.records_from(datasets[0]), 3))
    assert one and all(r.metadata["dataset"] == datasets[0] for r in one)


def test_get_corpus_rejects_unknown():
    with pytest.raises(ValueError):
        get_corpus("not-a-corpus")


def test_available_corpora_reports_status():
    status = available_corpora()
    assert set(status) == {
        "enron",
        "linux",
        "cyber",
        "flores",
        "financial",
        "the_well",
    }
    assert all(isinstance(v, bool) for v in status.values())
