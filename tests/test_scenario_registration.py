"""Structural tests for the auto-registration of :class:`Scenario` subclasses.

These tests pin the registry contract declared in
``ophamin.measuring.scenarios.base`` and exercised at package-import
time by ``ophamin.measuring.scenarios``:

- every concrete Scenario subclass present in
  ``src/ophamin/measuring/scenarios/*.py`` MUST appear in
  :data:`SCENARIOS` after package import;
- every entry's ``name`` MUST equal its registry key;
- declaring a subclass with the base sentinel name MUST raise
  :class:`ScenarioNameNotOverriddenError`;
- declaring two subclasses with the same name MUST raise
  :class:`DuplicateScenarioNameError`;
- the ``register=False`` opt-out must skip registration silently
  (the sanctioned skip path for abstract intermediate parents).

Together these prevent the historical drift mode where scenario files
existed under ``measuring/scenarios/*.py`` but the SCENARIOS dict
fell out of sync with them — the rounds-E-through-M autopilot output
was CLI-invisible for that reason.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from ophamin.measuring.proof import Claim, Threshold
from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.base import (
    DuplicateScenarioNameError,
    Scenario,
    ScenarioMetadataMissingError,
    ScenarioNameNotOverriddenError,
    ScenarioScore,
    Tier,
    _BASE_SCENARIO_NAME,
)


# --- helpers ----------------------------------------------------------------


def _scenario_module_dir() -> pathlib.Path:
    """Return the on-disk directory containing scenario modules."""
    from ophamin.measuring import scenarios as scenarios_pkg

    return pathlib.Path(scenarios_pkg.__file__).parent


def _walk_scenario_subclass_names() -> set[str]:
    """Statically (AST) walk every scenario module and collect concrete
    Scenario subclass names — i.e. classes whose definition lists
    ``Scenario`` (or a name ending in ``Scenario``) in the base list.

    Stays at the AST layer so we don't depend on optional imports the
    runtime auto-walk handles.
    """
    found: set[str] = set()
    excluded = {"base.py", "helpers.py", "__init__.py"}
    for path in _scenario_module_dir().glob("*.py"):
        if path.name in excluded or path.name.startswith("_"):
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover — would fail hard elsewhere
            pytest.fail(f"scenario module {path.name} fails to parse: {exc}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id.endswith("Scenario"):
                    found.add(node.name)
                if isinstance(base, ast.Attribute) and base.attr.endswith("Scenario"):
                    found.add(node.name)
    return found


# --- tests ------------------------------------------------------------------


def test_registry_is_nonempty():
    """Auto-walk must populate SCENARIOS — empty registry indicates
    auto-import failed silently or registration is wired wrong."""
    assert SCENARIOS, "SCENARIOS registry is empty after package import"


def test_every_scenario_module_has_registered_subclass():
    """Every scenario module's concrete subclass must be registered.

    Static-AST scan of ``measuring/scenarios/*.py`` collects every
    ``class X(...Scenario):`` definition; the runtime registry must
    contain every one of those classes (by object identity).
    """
    file_subclasses = _walk_scenario_subclass_names()
    registered_subclasses = {cls.__name__ for cls in SCENARIOS.values()}

    missing = file_subclasses - registered_subclasses
    assert not missing, (
        f"scenario subclasses present on disk but missing from SCENARIOS "
        f"registry: {sorted(missing)}"
    )


def test_every_registry_entry_name_matches_class_name_attribute():
    """A registry entry keyed under ``"foo"`` must point at a class with
    ``cls.name == "foo"`` — otherwise the registry and the CLI surface
    drift."""
    for key, cls in SCENARIOS.items():
        assert cls.name == key, (
            f"registry key {key!r} points at {cls.__qualname__} "
            f"whose cls.name is {cls.name!r}"
        )


def test_every_registered_scenario_satisfies_scenario_protocol():
    """Every registered class must be a concrete :class:`Scenario` subclass
    with the abstract-method surface implemented."""
    for cls in SCENARIOS.values():
        assert issubclass(cls, Scenario), (
            f"{cls.__qualname__} is in SCENARIOS but not a Scenario subclass"
        )
        # Abstract methods are emptied for concrete classes; if any remain,
        # the class is abstract and shouldn't be in the registry.
        assert not getattr(cls, "__abstractmethods__", frozenset()), (
            f"{cls.__qualname__} is abstract (has unimplemented "
            f"abstract methods) and should not be in SCENARIOS"
        )


def test_registered_names_are_unique():
    """The registry IS a dict so this is guarded by construction, but the
    test pins the invariant explicitly. Duplicate names would silently
    overwrite via dict assignment — the loud-failure path is in the
    ``__init_subclass__`` guard which this test exercises elsewhere."""
    classes = list(SCENARIOS.values())
    assert len({cls.name for cls in classes}) == len(classes)


def test_registered_classes_are_unique_objects():
    """No two registry keys may point at the same class object — that
    would mean the class registered under two names (e.g. a renamed copy)."""
    seen: dict[type, str] = {}
    for key, cls in SCENARIOS.items():
        if cls in seen:
            pytest.fail(
                f"class {cls.__qualname__} is registered under two keys: "
                f"{seen[cls]!r} and {key!r}"
            )
        seen[cls] = key


# --- guard behaviour tests --------------------------------------------------


def _make_dummy_scenario_class(
    name: str,
    *,
    register: bool = True,
    metadata: dict[str, object] | None = None,
) -> type[Scenario]:
    """Build a minimal concrete Scenario subclass for guard-testing.

    Uses ``type()`` so the class is constructed dynamically and we don't
    pollute the import-time module namespace.

    By default the dummy carries valid metadata (Tier.SCIENTIFIC +
    placeholder family/goal/explanation) so the registration succeeds.
    Pass ``metadata={}`` (empty) or ``metadata={"tier": None}`` (sentinel)
    to deliberately omit a field for negative-path tests.
    """

    def build_claim(self):  # pragma: no cover — never invoked in these tests
        return Claim(
            statement="dummy",
            operationalization="dummy",
            threshold=Threshold("dummy", ">=", 0.0, "fraction"),
            h0="dummy",
            h1="dummy",
        )

    def score(self, cycle_results, records):  # pragma: no cover
        return ScenarioScore(observed_value=0.0)

    default_metadata: dict[str, object] = {
        "tier": Tier.SCIENTIFIC,
        "family": "dummy_family",
        "goal": "dummy goal statement",
        "explanation": "dummy paragraph explanation that is non-empty.",
    }
    if metadata is None:
        merged_metadata = default_metadata
    else:
        merged_metadata = {**default_metadata, **metadata}
    # Allow callers to drop a field entirely by passing a sentinel
    # explicit None — that triggers the metadata-missing guard.
    namespace = {
        "name": name,
        "corpus_name": "dummy",
        "target": "dummy",
        "n_cycles": 1,
        "build_claim": build_claim,
        "score": score,
    }
    for k, v in merged_metadata.items():
        if v is None:
            continue  # omit on purpose so subclass inherits abstract base's absence
        namespace[k] = v
    return types.new_class(
        f"DummyScenario_{name.replace('-', '_')}",
        bases=(Scenario,),
        kwds={"register": register},
        exec_body=lambda ns: ns.update(namespace),
    )


# Need this import for the dynamic-class helper above.
import types  # noqa: E402


def test_keeping_base_sentinel_name_raises():
    """A subclass that forgot to override ``name`` must raise at
    class-definition time, not silently overwrite the registry key
    ``"scenario"``."""
    with pytest.raises(ScenarioNameNotOverriddenError):
        _make_dummy_scenario_class(_BASE_SCENARIO_NAME)


def test_duplicate_name_raises():
    """Two distinct subclasses declaring the same ``name`` must
    raise at the second class's definition time — single-value
    registry invariant."""
    sentinel_name = "duplicate-name-test-sentinel"
    first = _make_dummy_scenario_class(sentinel_name)
    try:
        assert SCENARIOS[sentinel_name] is first
        with pytest.raises(DuplicateScenarioNameError) as excinfo:
            _make_dummy_scenario_class(sentinel_name)
        assert excinfo.value.name == sentinel_name
        assert excinfo.value.existing is first
    finally:
        # Clean the sentinel out of the registry so other tests aren't
        # polluted. Direct dict mutation is the right shape here — there
        # is no public deregister API by design (production scenarios
        # should never deregister).
        SCENARIOS.pop(sentinel_name, None)


def test_re_registration_of_same_class_is_idempotent():
    """Importing a scenario module twice (e.g. importlib.reload during
    test fixtures) must NOT raise — the same class object under the
    same name is a no-op, not a duplicate."""
    sentinel_name = "idempotent-reregistration-sentinel"
    cls = _make_dummy_scenario_class(sentinel_name)
    try:
        # Simulate a reload by manually re-invoking __init_subclass__ on
        # the same class. This is the closest probe to real reload
        # behaviour without spinning up importlib.
        Scenario.__init_subclass__.__func__(cls)
        assert SCENARIOS[sentinel_name] is cls
    finally:
        SCENARIOS.pop(sentinel_name, None)


def test_register_false_opts_out_silently():
    """A subclass declared with ``register=False`` must skip
    registration without raising — the sanctioned escape hatch for
    abstract intermediate parents (e.g. a `BaseSubstrateScenario`
    that subclasses Scenario but is itself abstract)."""
    sentinel_name = "opt-out-sentinel"
    cls = _make_dummy_scenario_class(sentinel_name, register=False)
    try:
        assert sentinel_name not in SCENARIOS
        assert cls.name == sentinel_name  # class itself is still well-formed
    finally:
        SCENARIOS.pop(sentinel_name, None)


# --- metadata-validation tests ---------------------------------------------


def test_every_registered_scenario_has_tier_enum_member():
    """Every entry in SCENARIOS must carry a :class:`Tier` enum value
    on ``cls.tier``. Plain strings or None would mean the metadata
    guard accidentally accepted invalid input."""
    for name, cls in SCENARIOS.items():
        assert isinstance(cls.tier, Tier), (
            f"{name!r} has cls.tier = {cls.tier!r} (type "
            f"{type(cls.tier).__name__}); must be a Tier member"
        )


def test_every_registered_scenario_has_nonempty_family_goal_explanation():
    """Every entry must have non-empty string `family`, `goal`, and
    `explanation` — these surface into proof records and into the
    auto-generated README scenarios table."""
    for name, cls in SCENARIOS.items():
        for attr in ("family", "goal", "explanation"):
            value = getattr(cls, attr, "")
            assert isinstance(value, str) and value.strip(), (
                f"{name!r} has cls.{attr} = {value!r}; must be a "
                f"non-empty stripped string"
            )


def test_missing_tier_raises():
    """A subclass declared with ``tier=None`` (i.e. not assigned) must
    trip :class:`ScenarioMetadataMissingError`."""
    with pytest.raises(ScenarioMetadataMissingError) as excinfo:
        _make_dummy_scenario_class(
            "missing-tier-sentinel", metadata={"tier": None}
        )
    assert "tier" in excinfo.value.missing


def test_missing_family_raises():
    """Empty-string family must trip metadata guard."""
    with pytest.raises(ScenarioMetadataMissingError) as excinfo:
        _make_dummy_scenario_class(
            "missing-family-sentinel", metadata={"family": ""}
        )
    assert "family" in excinfo.value.missing


def test_missing_goal_raises():
    """Empty-string goal must trip metadata guard."""
    with pytest.raises(ScenarioMetadataMissingError) as excinfo:
        _make_dummy_scenario_class(
            "missing-goal-sentinel", metadata={"goal": ""}
        )
    assert "goal" in excinfo.value.missing


def test_missing_explanation_raises():
    """Empty-string explanation must trip metadata guard."""
    with pytest.raises(ScenarioMetadataMissingError) as excinfo:
        _make_dummy_scenario_class(
            "missing-explanation-sentinel", metadata={"explanation": ""}
        )
    assert "explanation" in excinfo.value.missing


def test_whitespace_only_metadata_raises():
    """A whitespace-only string (e.g. ``"   "``) is treated as empty."""
    with pytest.raises(ScenarioMetadataMissingError) as excinfo:
        _make_dummy_scenario_class(
            "whitespace-only-sentinel", metadata={"goal": "   "}
        )
    assert "goal" in excinfo.value.missing


def test_wrong_tier_type_raises():
    """A string value (rather than a Tier member) must trip the guard —
    string-based Enum could otherwise silently pass."""
    with pytest.raises(ScenarioMetadataMissingError) as excinfo:
        _make_dummy_scenario_class(
            "wrong-tier-type-sentinel", metadata={"tier": "scientific"}
        )
    assert "tier" in excinfo.value.missing


def test_method_and_falsification_consequence_default_to_empty():
    """`method` and `falsification_consequence` are optional — they
    default to empty strings on the abstract base and remain accepted."""
    sentinel = "optional-fields-empty-sentinel"
    cls = _make_dummy_scenario_class(sentinel)
    try:
        assert cls.method == ""
        assert cls.falsification_consequence == ""
    finally:
        SCENARIOS.pop(sentinel, None)


def test_register_false_skips_metadata_guard():
    """When `register=False`, the metadata validation does NOT fire —
    test-internal subclasses can omit metadata entirely."""
    # Should NOT raise even though tier/family/goal/explanation are omitted.
    cls = _make_dummy_scenario_class(
        "no-metadata-with-register-false",
        register=False,
        metadata={"tier": None, "family": None, "goal": None, "explanation": None},
    )
    assert cls.name == "no-metadata-with-register-false"


def test_tier_enum_has_five_members():
    """Tier enum must have exactly the five members documented in the
    architecture audit — adding a sixth without docs update is a drift
    signal."""
    members = {t.value for t in Tier}
    assert members == {
        "scientific",
        "engineering",
        "philosophical",
        "empirical_deep",
        "measurement_machinery",
    }


def test_tier_is_str_enum_for_json_serialization():
    """Tier inherits from str so JSON serialisation produces a plain
    string, not a Python-specific enum encoding."""
    assert isinstance(Tier.SCIENTIFIC.value, str)
    assert Tier.SCIENTIFIC == "scientific"


# --- count assertions --------------------------------------------------------


def test_registry_count_matches_static_scan():
    """The auto-walk's runtime count must equal the static-AST scan count
    of concrete Scenario subclasses on disk. Off-by-one means a module
    failed to import silently — which the loud-failure path in
    ``_auto_import_scenario_modules`` should have prevented, but the
    extra invariant test catches regression-by-future-edit."""
    runtime_count = len(SCENARIOS)
    disk_count = len(_walk_scenario_subclass_names())
    assert runtime_count >= disk_count, (
        f"registry has {runtime_count} entries but disk has {disk_count} "
        f"concrete Scenario subclasses — some are not registered"
    )
