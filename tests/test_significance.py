"""Per-proof plain-language significance — the corpus must explain itself.

Ophamin's first purpose is legibility (the explanation the owner cannot give in
words). These tests pin that the authored, verdict-aware significance renders
deterministically, branches on the verdict, stays honest on unknown metrics, and
carries the owner's framing for the open size-meter gap.
"""

from ophamin.reporting.significance import has_significance, plain_significance


def _rec(metric, outcome, observed=None):
    return {
        "claim": {"threshold": {"metric": metric}},
        "verdict": {"outcome": outcome, "observed_value": observed},
    }


def test_order_hysteresis_branches_on_verdict():
    v = plain_significance(_rec("order_hysteresis", "VALIDATED", 0.93))
    r = plain_significance(_rec("order_hysteresis", "REFUTED", -0.01))
    assert v and "order" in v.lower() and "0.93" in v
    assert r and v != r  # the meaning flips with the verdict


def test_unknown_metric_is_an_honest_gap():
    assert plain_significance(_rec("totally_unknown_metric", "VALIDATED", 1.0)) is None
    assert not has_significance("totally_unknown_metric")
    assert has_significance("order_hysteresis")


def test_size_meter_inconclusive_is_honest_about_the_gap():
    s = plain_significance(_rec("drawdown_tracking_rho", "INCONCLUSIVE", 0.43))
    assert s and "size-meter" in s


def test_all_seven_flagship_metrics_have_all_three_branches():
    metrics = [
        "memory_path_dependence", "order_hysteresis", "recognition_jaccard_floor",
        "memory_lift", "history_separation_advantage", "drawdown_tracking_rho",
        "phi_floor",
    ]
    for m in metrics:
        for outcome in ("VALIDATED", "REFUTED", "INCONCLUSIVE"):
            assert plain_significance(_rec(m, outcome, 1.0)), f"{m}/{outcome} missing"


def test_missing_observed_value_omits_the_parenthetical():
    s = plain_significance(_rec("phi_floor", "VALIDATED"))
    assert s and "observed" not in s


def test_empty_or_malformed_record_is_safe():
    assert plain_significance({}) is None
    assert plain_significance({"claim": {}, "verdict": {}}) is None
