"""Time-series helpers — STUMPY + PyOD + Darts + tsfresh wrappers.

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §12. Four wrappers for the most
load-bearing time-series operations on Kimera-SWM streams:

  matrix_profile_motifs(...)        — STUMPY: motifs + discords
  detect_outliers_pyod(...)         — PyOD: 50+ algorithms; default IForest
  forecast_with_darts(...)          — Darts: NaiveSeasonal / ARIMA / etc.
  extract_features_tsfresh(...)     — TSFresh: 1000+ features per series

Each loud-fails on missing dep. Numerical defaults align with the
published reference tutorials.
"""

from __future__ import annotations

from typing import Any


def matrix_profile_motifs(
    series: list[float] | tuple[float, ...],
    *,
    window_size: int = 10,
    k: int = 1,
) -> dict[str, Any]:
    """Compute the matrix profile + return top-k motifs and discords.

    The matrix profile is the per-window distance to the nearest non-self
    neighbour. Low values = motifs (repeated patterns); high values =
    discords (anomalies).

    Returns ``{"profile": [float, ...], "motif_indices": [int, ...],
              "discord_indices": [int, ...], "window_size": int}``.

    For Kimera: feed per-cycle Φ trajectory; motifs = recurring cognitive
    patterns; discords = outlier cycles worth investigating.
    """
    try:
        import numpy as np
        import stumpy
    except ImportError as e:
        raise ImportError("stumpy required; `pip install stumpy`") from e
    arr = np.asarray(series, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"series must be 1-D; got shape {arr.shape}")
    if window_size < 3:
        raise ValueError(f"window_size must be ≥ 3; got {window_size}")
    if len(arr) < 2 * window_size:
        raise ValueError(
            f"need ≥ 2 × window_size = {2 * window_size} samples; "
            f"got {len(arr)}"
        )
    mp = stumpy.stump(arr, m=window_size)
    profile = mp[:, 0].astype(float)
    # Motifs: lowest k profile values.
    motif_idx = np.argsort(profile)[:k].tolist()
    # Discords: highest k profile values (skip inf).
    finite_mask = np.isfinite(profile)
    finite_profile = profile.copy()
    finite_profile[~finite_mask] = -np.inf
    discord_idx = np.argsort(finite_profile)[::-1][:k].tolist()
    return {
        "profile": [float(p) for p in profile],
        "motif_indices": [int(i) for i in motif_idx],
        "discord_indices": [int(i) for i in discord_idx],
        "window_size": int(window_size),
        "n_samples": int(len(arr)),
    }


def detect_outliers_pyod(
    points: list[list[float]] | tuple[tuple[float, ...], ...],
    *,
    contamination: float = 0.1,
    method: str = "iforest",
) -> dict[str, Any]:
    """Detect outliers via PyOD's standard detectors.

    ``method`` choices: ``"iforest"`` (Isolation Forest, default),
    ``"lof"`` (Local Outlier Factor), ``"knn"``, ``"copod"``.

    Returns ``{"outlier_indices": [int, ...], "scores": [float, ...],
              "n_outliers": int, "n_total": int, "method": str}``.
    """
    try:
        import numpy as np
    except ImportError as e:
        raise ImportError("numpy required") from e
    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2:
        raise ValueError(
            f"points must be 2-D (n × d); got shape {arr.shape}"
        )
    if not 0 < contamination < 0.5:
        raise ValueError(
            f"contamination must be in (0, 0.5); got {contamination}"
        )
    method_norm = method.strip().lower()
    try:
        if method_norm == "iforest":
            from pyod.models.iforest import IForest
            detector = IForest(contamination=contamination, random_state=42)
        elif method_norm == "lof":
            from pyod.models.lof import LOF
            detector = LOF(contamination=contamination)
        elif method_norm == "knn":
            from pyod.models.knn import KNN
            detector = KNN(contamination=contamination)
        elif method_norm == "copod":
            from pyod.models.copod import COPOD
            detector = COPOD(contamination=contamination)
        else:
            raise ValueError(
                f"unknown method {method!r}; available: iforest|lof|knn|copod"
            )
    except ImportError as e:
        raise ImportError("pyod required; `pip install pyod`") from e
    detector.fit(arr)
    labels = detector.labels_         # 0 = inlier, 1 = outlier
    scores = detector.decision_scores_
    out_idx = [int(i) for i, lab in enumerate(labels) if lab == 1]
    return {
        "outlier_indices": out_idx,
        "scores": [float(s) for s in scores],
        "n_outliers": len(out_idx),
        "n_total": int(len(arr)),
        "method": method_norm,
    }


