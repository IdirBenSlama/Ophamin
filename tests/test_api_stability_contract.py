"""The API stability contract — RFC 0002 Phase E8.

Two layers of regression-pinning live here:

1. **Tier coverage** — every public symbol re-exported from
   :mod:`ophamin` (or named in this test's `_LOAD_BEARING` list)
   MUST carry a :class:`StabilityInfo` annotation. The test fails
   loud at PR time if a public symbol drifts un-tagged. This is the
   gate that keeps the policy from rotting.

2. **Signature pinning** — for every symbol declared at tier
   :class:`Stable`, the test inspects its public signature and
   compares against a pinned canonical-form representation captured
   here. The contract:
     * adding optional parameters with defaults is allowed
       (the test ignores params with defaults at the END);
     * renames, removals, type-narrowing of required params,
       changing positional-only / keyword-only status all fail
       the suite.
   When you intentionally extend a Stable API at minor, regenerate
   the pin by running the test once with `OPHAMIN_REGENERATE_API_PINS=1`
   in the environment + commit the updated _STABLE_SIGNATURE_PINS.

Reference: RFC 0002 §3.2 + `src/ophamin/_stability.py` for the tier
mechanics; `docs/STABILITY.md` for the consumer-facing policy.
"""

from __future__ import annotations

import inspect
import os
from typing import Any

import pytest

from ophamin._stability import (
    TIERS,
    StabilityInfo,
    get_stability,
)


# Symbols that MUST carry a stability annotation. Sourced from
# ``ophamin.__all__`` + the load-bearing campaign / FWER public API.
# Treating this as an explicit allow-list (rather than re-scanning
# every module's __all__) keeps the contract auditable in one place.
_LOAD_BEARING_PUBLIC: tuple[tuple[str, str], ...] = (
    # ophamin top-level re-exports
    ("ophamin", "EmpiricalProofRecord"),
    ("ophamin", "Claim"),
    ("ophamin", "Threshold"),
    ("ophamin", "PreRegistration"),
    ("ophamin", "PillarEvidence"),
    ("ophamin", "Verdict"),
    ("ophamin", "CycleResult"),
    ("ophamin", "SubstrateUnderTest"),
    ("ophamin", "MetricBundle"),
    ("ophamin", "Tier1Metrics"),
    ("ophamin", "Tier2Metrics"),
    ("ophamin", "Tier3Metrics"),
    # campaign
    ("ophamin.campaign", "CampaignRecord"),
    ("ophamin.campaign", "CampaignPhase"),
    ("ophamin.campaign", "run_campaign"),
    ("ophamin.campaign", "correction_family_from_directory"),
    ("ophamin.campaign", "dump_campaign"),
    ("ophamin.campaign", "load_campaign"),
    # FWER (Phase E2)
    ("ophamin.comparing.fwer", "CorrectionInput"),
    ("ophamin.comparing.fwer", "CorrectionResult"),
    ("ophamin.comparing.fwer", "CorrectionFamily"),
    ("ophamin.comparing.fwer", "apply_correction"),
    ("ophamin.comparing.fwer", "holm_bonferroni"),
    ("ophamin.comparing.fwer", "benjamini_hochberg"),
    ("ophamin.comparing.fwer", "no_correction"),
)


