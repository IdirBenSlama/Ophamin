"""Tests for the primitive-inspector wheel.

Exercises the catalog, the locator (against a synthetic Kimera-shaped tree
under tmp_path), and the inspector orchestrator (with discovery + audit
disabled — those touch external systems and are covered by the example
runner).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from ophamin.inspecting import (
    KNOWN_PRIMITIVES,
    PrimitiveCatalog,
    PrimitiveEntry,
    PrimitiveInspector,
    PrimitiveLocator,
    PrimitiveProfile,
)


# --------------------------------------------------------------------------
# Helpers: build a synthetic Kimera-shaped tree in tmp_path
# --------------------------------------------------------------------------


def _make_synthetic_kimera(tmp_path: Path) -> Path:
    """Build a kimera_swm/ tree with a couple of fake primitive classes."""
    swm = tmp_path / "kimera_swm"
    (swm / "domain" / "cognitive").mkdir(parents=True)
    (swm / "domain" / "security" / "gwf").mkdir(parents=True)
    (swm / "__init__.py").write_text("")
    (swm / "domain" / "__init__.py").write_text("")
    (swm / "domain" / "cognitive" / "__init__.py").write_text("")
    (swm / "domain" / "security" / "__init__.py").write_text("")
    (swm / "domain" / "security" / "gwf" / "__init__.py").write_text("")

    (swm / "domain" / "cognitive" / "walker.py").write_text(textwrap.dedent('''
        """Module-level docstring."""
        from typing import Any

        class PrimeTopologyWalker:
            """Physics-driven manifold traversal.

            Four modes (M1-M4)."""

            def __init__(self, graph_seed: int = 0):
                self.graph_seed = graph_seed

            def traverse(self, max_steps: int = 50) -> Any:
                ...

            def reset(self) -> None:
                ...

        class UnrelatedClass:
            """Should not match."""
            pass
    ''').strip())

    (swm / "domain" / "security" / "gwf" / "protocol.py").write_text(textwrap.dedent('''
        """The Gyroscopic Water Fortress immune membrane."""
        from dataclasses import dataclass

        @dataclass
        class GWFVerdict:
            allowed: bool

        class GWFProtocol:
            """Immune membrane."""
            def screen_input(self, features, baseline) -> GWFVerdict:
                return GWFVerdict(allowed=True)
    ''').strip())

    # a caller file that references PrimeTopologyWalker by name
    (swm / "domain" / "cognitive" / "uses_walker.py").write_text(textwrap.dedent('''
        from kimera_swm.domain.cognitive.walker import PrimeTopologyWalker

        def make() -> PrimeTopologyWalker:
            return PrimeTopologyWalker(graph_seed=1)
    ''').strip())
    return tmp_path


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------


def test_known_primitives_has_expected_entries():
    names = {e.name for e in KNOWN_PRIMITIVES}
    # spot-check a handful — these MUST stay catalogued
    for required in ("Walker", "GWF", "Rosetta", "Arachne", "Ouroboros"):
        assert required in names


def test_primitive_catalog_lookup_by_name_and_class():
    cat = PrimitiveCatalog()
    walker = cat.by_name("Walker")
    assert walker is not None
    assert walker.canonical_class == "PrimeTopologyWalker"
    # lookup by class name should also work
    same = cat.by_name("PrimeTopologyWalker")
    assert same is walker


def test_primitive_catalog_lookup_is_case_insensitive():
    cat = PrimitiveCatalog()
    assert cat.by_name("walker") is not None
    assert cat.by_name("WALKER") is not None
    assert cat.by_name(" walker ") is not None


def test_primitive_catalog_unknown_returns_none():
    cat = PrimitiveCatalog()
    assert cat.by_name("DoesNotExist") is None


def test_primitive_catalog_by_family():
    cat = PrimitiveCatalog()
    brain = cat.by_family("brain")
    assert any(e.name == "Takwin" for e in brain)
    assert any(e.name == "Walker" for e in brain)


def test_primitive_catalog_register_rejects_duplicate():
    cat = PrimitiveCatalog()
    with pytest.raises(ValueError, match="already registered"):
        cat.register(PrimitiveEntry(
            name="Walker",
            canonical_class="OtherClass",
            canonical_module="x",
            family_tags=(),
        ))


def test_primitive_catalog_register_accepts_new_primitive():
    cat = PrimitiveCatalog()
    entry = PrimitiveEntry(
        name="TestPrimitive",
        canonical_class="TestPrimitiveClass",
        canonical_module="x.y",
        family_tags=("test",),
    )
    cat.register(entry)
    assert cat.by_name("TestPrimitive") is entry
    assert "test" in {tag for e in cat for tag in e.family_tags}


# --------------------------------------------------------------------------
# Locator
# --------------------------------------------------------------------------


def test_locator_rejects_missing_repo(tmp_path):
    with pytest.raises(NotADirectoryError):
        PrimitiveLocator(tmp_path / "nope")


def test_locator_rejects_non_kimera_dir(tmp_path):
    # no kimera_swm/ under it
    with pytest.raises(NotADirectoryError, match="kimera_swm"):
        PrimitiveLocator(tmp_path)


def test_locator_finds_class_and_extracts_metadata(tmp_path):
    repo = _make_synthetic_kimera(tmp_path)
    loc = PrimitiveLocator(repo)
    result = loc.locate("PrimeTopologyWalker")
    assert result.found is True
    assert result.source_file.endswith("walker.py")
    assert result.source_line > 0
    assert "Physics-driven manifold traversal" in result.docstring
    # methods extracted
    assert "__init__" in result.method_names
    assert "traverse" in result.method_names
    assert "reset" in result.method_names
    # caller count includes the class def itself + the uses_walker.py file
    assert result.n_callers >= 2


def test_locator_returns_unfound_with_caller_count_for_unknown_class(tmp_path):
    repo = _make_synthetic_kimera(tmp_path)
    loc = PrimitiveLocator(repo)
    result = loc.locate("DoesNotExist")
    assert result.found is False
    assert result.source_file == ""
    assert result.source_line == 0
    assert result.n_callers == 0
    assert result.notes  # has a "not located" note


def test_locator_extracts_imports_and_parent_classes(tmp_path):
    repo = _make_synthetic_kimera(tmp_path)
    loc = PrimitiveLocator(repo)
    result = loc.locate("GWFProtocol")
    assert result.found is True
    # imports include dataclasses
    assert any("dataclass" in imp for imp in result.imports)
    # GWFProtocol has no explicit parents in the synthetic source
    assert result.parent_classes == ()


def test_locator_does_not_match_partial_class_name(tmp_path):
    """Lookup for 'Walker' alone shouldn't match 'PrimeTopologyWalker'."""
    repo = _make_synthetic_kimera(tmp_path)
    loc = PrimitiveLocator(repo)
    result = loc.locate("Walker")
    # the regex requires `class Walker(...):` so PrimeTopologyWalker does NOT match
    assert result.found is False


