"""Tests for the three-tier metric model."""

from ophamin.metrics.tiers import MetricBundle, Tier1Metrics, Tier2Metrics, Tier3Metrics


def test_tier1_timer_recording():
    t1 = Tier1Metrics()
    t1.record_timer("latency", 1.0)
    t1.record_timer("latency", 3.0)
    assert t1.timers["latency"] == [1.0, 3.0]


def test_metric_bundle_flat_namespacing():
    bundle = MetricBundle(
        cycle_index=4,
        tier1=Tier1Metrics(
            counters={"cycles": 4.0},
            gauges={"phi": 0.6},
            timers={"latency": [2.0, 4.0]},
        ),
        tier2=Tier2Metrics(drift_score=0.1),
        tier3=Tier3Metrics(jaccard_overlap=0.5),
    )
    flat = bundle.flat()
    assert flat["cycle_index"] == 4
    assert flat["t1.counter.cycles"] == 4.0
    assert flat["t1.gauge.phi"] == 0.6
    assert flat["t1.timer.latency.mean"] == 3.0
    assert flat["t2.drift_score"] == 0.1
    assert flat["t3.jaccard_overlap"] == 0.5


def test_metric_bundle_to_dict_round_trips_structure():
    bundle = MetricBundle(cycle_index=0)
    d = bundle.to_dict()
    assert set(d) == {"cycle_index", "stimulus_id", "wall_time", "tier1", "tier2", "tier3"}
    assert set(d["tier1"]) == {"counters", "gauges", "timers"}