# Signature pins for @Stable callables. The pin is a list of
# (name, kind, has_default) tuples — comparing this canonical form
# detects renames, removals, and kind changes regardless of formatting.
# Regenerate via `OPHAMIN_REGENERATE_API_PINS=1 pytest ... -k regenerate`
# below + commit the updated dict.
#
# Functions only — classes are pinned via their __init__ signature in a
# separate test.
_STABLE_SIGNATURE_PINS: dict[str, tuple[tuple[str, str, bool], ...]] = {
    "ophamin.campaign.run_campaign": (
        ("substrate", "KEYWORD_ONLY", False),
        ("target_name", "KEYWORD_ONLY", True),
        ("target_git_commit", "KEYWORD_ONLY", True),
        ("scenarios", "KEYWORD_ONLY", True),
        ("enable_phases", "KEYWORD_ONLY", True),
        ("out_dir", "KEYWORD_ONLY", True),
        ("sign_key", "KEYWORD_ONLY", True),
        ("fwer_method", "KEYWORD_ONLY", True),
        ("fwer_alpha", "KEYWORD_ONLY", True),
    ),
    "ophamin.campaign.correction_family_from_directory": (
        ("proofs_dir", "POSITIONAL_OR_KEYWORD", False),
        ("method", "KEYWORD_ONLY", True),
        ("alpha", "KEYWORD_ONLY", True),
    ),
    "ophamin.campaign.dump_campaign": (
        ("record", "POSITIONAL_OR_KEYWORD", False),
        ("path", "POSITIONAL_OR_KEYWORD", False),
    ),
    "ophamin.campaign.load_campaign": (
        ("path", "POSITIONAL_OR_KEYWORD", False),
    ),
    "ophamin.comparing.fwer.apply_correction": (
        ("inputs", "POSITIONAL_OR_KEYWORD", False),
        ("method", "KEYWORD_ONLY", True),
        ("alpha", "KEYWORD_ONLY", True),
    ),
    "ophamin.comparing.fwer.holm_bonferroni": (
        ("inputs", "POSITIONAL_OR_KEYWORD", False),
        ("alpha", "KEYWORD_ONLY", True),
    ),
    "ophamin.comparing.fwer.benjamini_hochberg": (
        ("inputs", "POSITIONAL_OR_KEYWORD", False),
        ("alpha", "KEYWORD_ONLY", True),
    ),
    "ophamin.comparing.fwer.no_correction": (
        ("inputs", "POSITIONAL_OR_KEYWORD", False),
        ("alpha", "KEYWORD_ONLY", True),
    ),
}


def _resolve(modname: str, symbol: str) -> Any:
    """Import ``modname`` and return ``getattr(mod, symbol)``."""
    import importlib

    mod = importlib.import_module(modname)
    return getattr(mod, symbol)


def _signature_pin(callable_obj: Any) -> tuple[tuple[str, str, bool], ...]:
    """Canonical-form pin: ``(name, kind_name, has_default)`` per param.

    Skips ``self`` / ``cls`` so the comparison works for both functions
    and method-callable classes.
    """
    sig = inspect.signature(callable_obj)
    out: list[tuple[str, str, bool]] = []
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        # VAR_POSITIONAL / VAR_KEYWORD (*args / **kwargs) are recorded
        # as-is — adding *args / **kwargs is API-extending; removing
        # them is API-shrinking. Their "default" is meaningless.
        has_default = param.default is not inspect.Parameter.empty
        out.append((name, param.kind.name, has_default))
    return tuple(out)


# ---------------------------------------------------------------------------
# Layer 1 — tier coverage: every load-bearing symbol must be annotated
# ---------------------------------------------------------------------------


class TestTierCoverage:
    """The 'no public symbol drifts un-tagged' gate."""

    @pytest.mark.parametrize("modname,symbol", _LOAD_BEARING_PUBLIC)
    def test_each_load_bearing_symbol_carries_stability_info(
        self, modname: str, symbol: str
    ) -> None:
        obj = _resolve(modname, symbol)
        info = get_stability(obj)
        assert info is not None, (
            f"{modname}.{symbol} is in the load-bearing public-API list "
            f"but carries no StabilityInfo. Tag it with one of "
            f"@Stable / @Provisional / @Internal / @Deprecated, or remove "
            f"it from _LOAD_BEARING_PUBLIC if it's no longer public."
        )

    @pytest.mark.parametrize("modname,symbol", _LOAD_BEARING_PUBLIC)
    def test_load_bearing_tier_is_stable_or_provisional(
        self, modname: str, symbol: str
    ) -> None:
        """Load-bearing symbols are Stable or Provisional, never Internal."""
        obj = _resolve(modname, symbol)
        info = get_stability(obj)
        assert info is not None
        assert info.tier in ("Stable", "Provisional"), (
            f"{modname}.{symbol} is load-bearing but tagged {info.tier!r}. "
            f"Public-facing symbols must be Stable or Provisional."
        )