def forecast_with_darts(
    series: list[float] | tuple[float, ...],
    *,
    horizon: int = 10,
    model: str = "naive_seasonal",
) -> dict[str, Any]:
    """Forecast next ``horizon`` steps via Darts.

    ``model`` choices: ``"naive_seasonal"`` (default — repeats last cycle),
    ``"naive_drift"`` (linear extrapolation), ``"naive_mean"``.

    Returns ``{"forecast": [float, ...], "horizon": int, "model": str,
              "n_history": int}``.
    """
    try:
        import numpy as np
        from darts import TimeSeries
    except ImportError as e:
        raise ImportError("darts required; `pip install darts`") from e
    arr = np.asarray(series, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"series must be 1-D; got shape {arr.shape}")
    if len(arr) < 4:
        raise ValueError(f"need ≥ 4 samples; got {len(arr)}")
    if horizon < 1:
        raise ValueError(f"horizon must be ≥ 1; got {horizon}")
    ts = TimeSeries.from_values(arr)
    method_norm = model.strip().lower()
    try:
        if method_norm == "naive_seasonal":
            from darts.models import NaiveSeasonal
            m = NaiveSeasonal(K=max(1, min(len(arr) // 2, 12)))
        elif method_norm == "naive_drift":
            from darts.models import NaiveDrift
            m = NaiveDrift()
        elif method_norm == "naive_mean":
            from darts.models import NaiveMean
            m = NaiveMean()
        else:
            raise ValueError(
                f"unknown model {model!r}; "
                f"available: naive_seasonal|naive_drift|naive_mean"
            )
    except ImportError as e:
        raise ImportError("darts required; `pip install darts`") from e
    m.fit(ts)
    forecast = m.predict(horizon)
    return {
        "forecast": [float(v) for v in forecast.values().flatten()],
        "horizon": horizon,
        "model": method_norm,
        "n_history": int(len(arr)),
    }


def extract_features_tsfresh(
    series_per_id: dict[str, list[float]],
) -> dict[str, dict[str, float]]:
    """Extract minimal-set time-series features for each ID's series.

    ``series_per_id``: ``{"series_a": [v1, v2, ...], "series_b": [...]}``.

    Uses tsfresh's ``MinimalFCParameters`` (10 quick features per series:
    mean, length, sum_values, abs_max, etc.). For full extraction use
    ``EfficientFCParameters`` (~100 features) directly via tsfresh's API.

    Returns ``{"series_a": {"feat_name": value, ...}, ...}``.
    """
    try:
        import numpy as np
        import pandas as pd
        from tsfresh import extract_features
        from tsfresh.feature_extraction import MinimalFCParameters
    except ImportError as e:
        raise ImportError("tsfresh required; `pip install tsfresh`") from e
    if not series_per_id:
        raise ValueError("series_per_id must be non-empty")
    rows = []
    for sid, values in series_per_id.items():
        for t, v in enumerate(values):
            rows.append({"id": sid, "time": t, "value": float(v)})
    df = pd.DataFrame(rows)
    feats = extract_features(
        df, column_id="id", column_sort="time", column_value="value",
        default_fc_parameters=MinimalFCParameters(),
        disable_progressbar=True,
    )
    out: dict[str, dict[str, float]] = {}
    for sid, row in feats.iterrows():
        out[str(sid)] = {
            str(k): float(v) if not (isinstance(v, float) and np.isnan(v)) else 0.0
            for k, v in row.items()
        }
    return out
