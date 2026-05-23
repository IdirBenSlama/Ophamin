"""Hardening tests for the central plug-in registry (Move G).

Closes gap A + gap B from
``docs/ARCHITECTURE_INTENT_VS_REALITY_2026_05_16.md`` — the Pillar
Protocol from :mod:`ophamin.protocols` is now satisfied by every
shipped pillar adapter, and the registration surface
(:func:`ophamin.registry.register_pillar`) is the canonical
discovery + idempotency + duplicate-detection layer.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from ophamin.measuring import pillars  # noqa: F401 — fires registration
from ophamin.measuring.pillars._adapters import (
    REGISTERED_PILLARS,
    SPCPillar,
)
from ophamin.measuring.pillars.base import (
    NonUniformComputeError,
    PillarBase,
)
from ophamin.protocols import Pillar
from ophamin.registry import (
    DuplicatePluginError,
    PILLARS,
    PluginProtocolViolationError,
    get_pillar,
    get_scenario,
    list_pillars,
    list_scenarios,
    register_pillar,
)


# --- structural pins (gap A — Pillar Protocol satisfaction) ---------------


def test_pillars_registry_has_eleven_entries():
    """Every shipped adapter registered at import time."""
    assert len(PILLARS) >= 11
    expected = {
        "O.spc",
        "O.srm",
        "O.drift",
        "A.sprt",
        "M.mixed_effects",
        "M.mea",
        "I.cma",
        "N.cross_validation",
        "diagnostics.anticipatory",
        "diagnostics.inertia",
        "diagnostics.kernel_coupling",
    }
    assert expected.issubset(PILLARS.keys())


def test_every_registered_pillar_satisfies_pillar_protocol():
    """isinstance(p, Pillar) returns True for every adapter — the
    Protocol contract is structurally enforced."""
    for name, pillar in PILLARS.items():
        assert isinstance(pillar, Pillar), (
            f"{name!r} ({type(pillar).__qualname__}) does not satisfy "
            f"the runtime Pillar Protocol"
        )


def test_every_registered_pillar_is_pillar_base_instance():
    """Every adapter inherits from PillarBase (the ABC used to share
    code) — Protocol satisfaction is structural, this is the ABC anchor."""
    for name, pillar in PILLARS.items():
        assert isinstance(pillar, PillarBase), (
            f"{name!r} is in PILLARS but not a PillarBase subclass instance"
        )


def test_every_registered_pillar_has_nonempty_metadata():
    for name, pillar in PILLARS.items():
        assert pillar.pillar_name == name
        assert pillar.library, f"{name!r} has empty library attribution"
        assert pillar.library_version, f"{name!r} has empty library_version"


def test_pillar_library_versions_are_resolved_from_metadata():
    """At least one well-known library version matches the installed
    distribution version — pins that _pkg_version() is actually wiring
    the resolution."""
    import importlib.metadata as md
    expected_numpy = md.version("numpy")
    spc = PILLARS["O.spc"]
    assert spc.library_version == expected_numpy


# --- list / get / sort order ----------------------------------------------


def test_list_pillars_returns_sorted_order():
    """list_pillars() yields in pillar-name-sorted order."""
    yielded = [p.pillar_name for p in list_pillars()]
    assert yielded == sorted(yielded)


def test_get_pillar_returns_registered_instance():
    p = get_pillar("O.spc")
    assert isinstance(p, SPCPillar)


def test_get_pillar_unknown_name_raises_keyerror():
    with pytest.raises(KeyError) as excinfo:
        get_pillar("totally-fictional-pillar")
    assert "available:" in str(excinfo.value)


# --- registration guards --------------------------------------------------


def test_register_pillar_rejects_non_protocol_object():
    """A plain object without the required attributes is rejected."""
    class NotAPillar:
        pass
    with pytest.raises(PluginProtocolViolationError):
        register_pillar(NotAPillar())  # type: ignore[arg-type]


def test_register_pillar_idempotent_for_same_object():
    """Re-registering the exact same object under the same name is a no-op."""
    existing = PILLARS["O.spc"]
    register_pillar(existing)  # idempotent
    assert PILLARS["O.spc"] is existing


def test_register_pillar_rejects_duplicate_name():
    """A different object under an existing name triggers DuplicatePluginError."""
    duplicate = SPCPillar()  # same pillar_name as the already-registered one
    with pytest.raises(DuplicatePluginError) as excinfo:
        register_pillar(duplicate)
    assert excinfo.value.kind == "pillar"
    assert excinfo.value.key == "O.spc"


def test_register_pillar_with_test_pillar_then_clean_up():
    """Register + use + manual deregister via dict mutation. There is
    no public deregister API by design — production pillars stay
    registered; this dict-mutation pattern is acceptable for tests."""
    class TestOnlyPillar(PillarBase):
        pillar_name = "test.only.sentinel"
        library = "unknown"
        library_version = "1.0"

        def compute(self, cycle_results, records=None, **kwargs):
            return None

    try:
        register_pillar(TestOnlyPillar())
        assert "test.only.sentinel" in PILLARS
        assert isinstance(PILLARS["test.only.sentinel"], TestOnlyPillar)
    finally:
        PILLARS.pop("test.only.sentinel", None)


# --- NonUniformComputeError ------------------------------------------------


def test_compute_raises_non_uniform_for_pillars_that_dont_fit():
    """Pillars that can't honour the uniform compute(cycle_results) shape
    raise NonUniformComputeError pointing at the canonical API."""
    with pytest.raises(NonUniformComputeError) as excinfo:
        PILLARS["O.spc"].compute(cycle_results=[])
    assert "IndividualsChart" in str(excinfo.value) or "XbarRChart" in str(excinfo.value)


def test_non_uniform_compute_error_is_notimplementederror_subclass():
    """NonUniformComputeError inherits from NotImplementedError —
    callers handling NotImplementedError naturally catch it."""
    assert issubclass(NonUniformComputeError, NotImplementedError)


# --- registered tuple matches dict ------------------------------------------


def test_registered_tuple_matches_pillars_dict_membership():
    for adapter in REGISTERED_PILLARS:
        assert PILLARS[adapter.pillar_name] is adapter


def test_registered_tuple_length_is_eleven():
    assert len(REGISTERED_PILLARS) == 11


# --- scenario registry surface re-export ----------------------------------


def test_get_scenario_re_exports_scenarios_dict():
    """get_scenario in the registry mirrors the SCENARIOS dict."""
    from ophamin.measuring.scenarios import SCENARIOS
    for name in SCENARIOS:
        assert get_scenario(name) is SCENARIOS[name]


def test_list_scenarios_yields_in_name_sorted_order():
    yielded = [cls.name for cls in list_scenarios()]
    assert yielded == sorted(yielded)


def test_get_scenario_unknown_name_raises_keyerror():
    with pytest.raises(KeyError):
        get_scenario("not-a-real-scenario")


# --- CLI smoke -------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "pillar", *args],
        capture_output=True,
        text=True,
    )


def test_cli_pillar_list_human():
    result = _run_cli("list")
    assert result.returncode == 0
    assert "pillar_name" in result.stdout
    assert "O.spc" in result.stdout
    assert "(11 pillar(s) registered)" in result.stdout


def test_cli_pillar_list_json():
    result = _run_cli("list", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert len(payload) == 11
    names = {e["name"] for e in payload}
    assert "O.spc" in names


def test_cli_pillar_show_known_name():
    result = _run_cli("show", "O.spc")
    assert result.returncode == 0
    assert "pillar_name:       O.spc" in result.stdout
    assert "library:           numpy" in result.stdout
    assert "protocol_check:    isinstance(pillar, Pillar) = True" in result.stdout


def test_cli_pillar_show_unknown_name_returns_2():
    result = _run_cli("show", "totally-fictional-pillar")
    assert result.returncode == 2
    assert "unknown pillar" in result.stderr


def test_cli_pillar_missing_action_fails():
    """Bare `ophamin pillar` requires an action."""
    result = subprocess.run(
        [sys.executable, "-m", "ophamin.cli", "pillar"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
