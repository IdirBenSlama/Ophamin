"""Tests for round-3 wrappers: 2 new pillars + 4 helper modules + extensions.

Smoke-level: prove each wrapper executes correctly on synthetic input,
loud-fails on bad input, and slots into the registry where applicable.
"""

from __future__ import annotations

import random

import pytest

from ophamin.auditing.pillars import (
    DEEP_PILLAR_CLASSES,
    PROJECT_PILLAR_CLASSES,
    ProspectorPillar,
    SchemathesisPillar,
)
from ophamin.measuring.analytic_helpers import (
    conformal_prediction_intervals_puncc,
    kl_divergence_discrete,
    nonlinear_correlation,
    shannon_entropy_discrete,
)
from ophamin.measuring.bayesian_helpers import (
    posterior_for_normal_mean,
)
from ophamin.measuring.causal_helpers import (
    causal_discovery_pcmci,
    estimate_average_treatment_effect,
)
from ophamin.measuring.graph_helpers import (
    betweenness_top_k,
    community_detection,
    pagerank_top_k,
)
from ophamin.measuring.sat_smt_helpers import (
    check_sat_cross_backend,
    check_sat_z3,
)
from ophamin.measuring.timeseries_helpers import (
    detect_outliers_pyod,
    forecast_with_darts,
    matrix_profile_motifs,
)


# --------------------------------------------------------------------------
# Pillar registry
# --------------------------------------------------------------------------


def test_schemathesis_in_project_pillars():
    assert SchemathesisPillar in PROJECT_PILLAR_CLASSES


def test_prospector_in_deep_pillars():
    assert ProspectorPillar in DEEP_PILLAR_CLASSES


def test_schemathesis_pillar_shape():
    p = SchemathesisPillar()
    assert p.name == "schemathesis"
    assert p.tool_binary == "schemathesis"


def test_prospector_pillar_shape():
    p = ProspectorPillar()
    assert p.name == "prospector"
    assert p.tool_binary == "prospector"


def test_schemathesis_errors_on_target_without_spec(tmp_path):
    p = SchemathesisPillar()
    if not p.is_available():
        pytest.skip("schemathesis not installed")
    result = p.run(tmp_path)
    assert result.status == "error"
    assert "OpenAPI" in result.error_message


def test_schemathesis_unavailable_when_binary_missing(tmp_path, monkeypatch):
    p = SchemathesisPillar()
    monkeypatch.setattr(p, "is_available", lambda: False)
    assert p.run(tmp_path).status == "unavailable"


def test_prospector_unavailable_when_binary_missing(tmp_path, monkeypatch):
    p = ProspectorPillar()
    monkeypatch.setattr(p, "is_available", lambda: False)
    assert p.run(tmp_path).status == "unavailable"


# --------------------------------------------------------------------------
# Causal helpers
# --------------------------------------------------------------------------


def test_estimate_ate_runs_on_synthetic():
    """Build a tiny dataset where treatment X causes Y; ATE should be ≈ 1.

    NOTE: PyPI's dowhy caps at 0.8, which uses the now-removed
    ``networkx.algorithms.d_separated`` symbol (renamed to
    ``d_separation``). When that breakage hits we surface the upstream
    issue clearly rather than swallowing it. For a genuinely working
    causal pipeline, install dowhy from PyWhy's git directly.
    """
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas required")
    rng = random.Random(0)
    n = 200
    common = [rng.gauss(0, 1) for _ in range(n)]
    treatment = [1 if rng.random() < 0.5 + 0.3 * c else 0 for c in common]
    outcome = [t + 0.5 * c + rng.gauss(0, 0.1) for t, c in zip(treatment, common)]
    df = pd.DataFrame({"T": treatment, "Y": outcome, "C": common})
    try:
        out = estimate_average_treatment_effect(
            df, treatment="T", outcome="Y", common_causes=["C"],
        )
    except AttributeError as e:
        if "d_separated" in str(e):
            pytest.skip(
                "dowhy 0.8 (PyPI cap) uses removed NetworkX symbol "
                "d_separated; install dowhy from git for the fix"
            )
        raise
    assert "ate" in out
    assert isinstance(out["ate"], float)
    # True ATE = 1; expect within wide tolerance for n=200.
    assert 0.5 < out["ate"] < 1.5


def test_estimate_ate_loud_failure_on_missing_columns():
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas required")
    df = pd.DataFrame({"X": [1, 2, 3]})
    with pytest.raises(ValueError, match="not in data"):
        estimate_average_treatment_effect(df, "T", "Y", ["X"])


def test_pcmci_discovers_causal_link_on_lagged_synthetic():
    rng = random.Random(0)
    T = 100
    x = [rng.gauss(0, 1) for _ in range(T)]
    # y[t] = 0.8 * x[t-2] + noise — strong lag-2 dependency.
    y = [0.0, 0.0]
    for t in range(2, T):
        y.append(0.8 * x[t - 2] + rng.gauss(0, 0.2))
    arr = list(zip(x, y))
    out = causal_discovery_pcmci(arr, var_names=["X", "Y"], max_lag=4)
    assert "links" in out
    # Expect to discover X → Y at lag 2 (low p-value).
    discovered = {(c, e, l) for c, e, l, _p in out["links"]}
    assert ("X", "Y", 2) in discovered or any(
        c == "X" and e == "Y" and l > 0 for c, e, l in discovered
    )


