"""Tests for config loading and sweep expansion."""

import textwrap

import pytest

from ophamin.config.sweep import (
    SweepSpec,
    deep_merge,
    get_in,
    load_config,
    load_sweep,
    set_in,
)


def test_get_in_and_set_in_dotted():
    d = {}
    set_in(d, "a.b.c", 7)
    assert d == {"a": {"b": {"c": 7}}}
    assert get_in(d, "a.b.c") == 7
    assert get_in(d, "a.b.missing", "default") == "default"
    assert get_in(d, "x.y.z", None) is None


def test_deep_merge_recurses():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 20, "z": 30}, "c": 4}
    merged = deep_merge(base, override)
    assert merged == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3, "c": 4}
    # base is untouched
    assert base == {"a": {"x": 1, "y": 2}, "b": 3}


def test_load_config_resolves_base(tmp_path):
    (tmp_path / "base.yaml").write_text(
        textwrap.dedent(
            """
            experiment:
              cycles_per_run: 100
              seed: 1
            substrate:
              kind: mock
            """
        )
    )
    (tmp_path / "child.yaml").write_text(
        textwrap.dedent(
            f"""
            base: "{tmp_path / 'base.yaml'}"
            experiment:
              seed: 99
            """
        )
    )
    cfg = load_config(tmp_path / "child.yaml")
    assert cfg["experiment"]["cycles_per_run"] == 100  # inherited
    assert cfg["experiment"]["seed"] == 99  # overridden
    assert cfg["substrate"]["kind"] == "mock"


def test_load_config_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_sweep_spec_expands_cartesian_product():
    spec = SweepSpec(
        base_config={"substrate": {"params": {}}},
        grid={"substrate.params.a": [1, 2, 3], "substrate.params.b": [10, 20]},
    )
    points = spec.points()
    assert len(points) == 6
    configs = spec.expand()
    assert len(configs) == 6
    # every child config has the swept values written in
    seen = set()
    for cfg, point in configs:
        a = cfg["substrate"]["params"]["a"]
        b = cfg["substrate"]["params"]["b"]
        assert point["substrate.params.a"] == a
        assert point["substrate.params.b"] == b
        seen.add((a, b))
    assert seen == {(1, 10), (1, 20), (2, 10), (2, 20), (3, 10), (3, 20)}


def test_load_sweep_inline_stimuli(tmp_path):
    (tmp_path / "base.yaml").write_text("experiment:\n  cycles_per_run: 50\n")
    (tmp_path / "sweep.yaml").write_text(
        textwrap.dedent(
            f"""
            base: "{tmp_path / 'base.yaml'}"
            parent_experiment:
              name: test-sweep
            sweep:
              substrate.params.rate: [0.1, 0.9]
            stimuli:
              source: inline
              items: ["one", "two"]
            """
        )
    )
    spec = load_sweep(tmp_path / "sweep.yaml")
    assert spec.parent_name == "test-sweep"
    assert spec.base_config["experiment"]["cycles_per_run"] == 50
    assert spec.stimuli == ["one", "two"]
    assert len(spec) == 2


def test_load_sweep_rejects_non_list_grid(tmp_path):
    (tmp_path / "bad.yaml").write_text("sweep:\n  k: 5\n")
    with pytest.raises(ValueError):
        load_sweep(tmp_path / "bad.yaml")