# --------------------------------------------------------------------------
# Inspector
# --------------------------------------------------------------------------


def test_inspector_produces_profile_for_known_primitive(tmp_path):
    repo = _make_synthetic_kimera(tmp_path)
    # build a tiny catalog with one entry matching our synthetic tree
    catalog = PrimitiveCatalog(entries=[
        PrimitiveEntry(
            name="Walker",
            canonical_class="PrimeTopologyWalker",
            canonical_module="domain.cognitive.walker",
            family_tags=("brain", "topology"),
        ),
    ])
    inspector = PrimitiveInspector(repo, catalog=catalog)
    profile = inspector.inspect("Walker")
    assert isinstance(profile, PrimitiveProfile)
    assert profile.canonical_class == "PrimeTopologyWalker"
    assert profile.source_file.endswith("walker.py")
    assert "Physics-driven" in profile.docstring
    assert profile.family_tags == ("brain", "topology")
    assert profile.n_callers >= 2
    assert profile.kimera_repo == str(repo.resolve())


def test_inspector_handles_unknown_primitive_gracefully(tmp_path):
    repo = _make_synthetic_kimera(tmp_path)
    inspector = PrimitiveInspector(repo, catalog=PrimitiveCatalog(entries=[]))
    profile = inspector.inspect("NonExistentClass")
    assert profile.name == "NonExistentClass"
    assert profile.canonical_class == "NonExistentClass"
    assert profile.source_file == ""
    assert profile.notes  # has the "not located" note


def test_inspector_inspect_all_filters_by_family(tmp_path):
    repo = _make_synthetic_kimera(tmp_path)
    catalog = PrimitiveCatalog(entries=[
        PrimitiveEntry("Walker", "PrimeTopologyWalker", "x", ("brain",)),
        PrimitiveEntry("GWF", "GWFProtocol", "y", ("defence",)),
        PrimitiveEntry("Other", "OtherClass", "z", ("brain",)),
    ])
    inspector = PrimitiveInspector(repo, catalog=catalog)
    brain_profiles = inspector.inspect_all(family_filter="brain")
    assert len(brain_profiles) == 2
    assert {p.name for p in brain_profiles} == {"Walker", "Other"}


def test_inspector_inspect_all_returns_all_when_no_filter(tmp_path):
    repo = _make_synthetic_kimera(tmp_path)
    catalog = PrimitiveCatalog(entries=[
        PrimitiveEntry("Walker", "PrimeTopologyWalker", "x", ("brain",)),
        PrimitiveEntry("GWF", "GWFProtocol", "y", ("defence",)),
    ])
    inspector = PrimitiveInspector(repo, catalog=catalog)
    profiles = inspector.inspect_all()
    assert len(profiles) == 2


# --------------------------------------------------------------------------
# Profile serialization
# --------------------------------------------------------------------------


def test_profile_to_dict_round_trips_through_json(tmp_path):
    profile = PrimitiveProfile(
        name="Walker",
        canonical_class="PrimeTopologyWalker",
        family_tags=("brain", "topology"),
        source_file="domain/cognitive/walker.py",
        source_line=12,
        docstring="Physics-driven manifold traversal.",
        method_names=("__init__", "traverse", "reset"),
        adapter_target="walker",
    )
    payload = json.loads(profile.to_json())
    assert payload["name"] == "Walker"
    assert payload["static"]["source_file"] == "domain/cognitive/walker.py"
    assert payload["adapter"]["target"] == "walker"


def test_profile_to_markdown_renders(tmp_path):
    profile = PrimitiveProfile(
        name="Walker",
        canonical_class="PrimeTopologyWalker",
        family_tags=("brain", "topology"),
        source_file="domain/cognitive/walker.py",
        source_line=12,
        docstring="Physics-driven manifold traversal.",
        method_names=("traverse", "reset"),
    )
    md = profile.to_markdown()
    assert "# Primitive Profile" in md
    assert "Walker" in md
    assert "traverse" in md
    assert "domain/cognitive/walker.py" in md


def test_profile_to_markdown_handles_missing_source():
    profile = PrimitiveProfile(
        name="Phantom",
        canonical_class="Phantom",
        family_tags=(),
        source_file="",
        notes=("not located",),
    )
    md = profile.to_markdown()
    assert "Phantom" in md
    assert "_class definition not located" in md