# --------------------------------------------------------------------------
# Bayesian helpers (PyMC may be slow — keep test small)
# --------------------------------------------------------------------------


def test_pymc_posterior_recovers_normal_mean():
    rng = random.Random(0)
    obs = [rng.gauss(5.0, 1.0) for _ in range(50)]
    out = posterior_for_normal_mean(obs, draws=300, tune=200, chains=2)
    assert "mu_mean" in out
    # Posterior mean should be close to true mean = 5.0.
    assert 4.5 < out["mu_mean"] < 5.5
    assert out["mu_hdi_low"] < out["mu_mean"] < out["mu_hdi_high"]
    assert out["n"] == 50


def test_pymc_loud_failure_on_too_few_obs():
    with pytest.raises(ValueError, match="≥ 2 observations"):
        posterior_for_normal_mean([1.0])


# --------------------------------------------------------------------------
# SAT/SMT helpers
# --------------------------------------------------------------------------


def test_z3_sat_check_recognises_satisfiable_formula():
    out = check_sat_z3(
        constraints=["(assert (and (>= x 0) (<= x 10)))"],
        declarations=["(declare-fun x () Int)"],
    )
    assert out["sat"] is True
    assert out["backend"] == "z3"
    assert out["model"] is not None


def test_z3_sat_check_recognises_unsatisfiable():
    out = check_sat_z3(
        constraints=["(assert (and (>= x 0) (< x 0)))"],
        declarations=["(declare-fun x () Int)"],
    )
    assert out["sat"] is False


def test_z3_loud_failure_on_bad_smt2():
    with pytest.raises(ValueError, match="parse"):
        check_sat_z3(constraints=["(this is not smt-lib)"])


def test_cross_backend_sat_agrees_on_simple_formula():
    out = check_sat_cross_backend(
        constraints=["(assert (and (>= x 0) (<= x 10)))"],
        declarations=["(declare-fun x () Int)"],
    )
    assert "z3" in out
    assert "cvc5" in out
    # Both backends should agree on this simple formula's SAT result.
    if not out["cvc5"].get("error"):
        assert out["agreed"] is True


# --------------------------------------------------------------------------
# Time-series helpers
# --------------------------------------------------------------------------


def test_matrix_profile_finds_motifs():
    # Period-10 sine wave repeated → motifs should land at recurring peaks.
    import math
    series = [math.sin(2 * math.pi * i / 10) for i in range(50)]
    out = matrix_profile_motifs(series, window_size=10, k=2)
    assert len(out["profile"]) == 50 - 10 + 1
    assert len(out["motif_indices"]) == 2
    assert len(out["discord_indices"]) == 2


def test_matrix_profile_loud_failure_on_too_short():
    with pytest.raises(ValueError, match="2 × window_size"):
        matrix_profile_motifs([1.0, 2.0, 3.0], window_size=10)


def test_pyod_detects_outliers_in_synthetic():
    rng = random.Random(0)
    inliers = [[rng.gauss(0, 0.1), rng.gauss(0, 0.1)] for _ in range(90)]
    outliers = [[10.0, 10.0]] * 10
    out = detect_outliers_pyod(inliers + outliers, contamination=0.1,
                               method="iforest")
    # Most flagged outliers should be from the second half of the input.
    flagged = set(out["outlier_indices"])
    correct = sum(1 for i in flagged if i >= 90)
    assert correct >= 5


def test_pyod_loud_failure_on_bad_method():
    with pytest.raises(ValueError, match="unknown method"):
        detect_outliers_pyod([[1.0, 2.0], [3.0, 4.0]], method="bogus")


def test_darts_forecast_runs_on_naive_seasonal():
    series = [float(i % 7) for i in range(40)]
    out = forecast_with_darts(series, horizon=7, model="naive_seasonal")
    assert len(out["forecast"]) == 7
    assert out["model"] == "naive_seasonal"


# --------------------------------------------------------------------------
# Graph helpers
# --------------------------------------------------------------------------


def test_pagerank_top_k_returns_top_nodes():
    # Star graph: center node "hub" has the highest PageRank.
    edges = [("hub", f"leaf_{i}") for i in range(10)]
    edges += [(f"leaf_{i}", "hub") for i in range(10)]
    out = pagerank_top_k(edges, k=1, directed=True)
    assert len(out) == 1
    assert out[0][0] == "hub"


def test_community_detection_finds_two_communities():
    # Two disjoint triangles → 2 communities.
    edges = [
        ("a", "b"), ("b", "c"), ("c", "a"),     # triangle 1
        ("x", "y"), ("y", "z"), ("z", "x"),     # triangle 2
    ]
    out = community_detection(edges, method="louvain")
    assert out["n_communities"] == 2
    assert out["modularity"] > 0.4