# ---------------------------------------------------------------------------
# Layer 2 — signature pinning for Stable callables
# ---------------------------------------------------------------------------


class TestSignaturePins:
    """Detect renames, removals, kind changes on @Stable callables.

    Adding optional parameters with defaults is allowed — the regenerate
    helper at the bottom of this module shows the workflow when you do
    extend a Stable API at minor.
    """

    @pytest.mark.parametrize("fq_name,expected", list(_STABLE_SIGNATURE_PINS.items()))
    def test_signature_matches_pin(
        self, fq_name: str, expected: tuple[tuple[str, str, bool], ...]
    ) -> None:
        modname, _, symbol = fq_name.rpartition(".")
        obj = _resolve(modname, symbol)
        actual = _signature_pin(obj)
        assert actual == expected, (
            f"{fq_name} signature changed.\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual}\n"
            f"If the change is intentional (additive only at minor; "
            f"breaking at major with deprecation cycle), regenerate the "
            f"pin in _STABLE_SIGNATURE_PINS at the top of this file."
        )


# ---------------------------------------------------------------------------
# Layer 3 — StabilityInfo invariants
# ---------------------------------------------------------------------------


class TestStabilityInfo:
    """Smoke + invariants on the data class itself."""

    @pytest.mark.parametrize("tier", sorted(TIERS))
    def test_each_tier_constructs(self, tier: str) -> None:
        kwargs: dict[str, Any] = {"tier": tier}
        if tier == "Deprecated":
            kwargs["removal_version"] = "2.0.0"
        info = StabilityInfo(**kwargs)
        assert info.tier == tier

    def test_unknown_tier_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            StabilityInfo(tier="Experimental")

    def test_removal_version_only_for_deprecated(self) -> None:
        with pytest.raises(ValueError, match="only meaningful for tier='Deprecated'"):
            StabilityInfo(tier="Stable", removal_version="1.0.0")

    def test_replacement_only_for_deprecated(self) -> None:
        with pytest.raises(ValueError, match="only meaningful for tier='Deprecated'"):
            StabilityInfo(tier="Stable", replacement="ophamin.new_thing")


# ---------------------------------------------------------------------------
# Regeneration helper — opt-in via env var
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("OPHAMIN_REGENERATE_API_PINS") != "1",
    reason="Only runs when OPHAMIN_REGENERATE_API_PINS=1; opt-in API-pin regen.",
)
def test_regenerate_signature_pins_emits_paste_block(capsys: pytest.CaptureFixture[str]) -> None:
    """Emit a fresh _STABLE_SIGNATURE_PINS literal to stdout.

    Run::

        OPHAMIN_REGENERATE_API_PINS=1 pytest tests/test_api_stability_contract.py \\
            -k test_regenerate -s

    Paste the printed block into _STABLE_SIGNATURE_PINS, commit, ship.
    """
    lines = ["_STABLE_SIGNATURE_PINS: dict[str, tuple[tuple[str, str, bool], ...]] = {"]
    for fq_name in sorted(_STABLE_SIGNATURE_PINS.keys()):
        modname, _, symbol = fq_name.rpartition(".")
        obj = _resolve(modname, symbol)
        sig = _signature_pin(obj)
        lines.append(f'    "{fq_name}": (')
        for entry in sig:
            lines.append(f"        {entry!r},")
        lines.append("    ),")
    lines.append("}")
    text = "\n".join(lines)
    captured = capsys.readouterr()  # noqa: F841 — flush prior captures
    print("\n" + text + "\n")
