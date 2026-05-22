"""Tests for the tool-acquisition pipeline — Ophamin extending its toolchain.

Pins the responsible boundary: evaluate (license/maturity/fit), dry-run plan
(never executes, pinned only), verify (post-install gate), register (only what
passed). Especially: strong-copyleft rejection (business safety), unpinned
refusal (supply-chain), and refusal to register unverified/rejected tools.
"""

from __future__ import annotations

import pytest

from ophamin.interop.tool_acquisition import (
    CAUTION,
    RECOMMEND,
    REJECT,
    ToolCandidate,
    acquisition_plan,
    evaluate_candidate,
    register_acquired_tool,
    verify_acquired_tool,
)


def _mature_permissive(**kw):
    base = dict(name="ruptures", version="1.1.9", license="BSD-2-Clause",
                stars=1700, downloads_month=200000, import_name="ruptures",
                fit_note="change-point detection")
    base.update(kw)
    return ToolCandidate(**base)


class TestEvaluate:
    def test_permissive_mature_recommends(self):
        ev = evaluate_candidate(_mature_permissive())
        assert ev["verdict"] == RECOMMEND
        assert ev["license_class"] == "permissive"
        assert ev["license_ok"] is True

    def test_strong_copyleft_rejected_for_business(self):
        ev = evaluate_candidate(_mature_permissive(license="AGPL-3.0"))
        assert ev["verdict"] == REJECT
        assert ev["license_class"] == "strong-copyleft"
        assert any("AGPL" in r or "copyleft" in r for r in ev["reasons"])

    def test_strong_copyleft_allowed_when_opted_in(self):
        ev = evaluate_candidate(_mature_permissive(license="GPL-3.0"), allow_copyleft=True)
        assert ev["verdict"] != REJECT  # caution, not reject

    def test_unknown_license_not_recommended(self):
        ev = evaluate_candidate(_mature_permissive(license=""))
        assert ev["verdict"] in (CAUTION, REJECT)

    def test_low_maturity_is_caution(self):
        ev = evaluate_candidate(_mature_permissive(stars=10, downloads_month=50))
        assert ev["verdict"] == CAUTION
        assert ev["mature"] is False

    def test_invalid_name_rejected(self):
        ev = evaluate_candidate(_mature_permissive(name="evil; rm -rf /"))
        assert ev["verdict"] == REJECT
        assert ev["name_valid"] is False

    def test_security_step_always_required(self):
        ev = evaluate_candidate(_mature_permissive())
        assert "pip-audit" in ev["security_step"]


class TestPlan:
    def test_plan_is_dry_run_and_pinned(self):
        plan = acquisition_plan(_mature_permissive())
        assert plan["executes"] is False
        assert plan["pinned"] == "ruptures==1.1.9"
        assert "ruptures==1.1.9" in plan["install_command"]
        assert plan["gate_env"] == "OPHAMIN_ALLOW_TOOL_INSTALL"
        assert any("pip-audit" in s for s in plan["verification_steps"])

    def test_unpinned_refused(self):
        with pytest.raises(ValueError):
            acquisition_plan(_mature_permissive(version=""))

    def test_invalid_name_refused(self):
        with pytest.raises(ValueError):
            acquisition_plan(_mature_permissive(name="bad name!"))


class TestVerify:
    def test_verifies_installed_package(self):
        # use an installed dep as a post-install stand-in
        v = verify_acquired_tool("scipy", smoke_fn=lambda m: hasattr(m, "stats"))
        assert v["verified"] is True
        assert v["version"]

    def test_missing_package_fails_cleanly(self):
        v = verify_acquired_tool("no_such_module_xyz_123")
        assert v["verified"] is False
        assert v["stage"] == "import"

    def test_failed_smoke_fails(self):
        v = verify_acquired_tool("scipy", smoke_fn=lambda m: False)
        assert v["verified"] is False
        assert v["stage"] == "smoke"

    def test_version_mismatch_fails(self):
        v = verify_acquired_tool("scipy", expected_version="0.0.0-nope")
        assert v["verified"] is False
        assert v["stage"] == "version"

    def test_blank_name_raises(self):
        with pytest.raises(ValueError):
            verify_acquired_tool("  ")


class TestRegister:
    def test_registers_verified_tool(self):
        c = _mature_permissive()
        ev = evaluate_candidate(c)
        entry = register_acquired_tool(c, ev, {"verified": True, "version": "1.1.9"})
        assert entry["id"] == "ruptures"
        assert entry["pip_name"] == "ruptures"
        assert entry["_acquired"]["verified"] is True

    def test_refuses_unverified(self):
        c = _mature_permissive()
        ev = evaluate_candidate(c)
        with pytest.raises(ValueError):
            register_acquired_tool(c, ev, {"verified": False, "stage": "import"})

    def test_refuses_rejected(self):
        c = _mature_permissive(license="AGPL-3.0")
        ev = evaluate_candidate(c)  # reject
        with pytest.raises(ValueError):
            register_acquired_tool(c, ev, {"verified": True, "version": "1.1.9"})
