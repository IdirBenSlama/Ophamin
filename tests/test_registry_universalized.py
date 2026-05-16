"""Hardening tests for Move N — universalized plug-in registration
across all four Protocols (Pillars + Scenarios + Corpora + SubstrateProbes)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ophamin.registry import (
    PILLARS,
    SUBSTRATE_FACTORIES,
    DuplicatePluginError,
    get_corpus_by_name,
    get_pillar,
    get_scenario,
    get_substrate_class,
    list_corpora,
    list_pillars,
    list_scenarios,
    list_substrate_classes,
    register_corpus,
    register_substrate,
)
from ophamin.seeing.corpus import (
    CORPUS_FACTORIES,
    list_corpus_names,
    register_corpus_factory,
)


# --- corpus registry ------------------------------------------------------


def test_list_corpora_returns_known_names():
    names = list(list_corpora())
    expected = {"enron", "linux", "cyber", "flores", "financial", "the_well"}
    assert expected.issubset(set(names))


def test_corpus_factories_publicly_exposed():
    assert "enron" in CORPUS_FACTORIES
    assert callable(CORPUS_FACTORIES["enron"])


def test_list_corpus_names_sorted():
    names = list_corpus_names()
    assert list(names) == sorted(names)


def test_get_corpus_by_name_returns_corpus():
    corpus = get_corpus_by_name("enron")
    assert hasattr(corpus, "name")
    assert hasattr(corpus, "kind")
    assert hasattr(corpus, "is_available")


def test_register_corpus_with_third_party_factory():
    """A third-party corpus factory can register cleanly + the name
    becomes reachable via get_corpus_by_name."""
    sentinel = "test_only_corpus_sentinel"

    class _FakeCorpus:
        name = sentinel
        kind = "test"
        source = "test"
        def is_available(self): return True
        def records(self): return iter(())
        def content_hash(self): return ""
        def count(self): return 0

    def factory(root):
        return _FakeCorpus()

    try:
        register_corpus(sentinel, factory)
        assert sentinel in CORPUS_FACTORIES
        corpus = get_corpus_by_name(sentinel)
        assert corpus.name == sentinel
    finally:
        CORPUS_FACTORIES.pop(sentinel, None)


def test_register_corpus_duplicate_raises():
    sentinel = "duplicate_corpus_sentinel"
    factory_a = lambda root: None
    factory_b = lambda root: None
    try:
        register_corpus_factory(sentinel, factory_a)
        with pytest.raises(ValueError):
            register_corpus_factory(sentinel, factory_b)
    finally:
        CORPUS_FACTORIES.pop(sentinel, None)


def test_register_corpus_idempotent_same_factory():
    """Re-registering the SAME factory under the same name is a no-op."""
    sentinel = "idempotent_corpus_sentinel"
    factory = lambda root: None
    try:
        register_corpus_factory(sentinel, factory)
        register_corpus_factory(sentinel, factory)
        assert CORPUS_FACTORIES[sentinel] is factory
    finally:
        CORPUS_FACTORIES.pop(sentinel, None)


# --- substrate registry ---------------------------------------------------


def test_built_in_substrates_registered():
    assert "mock" in SUBSTRATE_FACTORIES
    assert "kimera" in SUBSTRATE_FACTORIES


def test_get_substrate_class_returns_class():
    cls = get_substrate_class("mock")
    assert isinstance(cls, type)


def test_get_substrate_class_unknown_raises():
    with pytest.raises(KeyError):
        get_substrate_class("not_a_real_substrate")


def test_list_substrate_classes_sorted():
    classes = list(list_substrate_classes())
    names = list(sorted(SUBSTRATE_FACTORIES))
    assert [SUBSTRATE_FACTORIES[n] for n in names] == classes


def test_register_substrate_duplicate_raises():
    """Different class under existing name triggers DuplicatePluginError."""
    class _FakeSubstrate:
        name = "mock"

    with pytest.raises(DuplicatePluginError):
        register_substrate("mock", _FakeSubstrate)


def test_register_substrate_idempotent_same_class():
    from ophamin.seeing.substrate import MockSubstrate

    # Already registered at import time; re-registering same class is no-op
    register_substrate("mock", MockSubstrate)
    assert SUBSTRATE_FACTORIES["mock"] is MockSubstrate


def test_register_substrate_rejects_non_class():
    with pytest.raises(TypeError):
        register_substrate("instance_not_class", object())  # type: ignore[arg-type]


def test_register_substrate_with_third_party_class():
    sentinel = "test_only_substrate"

    class _FakeSubstrate:
        name = "fake"

    try:
        register_substrate(sentinel, _FakeSubstrate)
        assert SUBSTRATE_FACTORIES[sentinel] is _FakeSubstrate
    finally:
        SUBSTRATE_FACTORIES.pop(sentinel, None)


# --- registry coverage check ----------------------------------------------


def test_four_protocols_covered():
    """All four declared Protocols in ``ophamin.protocols`` now have a
    registration surface."""
    from ophamin import registry
    # Pillar (Move G)
    assert hasattr(registry, "PILLARS")
    assert hasattr(registry, "register_pillar")
    # ScenarioProtocol (Move A — via SCENARIOS dict)
    assert callable(registry.get_scenario)
    # DatasetConnector (Move N)
    assert callable(registry.get_corpus_by_name)
    assert callable(registry.register_corpus)
    # SubstrateProbe (Move N)
    assert hasattr(registry, "SUBSTRATE_FACTORIES")
    assert callable(registry.register_substrate)


# --- CLI smoke ------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", *args],
        capture_output=True, text=True,
    )


def test_cli_corpus_list_human():
    result = _run_cli("corpus", "list")
    assert result.returncode == 0
    assert "enron" in result.stdout
    assert "(6 corpus/corpora registered)" in result.stdout


def test_cli_corpus_list_json():
    result = _run_cli("corpus", "list", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    names = {e["name"] for e in payload}
    assert "enron" in names


def test_cli_corpus_show_known():
    result = _run_cli("corpus", "show", "enron")
    assert result.returncode == 0
    assert "name:" in result.stdout


def test_cli_corpus_show_unknown_returns_2():
    result = _run_cli("corpus", "show", "not_a_real_corpus")
    assert result.returncode == 2


def test_cli_substrate_list():
    result = _run_cli("substrate", "list")
    assert result.returncode == 0
    assert "mock" in result.stdout
    assert "kimera" in result.stdout


def test_cli_substrate_list_json():
    result = _run_cli("substrate", "list", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    names = {e["name"] for e in payload}
    assert "mock" in names
