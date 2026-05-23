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

import math
import random
from collections import Counter
from typing import Any, Callable, Protocol, Sequence


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
    retriever_factory: Callable[[Sequence[str]], Retriever],
    docs: Sequence[str],
    query: str,
    *,
    seed: int = 0,
) -> dict[str, Any]:
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


def bag_representation_divergence(
    events_a: Sequence[str], events_b: Sequence[str],
) -> float:
    """Cosine distance between the mean TF-IDF vectors of two event orderings.

    A set-based representation pools its document vectors order-invariantly
    (sum/mean is commutative), so when ``events_a`` and ``events_b`` are the
    same multiset in different orders this is ~0 — the structural fact that a
    retriever cannot represent an order-dependent quantity. Demonstrated, not
    asserted: the scenario computes this on the real event sequences and shows
    the RAG side carries zero order-information.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    a_list, b_list = list(events_a), list(events_b)
    if not a_list or not b_list:
        return 0.0
    vec = TfidfVectorizer().fit(a_list + b_list)
    a = np.asarray(vec.transform(a_list).mean(axis=0)).ravel()
    b = np.asarray(vec.transform(b_list).mean(axis=0)).ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    cos = float(a @ b / (na * nb))
    return max(0.0, 1.0 - cos)


# ----------------------------------------------- order-BEARING comparators ----
#
# These exist to test, not assume, the claim that "retrieval conflates
# order-different histories". bag_representation_divergence is order-blind
# *because it mean-pools* (a representation choice), not because retrieval is
# inherently order-blind. The two functions below are standard retrieval
# representations that DO carry order; if they separate the same histories the
# mean-pool conflates, then the Kimera-vs-RAG "advantage" is an artifact of the
# representation/metric chosen for the baseline, not a capability gap.


def ordered_representation_divergence(
    events_a: Sequence[str], events_b: Sequence[str],
) -> float:
    """Cosine distance over an ORDER-BEARING shingle representation.

    Represents each history by unigram + consecutive-event **bigram** counts
    (shingling — a textbook IR technique). Bigrams encode local order, so
    reordering the same multiset changes the profile and the distance is > 0.
    Contrast with :func:`bag_representation_divergence` (mean-pooling →
    commutative → 0): order-blindness is a property of the *bag* representation,
    not of retrieval. Returns a cosine distance in ``[0, 1]``.
    """
    a_list = [str(e) for e in events_a]
    b_list = [str(e) for e in events_b]
    if not a_list or not b_list:
        return 0.0

    def _shingles(evs: list[str]) -> "Counter[tuple[str, ...]]":
        feats: Counter[tuple[str, ...]] = Counter()
        for e in evs:
            feats[("1", e)] += 1
        for x, y in zip(evs, evs[1:]):
            feats[("2", x, y)] += 1
        return feats

    a, b = _shingles(a_list), _shingles(b_list)
    keys = set(a) | set(b)
    dot = float(sum(a[k] * b[k] for k in keys))
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    # round away cosine float-epsilon so identical sequences read exactly 0.0
    return round(max(0.0, 1.0 - dot / (na * nb)), 12)


def event_set_jaccard_divergence(
    events_a: Sequence[str], events_b: Sequence[str],
) -> float:
    """``1 − Jaccard`` over the two event SETS — the *matched-metric* control.

    This is the SAME distance the finance scenario applies to Kimera's prime
    sets (``1 − Jaccard(prime_chain)``), applied to the retriever's own
    documents. When two orderings render to different (position, value) event
    strings, their sets are largely disjoint → distance ≈ 1.0. So a matched
    set comparison separates exactly the histories that mean-pooling reports as
    distance 0 — demonstrating the "RAG conflates them" result is a consequence
    of comparing Kimera and RAG with *different* metrics, not of retrieval.
    """
    a_set = {str(e) for e in events_a}
    b_set = {str(e) for e in events_b}
    if not a_set or not b_set:
        return 0.0
    union = len(a_set | b_set)
    return 1.0 - len(a_set & b_set) / union if union else 0.0


def graded_fidelity(distances: Sequence[float], targets: Sequence[float]) -> float:
    """Spearman rank-correlation between a representation's pairwise distances and
    a ground-truth GRADED quantity (e.g. |Δ max-drawdown| between two histories).

    This is the graded test the binary separation score missed: a genuine
    path-memory's distances should *scale* with how different the paths really
    are — not saturate at 1.0. Returns 0.0 on a degenerate input (constant /
    saturated distances, or constant targets), which is exactly how a binary
    order-detector scores here: its distances are all ~1.0, carry no graded
    signal, and so earn fidelity 0.
    """
    import numpy as np
    from scipy.stats import spearmanr

    d = np.asarray(list(distances), dtype=float)
    t = np.asarray(list(targets), dtype=float)
    if d.size < 3 or t.size != d.size:
        return 0.0
    if bool(np.allclose(d, d.flat[0])) or bool(np.allclose(t, t.flat[0])):
        return 0.0
    rho = spearmanr(d, t).correlation
    return 0.0 if (rho is None or bool(np.isnan(rho))) else float(rho)
