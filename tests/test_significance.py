"""Per-proof plain-language significance — the corpus must explain itself.

Ophamin's first purpose is legibility (the explanation the owner cannot give in
words). These tests pin that the authored, verdict-aware significance renders
deterministically, branches on the verdict, stays honest on unknown metrics, and
carries the owner's framing for the open size-meter gap.
"""

from ophamin.reporting.significance import (
    covered_metrics,
    has_significance,
    plain_significance,
)


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


def test_every_authored_metric_has_all_three_branches():
    # Each authored meaning must resolve for every verdict (no half-authored entry
    # that would silently drop the section on a REFUTED/INCONCLUSIVE proof).
    assert len(covered_metrics()) >= 14
    for m in covered_metrics():
        for outcome in ("VALIDATED", "REFUTED", "INCONCLUSIVE"):
            assert plain_significance(_rec(m, outcome, 1.0)), f"{m}/{outcome} missing"


def test_cross_instance_invariance_names_the_pooling_stakes():
    # The cross-instance prime-identity meaning must connect to Indra's-Net pooling.
    s = plain_significance(_rec("cross_instance_p_identity_invariance_rate", "VALIDATED", 1.0))
    assert s and ("pool" in s.lower() or "node" in s.lower())


def test_missing_observed_value_omits_the_parenthetical():
    s = plain_significance(_rec("phi_floor", "VALIDATED"))
    assert s and "observed" not in s


def test_empty_or_malformed_record_is_safe():
    assert plain_significance({}) is None
    assert plain_significance({"claim": {}, "verdict": {}}) is None
