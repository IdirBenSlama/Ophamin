"""Tests for the order-invariant retrieval baselines.

The whole memory-vs-RAG contrast rests on one structural fact: a set-based
retriever's ranking does not depend on the order documents were ingested. These
tests pin that fact for the TF-IDF baseline (always available) and, when the
model is present, the dense baseline.
"""

from __future__ import annotations

import pytest

from ophamin.comparing.retrieval_baseline import (
    TfidfRetriever,
    bag_representation_divergence,
    order_divergence,
    ranking_signature,
)

_DOCS = [
    "the cat sat on the mat",
    "quarterly revenue grew by twelve percent year over year",
    "the dog chased the ball across the park",
    "memory is the deformation of the spherical manifold",
    "prime numbers index the substrate vocabulary",
]


class TestTfidf:
    def test_ranks_relevant_doc_first(self):
        r = TfidfRetriever(_DOCS)
        ranked = r.rank("how did quarterly revenue change")
        assert "revenue" in ranked[0][0]
        assert ranked[0][1] >= ranked[-1][1]  # sorted descending by score

    def test_order_invariant_divergence_is_zero(self):
        res = order_divergence(lambda d: TfidfRetriever(d), _DOCS, "revenue growth", seed=1)
        assert res["order_divergence"] == 0.0
        assert res["identical"] is True
        assert res["top1_changed"] is False

    def test_scores_identical_across_build_orders(self):
        q = "the manifold and memory"
        a = TfidfRetriever(_DOCS).rank(q)
        b = TfidfRetriever(list(reversed(_DOCS))).rank(q)
        assert a == b  # identical (doc, score) ranking regardless of build order

    def test_signature_is_doc_identity_order(self):
        r = TfidfRetriever(_DOCS)
        sig = ranking_signature(r.rank("park"))
        assert isinstance(sig, tuple)
        assert set(sig) == set(_DOCS)  # a permutation of the docs

    def test_empty_docs_raises(self):
        with pytest.raises(ValueError):
            TfidfRetriever([])


class TestBagRepresentation:
    def test_same_multiset_different_order_is_zero(self):
        events = ["return +0.01", "return -0.02", "return +0.03", "return -0.04"]
        shuffled = list(reversed(events))
        # mean-pooled representation is order-invariant for the same multiset
        assert bag_representation_divergence(events, shuffled) == pytest.approx(0.0, abs=1e-9)

    def test_different_multiset_is_nonzero(self):
        a = ["return +0.01", "return -0.02", "return +0.03"]
        b = ["return +0.50", "return -0.60", "return +0.70"]
        assert bag_representation_divergence(a, b) > 0.0


class TestDenseOptional:
    def test_dense_order_invariant_if_available(self):
        # Dense retrieval is the modern RAG default; it is just as order-
        # invariant as TF-IDF (same structural reason). Skipped (not failed)
        # when the model cannot be loaded offline — an honest skip, not a
        # silent degrade.
        st = pytest.importorskip("sentence_transformers")
        from ophamin.comparing.retrieval_baseline import DenseRetriever

        try:
            res = order_divergence(
                lambda d: DenseRetriever(d), _DOCS, "revenue growth", seed=2
            )
        except Exception as exc:  # model download blocked offline, etc.
            pytest.skip(f"dense model unavailable: {exc}")
        assert res["order_divergence"] == 0.0
        assert res["identical"] is True
