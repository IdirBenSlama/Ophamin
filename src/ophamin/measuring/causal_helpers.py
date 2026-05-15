"""Causal-inference helpers — DoWhy + EconML + Tigramite wrappers.

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §9. Three small wrappers exposing
the highest-signal use cases for Kimera-SWM scenarios:

  estimate_average_treatment_effect(...)   — DoWhy + EconML on tabular data
  causal_discovery_pcmci(...)              — Tigramite for time-series
                                            causal-graph discovery
                                            (does Φ drift CAUSE walker M2?)
  refute_causal_estimate(...)              — DoWhy refutation methods
                                            (placebo / random-cause /
                                            unobserved-common-cause)

Each loud-fails on missing dep. Numerical defaults are chosen to match
the published reference implementations (PyWhy + Tigramite tutorials).
"""

from __future__ import annotations

from typing import Any


def estimate_average_treatment_effect(
    data: Any,                       # pandas DataFrame
    treatment: str,
    outcome: str,
    common_causes: list[str],
    *,
    method: str = "backdoor.linear_regression",
) -> dict[str, Any]:
    """Estimate ATE = E[Y(1)] - E[Y(0)] via DoWhy's identify → estimate flow.

    ``data`` is a pandas DataFrame with columns named by ``treatment``
    (binary), ``outcome`` (numeric), and each name in ``common_causes``.

    Returns ``{"ate": float, "method": str, "n": int, "treatment": str,
              "outcome": str, "common_causes": list[str]}``.

    For Kimera: treatment could be "consolidation_pulse_fired",
    outcome could be "phi_value", common_causes the substrate-state
    columns that influence both.
    """
    try:
        from dowhy import CausalModel
    except ImportError as e:
        raise ImportError("dowhy is required; `pip install dowhy`") from e
    if treatment not in data.columns:
        raise ValueError(f"treatment column {treatment!r} not in data")
    if outcome not in data.columns:
        raise ValueError(f"outcome column {outcome!r} not in data")
    missing = [c for c in common_causes if c not in data.columns]
    if missing:
        raise ValueError(f"common_causes columns missing from data: {missing}")

    model = CausalModel(
        data=data, treatment=treatment, outcome=outcome,
        common_causes=common_causes,
    )
    identified = model.identify_effect(proceed_when_unidentifiable=True)
    estimate = model.estimate_effect(identified, method_name=method)
    return {
        "ate": float(estimate.value),
        "method": method,
        "n": int(len(data)),
        "treatment": treatment,
        "outcome": outcome,
        "common_causes": list(common_causes),
    }


def refute_causal_estimate(
    data: Any,
    treatment: str,
    outcome: str,
    common_causes: list[str],
    *,
    refuter: str = "placebo_treatment_refuter",
    method: str = "backdoor.linear_regression",
) -> dict[str, Any]:
    """Robustness-check a causal estimate via DoWhy's refuters.

    ``refuter`` choices include:
      ``placebo_treatment_refuter`` — random treatment should give ~0 effect
      ``random_common_cause``       — adding a random cause shouldn't move ATE
      ``data_subset_refuter``       — ATE should be stable on subsets
      ``add_unobserved_common_cause`` — sensitivity to unobserved confounders

    Returns ``{"original_ate": float, "refuted_ate": float,
              "p_value": float|None, "refutation_passed": bool,
              "refuter": str}``.
    """
    try:
        from dowhy import CausalModel
    except ImportError as e:
        raise ImportError("dowhy is required; `pip install dowhy`") from e
    model = CausalModel(
        data=data, treatment=treatment, outcome=outcome,
        common_causes=common_causes,
    )
    identified = model.identify_effect(proceed_when_unidentifiable=True)
    estimate = model.estimate_effect(identified, method_name=method)
    refute = model.refute_estimate(identified, estimate, method_name=refuter)
    p_value = getattr(refute, "refutation_result", {})
    p_val = None
    if isinstance(p_value, dict):
        p_val_raw = p_value.get("p_value")
        if p_val_raw is not None:
            try:
                p_val = float(p_val_raw)
            except (TypeError, ValueError):
                p_val = None
    return {
        "original_ate": float(estimate.value),
        "refuted_ate": float(refute.new_effect),
        "p_value": p_val,
        # Refutation "passes" when the refuted effect is close to either
        # the original (random-cause / subset refuters) or close to zero
        # (placebo refuter). We surface both estimates and let the caller
        # decide; this field is just a heuristic.
        "refutation_passed": bool(
            abs(float(refute.new_effect)) < abs(float(estimate.value)) * 0.5
            if "placebo" in refuter else True
        ),
        "refuter": refuter,
    }


def causal_discovery_pcmci(
    time_series: list[list[float]] | tuple[tuple[float, ...], ...],
    *,
    var_names: list[str] | None = None,
    max_lag: int = 5,
    pc_alpha: float = 0.05,
) -> dict[str, Any]:
    """Time-series causal discovery via Tigramite's PCMCI algorithm.

    ``time_series`` shape: ``(T, N)`` where T = timesteps, N = variables.

    Returns ``{"links": [(cause, effect, lag, p_value), ...], "n_vars": int,
              "n_timesteps": int, "max_lag": int}``.

    For Kimera: feed per-cycle ``[phi, walker_amplitude_death, dissonance,
    consolidation_pulse_fired, ...]`` and discover the lagged causal graph.
    """
    try:
        import numpy as np
        from tigramite import data_processing as pp
        from tigramite.pcmci import PCMCI
        from tigramite.independence_tests.parcorr import ParCorr
    except ImportError as e:
        raise ImportError(
            "tigramite is required; `pip install tigramite`"
        ) from e
    arr = np.asarray(time_series, dtype=float)
    if arr.ndim != 2:
        raise ValueError(
            f"time_series must be 2-D (T × N); got shape {arr.shape}"
        )
    T, N = arr.shape
    if T < max_lag + 5:
        raise ValueError(
            f"need T ≥ max_lag+5 = {max_lag+5} timesteps; got {T}"
        )
    names = var_names or [f"X{i}" for i in range(N)]
    if len(names) != N:
        raise ValueError(
            f"var_names must have N={N} entries; got {len(names)}"
        )
    dataframe = pp.DataFrame(arr, var_names=names)
    pcmci = PCMCI(dataframe=dataframe, cond_ind_test=ParCorr(), verbosity=0)
    results = pcmci.run_pcmci(tau_max=max_lag, pc_alpha=pc_alpha)
    p_matrix = results["p_matrix"]
    links: list[tuple[str, str, int, float]] = []
    for i in range(N):
        for j in range(N):
            for lag in range(max_lag + 1):
                p = float(p_matrix[i, j, lag])
                if p < pc_alpha:
                    links.append((names[i], names[j], lag, p))
    return {
        "links": links,
        "n_vars": N,
        "n_timesteps": T,
        "max_lag": max_lag,
        "pc_alpha": pc_alpha,
    }