def test_betweenness_finds_bridge():
    # Two triangles connected by a single edge through node "b".
    # "b" is the bridge → highest betweenness.
    edges = [("a", "b"), ("b", "c"), ("c", "a"),
             ("c", "d"), ("d", "e"), ("e", "c")]
    out = betweenness_top_k(edges, k=1, directed=False)
    assert out[0][0] in {"c", "b"}      # the two bridge candidates


def test_pagerank_loud_failure_on_empty():
    with pytest.raises(ValueError, match="non-empty"):
        pagerank_top_k([])


# --------------------------------------------------------------------------
# pyitlib + ennemi + puncc extensions to analytic_helpers
# --------------------------------------------------------------------------


def test_shannon_entropy_zero_for_constant():
    assert shannon_entropy_discrete([0, 0, 0, 0]) == pytest.approx(0.0)


def test_shannon_entropy_log2_n_for_uniform():
    # Uniform over 4 outcomes → H = log2(4) = 2 bits.
    samples = [0, 1, 2, 3] * 100
    h = shannon_entropy_discrete(samples)
    assert 1.95 < h < 2.05


def test_shannon_entropy_works_on_strings():
    samples = ["a", "b", "a", "b", "a", "b"]
    h = shannon_entropy_discrete(samples)
    assert 0.95 < h < 1.05      # H ≈ 1 bit


def test_kl_divergence_zero_for_identical():
    samples = [0, 1, 2, 0, 1, 2, 0, 1, 2]
    assert kl_divergence_discrete(samples, samples) == pytest.approx(0.0, abs=1e-9)


def test_nonlinear_correlation_high_for_dependent():
    rng = random.Random(0)
    x = [rng.gauss(0, 1) for _ in range(300)]
    y = [xi * 0.9 + rng.gauss(0, 0.2) for xi in x]
    val = nonlinear_correlation(x, y, k=3)
    assert val > 0.5


def test_nonlinear_correlation_loud_failure_on_length_mismatch():
    with pytest.raises(ValueError, match="same length"):
        nonlinear_correlation([1.0, 2.0], [1.0])


def test_puncc_intervals_match_crepes_intervals():
    """Cross-check oracle: crepes vs puncc on the same residuals + yhats
    must produce identical intervals (both use the same quantile rule).

    ``puncc`` was removed from the ``[conformal]`` and ``[all]`` extras
    in 0.7.1 (it pinned ``scikit-learn~=1.3.0`` which conflicted with
    ``causalml``'s ``>=1.6.0`` constraint, breaking CI). The cross-check
    oracle pattern is preserved; the test self-skips when puncc isn't
    installed.
    """
    from ophamin.measuring.analytic_helpers import (
        conformal_prediction_intervals,
    )
    try:
        puncc_intervals = conformal_prediction_intervals_puncc(
            [0.0, 1.0], [0.5], confidence=0.9,
        )
    except ImportError as exc:
        pytest.skip(f"puncc not installed: {exc}")
    cal = [-1.0, -0.5, 0.0, 0.5, 1.0, 0.2, -0.2, 0.8, -0.8, 0.0]
    yhats = [10.0, 20.0]
    crepes_intervals = conformal_prediction_intervals(cal, yhats, confidence=0.9)
    puncc_intervals = conformal_prediction_intervals_puncc(cal, yhats, confidence=0.9)
    for c, p in zip(crepes_intervals, puncc_intervals):
        assert c[0] == pytest.approx(p[0], abs=1e-9)
        assert c[1] == pytest.approx(p[1], abs=1e-9)


# --------------------------------------------------------------------------
# CRDT module
# --------------------------------------------------------------------------


def test_pycrdt_facade_round_trips_text():
    from ophamin.comparing.crdt_state import YDocFacade
    doc = YDocFacade(backend="pycrdt")
    doc.insert_text("main", 0, "hello")
    doc.insert_text("main", 5, " world")
    assert doc.get_text("main") == "hello world"


def test_y_py_facade_round_trips_text():
    from ophamin.comparing.crdt_state import YDocFacade
    doc = YDocFacade(backend="y_py")
    doc.insert_text("main", 0, "hello")
    doc.insert_text("main", 5, " world")
    assert doc.get_text("main") == "hello world"


def test_crdt_facade_loud_failure_on_unknown_backend():
    from ophamin.comparing.crdt_state import YDocFacade
    with pytest.raises(ValueError, match="backend must be"):
        YDocFacade(backend="not_a_real_backend")


def test_cross_backend_convergence_pycrdt_vs_ypy():
    from ophamin.comparing.crdt_state import cross_backend_convergence
    ops = [
        ("insert", 0, "h"),
        ("insert", 1, "i"),
        ("insert", 2, "!"),
    ]
    out = cross_backend_convergence(ops)
    assert out["agreed"] is True
    assert out["pycrdt_text"] == "hi!"
    assert out["y_py_text"] == "hi!"
    assert out["n_ops"] == 3


def test_cross_backend_convergence_loud_on_unknown_op():
    from ophamin.comparing.crdt_state import cross_backend_convergence
    with pytest.raises(ValueError, match="only 'insert'"):
        cross_backend_convergence([("delete", 0, "x")])
