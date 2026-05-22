"""Order-invariant retrieval baselines — the industry-standard "memory" Kimera
is contrasted against.

The memory-permanence proof established that Kimera's substrate is permanent and
path-dependent (a re-exposed, recognised probe lands on a strictly-deeper
manifold every time). The honest investor question is then: *how does that
differ from standard retrieval-augmented memory?* This module provides the fair
contrast.

The decisive structural fact: a standard retriever (TF-IDF, dense embeddings,
BM25, FAISS) is a pure function of the document **set** and the query — the
**order** in which documents were ingested does not change the index contents,
the vectors, or the cosine scores. So retrieval ranking is **order-invariant by
construction**. This is not a weakness we engineered into a strawman; it is the
defining property of set-based retrieval, and it is exactly the axis on which
Kimera's path-dependent (order-sensitive, hysteretic) memory either differs or
does not.

Two retrievers are provided so the contrast does not hinge on one method:

  * :class:`TfidfRetriever` — sklearn TF-IDF + cosine. Transparent, dependency-
    light, the classic IR baseline. A skeptic cannot say "you used a weak
    embedding" — the order-invariance is structural, not about embedding quality.
  * :class:`DenseRetriever` — sentence-transformers dense embeddings + cosine
    (the modern RAG default). Lazy-imported; raises (never silently degrades) if
    the model is unavailable, so a run either uses it for real or honestly says
    it did not.

Both expose ``rank(query) -> list[(doc_text, score)]``. The ranking is by doc
**identity**, so it can be compared across two retrievers built on the same docs
in different orders — :func:`order_divergence` does exactly that and returns 0.0
when the two rankings are identical (the expected, structural result).
"""

from __future__ import annotations

import random
from typing import Protocol, Sequence


class Retriever(Protocol):
    """A set-based retriever: built on docs, ranks them for a query."""

    def rank(self, query: str) -> list[tuple[str, float]]: ...


# --------------------------------------------------------------- TF-IDF ------


class TfidfRetriever:
    """TF-IDF + cosine retrieval. Order-invariant by construction."""

    def __init__(self, docs: Sequence[str]) -> None:
        if not docs:
            raise ValueError("TfidfRetriever needs at least one document")
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._docs = list(docs)
        self._vectorizer = TfidfVectorizer()
        self._matrix = self._vectorizer.fit_transform(self._docs)

    def rank(self, query: str) -> list[tuple[str, float]]:
        from sklearn.metrics.pairwise import cosine_similarity

        q = self._vectorizer.transform([query])
        sims = cosine_similarity(q, self._matrix)[0]
        order = sorted(range(len(self._docs)), key=lambda i: (-float(sims[i]), self._docs[i]))
        return [(self._docs[i], round(float(sims[i]), 8)) for i in order]


# ---------------------------------------------------------------- dense ------


class DenseRetriever:
    """Dense (sentence-transformers) + cosine. The modern RAG default.

    Lazy-imports the model; raises on unavailability rather than silently
    degrading — a run either uses dense retrieval for real or honestly records
    that it did not.
    """

    def __init__(self, docs: Sequence[str], model_name: str = "all-MiniLM-L6-v2") -> None:
        if not docs:
            raise ValueError("DenseRetriever needs at least one document")
        from sentence_transformers import SentenceTransformer

        self._docs = list(docs)
        self._model = SentenceTransformer(model_name)
        self._emb = self._model.encode(
            self._docs, normalize_embeddings=True, convert_to_numpy=True
        )

    def rank(self, query: str) -> list[tuple[str, float]]:
        qv = self._model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        sims = self._emb @ qv  # cosine (vectors are normalized)
        order = sorted(range(len(self._docs)), key=lambda i: (-float(sims[i]), self._docs[i]))
        return [(self._docs[i], round(float(sims[i]), 8)) for i in order]


# ------------------------------------------------------- order divergence ----


def ranking_signature(ranked: list[tuple[str, float]]) -> tuple[str, ...]:
    """The order-of-documents observable, by doc identity (text)."""
    return tuple(doc for doc, _ in ranked)


def order_divergence(
    retriever_factory,
    docs: Sequence[str],
    query: str,
    *,
    seed: int = 0,
) -> dict:
    """Build the retriever on ``docs`` and on a shuffled copy; rank the same
    query against both; return how much the ranking-by-doc-identity diverges.

    For any set-based retriever this is **0.0** — the structural fact the
    contrast rests on. Returned as a dict so the caller can record the two
    rankings as auditable evidence (not just the scalar).
    """
    docs = list(docs)
    shuffled = docs[:]
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    # guarantee a genuinely different order when possible
    if len(docs) > 1 and shuffled == docs:
        shuffled = list(reversed(docs))

    rank_a = retriever_factory(docs).rank(query)
    rank_b = retriever_factory(shuffled).rank(query)
    sig_a = ranking_signature(rank_a)
    sig_b = ranking_signature(rank_b)

    n = len(sig_a)
    disagreements = sum(1 for x, y in zip(sig_a, sig_b) if x != y)
    divergence = disagreements / n if n else 0.0
    # top-1 stability is what most RAG pipelines actually consume
    top1_changed = bool(sig_a and sig_b and sig_a[0] != sig_b[0])
    return {
        "order_divergence": divergence,
        "top1_changed": top1_changed,
        "n_docs": n,
        "ranking_order_a": list(sig_a),
        "ranking_order_b": list(sig_b),
        "identical": sig_a == sig_b,
    }
