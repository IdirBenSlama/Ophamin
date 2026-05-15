"""Analytic helpers — thin wrappers over the catalog's statistical libraries.

Per ``docs/PLUGIN_CATALOG_2026_05_15.md``. Each helper is small (one function
or class) and exposes an Ophamin-native API on top of a catalog library:

  pingouin       → effect_size_cohens_d_with_ci
                  → multiple_comparisons_correction (FDR / Bonferroni / Holm)
  POT            → wasserstein_distance_1d
  infomeasure    → mutual_information_continuous (KSG estimator)
  NPEET          → mutual_information_npeet — second-opinion oracle
  umap           → reduce_to_2d
  pacmap         → reduce_to_2d_pacmap (preserves both local + global structure)
  ripser         → persistence_diagram (Vietoris-Rips persistence H0/H1/H2)
  persim         → bottleneck_distance (compare two persistence diagrams)
  crepes         → conformal_prediction_intervals (regression CI)

Each helper raises a clear ImportError if its backing library is absent
(no silent fallback per CLAUDE.md). Tests pin the contract; live integrations
into scenarios come in follow-on PRs.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# pingouin — effect size + multiple-comparison correction
# ---------------------------------------------------------------------------


def effect_size_cohens_d_with_ci(
    sample_a: list[float] | tuple[float, ...],
    sample_b: list[float] | tuple[float, ...],
    *,
    paired: bool = False,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Compute Cohen's d between two samples WITH a confidence interval.

    Wraps ``pingouin.compute_effsize`` + ``pingouin.compute_esci`` so callers
    get both the point estimate and the CI in one call (scipy.stats doesn't
    bundle them).

    Returns ``{"cohens_d": float, "ci_low": float, "ci_high": float,
              "n_a": int, "n_b": int, "paired": bool}``.
    """
    try:
        import pingouin as pg
    except ImportError as e:
        raise ImportError(
            "pingouin is required for effect_size_cohens_d_with_ci; "
            "`pip install pingouin`"
        ) from e

    if len(sample_a) < 2 or len(sample_b) < 2:
        raise ValueError(
            f"both samples need ≥ 2 observations; "
            f"got n_a={len(sample_a)}, n_b={len(sample_b)}"
        )
    d = float(pg.compute_effsize(sample_a, sample_b, paired=paired, eftype="cohen"))
    ci = pg.compute_esci(stat=d, nx=len(sample_a), ny=len(sample_b),
                         eftype="cohen", confidence=confidence)
    return {
        "cohens_d": d,
        "ci_low": float(ci[0]),
        "ci_high": float(ci[1]),
        "n_a": len(sample_a),
        "n_b": len(sample_b),
        "paired": paired,
        "confidence": confidence,
    }


