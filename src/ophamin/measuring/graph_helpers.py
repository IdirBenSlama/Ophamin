"""Graph-analysis helpers — python-igraph wrappers.

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §18. NetworkX is fine for small
graphs but ~30× slower than python-igraph at scale; for Kimera's
SCAR network (1M+ scars potential) igraph is the right tool.

Three small wrappers exposing the highest-signal graph metrics:

  pagerank_top_k(edges, k)         — top-k PageRank nodes
  community_detection(edges)       — Louvain modularity-based clustering
  betweenness_centrality(edges)    — bottleneck-detection (slow on large graphs)
"""

from __future__ import annotations

from typing import Any


def pagerank_top_k(
    edges: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...],
    *,
    k: int = 10,
    directed: bool = True,
    damping: float = 0.85,
) -> list[tuple[Any, float]]:
    """Top-k nodes by PageRank.

    ``edges``: list of ``(source, target)`` tuples. Node IDs can be any
    hashable; igraph builds the integer index internally.

    Returns ``[(node_id, pagerank_score), ...]`` sorted descending,
    truncated to k.
    """
    try:
        import igraph as ig
    except ImportError as e:
        raise ImportError(
            "python-igraph required; `pip install python-igraph`"
        ) from e
    if not edges:
        raise ValueError("edges must be non-empty")
    g = ig.Graph.TupleList(
        list(edges), directed=directed, vertex_name_attr="name",
    )
    scores = g.pagerank(damping=damping, directed=directed)
    indexed = sorted(enumerate(scores), key=lambda x: -x[1])
    out: list[tuple[Any, float]] = []
    for vidx, score in indexed[:k]:
        out.append((g.vs[vidx]["name"], float(score)))
    return out


def community_detection(
    edges: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...],
    *,
    method: str = "louvain",
) -> dict[str, Any]:
    """Community detection via igraph.

    ``method`` choices: ``"louvain"`` (default), ``"leiden"``,
    ``"label_propagation"``, ``"infomap"``.

    Returns ``{"communities": [[node_ids], ...], "n_communities": int,
              "modularity": float, "method": str}``.
    """
    try:
        import igraph as ig
    except ImportError as e:
        raise ImportError(
            "python-igraph required; `pip install python-igraph`"
        ) from e
    if not edges:
        raise ValueError("edges must be non-empty")
    g = ig.Graph.TupleList(
        list(edges), directed=False, vertex_name_attr="name",
    )
    method_norm = method.strip().lower()
    if method_norm == "louvain":
        clusters = g.community_multilevel()
    elif method_norm == "leiden":
        clusters = g.community_leiden(objective_function="modularity")
    elif method_norm == "label_propagation":
        clusters = g.community_label_propagation()
    elif method_norm == "infomap":
        clusters = g.community_infomap()
    else:
        raise ValueError(
            f"unknown method {method!r}; available: "
            f"louvain|leiden|label_propagation|infomap"
        )
    communities = [
        [g.vs[v]["name"] for v in cluster]
        for cluster in clusters
    ]
    return {
        "communities": communities,
        "n_communities": len(communities),
        "modularity": float(clusters.modularity) if clusters.modularity is not None else 0.0,
        "method": method_norm,
    }


def betweenness_top_k(
    edges: list[tuple[Any, Any]] | tuple[tuple[Any, Any], ...],
    *,
    k: int = 10,
    directed: bool = False,
) -> list[tuple[Any, float]]:
    """Top-k nodes by betweenness centrality (bottleneck identification).

    Slow for large graphs (O(V·E)). Use sparingly; for Kimera's SCAR
    network at scale, prefer pagerank_top_k or community_detection.

    Returns ``[(node_id, betweenness_score), ...]`` sorted descending.
    """
    try:
        import igraph as ig
    except ImportError as e:
        raise ImportError(
            "python-igraph required; `pip install python-igraph`"
        ) from e
    if not edges:
        raise ValueError("edges must be non-empty")
    g = ig.Graph.TupleList(
        list(edges), directed=directed, vertex_name_attr="name",
    )
    scores = g.betweenness(directed=directed)
    indexed = sorted(enumerate(scores), key=lambda x: -x[1])
    return [
        (g.vs[vidx]["name"], float(score))
        for vidx, score in indexed[:k]
    ]
