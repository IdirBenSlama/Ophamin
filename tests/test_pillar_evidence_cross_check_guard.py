"""Pinning the construction-time guard on PillarEvidence.cross_check.

Background: 0.9.0 and 0.9.4 both shipped fixes for the SAME defect class
— parallel-session scenarios passing prose into ``cross_check`` when the
field is enum-constrained to ``{passed, skipped, failed, n/a}``. The
test that caught it (``test_validate_schema_passes_for_every_shipped_proof``)
fires at *ship time* — i.e. when the proof JSON is already on disk and
the CI matrix is running. By that point the scenario author has lost
the context for "why does this prose belong in detail not cross_check".

This module pins the **construction-time** guard added in 0.9.5: the
violation now raises ``ValueError`` the moment a PillarEvidence is
built with a non-enum cross_check value. Scenario authors see the
error immediately, with a clear message pointing them at ``detail``
as the right home for long-form context.
"""

from __future__ import annotations

import pytest

from ophamin.measuring.proof.record import PillarEvidence


# ---------------------------------------------------------------------------
# Accepted values
# ---------------------------------------------------------------------------


class TestAcceptedValues:
    """The four enum values must construct without complaint."""

    @pytest.mark.parametrize("value", ["passed", "skipped", "failed", "n/a"])
    def test_each_enum_value_accepted(self, value: str) -> None:
        evidence = PillarEvidence(
            pillar="test.pillar",
            statistic_name="dummy",
            statistic_value=1.0,
            library="pytest",
            library_version="1.0",
            cross_check=value,
        )
        assert evidence.cross_check == value

    def test_default_value_is_n_slash_a(self) -> None:
        evidence = PillarEvidence(
            pillar="test.pillar",
            statistic_name="dummy",
            statistic_value=1.0,
            library="pytest",
            library_version="1.0",
        )
        assert evidence.cross_check == "n/a"


# ---------------------------------------------------------------------------
# Rejected values
# ---------------------------------------------------------------------------


class TestRejectedValues:
    """Prose / typos / case-mismatches all fire loud at construction."""

    def test_short_prose_rejected_with_full_text_in_message(self) -> None:
        with pytest.raises(ValueError, match="must be one of") as info:
            PillarEvidence(
                pillar="test.pillar",
                statistic_name="dummy",
                statistic_value=1.0,
                library="pytest",
                library_version="1.0",
                cross_check="secondary: extra context",
            )
        # The original value is included verbatim in the error so the
        # author sees exactly what they passed.
        assert "secondary: extra context" in str(info.value)
        # The hint points them at the right home.
        assert "detail" in str(info.value)

    def test_long_prose_rejected_with_truncated_prefix(self) -> None:
        prose = (
            "Three sub-tests probe complementary self-discovery primitives. "
            "STRONG validation would mean the wiring debt contains working "
            "physics-discovery primitives. REFUTATION means the self-"
            "discovery layer is decoratively-named scaffolding."
        )
        with pytest.raises(ValueError) as info:
            PillarEvidence(
                pillar="test.pillar",
                statistic_name="dummy",
                statistic_value=1.0,
                library="pytest",
                library_version="1.0",
                cross_check=prose,
            )
        # Long prose is truncated to 57 chars + "..." in the error.
        assert "..." in str(info.value)
        # The first chars of the prose are still visible so the author
        # recognises what they passed.
        assert prose[:50] in str(info.value)

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            PillarEvidence(
                pillar="test.pillar",
                statistic_name="dummy",
                statistic_value=1.0,
                library="pytest",
                library_version="1.0",
                cross_check="",
            )

    def test_capitalized_passed_rejected(self) -> None:
        """The enum is case-sensitive — "Passed" should fail loud."""
        with pytest.raises(ValueError, match="must be one of"):
            PillarEvidence(
                pillar="test.pillar",
                statistic_name="dummy",
                statistic_value=1.0,
                library="pytest",
                library_version="1.0",
                cross_check="Passed",
            )

    def test_typo_passes_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            PillarEvidence(
                pillar="test.pillar",
                statistic_name="dummy",
                statistic_value=1.0,
                library="pytest",
                library_version="1.0",
                cross_check="passes",  # close but not in the enum
            )

    def test_typo_skip_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            PillarEvidence(
                pillar="test.pillar",
                statistic_name="dummy",
                statistic_value=1.0,
                library="pytest",
                library_version="1.0",
                cross_check="skip",  # not "skipped"
            )


# ---------------------------------------------------------------------------
# Codec round-trip preserves the guard
# ---------------------------------------------------------------------------


class TestCodecRoundTrip:
    """from_dict re-runs __post_init__ — bad data on disk fires loud too."""

    def test_from_dict_rejects_prose_in_cross_check_field(self) -> None:
        data = {
            "pillar": "test.pillar",
            "statistic_name": "dummy",
            "statistic_value": 1.0,
            "library": "pytest",
            "library_version": "1.0",
            "cross_check": "Some prose that doesn't match the enum.",
            "detail": {},
        }
        with pytest.raises(ValueError, match="must be one of"):
            PillarEvidence.from_dict(data)

    def test_from_dict_accepts_each_enum_value(self) -> None:
        for value in ["passed", "skipped", "failed", "n/a"]:
            data = {
                "pillar": "test.pillar",
                "statistic_name": "dummy",
                "statistic_value": 1.0,
                "library": "pytest",
                "library_version": "1.0",
                "cross_check": value,
                "detail": {},
            }
            ev = PillarEvidence.from_dict(data)
            assert ev.cross_check == value


# ---------------------------------------------------------------------------
# Regression guard pointing at the originating defect class
# ---------------------------------------------------------------------------


def test_regression_guard_for_0_9_0_and_0_9_4_defect_class() -> None:
    """The exact prose values shipped by the two parallel-session
    scenarios that bit us in 0.9.0 + 0.9.4 must be rejected NOW
    rather than slip through to ship-time validation."""
    bad_values = [
        # From sinew_conservation (0.9.0 cleanup, commit 5f693b6):
        "secondary: ouroboros + scar conservation ratios + scar magnitude quartile breakdown",
        # From sinew_modulation_disruption (0.9.0 cleanup):
        "secondary: ouroboros + scar conservation ratios in seed vs modulated form",
        # From sinew_wider_unification (0.9.0 cleanup):
        "Per-candidate breakdown: EXTENDS, COMPATIBLE, BREAKS, INSUFFICIENT.",
        # From proprio_self_discovery (0.9.4 cleanup, commit a088eba):
        "Three sub-tests probe complementary self-discovery primitives.",
    ]
    for prose in bad_values:
        with pytest.raises(ValueError, match="must be one of"):
            PillarEvidence(
                pillar="test.pillar",
                statistic_name="dummy",
                statistic_value=1.0,
                library="pytest",
                library_version="1.0",
                cross_check=prose,
            )