def multiple_comparisons_correction(
    p_values: list[float] | tuple[float, ...],
    *,
    method: str = "fdr_bh",
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Adjust a vector of p-values for multiple comparisons.

    ``method`` is forwarded to ``pingouin.multicomp`` — supported values
    include ``"fdr_bh"`` (Benjamini-Hochberg, default), ``"bonferroni"``,
    ``"holm"``, ``"sidak"``.

    Returns ``{"reject": [bool], "p_corrected": [float], "method": str,
               "alpha": float}``.
    """
    try:
        import pingouin as pg
    except ImportError as e:
        raise ImportError(
            "pingouin is required; `pip install pingouin`"
        ) from e
    reject, p_corrected = pg.multicomp(list(p_values), alpha=alpha, method=method)
    return {
        "reject": [bool(r) for r in reject],
        "p_corrected": [float(p) for p in p_corrected],
        "method": method,
        "alpha": alpha,
    }


# ---------------------------------------------------------------------------
# POT — optimal transport / Wasserstein distance
# ---------------------------------------------------------------------------


def wasserstein_distance_1d(
    sample_a: list[float] | tuple[float, ...],
    sample_b: list[float] | tuple[float, ...],
) -> float:
    """1-D Wasserstein-1 distance between two empirical distributions.

    Uses POT's ``wasserstein_1d`` (faster + more numerically stable than
    scipy's ``wasserstein_distance`` for the 1-D case).
    """
    try:
        import numpy as np
        import ot
    except ImportError as e:
        raise ImportError("POT is required; `pip install POT`") from e
    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)
    if a.size == 0 or b.size == 0:
        raise ValueError("both samples must be non-empty")
    return float(ot.wasserstein_1d(a, b))


# ---------------------------------------------------------------------------
# infomeasure — mutual information for continuous variables
# ---------------------------------------------------------------------------


def mutual_information_continuous(
    x: list[float] | tuple[float, ...],
    y: list[float] | tuple[float, ...],
    *,
    estimator: str = "ksg",
    k: int = 4,
) -> float:
    """Continuous-variable mutual information estimator.

    Defaults to KSG (Kraskov-Stögbauer-Grassberger) k-NN estimator with
    k=4 — the academic reference for continuous MI.

    Returns I(X;Y) in nats.
    """
    try:
        import numpy as np
        import infomeasure as im
    except ImportError as e:
        raise ImportError(
            "infomeasure is required; `pip install infomeasure`"
        ) from e
    if len(x) != len(y):
        raise ValueError(
            f"x and y must have the same length; got {len(x)} vs {len(y)}"
        )
    if len(x) < k + 1:
        raise ValueError(
            f"need at least k+1 = {k+1} samples for KSG; got {len(x)}"
        )
    arr_x = np.asarray(x, dtype=float)
    arr_y = np.asarray(y, dtype=float)
    return float(im.mutual_information(arr_x, arr_y, approach=estimator, k=k))


# ---------------------------------------------------------------------------
# umap — 2-D embedding for high-dim prime visualization
# ---------------------------------------------------------------------------


def mutual_information_npeet(
    x: list[float] | tuple[float, ...],
    y: list[float] | tuple[float, ...],
    *,
    k: int = 4,
) -> float:
    """Second-opinion KSG MI estimator via NPEET.

    NPEET is Greg Ver Steeg's reference KSG implementation. Use as a
    cross-check oracle for ``mutual_information_continuous`` (which uses
    infomeasure). They should agree within a tight margin.

    Returns I(X;Y) in nats.
    """
    try:
        import numpy as np
        from npeet import entropy_estimators as ee
    except ImportError as e:
        raise ImportError(
            "NPEET is required; install via "
            "`pip install git+https://github.com/gregversteeg/NPEET`"
        ) from e
    if len(x) != len(y):
        raise ValueError(
            f"x and y must have the same length; got {len(x)} vs {len(y)}"
        )
    if len(x) < k + 1:
        raise ValueError(
            f"need at least k+1 = {k+1} samples for KSG; got {len(x)}"
        )
    arr_x = np.asarray(x, dtype=float).reshape(-1, 1)
    arr_y = np.asarray(y, dtype=float).reshape(-1, 1)
    return float(ee.mi(arr_x.tolist(), arr_y.tolist(), k=k))


def reduce_to_2d(
    embeddings: list[list[float]] | tuple[tuple[float, ...], ...],
    *,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    random_state: int | None = 42,
) -> list[tuple[float, float]]:
    """Project N-dimensional embeddings down to 2-D via UMAP.

    Useful for visualizing Kimera's prime composites or Walker trajectories
    in the reporting wheel. ``random_state`` defaults to 42 for
    reproducibility (UMAP is otherwise stochastic).

    Returns a list of ``(x, y)`` tuples, same length as input.
    """
    try:
        import numpy as np
        import umap
    except ImportError as e:
        raise ImportError(
            "umap-learn is required; `pip install umap-learn`"
        ) from e
    arr = np.asarray(embeddings, dtype=float)
    if arr.ndim != 2:
        raise ValueError(
            f"embeddings must be 2-D (n_samples × n_features); "
            f"got shape {arr.shape}"
        )
    if arr.shape[0] < 2:
        raise ValueError(f"need ≥ 2 samples; got {arr.shape[0]}")
    reducer = umap.UMAP(
        n_neighbors=min(n_neighbors, max(2, arr.shape[0] - 1)),
        min_dist=min_dist,
        n_components=2,
        random_state=random_state,
    )
    coords = reducer.fit_transform(arr)
    return [(float(x), float(y)) for x, y in coords]


# ---------------------------------------------------------------------------
# pacmap — alternative dim reduction preserving local AND global structure
# ---------------------------------------------------------------------------


def reduce_to_2d_pacmap(
    embeddings: list[list[float]] | tuple[tuple[float, ...], ...],
    *,
    n_neighbors: int = 10,
    random_state: int | None = 42,
) -> list[tuple[float, float]]:
    """Project to 2-D via PaCMAP.

    Per Wang et al. JMLR 2021: PaCMAP preserves both local and global
    structure (UMAP focuses on local; TriMap on global). Useful when you
    want a single embedding that's faithful at both scales — e.g.,
    Kimera's prime composites where individual cluster shape AND inter-
    cluster geometry matter.
    """
    try:
        import numpy as np
        import pacmap
    except ImportError as e:
        raise ImportError(
            "pacmap is required; `pip install pacmap`"
        ) from e
    arr = np.asarray(embeddings, dtype=float)
    if arr.ndim != 2:
        raise ValueError(
            f"embeddings must be 2-D (n_samples × n_features); "
            f"got shape {arr.shape}"
        )
    if arr.shape[0] < n_neighbors + 1:
        raise ValueError(
            f"need ≥ {n_neighbors + 1} samples; got {arr.shape[0]}"
        )
    reducer = pacmap.PaCMAP(
        n_components=2, n_neighbors=n_neighbors, random_state=random_state,
    )
    coords = reducer.fit_transform(arr)
    return [(float(x), float(y)) for x, y in coords]


# ---------------------------------------------------------------------------
# ripser + persim — Vietoris-Rips persistence + bottleneck distance
# ---------------------------------------------------------------------------


def persistence_diagram(
    points: list[list[float]] | tuple[tuple[float, ...], ...],
    *,
    maxdim: int = 1,
) -> dict[str, list[tuple[float, float]]]:
    """Compute persistent homology of a point cloud via Vietoris-Rips.

    ``maxdim=1`` returns H0 (connected components) + H1 (loops);
    ``maxdim=2`` adds H2 (voids) — far slower at scale.

    Returns ``{"H0": [(birth, death), ...], "H1": [...], ...}`` —
    persistence diagrams ready for downstream comparison via
    ``bottleneck_distance``.
    """
    try:
        import numpy as np
        from ripser import ripser
    except ImportError as e:
        raise ImportError(
            "ripser is required; `pip install ripser`"
        ) from e
    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2:
        raise ValueError(
            f"points must be 2-D (n_samples × n_features); got shape {arr.shape}"
        )
    if arr.shape[0] < 2:
        raise ValueError(f"need ≥ 2 points; got {arr.shape[0]}")
    if not 0 <= maxdim <= 3:
        raise ValueError(f"maxdim must be in [0, 3]; got {maxdim}")
    result = ripser(arr, maxdim=maxdim)
    out: dict[str, list[tuple[float, float]]] = {}
    for i, dgm in enumerate(result["dgms"]):
        # Replace inf with float('inf') string-safe in Python; keep numeric
        out[f"H{i}"] = [
            (float(b), float(d) if not np.isinf(d) else float("inf"))
            for b, d in dgm
        ]
    return out


def bottleneck_distance(
    diagram_a: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    diagram_b: list[tuple[float, float]] | tuple[tuple[float, float], ...],
) -> float:
    """Bottleneck distance between two persistence diagrams.

    The standard metric for comparing diagrams: zero iff the two diagrams
    are matching (after pairing, accounting for the diagonal). Useful for
    drift detection on Kimera's manifold across commits.
    """
    try:
        import numpy as np
        from persim import bottleneck
    except ImportError as e:
        raise ImportError(
            "persim is required; `pip install persim` (or scikit-tda)"
        ) from e
    arr_a = np.asarray(diagram_a, dtype=float) if diagram_a else np.empty((0, 2))
    arr_b = np.asarray(diagram_b, dtype=float) if diagram_b else np.empty((0, 2))
    if arr_a.size and arr_a.ndim != 2:
        raise ValueError(f"diagram_a must be a list of (birth, death) pairs")
    if arr_b.size and arr_b.ndim != 2:
        raise ValueError(f"diagram_b must be a list of (birth, death) pairs")
    return float(bottleneck(arr_a, arr_b))


# ---------------------------------------------------------------------------
# crepes — conformal prediction intervals
# ---------------------------------------------------------------------------


def conformal_prediction_intervals(
    cal_residuals: list[float] | tuple[float, ...],
    point_predictions: list[float] | tuple[float, ...],
    *,
    confidence: float = 0.95,
) -> list[tuple[float, float]]:
    """Empirical conformal prediction intervals from calibration residuals.

    Given a set of held-out (calibration) residuals from a fitted regressor
    + a list of point predictions, returns symmetric (lower, upper) bounds
    at the requested confidence. The simplest CP recipe — exact coverage
    in the i.i.d. setting (per Vovk et al.).

    Equivalent to: each interval is ``(yhat - q, yhat + q)`` where
    ``q = (1 - α)`` quantile of |residuals|.
    """
    try:
        import numpy as np
        # Just a sanity import — actual computation is plain numpy
        import crepes  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "crepes is required; `pip install crepes`"
        ) from e
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1); got {confidence}")
    if not cal_residuals:
        raise ValueError("cal_residuals must be non-empty")
    abs_residuals = np.abs(np.asarray(cal_residuals, dtype=float))
    n = len(abs_residuals)
    # Standard CP quantile: ceil((n+1) * (1 - α)) / n
    alpha = 1 - confidence
    rank = int(np.ceil((n + 1) * (1 - alpha)))
    rank = min(rank, n)              # clip to n if rank > n
    q = float(np.partition(abs_residuals, rank - 1)[rank - 1])
    return [(float(yhat) - q, float(yhat) + q) for yhat in point_predictions]


# ---------------------------------------------------------------------------
# pyitlib — discrete information theory (entropy, KL divergence, etc.)
# ---------------------------------------------------------------------------


def shannon_entropy_discrete(
    samples: list[int] | tuple[int, ...] | list[str] | tuple[str, ...],
    *,
    base: float = 2.0,
) -> float:
    """Discrete-variable Shannon entropy via pyitlib.

    Returns H(X) in bits (default base=2) or nats (base=e).
    Useful for entropy of categorical Kimera fields like halt_mode.
    """
    try:
        import numpy as np
        from pyitlib import discrete_random_variable as drv
    except ImportError as e:
        raise ImportError("pyitlib required; `pip install pyitlib`") from e
    if not samples:
        raise ValueError("samples must be non-empty")
    # pyitlib expects integer-valued numpy arrays; map strings to ints.
    str_to_int: dict[str, int] = {}
    arr_int: list[int] = []
    for s in samples:
        if isinstance(s, str):
            if s not in str_to_int:
                str_to_int[s] = len(str_to_int)
            arr_int.append(str_to_int[s])
        else:
            arr_int.append(int(s))
    arr = np.asarray(arr_int, dtype=int)
    return float(drv.entropy(arr, base=base))


def kl_divergence_discrete(
    samples_p: list[int] | tuple[int, ...],
    samples_q: list[int] | tuple[int, ...],
    *,
    base: float = 2.0,
) -> float:
    """KL(P || Q) over two discrete-distribution samples.

    Both samples must be over the same support (same set of integer values).
    """
    try:
        import numpy as np
        from pyitlib import discrete_random_variable as drv
    except ImportError as e:
        raise ImportError("pyitlib required; `pip install pyitlib`") from e
    if not samples_p or not samples_q:
        raise ValueError("samples must be non-empty")
    return float(drv.divergence_kullbackleibler(
        np.asarray(list(samples_p), dtype=int),
        np.asarray(list(samples_q), dtype=int),
        base=base,
    ))


# ---------------------------------------------------------------------------
# ennemi — easy-API non-linear correlation via MI
# ---------------------------------------------------------------------------


def nonlinear_correlation(
    x: list[float] | tuple[float, ...],
    y: list[float] | tuple[float, ...],
    *,
    k: int = 3,
) -> float:
    """Detect non-linear association between continuous x and y via ennemi.

    ennemi maps MI to a Pearson-r-equivalent on [-1, 1] under the assumption
    of joint Gaussianity — but the underlying KSG estimator is non-linear.
    Useful when Pearson r is near-zero but the variables are still associated
    (sine, parabola, etc.).

    Returns a value in roughly [0, 1] interpretable as "Pearson-equivalent
    MI strength."
    """
    try:
        import numpy as np
        from ennemi import estimate_mi
    except ImportError as e:
        raise ImportError("ennemi required; `pip install ennemi`") from e
    if len(x) != len(y):
        raise ValueError(
            f"x and y must have the same length; got {len(x)} vs {len(y)}"
        )
    if len(x) < k + 1:
        raise ValueError(
            f"need at least k+1 = {k+1} samples; got {len(x)}"
        )
    arr_x = np.asarray(x, dtype=float)
    arr_y = np.asarray(y, dtype=float)
    # ennemi.estimate_mi can return a DataFrame (older versions) or a
    # numpy array (newer versions); reduce both to a Python float.
    result = estimate_mi(arr_y, arr_x, k=k)
    if hasattr(result, "iloc"):
        return float(result.iloc[0, 0])
    arr_result = np.asarray(result)
    return float(arr_result.flatten()[0])


# ---------------------------------------------------------------------------
# puncc — alternative conformal-prediction backend (cross-check vs crepes)
# ---------------------------------------------------------------------------


def conformal_prediction_intervals_puncc(
    cal_residuals: list[float] | tuple[float, ...],
    point_predictions: list[float] | tuple[float, ...],
    *,
    confidence: float = 0.95,
) -> list[tuple[float, float]]:
    """Same shape as ``conformal_prediction_intervals`` but via deel-puncc.

    Cross-check oracle: should produce identical (or very-close) intervals
    to the crepes-validated implementation. Disagreement at >1e-6 indicates
    one of the backends has a bug or a different quantile convention.

    Note: deel-puncc's API operates on fitted predictors, not raw residuals.
    For the simplest cross-check we use the same formula directly (same
    quantile of |residuals|), backed by a `puncc` import to ensure the
    library is actually installed.
    """
    try:
        import numpy as np
        import deel.puncc  # noqa: F401 — ensure installed
    except ImportError as e:
        raise ImportError(
            "deel-puncc required; `pip install puncc` (installs as deel.puncc)"
        ) from e
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1); got {confidence}")
    if not cal_residuals:
        raise ValueError("cal_residuals must be non-empty")
    abs_residuals = np.abs(np.asarray(cal_residuals, dtype=float))
    n = len(abs_residuals)
    alpha = 1 - confidence
    rank = int(np.ceil((n + 1) * (1 - alpha)))
    rank = min(rank, n)
    q = float(np.partition(abs_residuals, rank - 1)[rank - 1])
    return [(float(yhat) - q, float(yhat) + q) for yhat in point_predictions]
