"""Tests for the v0.2 extended wave: TDA + conformal + extra pillars.

Covers helpers added to ``measuring/analytic_helpers.py``:
  bottleneck_distance, persistence_diagram, conformal_prediction_intervals,
  mutual_information_npeet, reduce_to_2d_pacmap

Plus the three new pillars: SemgrepPillar, CoveragePillar (smoke tests
+ shape; they're project-scope and slow on Ophamin).
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from ophamin.auditing.pillars import (
    DEEP_PILLAR_CLASSES,
    PROJECT_PILLAR_CLASSES,
    CoveragePillar,
    SemgrepPillar,
)
from ophamin.measuring.analytic_helpers import (
    bottleneck_distance,
    conformal_prediction_intervals,
    mutual_information_npeet,
    persistence_diagram,
    reduce_to_2d_pacmap,
)


# --------------------------------------------------------------------------
# ripser / persim — TDA
# --------------------------------------------------------------------------


def test_persistence_diagram_returns_h0_h1_for_circle():
    import math
    pts = [
        [math.cos(2 * math.pi * i / 30), math.sin(2 * math.pi * i / 30)]
        for i in range(30)
    ]
    dgms = persistence_diagram(pts, maxdim=1)
    assert "H0" in dgms
    assert "H1" in dgms
    # A circle (30 points evenly spaced) has β1 = 1 → exactly one
    # long-lived H1 feature.
    long_h1 = [(b, d) for b, d in dgms["H1"] if d - b > 0.3]
    assert len(long_h1) >= 1


def test_persistence_diagram_loud_failure_on_too_few_points():
    with pytest.raises(ValueError, match="≥ 2 points"):
        persistence_diagram([[1.0, 2.0]])


def test_persistence_diagram_rejects_invalid_maxdim():
    with pytest.raises(ValueError, match="maxdim must be in"):
        persistence_diagram([[0, 0], [1, 1], [2, 2]], maxdim=5)


def test_bottleneck_distance_zero_for_identical_diagrams():
    dgm = [(0.0, 1.0), (0.5, 2.0)]
    assert bottleneck_distance(dgm, dgm) == pytest.approx(0.0, abs=1e-9)


def test_bottleneck_distance_positive_for_different_diagrams():
    a = [(0.0, 1.0)]
    b = [(0.0, 5.0)]
    d = bottleneck_distance(a, b)
    assert d > 0.0


def test_bottleneck_distance_handles_empty_diagrams():
    assert bottleneck_distance([], []) == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------
# crepes — conformal prediction
# --------------------------------------------------------------------------


def test_conformal_intervals_have_correct_shape():
    cal = [-1.0, -0.5, 0.0, 0.5, 1.0, 0.2, -0.2, 0.8, -0.8, 0.0]
    yhats = [10.0, 20.0, 30.0]
    intervals = conformal_prediction_intervals(cal, yhats, confidence=0.9)
    assert len(intervals) == 3
    for (lo, hi), y in zip(intervals, yhats):
        assert lo < y < hi
        # Symmetric around the prediction.
        assert abs((y - lo) - (hi - y)) < 1e-9


def test_conformal_intervals_widen_with_higher_confidence():
    cal = [-1.0, -0.5, 0.0, 0.5, 1.0, 0.2, -0.2, 0.8, -0.8, 0.0]
    narrow = conformal_prediction_intervals(cal, [0.0], confidence=0.5)
    wide = conformal_prediction_intervals(cal, [0.0], confidence=0.99)
    assert (wide[0][1] - wide[0][0]) >= (narrow[0][1] - narrow[0][0])


def test_conformal_intervals_loud_failure_on_invalid_confidence():
    with pytest.raises(ValueError, match="confidence"):
        conformal_prediction_intervals([1.0], [0.0], confidence=1.5)


def test_conformal_intervals_loud_failure_on_empty_calibration():
    with pytest.raises(ValueError, match="non-empty"):
        conformal_prediction_intervals([], [0.0])


# --------------------------------------------------------------------------
# NPEET — second-opinion MI
# --------------------------------------------------------------------------


def test_npeet_mi_low_for_independent():
    rng = random.Random(0)
    x = [rng.gauss(0, 1) for _ in range(500)]
    y = [rng.gauss(0, 1) for _ in range(500)]
    mi = mutual_information_npeet(x, y, k=4)
    assert mi < 0.3


def test_npeet_mi_high_for_dependent():
    rng = random.Random(0)
    x = [rng.gauss(0, 1) for _ in range(500)]
    y = [xi * 0.95 + rng.gauss(0, 0.1) for xi in x]
    mi = mutual_information_npeet(x, y, k=4)
    assert mi > 0.8


def test_npeet_mi_loud_failure_on_length_mismatch():
    with pytest.raises(ValueError, match="same length"):
        mutual_information_npeet([1.0, 2.0], [1.0, 2.0, 3.0])


# --------------------------------------------------------------------------
# pacmap — alternative dim reduction
# --------------------------------------------------------------------------


def test_pacmap_reduces_to_2d_correct_shape():
    rng = random.Random(0)
    embeddings = [
        [rng.gauss(0, 1) for _ in range(8)]
        for _ in range(30)
    ]
    coords = reduce_to_2d_pacmap(embeddings, n_neighbors=5, random_state=42)
    assert len(coords) == 30
    for c in coords:
        assert len(c) == 2


def test_pacmap_loud_failure_on_too_few_samples():
    with pytest.raises(ValueError, match="need ≥"):
        reduce_to_2d_pacmap([[1.0, 2.0]], n_neighbors=5)


# --------------------------------------------------------------------------
# Pillar registry — SemgrepPillar in DEEP, CoveragePillar in PROJECT
# --------------------------------------------------------------------------


def test_semgrep_in_deep_pillars():
    assert SemgrepPillar in DEEP_PILLAR_CLASSES


def test_coverage_in_project_pillars():
    assert CoveragePillar in PROJECT_PILLAR_CLASSES


def test_semgrep_pillar_shape():
    p = SemgrepPillar()
    assert p.name == "semgrep"
    assert p.tool_binary == "semgrep"


def test_coverage_pillar_shape():
    p = CoveragePillar()
    assert p.name == "coverage"
    assert p.tool_binary == "coverage"


def test_semgrep_unavailable_when_binary_missing(tmp_path, monkeypatch):
    p = SemgrepPillar()
    monkeypatch.setattr(p, "is_available", lambda: False)
    assert p.run(tmp_path).status == "unavailable"


def test_coverage_errors_on_non_directory_target(tmp_path):
    f = tmp_path / "not_a_dir.txt"
    f.write_text("x")
    p = CoveragePillar()
    if not p.is_available():
        pytest.skip("coverage not installed")
    result = p.run(f)
    assert result.status == "error"
    assert "directory" in result.error_message
